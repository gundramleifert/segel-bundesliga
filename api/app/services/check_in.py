"""Checking a team in, gated by the liability waiver (Stories VA-2, VA-5).

The owner's decision on review 5.7 (2026-11-13): the waiver gates check-in. A crew may be
lined up while someone in it has not signed — a lineup is planned for weeks and changed
on the pontoon (V-2) — but the team checks in only once everyone in its named crew is
cleared. ``Team.checked_in_at`` is written here and nowhere else but
``lineup.set_lineup``, which clears it: checked in means *this* crew was cleared.

Who may check a team in is the router's question — whoever may set its lineup. Nothing
here commits.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event, EventCrew, Team, TeamStatus
from app.models.auth import User
from app.problems import Problem
from app.services.audit import EntityType, audit
from app.services.waivers import (
    UNREAD,
    WaiverStatus,
    WaiverText,
    _Unread,
    current_waiver_text,
    event_waiver_status,
)

#: A status that lets a sailor through the gate. ``not_required``: no text is published.
CLEARED = frozenset({WaiverStatus.CLEARED, WaiverStatus.NOT_REQUIRED})


@dataclass(frozen=True)
class TeamCheckIn:
    """One entered team on the check-in list."""

    team_id: int
    name: str
    checked_in_at: datetime | None
    crew: int
    not_cleared: list[int]


async def _crews(session: AsyncSession, event_id: int) -> dict[int, list[int]]:
    rows = await session.execute(
        select(EventCrew.team_id, EventCrew.person_id)
        .where(EventCrew.event_id == event_id)
        .order_by(EventCrew.person_id)
    )
    crews: dict[int, list[int]] = {}
    for team_id, person_id in rows.all():
        crews.setdefault(team_id, []).append(person_id)
    return crews


async def _not_cleared(
    session: AsyncSession,
    event: Event,
    person_ids: list[int],
    required: WaiverText | None | _Unread = UNREAD,
) -> list[int]:
    status = await event_waiver_status(session, event, person_ids, required)
    return [pid for pid in person_ids if status[pid].status not in CLEARED]


async def teams(session: AsyncSession, event: Event) -> list[TeamCheckIn]:
    """Every accepted entry of the event, checked in or not, with how many of its crew
    are not cleared — the check-in list's team half."""
    entries = (
        await session.execute(
            select(Team)
            .where(Team.event_id == event.id, Team.status == TeamStatus.ACCEPTED)
            .order_by(Team.name, Team.number)
        )
    ).scalars()
    crews = await _crews(session, event.id)
    required = await current_waiver_text(session)
    everyone = sorted({pid for crew in crews.values() for pid in crew})
    blocked = set(await _not_cleared(session, event, everyone, required))
    return [
        TeamCheckIn(
            team_id=team.id,
            name=team.name,
            checked_in_at=team.checked_in_at,
            crew=len(crews.get(team.id, [])),
            not_cleared=[pid for pid in crews.get(team.id, []) if pid in blocked],
        )
        for team in entries
    ]


async def check_in(session: AsyncSession, event: Event, team: Team, actor: User) -> None:
    """Checks the entry in — refused while no crew is named, or anyone in it is not
    cleared (named in ``person_ids``)."""
    crew = (await _crews(session, event.id)).get(team.id, [])
    if not crew:
        raise Problem(409, "crew-missing", "Name the crew before checking the team in.")
    missing = await _not_cleared(session, event, crew)
    if missing:
        raise Problem(
            409,
            "crew-waiver-missing",
            "Everyone in the crew must have cleared the liability waiver first.",
            person_ids=missing,
        )
    team.checked_in_at = datetime.now(UTC)
    audit(session, EntityType.TEAM, team.id, "check_in", actor, event_id=event.id)


def undo(session: AsyncSession, team: Team, actor: User) -> None:
    """Takes the check-in back — a mistake on the dock, or a crew about to change."""
    team.checked_in_at = None
    audit(session, EntityType.TEAM, team.id, "check_in_undone", actor, event_id=team.event_id)
