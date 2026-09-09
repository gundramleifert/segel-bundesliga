"""Read-only endpoints of the public website.

All routes address via the primary key; the slug appears in responses and is used for
display, not as an address. See ``docs/concepts.md`` for terminology.

**Only published data appears here** (Story VA-8). A series and an event each carry a
``published`` flag; while it is false the thing is a draft — planned, edited, discussed —
and this router behaves as if it did not exist, down to answering 404 rather than
admitting that it is there. The ``/api/admin/...`` routers show everything, drafts
included; that is where the work happens.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crests import crest_path
from app.db import get_session
from app.i18n import Locale, resolve_locale, tr
from app.models import (
    Boat,
    Club,
    CrewRole,
    Event,
    EventCrew,
    Flight,
    Race,
    RaceEntry,
    Sailor,
    Series,
    Team,
    TeamMembership,
    TeamStatus,
)
from app.problems import Problem
from app.schemas.public import (
    BoatOut,
    ClubDetail,
    ClubEventOut,
    ClubOut,
    ClubTeamOut,
    EventDetail,
    EventOut,
    EventStandingRow,
    MemberOut,
    PairingList,
    PairingRow,
    SailorDetail,
    SailorEventOut,
    SailorTeamOut,
    SeriesOut,
    SeriesStandingRow,
    SeriesTable,
    TeamOut,
    VenueOut,
)
from app.services import compute_event, compute_series, current_year

router = APIRouter(prefix="/api", tags=["public"])

# Relationships every Event response needs — otherwise lazy loading fails in async context.
_EVENT_RELATIONSHIPS = ("series", "venue", "host_club")
_EVENT_LOAD = tuple(selectinload(getattr(Event, name)) for name in _EVENT_RELATIONSHIPS)

# Helm first, then crew, then substitute — the order a crew is announced.
_ROLE_ORDER = {CrewRole.HELM: 0, CrewRole.CREW: 1, CrewRole.SUBSTITUTE: 2}


def _only_public_events(stmt):
    """Narrows an ``Event`` query to what a visitor may see.

    Two conditions, because an event hangs off a series: the event itself must be
    published, and it must not belong to an **unpublished** series — otherwise publishing
    a single matchday would leak the draft series it belongs to through
    ``EventOut.series``. A standalone event has no series and passes on its own flag.
    """
    draft_series = (
        select(Series.id)
        .where(Series.id == Event.series_id, Series.published.is_(False))
        .exists()
    )
    return stmt.where(Event.published.is_(True), ~draft_series)


# -------------------------------------------------------------------------- Series


@router.get("/series", response_model=list[SeriesOut], summary="Series of a year")
async def list_series(
    year: int | None = Query(default=None, description="Year; otherwise the current one"),
    session: AsyncSession = Depends(get_session),
) -> list[Series]:
    """A series is a set of events that are scored together. Published ones only."""
    effective_year = (
        year if year is not None else await current_year(session, published_only=True)
    )
    stmt = (
        select(Series)
        .where(Series.published.is_(True))
        .order_by(Series.level.nulls_last(), Series.name)
    )
    if effective_year is not None:
        stmt = stmt.where(Series.year == effective_year)
    return list((await session.execute(stmt)).scalars())


@router.get("/series/{series_id}/table", response_model=SeriesTable)
async def get_series_table(
    series_id: int,
    session: AsyncSession = Depends(get_session),
    locale: Locale = Depends(resolve_locale),
) -> SeriesTable:
    """The series standings table: the placements of all matchdays, summed. Lower is better.

    Anyone who missed a matchday gets participant count + 1 for that matchday — failing to
    compete must never be better than competing and placing last.
    """
    series = (
        await session.execute(
            # An unpublished series is not a 403 but a 404: a draft's existence is itself
            # not public.
            select(Series).where(Series.id == series_id, Series.published.is_(True))
        )
    ).scalar_one_or_none()
    if series is None:
        raise HTTPException(
            status_code=404,
            detail=tr(
                locale,
                en=f"Series {series_id} not found",
                de=f"Serie {series_id} nicht gefunden",
            ),
        )

    events = list(
        (
            await session.execute(
                _only_public_events(
                    select(Event)
                    .options(*_EVENT_LOAD)
                    .where(Event.series_id == series.id)
                    .order_by(Event.matchday.nulls_last(), Event.starts_on)
                )
            )
        ).scalars()
    )
    matchday_by_event = {event.id: event.matchday for event in events}
    teams = await _teams_of_series(session, series.id)

    rows = []
    for row in await compute_series(session, series.id):
        # Only published matchdays are broken out. The **points** still come from every
        # event of the series — that is the sporting truth, and a sailed matchday someone
        # forgot to publish must not silently change a standing — but its column would
        # give away an event the visitor is not meant to see yet.
        acts = {
            matchday_by_event[event_id] or 0: rank
            for event_id, rank in row.event_ranks.items()
            if event_id in matchday_by_event
        }
        rows.append(
            SeriesStandingRow(
                rank=row.rank,
                team=teams[row.team_id],
                points=row.points,
                ranks_by_matchday=acts,
                missed_matchdays=sorted(
                    matchday_by_event[event_id] or 0
                    for event_id in row.missed_events
                    if event_id in matchday_by_event
                ),
                events_sailed=row.events_sailed,
            )
        )

    return SeriesTable(
        series=SeriesOut.model_validate(series),
        rows=rows,
        events=[_event_out(event) for event in events],
    )


# -------------------------------------------------------------------------- Clubs


@router.get("/clubs", response_model=list[ClubOut])
async def list_clubs(
    year: int | None = Query(default=None, description="Year; otherwise the current one"),
    series: int | None = Query(default=None, description="ID of a series"),
    session: AsyncSession = Depends(get_session),
) -> list[Club]:
    """Clubs assigned to at least one **published** series in the year.

    A newly created club does **not** appear here as long as it is not assigned to a
    series — and an assignment always applies only to one year. An assignment to a series
    still in draft counts just as little: the club page would otherwise name a competition
    nobody is supposed to know about yet.
    """
    stmt = (
        select(Club)
        .join(Team, Team.club_id == Club.id)
        .join(Series, Team.series_id == Series.id)
        # A pending club is not yet a participant. We count registration for the series,
        # not participation in a single event.
        .where(
            Team.status == TeamStatus.ACCEPTED,
            Team.event_id.is_(None),
            Series.published.is_(True),
        )
        .order_by(Club.name)
        .distinct()
    )
    if series is not None:
        stmt = stmt.where(Series.id == series)
    else:
        effective_year = (
            year if year is not None else await current_year(session, published_only=True)
        )
        if effective_year is None:
            return []
        stmt = stmt.where(Series.year == effective_year)

    return list((await session.execute(stmt)).scalars())


@router.get("/clubs/{club_id}", response_model=ClubDetail)
async def get_club(
    club_id: int,
    year: int | None = Query(default=None, description="Year; otherwise the current one"),
    session: AsyncSession = Depends(get_session),
    locale: Locale = Depends(resolve_locale),
) -> ClubDetail:
    """The club page: master data, emblem, brief description, and teams.

    A club can participate in multiple series — so this is a list. The events of a series
    appear under their team; events hosted by the club without a series appear separately.
    """
    club = (
        await session.execute(select(Club).where(Club.id == club_id))
    ).scalar_one_or_none()
    if club is None:
        raise HTTPException(
            status_code=404,
            detail=tr(
                locale,
                en=f"Club {club_id} not found",
                de=f"Verein {club_id} nicht gefunden",
            ),
        )

    effective_year = (
        year if year is not None else await current_year(session, published_only=True)
    )

    teams: list[ClubTeamOut] = []
    if effective_year is not None:
        rows = (
            await session.execute(
                select(Team, Series)
                .join(Series, Team.series_id == Series.id)
                .where(
                    Team.club_id == club.id,
                    Team.event_id.is_(None),
                    Series.year == effective_year,
                    Series.published.is_(True),
                    Team.status == TeamStatus.ACCEPTED,
                )
                .order_by(Series.level.nulls_last(), Series.name)
            )
        ).all()

        squad = await _squad(session, [team.id for team, _ in rows])
        events_by_team = await _events_by_team(
            session, club.id, [(team.id, team.series_id) for team, _ in rows]
        )
        teams = [
            ClubTeamOut(
                id=team.id,
                name=team.name,
                series=SeriesOut.model_validate(series),
                members=squad.get(team.id, []),
                events=events_by_team.get(team.id, []),
            )
            for team, series in rows
        ]

    # Events without a series cannot be grouped under a team — they appear separately.
    # They are identified by the host club.
    standalone_events = (
        await session.execute(
            _only_public_events(
                select(Event)
                .options(*_EVENT_LOAD)
                .where(Event.host_club_id == club.id, Event.series_id.is_(None))
                .order_by(Event.starts_on)
            )
        )
    ).scalars()

    return ClubDetail(
        **ClubOut.model_validate(club).model_dump(),
        teams=teams,
        events=[ClubEventOut(event=_event_out(e)) for e in standalone_events],
    )


@router.get("/clubs/{club_id}/logo", summary="A club's crest")
async def get_club_logo(club_id: int) -> FileResponse:
    """Serves the uploaded crest — Story V-3.

    Public, like the rest of this router: a club emblem is on every table row and every
    matchday card. No placeholder is invented here (same as the sailor photo): a club
    without an uploaded crest simply has no file, and its `logo_url` then either points at
    an external image or is empty, which the frontend already handles by showing the
    abbreviation.

    Needs no database round-trip — the file's presence answers the question. A club id
    that does not exist and a club without a crest are the same 404 here.
    """
    path = crest_path(club_id)
    if not path.exists():
        raise Problem(404, "club-crest-not-found", "This club has no uploaded crest.")
    return FileResponse(path, media_type="image/png")


# ----------------------------------------------------------------------- Sailors


@router.get("/sailors/{sailor_id}", response_model=SailorDetail)
async def get_sailor(
    sailor_id: int,
    year: int | None = Query(default=None, description="Year; otherwise the current one"),
    session: AsyncSession = Depends(get_session),
    locale: Locale = Depends(resolve_locale),
) -> SailorDetail:
    """The sailor page: which club and series someone is registered with, where they compete.

    Two levels: the **series registration** (squad) and the **lineup for a single event**.
    Being on the squad does not mean sailing every event.

    Deliberately no email or birth year — same as on the club page.
    """
    sailor = (
        await session.execute(select(Sailor).where(Sailor.id == sailor_id))
    ).scalar_one_or_none()
    if sailor is None:
        raise HTTPException(
            status_code=404,
            detail=tr(
                locale,
                en="This person is not registered.",
                de="Diese Person ist nicht gemeldet.",
            ),
        )

    effective_year = (
        year if year is not None else await current_year(session, published_only=True)
    )
    teams: list[SailorTeamOut] = []
    events: list[SailorEventOut] = []

    if effective_year is not None:
        rows = (
            await session.execute(
                select(TeamMembership, Team, Club, Series)
                .join(Team, TeamMembership.team_id == Team.id)
                .join(Club, Team.club_id == Club.id)
                .join(Series, Team.series_id == Series.id)
                .where(
                    TeamMembership.sailor_id == sailor.id,
                    Team.event_id.is_(None),
                    Series.year == effective_year,
                    Series.published.is_(True),
                    Team.status == TeamStatus.ACCEPTED,
                )
                .order_by(Series.level.nulls_last(), Series.name)
            )
        ).all()
        teams = [
            SailorTeamOut(
                team_id=team.id,
                role=membership.role,
                club=ClubOut.model_validate(club),
                series=SeriesOut.model_validate(series),
            )
            for membership, team, club, series in rows
        ]

        lineups = (
            await session.execute(
                _only_public_events(
                    select(EventCrew, Event)
                    .join(Event, EventCrew.event_id == Event.id)
                    .options(*_EVENT_LOAD)
                    .where(EventCrew.sailor_id == sailor.id)
                    .order_by(Event.starts_on)
                )
            )
        ).all()
        events = [
            SailorEventOut(event=_event_out(event), team_id=crew.team_id, role=crew.role)
            for crew, event in lineups
        ]

    return SailorDetail(
        id=sailor.id,
        first_name=sailor.first_name,
        last_name=sailor.last_name,
        teams=teams,
        events=events,
    )


# ----------------------------------------------------------------------- Events


@router.get("/events", response_model=list[EventOut])
async def list_events(
    year: int | None = Query(default=None, description="Year of the series"),
    series: int | None = Query(default=None, description="ID of a series"),
    session: AsyncSession = Depends(get_session),
) -> list[EventOut]:
    stmt = _only_public_events(select(Event).options(*_EVENT_LOAD).order_by(Event.starts_on))
    if series is not None:
        stmt = stmt.where(Event.series_id == series)
    elif year is not None:
        stmt = stmt.join(Series, Event.series_id == Series.id).where(Series.year == year)
    return [_event_out(e) for e in (await session.execute(stmt)).scalars()]


@router.get("/events/{event_id}", response_model=EventDetail)
async def get_event(
    event_id: int,
    session: AsyncSession = Depends(get_session),
    locale: Locale = Depends(resolve_locale),
) -> EventDetail:
    event = await _event_by_id(session, event_id, locale)
    teams = await _teams_of_event(session, event.id)

    scores = await compute_event(session, event.id)
    races_total = await _count_races(session, event.id)
    # Get the race ID -> race number mapping once, rather than repeatedly for each team.
    sequences = await _race_sequences(session, event.id)

    rows = [
        EventStandingRow(
            rank=score.rank,
            team=teams[score.team_id],
            total=score.total,
            net=score.net,
            races_scored=len(score.points_by_race),
            points_by_race={
                sequences[race_id]: points for race_id, points in score.points_by_race.items()
            },
            discarded_races=sorted(sequences[race_id] for race_id in score.discarded_races),
        )
        for score in scores
        if score.team_id in teams
    ]

    return EventDetail(
        event=_event_out(event),
        standings=rows,
        races_total=races_total,
        races_scored=await _count_scored_races(session, event.id),
    )


@router.get("/events/{event_id}/pairing", response_model=PairingList)
async def get_pairing(
    event_id: int,
    session: AsyncSession = Depends(get_session),
    locale: Locale = Depends(resolve_locale),
) -> PairingList:
    """The pairing list: which team sails when on which boat."""
    event = await _event_by_id(session, event_id, locale)
    teams = await _teams_of_event(session, event.id)

    boats = list(
        (
            await session.execute(
                select(Boat).where(Boat.event_id == event.id).order_by(Boat.number)
            )
        ).scalars()
    )
    boat_number = {boat.id: boat.number for boat in boats}

    stmt = (
        select(Race, RaceEntry, Flight)
        .join(Flight, Race.flight_id == Flight.id)
        .join(RaceEntry, RaceEntry.race_id == Race.id)
        .where(Flight.event_id == event.id)
        .order_by(Race.sequence)
    )
    rows: dict[int, PairingRow] = {}
    for race, entry, flight in (await session.execute(stmt)).all():
        if entry.team_id not in teams:
            continue
        row = rows.get(race.sequence)
        if row is None:
            row = PairingRow(
                sequence=race.sequence,
                flight=flight.number,
                race_in_flight=race.number_in_flight,
                status=race.status,
                teams_by_boat={},
            )
            rows[race.sequence] = row
        row.teams_by_boat[boat_number[entry.boat_id]] = teams[entry.team_id]

    return PairingList(
        event=_event_out(event),
        boats=[BoatOut.model_validate(boat) for boat in boats],
        races=[rows[key] for key in sorted(rows)],
    )


# ---------------------------------------------------------------------- Helpers


async def _event_by_id(session: AsyncSession, event_id: int, locale: Locale) -> Event:
    """The event, if a visitor may see it — a draft is a 404 here, like anywhere public."""
    event = (
        await session.execute(
            _only_public_events(
                select(Event).options(*_EVENT_LOAD).where(Event.id == event_id)
            )
        )
    ).scalar_one_or_none()
    if event is None:
        raise HTTPException(
            status_code=404,
            detail=tr(
                locale,
                en=f"Event {event_id} not found",
                de=f"Veranstaltung {event_id} nicht gefunden",
            ),
        )
    return event


async def _teams_of_event(
    session: AsyncSession, event_id: int
) -> dict[int, TeamOut]:
    """The teams participating in this event.

    Event standings and pairing list depend on the event — so do the teams in them.
    If no one participates, both remain empty.
    """
    return await _as_teamout(
        session, Team.event_id == event_id, Team.status == TeamStatus.ACCEPTED
    )


async def _teams_of_series(session: AsyncSession, series_id: int) -> dict[int, TeamOut]:
    """Everything in the series — registrations and participations — indexed by ID.

    The series standings table is at the registration level. A participation without
    registration would be against the rules, but would still generate a row. To give it
    a name, both levels are included in this mapping.
    """
    return await _as_teamout(
        session, Team.series_id == series_id, Team.status == TeamStatus.ACCEPTED
    )


async def _as_teamout(session: AsyncSession, *conditions) -> dict[int, TeamOut]:
    result = await session.execute(
        select(Team).options(selectinload(Team.club)).where(*conditions)
    )
    return {
        team.id: TeamOut(id=team.id, name=team.name, club=ClubOut.model_validate(team.club))
        for team in result.scalars()
    }


async def _squad(session: AsyncSession, team_ids: list[int]) -> dict[int, list[MemberOut]]:
    """The registered members of each team.

    No email or birth year: names appear on every results list anyway, contact data do not
    belong on a public page.
    """
    if not team_ids:
        return {}

    rows = (
        await session.execute(
            select(TeamMembership, Sailor)
            .join(Sailor, TeamMembership.sailor_id == Sailor.id)
            .where(TeamMembership.team_id.in_(team_ids))
        )
    ).all()

    by_team: dict[int, list[MemberOut]] = {}
    for membership, sailor in rows:
        by_team.setdefault(membership.team_id, []).append(
            MemberOut(
                id=sailor.id,
                first_name=sailor.first_name,
                last_name=sailor.last_name,
                role=membership.role,
            )
        )
    for members in by_team.values():
        members.sort(key=lambda m: (_ROLE_ORDER.get(m.role, 9), m.last_name, m.first_name))
    return by_team


async def _events_by_team(
    session: AsyncSession, club_id: int, teams: list[tuple[int, int]]
) -> dict[int, list[ClubEventOut]]:
    """The events of a series along with this club's lineups.

    The schedule is tied to the series, not the club: all events are shown, along with who
    from the club sails in them. If no one is assigned yet, the lineup remains empty —
    that is the message, not a missing entry.

    ``teams`` are the **series registrations** of the club; the lineup is tied to **participation**
    in a single event. Both are linked through the club.
    """
    series_ids = {series_id for _, series_id in teams}
    if not series_ids:
        return {}

    events = (
        await session.execute(
            _only_public_events(
                select(Event)
                .options(*_EVENT_LOAD)
                .where(Event.series_id.in_(series_ids))
                .order_by(Event.starts_on)
            )
        )
    ).scalars().all()

    lineups = (
        await session.execute(
            select(EventCrew, Sailor)
            .join(Sailor, EventCrew.sailor_id == Sailor.id)
            .join(Team, EventCrew.team_id == Team.id)
            .where(Team.club_id == club_id)
        )
    ).all()

    crew_by_event: dict[int, list[MemberOut]] = {}
    for crew, sailor in lineups:
        crew_by_event.setdefault(crew.event_id, []).append(
            MemberOut(
                id=sailor.id,
                first_name=sailor.first_name,
                last_name=sailor.last_name,
                role=crew.role,
            )
        )
    for members in crew_by_event.values():
        members.sort(key=lambda m: (_ROLE_ORDER.get(m.role, 9), m.last_name, m.first_name))

    return {
        team_id: [
            ClubEventOut(
                event=_event_out(event),
                crew=crew_by_event.get(event.id, []),
            )
            for event in events
            if event.series_id == series_id
        ]
        for team_id, series_id in teams
    }


async def _count_races(session: AsyncSession, event_id: int) -> int:
    stmt = (
        select(func.count(Race.id))
        .join(Flight, Race.flight_id == Flight.id)
        .where(Flight.event_id == event_id)
    )
    return int((await session.execute(stmt)).scalar_one())


async def _count_scored_races(session: AsyncSession, event_id: int) -> int:
    """Races of the event for which results are already available."""
    stmt = (
        select(func.count(func.distinct(Race.id)))
        .join(Flight, Race.flight_id == Flight.id)
        .join(RaceEntry, RaceEntry.race_id == Race.id)
        .where(Flight.event_id == event_id, RaceEntry.code.is_not(None))
    )
    return int((await session.execute(stmt)).scalar_one())


async def _race_sequences(session: AsyncSession, event_id: int) -> dict[int, int]:
    """Race ID -> race number (1..48), as shown on results lists."""
    stmt = (
        select(Race.id, Race.sequence)
        .join(Flight, Race.flight_id == Flight.id)
        .where(Flight.event_id == event_id)
    )
    return dict((await session.execute(stmt)).all())


def _event_out(event: Event) -> EventOut:
    host_club = ClubOut.model_validate(event.host_club) if event.host_club else None
    return EventOut(
        id=event.id,
        slug=event.slug,
        title=event.title,
        matchday=event.matchday,
        starts_on=event.starts_on,
        ends_on=event.ends_on,
        status=event.status,
        published=event.published,
        series=SeriesOut.model_validate(event.series) if event.series else None,
        venue=VenueOut.model_validate(event.venue) if event.venue else None,
        host_club=host_club,
        # Without its own logo, the host club's emblem takes its place — taken from the
        # serialized `ClubOut`, not the ORM column, so an uploaded crest (Story V-3,
        # `ClubOut._prefer_uploaded_crest`) wins here too.
        logo_url=event.logo_url or (host_club.logo_url if host_club else None),
        team_count=event.team_count,
        boat_count=event.boat_count,
        flight_count=event.flight_count,
        crew_size=event.crew_size,
    )
