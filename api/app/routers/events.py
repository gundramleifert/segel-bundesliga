"""Create and manage matchdays.

Access is available to administration, editorial, and race officers — all three contribute
to an event and should be able to record a date without waiting for someone else.

To create an event, only **name, date and host club** are required. Venue, boat count, and
flight count can be added later; the matchday number is incremented if not specified.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import current_user, require_event_manager
from app.db import get_session
from app.i18n import Locale, resolve_locale, tr
from app.models import Boat, Club, Event, EventStatus, Series, Team, TeamStatus, Venue
from app.models.auth import Role, User
from app.models.racing import BOAT_COLORS
from app.routers.public import _event_out
from app.schemas.public import ClubOut, EventOut
from app.services import (
    ParticipationError,
    adopt_series_registrations,
    event_entries,
    has_results,
    new_event_entry,
)
from app.text import slugify

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


class EventCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200, description="Matchday name")
    starts_on: date
    ends_on: date | None = Field(
        default=None, description="If omitted, the matchday is treated as single-day."
    )
    series: int | None = Field(
        default=None,
        description=(
            "Series ID. If not specified, the event stands alone and counts in no "
            "series ranking."
        ),
    )

    host_club_id: int | None = Field(default=None, description="Host club")
    logo_url: str | None = Field(
        default=None, description="Custom logo; otherwise the host club's emblem is used."
    )
    venue_id: int | None = None
    matchday: int | None = Field(
        default=None,
        description="Which act of the series. If omitted, it will be incremented.",
    )
    team_count: int = Field(default=18, ge=2, le=64)
    boat_count: int = Field(default=6, ge=2, le=20)
    flight_count: int = Field(default=16, ge=1, le=40)
    boats: list[BoatSpec] = Field(
        default_factory=list,
        description=(
            "Boats with color and name. If not specified, boat_count boats are created in "
            "league colors; if specified, their count determines boat_count."
        ),
    )

    @model_validator(mode="after")
    def _validate(self) -> EventCreate:
        if self.ends_on is None:
            self.ends_on = self.starts_on
        elif self.ends_on < self.starts_on:
            raise ValueError("End date cannot be before start date.")
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
    status: str | None = None
    host_club_id: int | None = None
    logo_url: str | None = None
    venue_id: int | None = None
    series: int | None = None
    matchday: int | None = None
    team_count: int | None = Field(default=None, ge=2, le=64)
    boat_count: int | None = Field(default=None, ge=2, le=20)
    flight_count: int | None = Field(default=None, ge=1, le=40)


@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED)
async def create_event(
    request: EventCreate,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
    locale: Locale = Depends(resolve_locale),
) -> EventOut:
    """Create an event — Stories A-4 and VA-6.

    Only **name and date** are required; everything else has sensible defaults. The
    dimensions (teams, boats, flights) determine the pairing list: either a catalog entry
    fits, or it must be calculated.

    The **host club's** leadership can create events — they organize it, so they should be
    able to record the date — as well as administration, editorial, and race officers.
    """
    _can_create(acting, request.host_club_id)
    series = await _series(session, request.series) if request.series else None
    await _check_club(session, request.host_club_id)
    await _check_venue(session, request.venue_id)

    matchday = None
    if series is not None:
        matchday = request.matchday
        if matchday is None:
            highest = (
                await session.execute(
                    select(func.max(Event.matchday)).where(Event.series_id == series.id)
                )
            ).scalar_one()
            matchday = (highest or 0) + 1
        elif await _matchday_exists(session, series.id, matchday):
            raise HTTPException(
                status_code=409,
                detail=tr(
                    locale,
                    en=f"This series already has Act {matchday}.",
                    de=f"In dieser Serie gibt es den {matchday}. Act schon.",
                ),
            )
        desired = f"{series.slug}-act-{matchday}"
    else:
        # Standalone event: the URL is created from title and year.
        desired = f"{slugify(request.title)}-{request.starts_on.year}"

    slug = await _find_free_slug(session, desired)

    event = Event(
        slug=slug,
        title=request.title.strip(),
        matchday=matchday,
        starts_on=request.starts_on,
        ends_on=request.ends_on or request.starts_on,
        status=EventStatus.PLANNED,
        series_id=series.id if series else None,
        venue_id=request.venue_id,
        host_club_id=request.host_club_id,
        logo_url=request.logo_url,
        team_count=request.team_count,
        boat_count=request.boat_count,
        flight_count=request.flight_count,
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
    dependencies=[Depends(require_event_manager)],
)
async def update_event(
    event_id: int,
    request: EventUpdate,
    session: AsyncSession = Depends(get_session),
    locale: Locale = Depends(resolve_locale),
) -> EventOut:
    event = await _event(session, event_id)

    changes = request.model_dump(exclude_unset=True)
    if "series" in changes:
        series = changes.pop("series")
        if series is not None:
            await _series(session, series)
        changes["series_id"] = series
    if "host_club_id" in changes:
        await _check_club(session, changes["host_club_id"])
    if "venue_id" in changes:
        await _check_venue(session, changes["venue_id"])
    if "status" in changes and changes["status"] not in set(EventStatus):
        possible_statuses = ", ".join(sorted(EventStatus))
        raise HTTPException(
            status_code=422,
            detail=tr(
                locale,
                en=f"Unknown status. Possible: {possible_statuses}",
                de=f"Unbekannter Status. Möglich: {possible_statuses}",
            ),
        )

    for field, value in changes.items():
        setattr(event, field, value)

    if event.ends_on < event.starts_on:
        raise HTTPException(
            status_code=422,
            detail=tr(
                locale,
                en="End date cannot be before start date.",
                de="Das Ende darf nicht vor dem Beginn liegen.",
            ),
        )

    await session.commit()
    return _event_out(await _with_relationships(session, event.id))


# ------------------------------------------------------------------ Helpers


async def _event(session: AsyncSession, event_id: int) -> Event:
    event = (
        await session.execute(select(Event).where(Event.id == event_id))
    ).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail=f"Matchday {event_id} not found")
    return event


async def _series(session: AsyncSession, series_id: int) -> Series:
    series = (
        await session.execute(select(Series).where(Series.id == series_id))
    ).scalar_one_or_none()
    if series is None:
        raise HTTPException(
            status_code=404,
            detail=f"Series {series_id} is not set up. Create the series first.",
        )
    return series


async def _check_club(session: AsyncSession, club_id: int | None) -> None:
    if club_id is None:
        return
    if (
        await session.execute(select(Club.id).where(Club.id == club_id))
    ).scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Club {club_id} is not known.")


async def _check_venue(session: AsyncSession, venue_id: int | None) -> None:
    if venue_id is None:
        return
    if (
        await session.execute(select(Venue.id).where(Venue.id == venue_id))
    ).scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Venue {venue_id} is not known.")


async def _matchday_exists(session: AsyncSession, series_id: int, matchday: int) -> bool:
    match = (
        await session.execute(
            select(Event.id).where(
                Event.series_id == series_id, Event.matchday == matchday
            )
        )
    ).scalar_one_or_none()
    return match is not None


async def _find_free_slug(session: AsyncSession, desired: str) -> str:
    """Appends a digit if the slug is already taken — it must be unique."""
    candidate = desired
    for counter in range(2, 50):
        taken = (
            await session.execute(select(Event.id).where(Event.slug == candidate))
        ).scalar_one_or_none()
        if taken is None:
            return candidate
        candidate = f"{desired}-{counter}"
    raise HTTPException(status_code=409, detail="Could not find a free URL.")


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
            "Clubs that enter this event. An empty list removes all."
        )
    )


class ParticipantOut(BaseModel):
    """An entry to this event."""

    team_id: int
    status: str
    club: ClubOut


@router.get(
    "/{event_id}/clubs",
    response_model=list[ParticipantOut],
    dependencies=[Depends(require_event_manager)],
    summary="Event participants",
)
async def list_participants(
    event_id: int, session: AsyncSession = Depends(get_session)
) -> list[ParticipantOut]:
    """Also those requested — administration must see what it is deciding about."""
    await _event(session, event_id)
    return await _participants_out(session, event_id)


@router.put(
    "/{event_id}/clubs",
    response_model=list[ParticipantOut],
    dependencies=[Depends(require_event_manager)],
    summary="Set event participants",
)
async def set_participants(
    event_id: int,
    request: ParticipantSetRequest,
    session: AsyncSession = Depends(get_session),
    locale: Locale = Depends(resolve_locale),
) -> list[ParticipantOut]:
    """Sets the clubs entering this event.

    The pairing list is attached to the event — so are the teams within it. Whoever
    stands here will be drawn and ranked.

    Two rules apply: if the event belongs to a series, the club must be **registered** for
    it. And a club that has already sailed cannot be removed — results are attached to it.
    """
    event = await _event(session, event_id)
    desired = {club.id: club for club in await _clubs(session, request.clubs)}

    existing = {
        team.club_id: team for team in await event_entries(session, event.id, accepted_only=False)
    }

    for club_id, team in existing.items():
        if club_id in desired:
            # An approval from above lifts a pending request.
            team.status = TeamStatus.ACCEPTED
            continue
        if await has_results(session, team):
            de_msg = (
                "Dieser Verein lässt sich nicht herausnehmen: "
                "es liegen bereits Wettfahrtergebnisse vor."
            )
            raise HTTPException(
                status_code=409,
                detail=tr(
                    locale,
                    en="This club cannot be removed: race results already exist.",
                    de=de_msg,
                ),
            )
        await session.delete(team)

    for club_id, club in desired.items():
        if club_id in existing:
            continue
        try:
            await new_event_entry(session, event, club)
        except ParticipationError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    await session.commit()
    return await _participants_out(session, event.id)


async def _participants_out(session: AsyncSession, event_id: int) -> list[ParticipantOut]:
    rows = (
        await session.execute(
            select(Team, Club)
            .join(Club, Team.club_id == Club.id)
            .where(Team.event_id == event_id)
            .order_by(Club.name)
        )
    ).all()
    return [
        ParticipantOut(team_id=team.id, status=team.status, club=ClubOut.model_validate(club))
        for team, club in rows
    ]


async def _clubs(session: AsyncSession, club_ids: list[int]) -> list[Club]:
    unique = list(dict.fromkeys(club_ids))
    if not unique:
        return []
    found = {
        club.id: club
        for club in (
            await session.execute(select(Club).where(Club.id.in_(unique)))
        ).scalars()
    }
    missing = [club_id for club_id in unique if club_id not in found]
    if missing:
        raise HTTPException(status_code=404, detail=f"These clubs do not exist: {missing}")
    return [found[club_id] for club_id in unique]


def _can_create(acting: User, host_club_id: int | None) -> None:
    """Who is permitted to create an event.

    In addition to administration, editorial, and race officers, also the **host club's
    leadership**: they organize the event, so they should be able to record the date without
    waiting for someone else. For a foreign host, this is not possible — otherwise a club
    would record dates for others.
    """
    if acting.has_any(Role.ADMIN, Role.EDITOR, Role.RACE_OFFICER):
        return
    if acting.has_any(Role.CLUB_MANAGER) and host_club_id is not None:
        if acting.manages_club(host_club_id):
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only host events for your own club.",
        )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "Events are created by administration, editorial, race officers, and the "
            "host club's leadership."
        ),
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
