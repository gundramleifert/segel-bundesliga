"""Lineup for a matchday — Story V-2.

The rule here: a club registers **X people for the league** (season squad, ``TeamMembership``).
For a matchday, it selects the **crew** from those (``EventCrew``). Anyone not in the squad
cannot be lined up — this endpoint enforces that, rather than relying on the UI only
offering suitable names.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user
from app.db import get_session
from app.i18n import Locale, resolve_locale, tr
from app.models import Event, EventCrew, Sailor, Team, TeamMembership, TeamStatus
from app.models.auth import Role, User
from app.models.org import CrewRole
from app.schemas.public import MemberOut
from app.services import TeilnahmeFehler, antritt, kader_mannschaft

router = APIRouter(prefix="/api/admin/events", tags=["administration"])


class CrewMember(BaseModel):
    sailor_id: int
    role: CrewRole = CrewRole.CREW


class SetCrewRequest(BaseModel):
    team_id: int = Field(
        description=(
            "Club team. Can be either the series registration or the entry to this event — "
            "lineup is always at the event entry."
        )
    )
    members: list[CrewMember] = Field(
        description="The lined-up crew. An empty list clears the lineup."
    )


class CrewOut(BaseModel):
    event_slug: str
    team_id: int
    # The typical size for this matchday — a guide for the UI, not a hard limit.
    crew_size: int
    members: list[MemberOut] = Field(default_factory=list)


@router.get("/{event_id}/crew/{team_id}", response_model=CrewOut, summary="View lineup")
async def get_crew(
    event_id: int, team_id: int, session: AsyncSession = Depends(get_session)
) -> CrewOut:
    event = await _event(session, event_id)
    return await _crew_out(session, event, (await _participation(session, event, team_id)).id)


@router.put("/{event_id}/crew", response_model=CrewOut, summary="Set lineup")
async def set_crew(
    event_id: int,
    request: SetCrewRequest,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
    locale: Locale = Depends(resolve_locale),
) -> CrewOut:
    """Lines up a club's crew for this matchday.

    The lined-up people **must come from the squad** of the same team — this is the rule
    enforced here.

    The **number** is otherwise free. ``Event.crew_size`` says how many typically sail this
    matchday, and the UI can use that as a guide; it is not enforced. Illness, late
    registration, and non-standard formats would not work otherwise.

    A club official can only line up their own team; administration and race officers can
    intervene everywhere — on event day, someone must be able to make changes on short notice.
    """
    event = await _event(session, event_id)
    team = await _participation(session, event, request.team_id)

    _check_permissions(acting, team)

    desired = {member.sailor_id: member.role for member in request.members}
    if len(desired) != len(request.members):
        raise HTTPException(
            status_code=422,
            detail=tr(
                locale,
                en="A person is lined up twice.",
                de="Eine Person ist doppelt aufgestellt.",
            ),
        )

    if desired:
        try:
            squad = await kader_mannschaft(session, team)
        except TeilnahmeFehler as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        await _from_squad(session, squad.id, set(desired))
        await _not_elsewhere_lined_up(session, event.id, team.id, set(desired))

    await session.execute(
        delete(EventCrew).where(
            EventCrew.event_id == event.id, EventCrew.team_id == team.id
        )
    )
    session.add_all(
        EventCrew(event_id=event.id, team_id=team.id, sailor_id=sailor_id, role=role)
        for sailor_id, role in desired.items()
    )
    await session.commit()
    return await _crew_out(session, event, team.id)


# ------------------------------------------------------------------ Helpers


async def _event(session: AsyncSession, event_id: int) -> Event:
    event = (
        await session.execute(select(Event).where(Event.id == event_id))
    ).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail=f"Matchday {event_id} not found")
    return event


async def _participation(session: AsyncSession, event: Event, team_id: int) -> Team:
    """The club's entry to **this** event.

    Lineup is always at the entry, not at the series registration — the lineup applies to
    one matchday. Either can be specified: the club is what matters.
    """
    team = (
        await session.execute(select(Team).where(Team.id == team_id))
    ).scalar_one_or_none()
    if team is None:
        raise HTTPException(status_code=404, detail="This team does not exist.")

    found = await antritt(session, event.id, team.club_id)
    if found is None or found.status != TeamStatus.ACCEPTED:
        raise HTTPException(
            status_code=422,
            detail="This club does not participate in this event.",
        )
    return found


def _check_permissions(acting: User, team: Team) -> None:
    if acting.has_any(Role.ADMIN, Role.RACE_OFFICER):
        return
    if not acting.has_any(Role.CLUB_MANAGER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Lineup can be set by club officials, administration, and race officers.",
        )
    if acting.club_id != team.club_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only line up your own team.",
        )


async def _from_squad(
    session: AsyncSession, team_id: int, sailor_ids: set[int]
) -> None:
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
            select(Sailor.id, Sailor.first_name, Sailor.last_name).where(
                Sailor.id.in_(external)
            )
        )
    ).all()
    name_list = ", ".join(f"{first} {last}" for _, first, last in names)
    description = name_list or ", ".join(map(str, external))
    raise HTTPException(
        status_code=422,
        detail=(
            f"Not in this team's squad: {description}. "
            "Register first, then line up."
        ),
    )


async def _not_elsewhere_lined_up(
    session: AsyncSession, event_id: int, team_id: int, sailor_ids: set[int]
) -> None:
    """No one sails for two teams in a single matchday."""
    duplicates = (
        await session.execute(
            select(EventCrew.sailor_id).where(
                EventCrew.event_id == event_id,
                EventCrew.team_id != team_id,
                EventCrew.sailor_id.in_(sailor_ids),
            )
        )
    ).scalars().all()
    if duplicates:
        raise HTTPException(
            status_code=409,
            detail=(
                "This person is already lined up for another team in this matchday."
            ),
        )


async def _crew_out(session: AsyncSession, event: Event, team_id: int) -> CrewOut:
    rows = (
        await session.execute(
            select(EventCrew, Sailor)
            .join(Sailor, EventCrew.sailor_id == Sailor.id)
            .where(EventCrew.event_id == event.id, EventCrew.team_id == team_id)
        )
    ).all()
    order = {CrewRole.HELM: 0, CrewRole.CREW: 1, CrewRole.SUBSTITUTE: 2}
    members = sorted(
        (
            MemberOut(
                id=sailor.id,
                first_name=sailor.first_name,
                last_name=sailor.last_name,
                role=crew.role,
            )
            for crew, sailor in rows
        ),
        key=lambda m: (order.get(m.role, 9), m.last_name, m.first_name),
    )
    return CrewOut(
        event_slug=event.slug,
        team_id=team_id,
        crew_size=event.crew_size,
        members=members,
    )
