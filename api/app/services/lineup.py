"""A club's lineup for one matchday — Story V-2.

The rule: a club registers **X people for the league** (the squad, ``TeamMembership``), and
for a matchday it picks the **crew** from those (``EventCrew``). Anyone not in the squad
cannot be lined up, and nobody sails for two teams on one matchday — enforced here rather
than relied on because the UI only offers suitable names.

The **number** is free: ``Event.crew_size`` is guidance, not a limit — illness, late
registration and non-standard formats would not work otherwise.

Who may line up is the router's question (``app/routers/crew.py``); this module answers
whether *these people* may sail for *this team*. Nothing here commits.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from typing import NamedTuple

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EventCrew, Sailor, Team, TeamMembership
from app.models.org import CrewRole
from app.services.participation import ParticipationError, squad_team


class LineupMember(NamedTuple):
    sailor_id: int
    role: CrewRole = CrewRole.CREW


class LineupRefusal(StrEnum):
    """Why a lineup was refused — the router words it."""

    LINED_UP_TWICE = "lined-up-twice"
    NO_SQUAD = "no-squad"
    NOT_IN_SQUAD = "not-in-squad"
    ELSEWHERE_LINED_UP = "elsewhere-lined-up"


class LineupError(Exception):
    """A lineup that breaks the rules; ``status`` is the HTTP status it answers with."""

    def __init__(self, reason: LineupRefusal, status: int, message: str) -> None:
        self.reason = reason
        self.status = status
        self.message = message
        super().__init__(message)


async def set_lineup(
    session: AsyncSession, event_id: int, team: Team, members: Sequence[LineupMember]
) -> None:
    """Replace ``team``'s crew for this event with ``members``; an empty list clears it.

    ``team`` is the club's entry to this event. The squad checked against is the club's
    series registration for an act, the entry itself for a standalone event
    (``squad_team``).
    """
    desired = {member.sailor_id: member.role for member in members}
    if len(desired) != len(members):
        raise LineupError(LineupRefusal.LINED_UP_TWICE, 422, "A person is lined up twice.")

    if desired:
        try:
            squad = await squad_team(session, team)
        except ParticipationError as error:
            raise LineupError(LineupRefusal.NO_SQUAD, 422, str(error)) from error
        await _from_squad(session, squad.id, set(desired))
        await _not_elsewhere_lined_up(session, event_id, team.id, set(desired))

    await session.execute(
        delete(EventCrew).where(EventCrew.event_id == event_id, EventCrew.team_id == team.id)
    )
    session.add_all(
        EventCrew(event_id=event_id, team_id=team.id, sailor_id=sailor_id, role=role)
        for sailor_id, role in desired.items()
    )


async def _from_squad(session: AsyncSession, team_id: int, sailor_ids: set[int]) -> None:
    """The core of the rule: only those registered for the series can be lined up.

    ``team_id`` is the team with the squad — for an act, the club's series registration,
    for a standalone event, the event entry itself.
    """
    in_squad = set(
        (
            await session.execute(
                select(TeamMembership.sailor_id).where(
                    TeamMembership.team_id == team_id,
                    TeamMembership.sailor_id.in_(sailor_ids),
                )
            )
        ).scalars()
    )
    external = sailor_ids - in_squad
    if not external:
        return

    names = (
        await session.execute(
            select(Sailor.id, Sailor.first_name, Sailor.last_name).where(Sailor.id.in_(external))
        )
    ).all()
    name_list = ", ".join(f"{first} {last}" for _, first, last in names)
    description = name_list or ", ".join(map(str, external))
    raise LineupError(
        LineupRefusal.NOT_IN_SQUAD,
        422,
        f"Not in this team's squad: {description}. Register first, then line up.",
    )


async def _not_elsewhere_lined_up(
    session: AsyncSession, event_id: int, team_id: int, sailor_ids: set[int]
) -> None:
    """No one sails for two teams in a single matchday."""
    duplicates = (
        (
            await session.execute(
                select(EventCrew.sailor_id).where(
                    EventCrew.event_id == event_id,
                    EventCrew.team_id != team_id,
                    EventCrew.sailor_id.in_(sailor_ids),
                )
            )
        )
        .scalars()
        .all()
    )
    if duplicates:
        raise LineupError(
            LineupRefusal.ELSEWHERE_LINED_UP,
            409,
            "This person is already lined up for another team in this matchday.",
        )
