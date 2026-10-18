"""Setting a club's series registrations, from either side.

Two screens write the same rows: the club's (``PUT /api/admin/clubs/{id}/series``) and the
series' (``PUT /api/admin/series/{id}/clubs``). Both are a set — the registrations wanted —
diffed against the series-level ``Team`` rows that exist. This is that diff, once.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event, EventStatus, Team, TeamStatus
from app.services.participation import (
    adopt_series_registrations,
    delete_event_entries,
    has_results,
)


class Registration(NamedTuple):
    """One club registered for one series, under the team name it gets when new."""

    club_id: int
    series_id: int
    team_name: str


class RegistrationHasResults(Exception):
    """A registration to be removed has race results under it — results depend on it."""

    def __init__(self, team: Team) -> None:
        super().__init__(f"Team {team.id} already has results")
        self.team = team


async def sync_registrations(
    session: AsyncSession, existing: Iterable[Team], desired: Iterable[Registration]
) -> None:
    """Makes ``existing`` (series-level teams) match ``desired``, then flushes.

    A removed registration takes its entries in the series' events with it; one that has
    results is refused with :class:`RegistrationHasResults` before anything is deleted for
    it. A new one is accepted at once (an admin assigning it is the participation) and is
    entered into the series' unraced events.
    """
    wanted = {(r.club_id, r.series_id): r for r in desired}
    have = {(team.club_id, team.series_id): team for team in existing}

    for key, team in have.items():
        if key in wanted:
            continue
        if await has_results(session, team):
            raise RegistrationHasResults(team)
        # Without series registration, no entry in its events.
        await delete_event_entries(session, team.series_id, team.club_id)
        await session.delete(team)

    session.add_all(
        Team(
            name=r.team_name,
            club_id=r.club_id,
            series_id=r.series_id,
            status=TeamStatus.ACCEPTED,
        )
        for key, r in wanted.items()
        if key not in have
    )
    await session.flush()
    await backfill_event_entries(session, {r.series_id for r in wanted.values()})


async def backfill_event_entries(session: AsyncSession, series_ids: Iterable[int]) -> None:
    """Enter each series' registered clubs in its unraced events.

    Normally the same clubs enter every event of a series; a club that joins later
    shouldn't need adding to each upcoming event by hand. An already-raced event stays
    untouched — otherwise someone would appear in a list they never started in.
    """
    events = (
        (
            await session.execute(
                select(Event).where(
                    Event.series_id.in_(list(series_ids)), Event.status == EventStatus.PLANNED
                )
            )
        )
        .scalars()
        .all()
    )
    for event in events:
        await adopt_series_registrations(session, event)
