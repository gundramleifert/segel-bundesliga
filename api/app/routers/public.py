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

import logging
import re
from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import current_user
from app.crests import crest_path
from app.db import get_session
from app.i18n import Locale, resolve_locale, tr
from app.live import hub
from app.models import (
    Boat,
    Club,
    ClubMember,
    ClubMemberStatus,
    CrewRole,
    Event,
    EventCrew,
    EventStatus,
    Flight,
    Race,
    RaceEntry,
    Sailor,
    Series,
    Team,
    TeamMembership,
    TeamStatus,
    Venue,
)
from app.models.auth import User
from app.pagination import Page, PageInput, PageParams, apply_search, page_of, paginate
from app.pairing.pdf import PairingPdfError, render_pdf, renderer_available
from app.problems import Problem
from app.schemas.public import (
    BoatOut,
    ClubDetail,
    ClubEventOut,
    ClubOut,
    ClubTeamOut,
    EventCrewList,
    EventDetail,
    EventOut,
    EventStandingRow,
    LiveNowOut,
    MemberOut,
    MyClubOut,
    MySeriesOut,
    MyTeamOut,
    PairingList,
    PairingRow,
    SailorDetail,
    SailorEventOut,
    SailorTeamOut,
    SeriesOut,
    SeriesStandingRow,
    SeriesTable,
    TeamCrewOut,
    TeamOut,
    VenueOut,
)
from app.services import compute_event, compute_series, current_year
from app.services.pairing_service import TeamNotInPairing, stored_pairing
from app.text import slugify

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

    ``correlate(Event)`` is load-bearing: a query that also **joins** ``Series`` — the
    calendar filtered by year does — otherwise has SQLAlchemy correlate the subquery's own
    ``Series`` to the outer one, leaving it with no FROM at all and raising rather than
    answering. Naming the one table to correlate keeps ``Series`` inside the subquery
    whatever the caller joined outside it.
    """
    draft_series = (
        select(Series.id)
        .where(Series.id == Event.series_id, Series.published.is_(False))
        .correlate(Event)
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


# -------------------------------------------------------------------------- Live


#: The one topic a browser may listen to. Live is an event — a series only has one that is.
_LIVE_TOPIC = re.compile(r"^event:(?P<id>\d+)$")


@router.get(
    "/live",
    summary="Live updates for one event",
    # Deliberately kept out of the OpenAPI document: the generated client would turn a
    # text/event-stream into a query hook that resolves once, with a body it cannot parse
    # — a trap, not a convenience. The browser side is `EventSource` in
    # `web/src/api/useLive.ts`, which is the one place this path is written by hand.
    include_in_schema=False,
)
async def live_stream(
    topic: str = Query(description="`event:{id}`"),
    last_event_id: int | None = Header(default=None, alias="Last-Event-ID"),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Server-Sent Events: a ``change`` frame whenever the event's data changed — Story B-5.

    The frame carries a version, never the data: the browser refetches through the
    generated client, so this stream can never disagree with the tables it announces.

    A draft has no stream, and "draft" is the public router's own predicate,
    ``_only_public_events`` — the event published **and** its series not a draft — so
    this endpoint cannot leak an event the calendar hides.
    """
    match = _LIVE_TOPIC.match(topic)
    if match is None:
        raise Problem(422, "live-topic-invalid", "A live topic is `event:{id}`.", topic=topic)
    event_id = int(match["id"])
    stmt = _only_public_events(select(Event.id).where(Event.id == event_id))
    if (await session.execute(stmt)).scalar_one_or_none() is None:
        raise Problem(404, "event-not-found", f"Event {event_id} not found.")

    return StreamingResponse(
        hub.stream(topic, last_event_id=last_event_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            # nginx-style proxies buffer responses by default, which turns a stream into
            # a response that arrives when the connection closes. This header asks them
            # not to; the browser's polling fallback covers the ones that ignore it.
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/live/now", response_model=LiveNowOut, summary="Where /live should lead now")
async def get_live_now(session: AsyncSession = Depends(get_session)) -> LiveNowOut:
    """The running event, else the next published date — Story B-5.

    The live page must never open on an empty table: if nothing is being sailed right
    now, it leads to the next date instead. Published events only, as everywhere here.
    """
    public_events = _only_public_events(select(Event).options(*_EVENT_LOAD))
    running = (
        await session.execute(
            public_events.where(Event.status == EventStatus.LIVE)
            .order_by(Event.starts_on.nulls_last(), Event.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if running is not None:
        return LiveNowOut(event=_event_out(running), running=True)

    upcoming = (
        await session.execute(
            public_events.where(
                Event.status == EventStatus.PLANNED,
                Event.starts_on.is_not(None),
                Event.starts_on >= date.today(),
            )
            .order_by(Event.starts_on, Event.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    return LiveNowOut(event=_event_out(upcoming) if upcoming else None, running=False)


# -------------------------------------------------------------------------- Clubs


#: Story A-13 — the columns this list may be sorted by.
PUBLIC_CLUB_SORT = {"name": Club.name, "short_name": Club.short_name, "city": Club.city}


@router.get("/clubs", response_model=Page[ClubOut])
async def list_clubs(
    q: str | None = Query(default=None, description="Search in name, abbreviation and city"),
    year: int | None = Query(default=None, description="Year; otherwise the current one"),
    series: int | None = Query(default=None, description="ID of a series"),
    params: PageParams = PageInput,
    session: AsyncSession = Depends(get_session),
) -> Page[ClubOut]:
    """Clubs assigned to at least one **published** series in the year.

    A newly created club does **not** appear here as long as it is not assigned to a
    series — and an assignment always applies only to one year. An assignment to a series
    still in draft counts just as little: the club page would otherwise name a competition
    nobody is supposed to know about yet.

    Searchable since Story A-13, and that is the half the visitor notices: the club page
    used to fetch a page of clubs and filter it in the browser, which can only ever find
    what happened to be on the page it was holding. ``q`` narrows, it never widens — a
    club that is not public is not found by naming it either.
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
        .distinct()
    )
    if series is not None:
        stmt = stmt.where(Series.id == series)
    else:
        effective_year = (
            year if year is not None else await current_year(session, published_only=True)
        )
        if effective_year is None:
            return page_of([], 0, params)
        stmt = stmt.where(Series.year == effective_year)

    stmt = apply_search(stmt, q, Club.name, Club.short_name, Club.city)
    clubs, total = await paginate(
        session, stmt, params, sortable=PUBLIC_CLUB_SORT, default_order=[Club.name, Club.id]
    )
    return page_of([ClubOut.model_validate(club) for club in clubs], total, params)


@router.get(
    "/clubs/mine",
    response_model=list[MyClubOut],
    tags=["membership"],
    summary="The clubs this account belongs to or may manage",
)
async def my_clubs(
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> list[MyClubOut]:
    """Stories B-10 and V-12: one request for "the clubs that are something to me".

    Two independent relationships, both reported, because the two screens reading this
    need different ones — `/clubs` lists what someone *belongs to*, `/club` opens what
    they may *act for* — and because they genuinely do not imply each other. Deciding
    here which of the two counts would force the other screen into a second endpoint.

    **`admin` gets no shortcut.** The role may manage every club, but this route answers
    "mine", not "all": handing an administrator eighteen clubs would make the club screen
    a worse copy of the admin screen and bury the one club they actually sail for. The
    admin screen is where all eighteen belong.

    Registered above `/clubs/{club_id}` on purpose — Starlette matches in registration
    order, so "mine" would otherwise be read as a club id (the same reason
    `sailors.me_router` is included before `public.router` in `app/main.py`).
    """
    member_of = set(
        (
            await session.execute(
                select(ClubMember.club_id).where(
                    ClubMember.user_id == acting.id,
                    ClubMember.status == ClubMemberStatus.ACTIVE,
                )
            )
        ).scalars()
    )
    # `club_manager` is granted per club (`UserRole.club_id`), never globally — so this
    # comes off the role rows and not off `User.club_id`, which is the separate and
    # narrower "this account represents that club".
    manages = acting.managed_club_ids
    club_ids = member_of | manages
    if not club_ids:
        return []

    clubs = list(
        (
            await session.execute(
                select(Club).where(Club.id.in_(club_ids)).order_by(Club.name)
            )
        ).scalars()
    )

    # Series registrations only — a `Team` with an `event_id` is an entry in one event and
    # carries no squad (Story V-1), so offering it would produce a panel every save
    # refuses.
    rows = (
        await session.execute(
            select(Team.id, Team.club_id, Series, func.count(TeamMembership.id))
            .join(Series, Team.series_id == Series.id)
            .outerjoin(TeamMembership, TeamMembership.team_id == Team.id)
            .where(Team.club_id.in_(club_ids), Team.event_id.is_(None))
            .group_by(Team.id, Team.club_id, Series.id)
            .order_by(Series.year.desc(), Series.name)
        )
    ).all()

    teams_by_club: dict[int, list[MyTeamOut]] = {}
    for team_id, club_id, series, squad_size in rows:
        teams_by_club.setdefault(club_id, []).append(
            MyTeamOut(
                team_id=team_id,
                series=MySeriesOut.model_validate(series, from_attributes=True),
                squad_size=squad_size,
            )
        )

    return [
        MyClubOut(
            club=ClubOut.model_validate(club, from_attributes=True),
            is_member=club.id in member_of,
            may_manage=club.id in manages,
            teams=teams_by_club.get(club.id, []),
        )
        for club in clubs
    ]


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


#: Story A-13 — the columns this list may be sorted by.
PUBLIC_EVENT_SORT = {
    "title": Event.title,
    "starts_on": Event.starts_on,
    "matchday": Event.matchday,
}


def search_events(stmt, q: str | None):
    """Narrows an ``Event`` query to what someone searching would mean by ``q``.

    Title, venue and host club in **one** statement: the two outer joins keep it a single
    query rather than a name lookup per row, and neither can multiply an event — an event
    has at most one venue and at most one host — so ``total`` still counts events and not
    join rows. They are added only when there is something to search for, so an ordinary
    listing is the query it always was.

    Shared with the admin list (``app/routers/events.py``): the two lists differ in what
    they may show, never in what "search" means.
    """
    if not (q or "").strip():
        return stmt
    return apply_search(
        stmt.outerjoin(Venue, Event.venue_id == Venue.id).outerjoin(
            Club, Event.host_club_id == Club.id
        ),
        q,
        Event.title,
        Venue.name,
        Club.name,
        Club.short_name,
    )


@router.get("/events", response_model=Page[EventOut])
async def list_events(
    q: str | None = Query(default=None, description="Search in title, venue and host club"),
    year: int | None = Query(default=None, description="Year of the series"),
    series: int | None = Query(default=None, description="ID of a series"),
    params: PageParams = PageInput,
    session: AsyncSession = Depends(get_session),
) -> Page[EventOut]:
    """The public calendar. Paged since Story A-13 — it gains a season every year.

    Searching it stays on the server for the same reason the paging does: a draft event
    is not in the answer at all, so a term that names one finds nothing here however it
    is spelled.
    """
    stmt = _only_public_events(select(Event).options(*_EVENT_LOAD))
    if series is not None:
        stmt = stmt.where(Event.series_id == series)
    elif year is not None:
        stmt = stmt.join(Series, Event.series_id == Series.id).where(Series.year == year)
    stmt = search_events(stmt, q)

    events, total = await paginate(
        session,
        stmt,
        params,
        sortable=PUBLIC_EVENT_SORT,
        default_order=[Event.starts_on, Event.id],
    )
    return page_of([_event_out(e) for e in events], total, params)


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


@router.get(
    "/events/{event_id}/crew",
    response_model=EventCrewList,
    summary="Who sails for each team at this matchday",
)
async def get_event_crew(
    event_id: int,
    session: AsyncSession = Depends(get_session),
    locale: Locale = Depends(resolve_locale),
) -> EventCrewList:
    """The lineups of one matchday, per team — Story B-12.

    Public, with no login: whoever is entered is named on the pairing list, the results and
    the standings anyway, so putting the lineup behind a session would hide nothing. Club
    **membership** is the private thing (Story V-10), and this is not that.

    A team that is entered but has nobody named yet is listed with an **empty** crew rather
    than left out — "not named yet" is the answer to the question, while a missing row would
    read as "this club is not sailing here".

    Separate from ``get_event`` on purpose: the standings are what the page opens with, and
    every visitor would otherwise pay for a join most of them never look at.
    """
    event = await _event_by_id(session, event_id, locale)
    teams = await _teams_of_event(session, event.id)

    rows = (
        await session.execute(
            select(EventCrew, Sailor)
            .join(Sailor, EventCrew.sailor_id == Sailor.id)
            .where(EventCrew.event_id == event.id)
        )
    ).all()

    crew_by_team: dict[int, list[MemberOut]] = {}
    for crew, sailor in rows:
        crew_by_team.setdefault(crew.team_id, []).append(
            MemberOut(
                id=sailor.id,
                first_name=sailor.first_name,
                last_name=sailor.last_name,
                role=crew.role,
            )
        )
    for members in crew_by_team.values():
        members.sort(key=lambda m: (_ROLE_ORDER.get(m.role, 9), m.last_name, m.first_name))

    return EventCrewList(
        event=_event_out(event),
        teams=[
            TeamCrewOut(team=team, crew=crew_by_team.get(team.id, []))
            for team in sorted(teams.values(), key=lambda t: t.name)
        ],
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
        pdf_available=renderer_available(),
    )


@router.get(
    "/events/{event_id}/pairing.pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}, "description": "The printable list"}},
    summary="Pairing list as PDF",
)
async def download_pairing_pdf(
    event_id: int,
    team: int | None = Query(
        default=None,
        description="Print only this team's own page instead of the whole sheet",
    ),
    session: AsyncSession = Depends(get_session),
    locale: Locale = Depends(resolve_locale),
) -> Response:
    """The pairing list as the sheet that is printed and handed out (Story B-3).

    Same data as ``get_pairing``, same visibility — a draft is a 404 here as it is
    everywhere public. It is rendered by the Java tool that owns the print layout; see
    ``app.pairing.pdf`` for why this one may run inside a request while a draw may not.

    With ``team``, the answer is that club's own page: its races marked and the teams it
    shares a shuttle with. That is the sheet one crew wants — finding its page among
    eighteen is what a crew does at the dock, in the wind, on paper.
    """
    event = await _event_by_id(session, event_id, locale)

    try:
        request = await stored_pairing(
            session, event, title=_pdf_title(event), team_id=team
        )
    except TeamNotInPairing as error:
        raise Problem(
            404,
            "team-not-in-pairing-list",
            "This team has no place in the pairing list of this event.",
            event_id=event.id,
            team_id=team,
        ) from error
    if request is None:
        raise Problem(
            404,
            "pairing-list-missing",
            "This event has no pairing list yet, so there is nothing to print.",
            event_id=event.id,
        )

    try:
        pdf = await render_pdf(request)
    except PairingPdfError as error:
        # The renderer is a separate program, and a server without a Java runtime is a
        # deployment state, not a bad request: say so instead of answering 500. The reason
        # goes to the log, not into the response — it names paths on the server, and this
        # endpoint answers anyone.
        logging.getLogger(__name__).error("Rendering the pairing list failed: %s", error)
        raise Problem(
            503,
            "pairing-pdf-unavailable",
            "The pairing list could not be rendered.",
        ) from error

    # A crew's own sheet is named after the club, so eighteen downloads in one folder stay
    # apart. `request.team_index` is set exactly when `team` was given.
    name = event.slug
    if request.team_index is not None:
        name = f"{event.slug}-{slugify(request.teams[request.team_index])}"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}-pairing-list.pdf"'},
    )


# ---------------------------------------------------------------------- Helpers


def _pdf_title(event: Event) -> str:
    """What is printed above the grid.

    The series carries the year and the league, the event the occasion — on a sheet pinned
    to a clubhouse wall, neither alone says which matchday it is.
    """
    if event.series is not None:
        return f"{event.series.name} — {event.title}"
    return event.title


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
        live_url=event.live_url,
        team_count=event.team_count,
        boat_count=event.boat_count,
        flight_count=event.flight_count,
        crew_size=event.crew_size,
        print_settings=event.print_settings,
    )
