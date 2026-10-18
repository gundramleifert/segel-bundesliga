"""Where a new event sits: its matchday number in its series and its URL slug.

Stories A-4 and VA-6. An act of a series is numbered after the series' highest act unless
one is asked for, and is addressed as ``<series-slug>-act-<n>``; a standalone event is
addressed by its title and year. Taken slugs get a digit appended — a slug must be unique.

Kept out of the router so an import or a script creating an event numbers and names it
the same way the screen does.
"""

from __future__ import annotations

from datetime import date
from typing import NamedTuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event, Series
from app.text import slugify

# How many ``-2``, ``-3`` … suffixes are tried before giving up.
_SLUG_ATTEMPTS = 50


class EventPlacement(NamedTuple):
    matchday: int | None
    slug: str


class MatchdayTaken(Exception):
    """The series already has an event with this matchday number."""

    def __init__(self, matchday: int) -> None:
        self.matchday = matchday
        super().__init__(f"This series already has Act {matchday}.")


class NoFreeSlug(Exception):
    """Every candidate slug is taken."""

    def __init__(self) -> None:
        super().__init__("Could not find a free URL.")


async def place_event(
    session: AsyncSession,
    *,
    title: str,
    starts_on: date | None,
    series: Series | None,
    matchday: int | None,
) -> EventPlacement:
    """The matchday number and the free slug for a new event.

    In a series, ``matchday`` ``None`` means "the next one"; a number the series already
    has is refused with :class:`MatchdayTaken`. Outside a series there is no matchday, and
    without a date yet the current year stands in for the slug — it only has to be unique
    and readable.
    """
    if series is not None:
        if matchday is None:
            highest = (
                await session.execute(
                    select(func.max(Event.matchday)).where(Event.series_id == series.id)
                )
            ).scalar_one()
            matchday = (highest or 0) + 1
        elif await _matchday_exists(session, series.id, matchday):
            raise MatchdayTaken(matchday)
        desired = f"{series.slug}-act-{matchday}"
    else:
        matchday = None
        year = (starts_on or date.today()).year
        desired = f"{slugify(title)}-{year}"
    return EventPlacement(matchday, await free_slug(session, desired))


async def _matchday_exists(session: AsyncSession, series_id: int, matchday: int) -> bool:
    match = (
        await session.execute(
            select(Event.id).where(Event.series_id == series_id, Event.matchday == matchday)
        )
    ).scalar_one_or_none()
    return match is not None


async def free_slug(session: AsyncSession, desired: str) -> str:
    """``desired``, or ``desired-2``, ``desired-3`` … — the first no event has yet."""
    candidate = desired
    for counter in range(2, _SLUG_ATTEMPTS):
        taken = (
            await session.execute(select(Event.id).where(Event.slug == candidate))
        ).scalar_one_or_none()
        if taken is None:
            return candidate
        candidate = f"{desired}-{counter}"
    raise NoFreeSlug
