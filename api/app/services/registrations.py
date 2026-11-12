"""Who sails: a club's series registrations and an event's field, from every side.

Two screens write the same series rows: the club's (``PUT /api/admin/clubs/{id}/series``)
and the series' (``PUT /api/admin/series/{id}/clubs``). Both are a set — the registrations
wanted — diffed against the series-level ``Team`` rows that exist. This is that diff, once.
The event's field (``PUT /api/admin/events/{id}/clubs``) and a decided application are
the other two writers. This module owns ``TeamStatus``.

**One rule for a changed field** (review 3.4): before racing starts, any change to who
sails an event clears its draw — the list was drawn for other clubs; after it, the change
is refused (``event-configuration-frozen``). :func:`field_changing` is that rule, and
every writer here calls it before it touches an event's entries.

**Listing a club accepts it** (review 3.5): a ``requested`` or ``rejected`` row of a club
an organizer sets is accepted, on both screens.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Club, Event, EventStatus, Team, TeamStatus
from app.models.auth import User
from app.problems import Problem
from app.services.audit import EntityType, audit
from app.services.event_readiness import racing_started, require_editable_configuration
from app.services.pairing_service import clear_pairing
from app.services.participation import (
    adopt_series_registrations,
    event_entries,
    has_results,
    new_event_entry,
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
            team.status = TeamStatus.ACCEPTED
            continue
        if await has_results(session, team):
            raise RegistrationHasResults(team)
        # Without series registration, no entry in its events.
        assert team.series_id is not None
        for entry in await _entries_in_series(session, team.series_id, team.club_id):
            await field_changing(session, entry.event_id)
            await session.delete(entry)
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
    shouldn't need adding to each upcoming event by hand. An event where racing started
    stays untouched — otherwise someone would appear in a list they never started in —
    and one that took a club in loses its draw.
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
        if await racing_started(session, event.id):
            continue
        if await adopt_series_registrations(session, event):
            await clear_pairing(session, event.id)


async def field_changing(session: AsyncSession, event_id: int | None) -> None:
    """Who sails this event is about to change: refused once racing started, and the
    draw — made for the old field — cleared before it. A series row (no event) has no
    draw of its own."""
    if event_id is None:
        return
    await require_editable_configuration(session, event_id)
    await clear_pairing(session, event_id)


async def _entries_in_series(session: AsyncSession, series_id: int, club_id: int) -> list[Team]:
    return list(
        (
            await session.execute(
                select(Team).where(
                    Team.series_id == series_id,
                    Team.club_id == club_id,
                    Team.event_id.is_not(None),
                )
            )
        ).scalars()
    )


async def set_event_clubs(
    session: AsyncSession, event: Event, clubs: dict[int, Club], club_ids: list[int]
) -> None:
    """The event's field as an organizer lists it: a club as many teams as its id is
    listed (Story VA-13); a team taken away is the highest-numbered. A listed club's
    pending or rejected request is accepted. Any change clears the draw, and none is
    allowed once racing started (Story VA-8)."""
    wanted = Counter(club_ids)
    existing = await event_entries(session, event.id, accepted_only=False)
    keep = [team for team in existing if team.number <= wanted[team.club_id]]
    drop = [team for team in existing if team.number > wanted[team.club_id]]
    entered = {(team.club_id, team.number) for team in existing}
    add = [
        (club_id, number)
        for club_id, count in wanted.items()
        for number in range(1, count + 1)
        if (club_id, number) not in entered
    ]
    accept = [team for team in keep if team.status != TeamStatus.ACCEPTED]
    if not (drop or add or accept):
        return
    await field_changing(session, event.id)
    for team in accept:
        team.status = TeamStatus.ACCEPTED
    for team in drop:
        await session.delete(team)
    for club_id, number in add:
        await new_event_entry(session, event, clubs[club_id], number=number)


async def decide(
    session: AsyncSession, team: Team, status: TeamStatus, note: str | None, acting: User
) -> None:
    """An application decided (Story A-9). Accepting or revoking an entry in an event
    changes its field; revoking one with results is refused."""
    if team.status == TeamStatus.ACCEPTED and status != TeamStatus.ACCEPTED:
        if await has_results(session, team):
            raise Problem(
                409,
                "participation-has-results",
                "This participation cannot be revoked: race results already exist.",
            )
    if (team.status == TeamStatus.ACCEPTED) != (status == TeamStatus.ACCEPTED):
        await field_changing(session, team.event_id)
    previous = team.status
    team.status = status
    team.decision_note = note
    team.decided_at = datetime.now(UTC)
    # Who decided what and when must be auditable.
    audit(
        session,
        EntityType.TEAM,
        team.id,
        "decide_participation",
        acting,
        # "from" is a Python keyword, so this payload stays a mapping.
        **{"from": previous, "to": status, "note": note},
    )
