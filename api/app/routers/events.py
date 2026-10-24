"""Create and manage matchdays.

Access is available to administration, editorial, and race officers — all three contribute
to an event and should be able to record a date without waiting for someone else.

To create an event, only the **name** is required — everything else, the date included, can
be filled in later. **Saving never depends on validity** (Story VA-8): an event with the
wrong number of clubs, no boats and no date is how one starts out, not an error worth
rejecting. What validity gates is the *draw* and the *start*; what freezes the setup is the
*first race*. Both live in ``app/services/event_readiness.py``.
"""

from __future__ import annotations

from collections import Counter
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import authz
from app.auth import current_user, forbidden, require_event_control, require_event_manager_for
from app.authz import ObjectRef
from app.db import get_session
from app.live import event_topic, hub
from app.models import (
    Boat,
    Club,
    Event,
    EventStatus,
    Series,
    Team,
    TeamStatus,
    Venue,
)
from app.models.auth import ObjectType, Relation, User
from app.models.racing import BOAT_COLORS
from app.pagination import Page, PageInput, PageParams, page_of, paginate
from app.problems import Problem
from app.routers.public import _EVENT_LOAD, _event_out, search_events
from app.schemas.public import ClubOut, EventOut
from app.services import (
    adopt_series_registrations,
    candidate_clubs,
    check_squad_limits,
    configuration_frozen,
    event_entries,
    event_readiness,
    event_state,
    has_results,
    new_event_entry,
    require_editable_configuration,
)
from app.services.events import MatchdayTaken, NoFreeSlug, place_event
from app.services.lookup import get_or_404

# Permissions are attached to individual routes, not the router: creating an event is also
# permitted to the host club's leadership (Story VA-6) — everything else is modified only by
# administration, editorial, and race officers.
router = APIRouter(prefix="/api/admin/events", tags=["administration"])


class BoatSpec(BaseModel):
    """A boat in this event.

    On the water, people refer to color and name; the number is only the position in the
    pairing list. If omitted, it will be auto-numbered.
    """

    number: int | None = Field(default=None, ge=1, le=40)
    color: str | None = Field(default=None, max_length=24)
    name: str | None = Field(default=None, max_length=80)
    sail_number: str | None = Field(default=None, max_length=32)


class PrintSettingsIn(BaseModel):
    """How this event's pairing list is printed (Story B-3).

    Left alone, the sheet is printed the way its configuration implies — the sizes the
    league's own matchdays have been printed at for years (``app/pairing/pdf.py``). The
    organizer overrides them because they know the venue, the printer and the paper, and
    nobody else does.
    """

    font_size: int | None = Field(
        default=None,
        ge=5,
        le=16,
        description="Points. Empty means derived from flights × races per flight.",
    )
    landscape: bool = Field(
        default=False, description="Rotate the sheet; a wide fleet reads better across it."
    )
    team_pages: bool = Field(default=True, description="One page per team after the overview.")


class EventCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200, description="Matchday name")
    starts_on: date | None = Field(
        default=None,
        description=(
            "Optional: an event whose date is still being negotiated with the host can be "
            "saved without one. It cannot be started without one."
        ),
    )
    ends_on: date | None = Field(
        default=None, description="If omitted, the matchday is treated as single-day."
    )
    series: int | None = Field(
        default=None,
        description=(
            "Series ID. If not specified, the event stands alone and counts in no series ranking."
        ),
    )

    host_club_id: int | None = Field(default=None, description="Host club")
    logo_url: str | None = Field(
        default=None, description="Custom logo; otherwise the host club's emblem is used."
    )
    live_url: str | None = Field(
        default=None,
        max_length=300,
        pattern=r"^https?://",
        description=(
            "An external live view (e.g. SAP Sailing). Set, the site's live links lead "
            "there; empty, the internal map is the live view."
        ),
    )
    venue_id: int | None = None
    matchday: int | None = Field(
        default=None,
        description="Which act of the series. If omitted, it will be incremented.",
    )
    team_count: int = Field(default=18, ge=2, le=64)
    boat_count: int = Field(default=6, ge=2, le=20)
    flight_count: int = Field(default=16, ge=1, le=40)
    teams_per_club: int = Field(
        default=1,
        ge=1,
        le=64,
        description="How many teams one club may enter (Story VA-13); 1 is the normal case.",
    )
    boats: list[BoatSpec] = Field(
        default_factory=list,
        description=(
            "Boats with color and name. If not specified, boat_count boats are created in "
            "league colors; if specified, their count determines boat_count."
        ),
    )
    published: bool = Field(
        default=False,
        description=(
            "Whether the event is visible on the public site right away. A draft stays "
            "invisible until published; publishing locks nothing."
        ),
    )
    # The squad's size, used only when the event stands alone (Story V-1).
    squad_min: int = Field(default=4, ge=1, le=50)
    squad_max: int = Field(default=10, ge=1, le=50)
    print_settings: PrintSettingsIn | None = Field(
        default=None, description="Print settings for the pairing list; empty for defaults."
    )

    @model_validator(mode="after")
    def _validate(self) -> EventCreate:
        if self.ends_on is None:
            self.ends_on = self.starts_on
        elif self.starts_on is not None and self.ends_on < self.starts_on:
            raise ValueError("End date cannot be before start date.")
        if self.teams_per_club > self.team_count:
            raise ValueError("A club cannot enter more teams than the event has.")
        if self.boats:
            self.boat_count = len(self.boats)
            numbers = [b.number for b in self.boats if b.number is not None]
            if len(set(numbers)) != len(numbers):
                raise ValueError("Two boats have the same number.")
        return self


class EventUpdate(BaseModel):
    """All fields optional — only those provided will be set."""

    title: str | None = Field(default=None, min_length=3, max_length=200)
    starts_on: date | None = None
    ends_on: date | None = None
    # No ``status``: it changes only through start/finish/cancel/reopen (Story VA-10,
    # ``services/event_state.py``) — here it once skipped every one of their rules. A
    # ``status`` sent anyway is ignored, like any other unknown field.
    published: bool | None = None
    host_club_id: int | None = None
    logo_url: str | None = None
    live_url: str | None = Field(default=None, max_length=300, pattern=r"^https?://")
    venue_id: int | None = None
    series: int | None = None
    matchday: int | None = None
    team_count: int | None = Field(default=None, ge=2, le=64)
    boat_count: int | None = Field(default=None, ge=2, le=20)
    flight_count: int | None = Field(default=None, ge=1, le=40)
    teams_per_club: int | None = Field(default=None, ge=1, le=64)
    squad_min: int | None = Field(default=None, ge=1, le=50)
    squad_max: int | None = Field(default=None, ge=1, le=50)
    print_settings: PrintSettingsIn | None = None


# The fields that make up the **configuration** of the event: what gets drawn and sailed.
# Once racing has started these are frozen (Story VA-8) — a pairing list is sailed against
# these numbers, and moving an event into another series would re-home results that are
# already in a standings table. Everything else (title, dates, venue, host, logo,
# publication) stays editable: a typo or a moved venue must remain fixable while racing.
_CONFIGURATION_FIELDS = frozenset(
    {"team_count", "boat_count", "flight_count", "teams_per_club", "series", "matchday"}
)


#: Story A-13 — the columns this list may be sorted by.
EVENT_SORT = {
    "title": Event.title,
    "starts_on": Event.starts_on,
    "status": Event.status,
    "matchday": Event.matchday,
}


@router.get(
    "",
    response_model=Page[EventOut],
    summary="All events, drafts included",
)
async def list_all_events(
    q: str | None = Query(default=None, description="Search in title, venue and host club"),
    params: PageParams = PageInput,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> Page[EventOut]:
    """Everything that has been saved — deliberately *not* the public list.

    ``GET /api/events`` shows only what is published, which is exactly the wrong list for
    the screen that publishes things: a draft would be invisible on the one page meant to
    finish it. Drafts sort first, then by date, newest first — an event with no date yet is
    the one still being worked on, so it belongs at the top rather than at the end. Paged
    since Story A-13; this list grows by a dozen or so every season and never shrinks.

    Searched by the same fields as the public calendar, through the same function: the two
    lists differ in what they may show — drafts included here — not in what a search term
    means.

    A race officer granted on one event, one series or one club (Story Z-2) sees the
    events those grants reach and nothing else — the same list, narrowed, rather than a
    tab that answers 403.
    """
    stmt = search_events(select(Event).options(*_EVENT_LOAD), q)
    # The site's editor reads them all to name a post's or a picture's regatta — reading
    # only: every change to an event asks the model about that event.
    if not acting.can(Relation.ADMIN, Relation.EDITOR, Relation.RACE_OFFICER):
        reach = _reach_of(acting)
        if reach is None:
            raise forbidden("this", [Relation.ADMIN, Relation.RACE_OFFICER])
        stmt = stmt.where(reach)
    events, total = await paginate(
        session,
        stmt,
        params,
        sortable=EVENT_SORT,
        default_order=[Event.starts_on.desc().nulls_first(), Event.id.desc()],
    )
    return page_of([_event_out(event) for event in events], total, params)


@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED)
async def create_event(
    request: EventCreate,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> EventOut:
    """Create an event — Stories A-4, VA-6 and VA-8.

    Only the **name** is required; everything else has sensible defaults or may stay
    empty — the date included, because saving must never depend on the setup being
    complete. The dimensions (teams, boats, flights) determine the pairing list: either a
    catalog entry fits, or it must be calculated.

    The **host club's** leadership can create events — they organize it, so they should be
    able to record the date — as well as administration, editorial, and race officers.
    """
    series = await get_or_404(session, Series, request.series) if request.series else None
    _can_create(acting, request.host_club_id, series.id if series else None)
    if request.host_club_id is not None:
        await get_or_404(session, Club, request.host_club_id)
    if request.venue_id is not None:
        await get_or_404(session, Venue, request.venue_id)

    try:
        matchday, slug = await place_event(
            session,
            title=request.title,
            starts_on=request.starts_on,
            series=series,
            matchday=request.matchday,
        )
    except MatchdayTaken as taken:
        raise Problem(409, "matchday-taken", str(taken), matchday=taken.matchday) from taken
    except NoFreeSlug as exhausted:
        raise Problem(409, "slug-exhausted", str(exhausted)) from exhausted

    check_squad_limits(request.squad_min, request.squad_max)
    event = Event(
        slug=slug,
        title=request.title.strip(),
        matchday=matchday,
        starts_on=request.starts_on,
        ends_on=request.ends_on or request.starts_on,
        status=EventStatus.PLANNED,
        published=request.published,
        series_id=series.id if series else None,
        venue_id=request.venue_id,
        host_club_id=request.host_club_id,
        logo_url=request.logo_url,
        live_url=request.live_url,
        team_count=request.team_count,
        boat_count=request.boat_count,
        flight_count=request.flight_count,
        teams_per_club=request.teams_per_club,
        squad_min=request.squad_min,
        squad_max=request.squad_max,
        print_settings=(request.print_settings.model_dump() if request.print_settings else None),
    )
    session.add(event)
    await session.flush()
    session.add_all(_boats(event, request))
    # Typically, the same clubs enter an act as in the series. The administration can
    # deviate later via PUT /api/admin/events/{id}/clubs.
    await adopt_series_registrations(session, event)
    await session.commit()
    return _event_out(await _with_relationships(session, event.id))


@router.patch(
    "/{event_id}",
    response_model=EventOut,
    dependencies=[Depends(require_event_manager_for)],
)
async def update_event(
    event_id: int,
    request: EventUpdate,
    session: AsyncSession = Depends(get_session),
) -> EventOut:
    """Change an event — Story VA-8.

    Never refuses because the event is incomplete: a half-filled event is savable, and the
    only thing that stands in the way of a change is the **first race**, which freezes the
    configuration (dimensions, series, matchday). Title, dates, venue, host, logo and
    publication stay editable throughout — a typo has to be fixable on a race day too. The
    status is not among them: it moves only through the transitions below (Story VA-10).
    """
    event = await _event(session, event_id)

    changes = request.model_dump(exclude_unset=True)
    # A null on a number every event has means "unchanged" — never None in a column the
    # checks below compare (`teams_per_club > team_count`).
    for field in ("team_count", "boat_count", "flight_count", "teams_per_club"):
        if field in changes and changes[field] is None:
            del changes[field]
    if _CONFIGURATION_FIELDS & changes.keys():
        await require_editable_configuration(session, event.id)
    check_squad_limits(
        changes.get("squad_min", event.squad_min), changes.get("squad_max", event.squad_max)
    )
    if "series" in changes:
        series = changes.pop("series")
        if series is not None:
            await _series(session, series)
        changes["series_id"] = series
    if "host_club_id" in changes:
        await _check_club(session, changes["host_club_id"])
    if "venue_id" in changes:
        await _check_venue(session, changes["venue_id"])
    for field, value in changes.items():
        setattr(event, field, value)
    if event.teams_per_club > event.team_count:
        raise Problem(
            422,
            "teams-per-club-exceeds-teams",
            "A club cannot enter more teams than the event has.",
            teams_per_club=event.teams_per_club,
            team_count=event.team_count,
        )
    if "teams_per_club" in changes:
        # The organizer's parameter (Story VA-13), changeable — but a club's team beyond it
        # is taken away first, in the clubs block, never silently left over.
        entered = (
            await session.execute(select(func.max(Team.number)).where(Team.event_id == event.id))
        ).scalar_one_or_none() or 1
        if event.teams_per_club < entered:
            raise Problem(
                422,
                "teams-per-club-below-entered",
                "A club has more teams entered than that; take them away first.",
                teams_per_club=event.teams_per_club,
                entered=entered,
            )

    if (
        event.starts_on is not None
        and event.ends_on is not None
        and event.ends_on < event.starts_on
    ):
        raise Problem(422, "event-dates-inverted", "End date cannot be before start date.")

    await session.commit()
    # After the commit, like every event mutation: a viewer refetching earlier would read
    # the old row and stay stale (Story B-5).
    hub.publish(event_topic(event.id))
    return _event_out(await _with_relationships(session, event.id))


# -------------------------------------------------- Lifecycle (Story VA-8)


class ReadinessReasonOut(BaseModel):
    """One thing standing between the event and its first race.

    ``code`` is the contract — the client maps it in its own ``errors`` namespace —
    ``details`` carries the numbers to phrase it with. Deliberately no English sentence:
    the same reason has to read in German too.
    """

    code: str
    details: dict[str, object] = Field(default_factory=dict)


class EventReadinessOut(BaseModel):
    """Whether this event can be drawn and started, and what's missing if not."""

    event_id: int
    ready: bool
    reasons: list[ReadinessReasonOut] = Field(default_factory=list)
    # Whether a pairing list exists. Not a readiness reason — readiness is the
    # precondition *for* the draw — but the start needs one, and the UI shows it.
    has_pairing_list: bool = False
    # Racing has begun, so the configuration is frozen. Results stay editable.
    configuration_frozen: bool = False
    races_started: int = 0
    results_recorded: int = 0


@router.get(
    "/{event_id}/readiness",
    response_model=EventReadinessOut,
    dependencies=[Depends(require_event_manager_for)],
    summary="Is this event ready to be drawn and started?",
)
async def get_readiness(
    event_id: int, session: AsyncSession = Depends(get_session)
) -> EventReadinessOut:
    """Read-only: computes, never stores — Story VA-8.

    The organizer needs to see *what* is missing, which is why this is a list of reasons
    rather than a flag. It is the same list the draw and the start refuse with, so the
    screen and the error can never disagree.
    """
    event = await _event(session, event_id)
    reasons = await event_readiness(session, event)
    frozen = await configuration_frozen(session, event.id)
    return EventReadinessOut(
        event_id=event.id,
        ready=not reasons,
        reasons=[ReadinessReasonOut(**reason.as_dict()) for reason in reasons],
        has_pairing_list=await event_state.has_pairing_list(session, event.id),
        configuration_frozen=frozen is not None,
        races_started=frozen.races_started if frozen else 0,
        results_recorded=frozen.results_recorded if frozen else 0,
    )


@router.post(
    "/{event_id}/publish",
    response_model=EventOut,
    dependencies=[Depends(require_event_manager_for)],
    summary="Make the event publicly visible",
)
async def publish_event(event_id: int, session: AsyncSession = Depends(get_session)) -> EventOut:
    """Publishing is **not** a lock — Story VA-8.

    A published event stays fully editable, and it does not have to be complete: the
    calendar entry is often what makes people ask about the missing details. Publication
    and ``status`` are orthogonal; this changes only who can see the event.
    """
    return await _set_published(session, event_id, True)


@router.post(
    "/{event_id}/unpublish",
    response_model=EventOut,
    dependencies=[Depends(require_event_manager_for)],
    summary="Withdraw the event from the public site",
)
async def unpublish_event(event_id: int, session: AsyncSession = Depends(get_session)) -> EventOut:
    """Back to a draft. Results and pairing list stay untouched — only visibility ends."""
    return await _set_published(session, event_id, False)


@router.post(
    "/{event_id}/start",
    response_model=EventOut,
    dependencies=[Depends(require_event_control)],
    summary="Start the event",
)
async def start_event(event_id: int, session: AsyncSession = Depends(get_session)) -> EventOut:
    """Moves the event to ``live`` — Story VA-8.

    An explicit decision by someone on site, deliberately **not** a side effect of a date
    passing: a matchday postponed by fog must not start itself. The event has to be ready
    (same reasons as the draw) and must have a pairing list — there is nothing to run
    without one.

    The catalog reason is exempt here: what matters at the start is that a list *exists*,
    not where it came from. A draw computed by the optimizer for dimensions the catalog
    doesn't hold is just as valid.
    """
    event = await _event(session, event_id)
    await event_state.start_event(session, event)
    return await _committed(session, event)


@router.post(
    "/{event_id}/finish",
    response_model=EventOut,
    dependencies=[Depends(require_event_control)],
    summary="Declare that racing is over",
)
async def finish_event(event_id: int, session: AsyncSession = Depends(get_session)) -> EventOut:
    """Moves a **live** event to ``final`` — Story VA-10.

    Like the start, a declaration by the people on site rather than a consequence of
    anything: a day is over when the race committee says so, not when the last scheduled
    race has been sailed or a date has passed.

    It therefore **does not require a complete race list**. A matchday that loses its last
    three flights to dying wind is still finished; demanding all 48 races would disable
    this exactly on the days it is needed. A day where nothing at all was sailed is a
    cancellation, not a finish.

    And it **freezes nothing**. The configuration was already frozen by the first race
    (``require_editable_configuration``), and results deliberately never freeze — a protest
    heard weeks later still has to land, which is what the race-committee screens are for.
    """
    event = await _event(session, event_id)
    event_state.finish_event(event)
    return await _committed(session, event)


@router.post(
    "/{event_id}/cancel",
    response_model=EventOut,
    dependencies=[Depends(require_event_control)],
    summary="Call the event off",
)
async def cancel_event(event_id: int, session: AsyncSession = Depends(get_session)) -> EventOut:
    """Moves the event to ``cancelled`` — Story VA-10.

    Available from ``planned`` **and** from ``live``: a day can be called off before anyone
    leaves the dock, or abandoned halfway through.

    It **deletes nothing**. The pairing list and any results recorded stay exactly where
    they are, so a cancellation that turns out to be premature costs no data and
    ``reopen`` is enough to undo it.

    A cancelled event leaves the scored set (``SCORED_STATES`` in
    ``app/services/standings.py``), which also means the "who misses an event gets
    participants + 1" rule does not fire for it: being at a regatta that was called off
    must never be worse than staying home.
    """
    event = await _event(session, event_id)
    event_state.cancel_event(event)
    return await _committed(session, event)


@router.post(
    "/{event_id}/reopen",
    response_model=EventOut,
    dependencies=[Depends(require_event_control)],
    summary="Undo a finish or a cancellation",
)
async def reopen_event(event_id: int, session: AsyncSession = Depends(get_session)) -> EventOut:
    """Takes a closed event back — Story VA-10.

    Both closings are judgements made in a hurry, on a jetty, so both undo. Where they go
    back to differs, and the difference is the honest one: a finished event returns to
    ``live`` because it was being sailed, a cancelled one returns to ``planned`` because a
    reinstated day is prepared again, not resumed mid-race.
    """
    event = await _event(session, event_id)
    event_state.reopen_event(event)
    return await _committed(session, event)


async def _committed(session: AsyncSession, event: Event) -> EventOut:
    """Commits a transition and tells live pages about it.

    The transition itself is ``services/event_state.py``'s; an idempotent repeat changes
    nothing and is committed all the same — it costs nothing and keeps one path. Publication
    is deliberately untouched (Story VA-8).
    """
    await session.commit()
    # Every transition is something a live page must hear — after the commit (Story B-5).
    hub.publish(event_topic(event.id))
    return _event_out(await _with_relationships(session, event.id))


async def _set_published(session: AsyncSession, event_id: int, published: bool) -> EventOut:
    event = await _event(session, event_id)
    event.published = published
    await session.commit()
    # Visibility is a change too: a page showing this event has to learn that it is gone
    # (or back), and the series table gains or loses a column.
    hub.publish(event_topic(event.id))
    return _event_out(await _with_relationships(session, event.id))


# ------------------------------------------------------------------ Helpers


async def _event(session: AsyncSession, event_id: int) -> Event:
    # `get`, not a select: a route guard (`require_on_event`) loaded it into this session
    # already, and `get` answers from there.
    event = await get_or_404(session, Event, event_id)
    return event


async def _series(session: AsyncSession, series_id: int) -> Series:
    series = await get_or_404(session, Series, series_id)
    return series


async def _check_club(session: AsyncSession, club_id: int | None) -> None:
    if club_id is None:
        return
    if (
        await session.execute(select(Club.id).where(Club.id == club_id))
    ).scalar_one_or_none() is None:
        raise Problem(404, "club-not-found", f"Club {club_id} is not known.", id=club_id)


async def _check_venue(session: AsyncSession, venue_id: int | None) -> None:
    if venue_id is None:
        return
    if (
        await session.execute(select(Venue.id).where(Venue.id == venue_id))
    ).scalar_one_or_none() is None:
        raise Problem(404, "venue-not-found", f"Venue {venue_id} is not known.", id=venue_id)


async def _with_relationships(session: AsyncSession, event_id: int) -> Event:
    return (
        await session.execute(
            select(Event)
            .options(
                selectinload(Event.series),
                selectinload(Event.venue),
                selectinload(Event.host_club),
            )
            .where(Event.id == event_id)
        )
    ).scalar_one()


class ParticipantSetRequest(BaseModel):
    clubs: list[int] = Field(
        description=(
            "Clubs that enter this event, a club's id once per team it enters (Story VA-13) "
            "— twice for its first and second team. An empty list removes all."
        )
    )


class ParticipantOut(BaseModel):
    """An entry to this event."""

    team_id: int
    status: TeamStatus
    club: ClubOut
    # The club's first, second, … team, and its name — `KYC (SH) 2` (Story VA-13).
    number: int = 1
    name: str = ""


@router.get(
    "/{event_id}/clubs",
    response_model=list[ParticipantOut],
    dependencies=[Depends(require_event_manager_for)],
    summary="Event participants",
)
async def list_participants(
    event_id: int, session: AsyncSession = Depends(get_session)
) -> list[ParticipantOut]:
    """Also those requested — administration must see what it is deciding about."""
    await _event(session, event_id)
    return await _participants_out(session, event_id)


@router.get(
    "/{event_id}/candidate-clubs",
    response_model=list[ClubOut],
    dependencies=[Depends(require_event_manager_for)],
    summary="Clubs that may enter this event",
)
async def list_candidate_clubs(
    event_id: int, session: AsyncSession = Depends(get_session)
) -> list[ClubOut]:
    """The choice the clubs step offers — Story VA-6.

    An act of a series takes its series' accepted registrations, a stand-alone event any
    club: the same rule ``PUT …/clubs`` enforces, answered from the same place
    (``app/services/participation.py``).
    """
    event = await _event(session, event_id)
    return [ClubOut.model_validate(club) for club in await candidate_clubs(session, event)]


@router.put(
    "/{event_id}/clubs",
    response_model=list[ParticipantOut],
    dependencies=[Depends(require_event_manager_for)],
    summary="Set event participants",
)
async def set_participants(
    event_id: int,
    request: ParticipantSetRequest,
    session: AsyncSession = Depends(get_session),
) -> list[ParticipantOut]:
    """Sets the clubs entering this event.

    The pairing list is attached to the event — so are the teams within it. Whoever
    stands here will be drawn and ranked.

    Three rules apply: if the event belongs to a series, the club must be **registered**
    for it. A club enters as many teams as its id is listed, no more than the event's
    ``teams_per_club`` (Story VA-13); a team taken away is the highest-numbered. And once
    racing has started the field is frozen altogether (Story VA-8) — the pairing list being
    sailed was drawn for exactly these clubs.
    """
    event = await _event(session, event_id)
    await require_editable_configuration(session, event.id)
    clubs = {club.id: club for club in await _clubs(session, request.clubs)}
    wanted = Counter(request.clubs)

    existing = await event_entries(session, event.id, accepted_only=False)
    for team in existing:
        if team.number <= wanted[team.club_id]:
            # An approval from above lifts a pending request.
            team.status = TeamStatus.ACCEPTED
            continue
        if await has_results(session, team):
            raise Problem(
                409,
                "participation-has-results",
                "This club cannot be removed: race results already exist.",
                club_id=team.club_id,
            )
        await session.delete(team)

    entered = {(team.club_id, team.number) for team in existing}
    for club_id, count in wanted.items():
        for number in range(1, count + 1):
            if (club_id, number) not in entered:
                await new_event_entry(session, event, clubs[club_id], number=number)

    await session.commit()
    return await _participants_out(session, event.id)


async def _participants_out(session: AsyncSession, event_id: int) -> list[ParticipantOut]:
    rows = (
        await session.execute(
            select(Team, Club)
            .join(Club, Team.club_id == Club.id)
            .where(Team.event_id == event_id)
            .order_by(Club.name, Team.number)
        )
    ).all()
    return [
        ParticipantOut(
            team_id=team.id,
            status=team.status,
            club=ClubOut.model_validate(club),
            number=team.number,
            name=team.name,
        )
        for team, club in rows
    ]


async def _clubs(session: AsyncSession, club_ids: list[int]) -> list[Club]:
    unique = list(dict.fromkeys(club_ids))
    if not unique:
        return []
    found = {
        club.id: club
        for club in (await session.execute(select(Club).where(Club.id.in_(unique)))).scalars()
    }
    missing = [club_id for club_id in unique if club_id not in found]
    if missing:
        raise Problem(
            404, "clubs-not-found", f"These clubs do not exist: {missing}", club_ids=missing
        )
    return [found[club_id] for club_id in unique]


def _reach_of(acting: User):
    """The WHERE clause for the events a person's tuples reach, or None if none does: the
    event itself, every event of a series they hold something on, every event a club they
    hold something on hosts. Manager, race committee and jury alike — each has a screen
    here; and editorial, whose posts and pictures name the regatta they are about."""
    relations = (
        Relation.ADMIN,
        Relation.MANAGER,
        Relation.RACE_OFFICER,
        Relation.JURY,
        Relation.EDITOR,
    )
    events = authz.list_objects(acting, relations, ObjectType.EVENT)
    series = authz.list_objects(acting, relations, ObjectType.SERIES)
    clubs = authz.list_objects(acting, relations, ObjectType.CLUB)
    clauses = [
        column.in_(ids)
        for column, ids in (
            (Event.id, events),
            (Event.series_id, series),
            (Event.host_club_id, clubs),
        )
        if ids
    ]
    return or_(*clauses) if clauses else None


def _can_create(acting: User, host_club_id: int | None, series_id: int | None) -> None:
    """Who is permitted to create an event.

    The league office and its race committee; and the **organizers** — the manager of the
    host club, because they run the event and should record the date without waiting for
    someone else, and the manager of the series it belongs to (Story Z-2). For a foreign
    host this is not possible — otherwise a club would record dates for others.
    """
    if authz.check(acting, Relation.ADMIN, Relation.RACE_OFFICER):
        return
    if host_club_id is not None and authz.check(
        acting, Relation.MANAGER, on=ObjectRef(ObjectType.CLUB, host_club_id)
    ):
        return
    if series_id is not None and authz.check(
        acting, Relation.MANAGER, on=ObjectRef(ObjectType.SERIES, series_id)
    ):
        return
    if host_club_id is not None and authz.list_objects(acting, Relation.MANAGER, ObjectType.CLUB):
        raise Problem(403, "host-club-not-mine", "You can only host events for your own club.")
    raise Problem(
        403,
        "event-create-forbidden",
        "Events are created by administration, editorial, race officers, and the "
        "host club's leadership.",
    )


def _boats(event: Event, request: EventCreate) -> list[Boat]:
    """The boats for the event — with color and name as they lie at the dock.

    They are attached to the event, not the pairing list: a new draw swaps the assignment,
    not the boats.
    """
    if request.boats:
        return [
            Boat(
                event_id=event.id,
                number=spec.number if spec.number is not None else position,
                color=spec.color,
                name=spec.name,
                sail_number=spec.sail_number,
            )
            for position, spec in enumerate(request.boats, start=1)
        ]
    return [
        Boat(
            event_id=event.id,
            number=num,
            color=BOAT_COLORS[num - 1] if num <= len(BOAT_COLORS) else None,
        )
        for num in range(1, request.boat_count + 1)
    ]
