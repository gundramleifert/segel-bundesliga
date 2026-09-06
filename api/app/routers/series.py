"""Series creation and management — Story A-6.

A series is a set of events scored together ("DSBL 2026").
When creating, admin selects from existing clubs which ones participate; this generates
the teams (`Team`).

This is the inverse of `PUT /api/admin/clubs/{id}/series`: there a club is attached to
multiple series, here a series is attached to multiple clubs. Both write the same rows.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.db import get_session
from app.i18n import Locale, resolve_locale, tr
from app.models import Club, Event, EventStatus, Series, Team, TeamStatus
from app.schemas.public import ClubOut, SeriesOut
from app.services import hat_ergebnisse, loesche_antritte, uebernehme_serienmeldungen
from app.text import slugify

router = APIRouter(
    prefix="/api/admin/series",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)

# At the matchday, racing without discards; percent penalty follows RRS 44.3.
DEFAULT_SCORING: dict[str, Any] = {"discard_after": [], "penalty_percent": 20}


class SeriesCreate(BaseModel):
    """Name and year suffice for creation; clubs can be selected immediately."""

    name: str = Field(min_length=3, max_length=160, description='e.g., "1. Segel-Bundesliga 2026"')
    short_name: str | None = Field(
        default=None, max_length=48, description="Abbreviation. If absent, the name is used."
    )
    year: int | None = Field(default=None, ge=1900, le=2200)
    starts_on: date | None = None
    ends_on: date | None = None
    level: int | None = Field(
        default=None, description="Rank in the year: 1 for the first, 2 for the second league"
    )
    clubs: list[int] = Field(
        default_factory=list, description="Clubs participating in this series"
    )
    scoring: dict[str, Any] | None = None
    slug: str | None = Field(default=None, description="If absent, it is generated from the name.")


class SeriesUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=160)
    short_name: str | None = Field(default=None, max_length=48)
    year: int | None = Field(default=None, ge=1900, le=2200)
    starts_on: date | None = None
    ends_on: date | None = None
    level: int | None = None
    scoring: dict[str, Any] | None = None


class SetClubs(BaseModel):
    clubs: list[int] = Field(
        description="The clubs in this series. An empty list removes all assignments."
    )


class SeriesParticipantOut(ClubOut):
    """A registered club — along with its team ID.

    The squad hangs off the team; without its ID, the UI couldn't reach it without
    querying each club individually.
    """

    team_id: int


class SeriesAdminOut(SeriesOut):
    """Like SeriesOut, plus participants and how many events have been scheduled."""

    clubs: list[SeriesParticipantOut] = Field(default_factory=list)
    event_count: int = 0


@router.get("", response_model=list[SeriesAdminOut], summary="All series")
async def list_all_series(session: AsyncSession = Depends(get_session)) -> list[SeriesAdminOut]:
    """All years, not just the current one — admin plans ahead."""
    series = (
        await session.execute(
            select(Series).order_by(Series.year.desc().nulls_last(), Series.level.nulls_last())
        )
    ).scalars().all()

    participants = (
        await session.execute(
            select(Team.series_id, Team.id, Club)
            .join(Club, Team.club_id == Club.id)
            .where(Team.status == TeamStatus.ACCEPTED, Team.event_id.is_(None))
            .order_by(Club.name)
        )
    ).all()
    by_series: dict[int, list[SeriesParticipantOut]] = {}
    for series_id, team_id, club in participants:
        by_series.setdefault(series_id, []).append(
            SeriesParticipantOut(**ClubOut.model_validate(club).model_dump(), team_id=team_id)
        )

    events = dict(
        (
            await session.execute(
                select(Event.series_id, func.count(Event.id))
                .where(Event.series_id.is_not(None))
                .group_by(Event.series_id)
            )
        ).all()
    )

    return [
        SeriesAdminOut(
            **SeriesOut.model_validate(s).model_dump(),
            clubs=by_series.get(s.id, []),
            event_count=events.get(s.id, 0),
        )
        for s in series
    ]


@router.post("", response_model=SeriesAdminOut, status_code=status.HTTP_201_CREATED)
async def create_series(
    request: SeriesCreate,
    session: AsyncSession = Depends(get_session),
    locale: Locale = Depends(resolve_locale),
) -> SeriesAdminOut:
    """Creates a series and registers the selected clubs immediately."""
    slug = slugify(request.slug or request.name)
    if await _slug_belegt(session, slug):
        raise HTTPException(
            status_code=409,
            detail=tr(
                locale,
                f"The URL '{slug}' is already taken. Please provide your own slug.",
                f"Die Adresse '{slug}' ist schon vergeben. Bitte einen eigenen Slug angeben.",
            ),
        )

    clubs = await _resolve_clubs(session, request.clubs, locale)

    series = Series(
        slug=slug,
        name=request.name.strip(),
        # Without its own abbreviation, use the name — better than a guessed one.
        short_name=(request.short_name or request.name).strip()[:48],
        year=request.year,
        starts_on=request.starts_on,
        ends_on=request.ends_on,
        level=request.level,
        scoring=request.scoring if request.scoring is not None else dict(DEFAULT_SCORING),
    )
    session.add(series)
    await session.flush()

    session.add_all(
        Team(
            name=club.short_name,
            club_id=club.id,
            series_id=series.id,
            status=TeamStatus.ACCEPTED,
        )
        for club in clubs
    )
    await session.commit()
    return await _series_out(session, series.id)


@router.patch("/{series_id}", response_model=SeriesAdminOut)
async def update_series(
    series_id: int,
    request: SeriesUpdate,
    session: AsyncSession = Depends(get_session),
    locale: Locale = Depends(resolve_locale),
) -> SeriesAdminOut:
    series = await _get_series(session, series_id, locale)
    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(series, field, value.strip() if isinstance(value, str) else value)
    await session.commit()
    return await _series_out(session, series.id)


@router.put("/{series_id}/clubs", response_model=SeriesAdminOut, summary="Set participants")
async def set_clubs(
    series_id: int,
    request: SetClubs,
    session: AsyncSession = Depends(get_session),
    locale: Locale = Depends(resolve_locale),
) -> SeriesAdminOut:
    """Sets the clubs participating in this series.

    A club that has already raced in this series cannot be removed — results depend on it.
    """
    series = await _get_series(session, series_id, locale)
    desired = {club.id: club for club in await _resolve_clubs(session, request.clubs, locale)}

    existing = {
        team.club_id: team
        for team in (
            await session.execute(
                select(Team).where(Team.series_id == series.id, Team.event_id.is_(None))
            )
        ).scalars()
    }

    for club_id, team in existing.items():
        if club_id in desired:
            continue
        if await hat_ergebnisse(session, team):
            raise HTTPException(
                status_code=409,
                detail=tr(
                    locale,
                    (
                        "This club cannot be removed: this series already has"
                        " race results for it."
                    ),
                    (
                        "Dieser Verein lässt sich nicht entfernen: in dieser Serie"
                        " liegen für ihn bereits Wettfahrtergebnisse vor."
                    ),
                ),
            )
        # Without series registration, no entry in its events.
        await loesche_antritte(session, series.id, club_id)
        await session.delete(team)

    session.add_all(
        Team(
            name=club.short_name,
            club_id=club.id,
            series_id=series.id,
            status=TeamStatus.ACCEPTED,
        )
        for club_id, club in desired.items()
        if club_id not in existing
    )
    await session.flush()
    await _antritte_nachziehen(session, series.id)
    await session.commit()
    return await _series_out(session, series.id)


# ------------------------------------------------------------------ Helper functions


async def _get_series(session: AsyncSession, series_id: int, locale: Locale) -> Series:
    """Fetch a series by ID, raising 404 if not found."""
    series = (
        await session.execute(select(Series).where(Series.id == series_id))
    ).scalar_one_or_none()
    if series is None:
        raise HTTPException(
            status_code=404,
            detail=tr(
                locale, f"Series {series_id} not found", f"Serie {series_id} nicht gefunden"
            ),
        )
    return series


async def _resolve_clubs(session: AsyncSession, club_ids: list[int], locale: Locale) -> list[Club]:
    """Resolve selected clubs by ID — and report which is missing rather than silently skip."""
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
        raise HTTPException(
            status_code=404,
            detail=tr(
                locale,
                f"These clubs do not exist: {missing}",
                f"Diese Vereine gibt es nicht: {missing}",
            ),
        )
    return [found[club_id] for club_id in unique]


async def _slug_belegt(session: AsyncSession, slug: str) -> bool:
    """Check if a slug is already taken."""
    hit = (
        await session.execute(select(Series.id).where(Series.slug == slug))
    ).scalar_one_or_none()
    return hit is not None


async def _series_out(session: AsyncSession, series_id: int) -> SeriesAdminOut:
    """Fetch the current state of a series for output."""
    return next(s for s in await list_all_series(session) if s.id == series_id)


async def _antritte_nachziehen(session: AsyncSession, series_id: int) -> None:
    """Register the series' clubs in unraced events of the series.

    Normally, the same clubs enter every event of a series; if a club joins later,
    it shouldn't need to be added individually to upcoming events. An already-raced
    event remains untouched — otherwise someone would appear in the list who never
    started.
    """
    events = (
        await session.execute(
            select(Event).where(
                Event.series_id == series_id, Event.status == EventStatus.PLANNED
            )
        )
    ).scalars().all()
    for event in events:
        await uebernehme_serienmeldungen(session, event)
