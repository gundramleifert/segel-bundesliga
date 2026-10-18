"""Lineup for a matchday — Story V-2.

The rule — only the squad can be lined up, nobody for two teams — lives in
``app/services/lineup.py``; this router answers who may set a lineup and maps the rule's
refusals to responses.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import authz
from app.auth import current_user
from app.authz import ObjectRef
from app.db import get_session
from app.i18n import Locale, resolve_locale, tr
from app.models import Event, EventCrew, Sailor, Team, TeamStatus
from app.models.auth import ObjectType, Relation, User
from app.models.org import CrewRole
from app.schemas.public import MemberOut
from app.services import event_entry
from app.services.lineup import LineupError, LineupMember, LineupRefusal, set_lineup
from app.services.lookup import get_or_404

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
    event = await get_or_404(session, Event, event_id)
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
    event = await get_or_404(session, Event, event_id)
    team = await _participation(session, event, request.team_id)

    _check_permissions(acting, team, event)

    try:
        await set_lineup(
            session,
            event.id,
            team,
            [LineupMember(member.sailor_id, member.role) for member in request.members],
        )
    except LineupError as error:
        detail = error.message
        if error.reason is LineupRefusal.LINED_UP_TWICE:
            detail = tr(locale, en=error.message, de="Eine Person ist doppelt aufgestellt.")
        raise HTTPException(status_code=error.status, detail=detail) from error

    await session.commit()
    return await _crew_out(session, event, team.id)


# ------------------------------------------------------------------ Helpers


async def _participation(session: AsyncSession, event: Event, team_id: int) -> Team:
    """The club's entry to **this** event.

    Lineup is always at the entry, not at the series registration — the lineup applies to
    one matchday. Either can be specified: the club is what matters.
    """
    team = await get_or_404(session, Team, team_id)

    found = await event_entry(session, event.id, team.club_id)
    if found is None or found.status != TeamStatus.ACCEPTED:
        raise HTTPException(
            status_code=422,
            detail="This club does not participate in this event.",
        )
    return found


def _check_permissions(acting: User, team: Team, event: Event) -> None:
    # The event's organizer and race committee — held on the event, its series, its host
    # club or the site (Story Z-2) — may line up a crew; one for a different event may not.
    if authz.check(acting, Relation.MANAGER, Relation.RACE_OFFICER, on=event):
        return
    if authz.check(acting, Relation.MANAGER, on=ObjectRef(ObjectType.CLUB, team.club_id)):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "You can only line up your own team."
            if authz.list_objects(acting, Relation.MANAGER, ObjectType.CLUB)
            else "Lineup can be set by club officials, administration, and race officers."
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
        key=MemberOut.announce_order,
    )
    return CrewOut(
        event_slug=event.slug,
        team_id=team_id,
        crew_size=event.crew_size,
        members=members,
    )
