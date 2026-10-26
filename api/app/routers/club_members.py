"""Who is in a club — Stories Z-5, V-10, and #40.

Membership is an active ``ClubMembership`` (`docs/PLAN_PEOPLE.md`): a person, with or
without an account, in a club. The club's admin adds a person and removes one; the person
leaves by ending their own. What each member *is* to the club besides — admin, manager,
treasurer — stays a tuple on their account (`app/services/grants.py`). A person already in
another club joins only with consent (step 4 of the plan); until that exists, only the
league office adds them.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import authz
from app.auth import current_user
from app.db import get_session
from app.models import Club, ClubMembership, MembershipStatus, Person
from app.models.auth import ObjectType, Relation, User
from app.problems import Problem
from app.schemas.public import ClubMemberIn, ClubMemberOut
from app.services import grants, people
from app.services.audit import EntityType, audit
from app.services.lookup import get_or_404
from app.services.participation import connect_person

router = APIRouter(tags=["clubs"])


async def _roster(session: AsyncSession, club: Club) -> list[ClubMemberOut]:
    """The club's active members, each with what else their account is to the club."""
    persons = (
        await session.execute(
            select(Person)
            .join(ClubMembership, ClubMembership.person_id == Person.id)
            .where(
                ClubMembership.club_id == club.id,
                ClubMembership.status == MembershipStatus.ACTIVE,
            )
        )
    ).scalars()
    roles: dict[int, list[str]] = {}
    for row in await grants.grants_on(session, ObjectType.CLUB, club.id):
        roles.setdefault(row.user_id, []).append(row.relation)
    order = list(Relation).index
    members = []
    for person in persons:
        held = roles.get(person.user_id, []) if person.user_id is not None else []
        relations = sorted({Relation.MEMBER, *held}, key=order)
        members.append(
            ClubMemberOut(
                person_id=person.id,
                user_id=person.user_id,
                display_name=person.full_name,
                relations=relations,
                organizer=Relation.MANAGER in relations or Relation.ADMIN in relations,
                admin=Relation.ADMIN in relations,
            )
        )
    members.sort(key=lambda member: member.display_name)
    return members


@router.get(
    "/api/clubs/{club_id}/members",
    response_model=list[ClubMemberOut],
    summary="Who belongs to this club",
)
async def list_club_members(
    club_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> list[ClubMemberOut]:
    """Every active member, with what else they are to the club, so the organizers are
    recognizable. Display name only — contact data is the club admin's business (the
    People panel). Open to the club's own members and organizers and to staff; a
    stranger, or a member of a *different* club, gets 403.
    """
    club = await get_or_404(session, Club, club_id)
    if not authz.check(acting, Relation.ADMIN) and not authz.check(
        acting, Relation.MEMBER, Relation.MANAGER, on=club
    ):
        raise Problem(
            403,
            "club-members-restricted-to-members",
            "Only members and organizers of this club, or staff, can see its member list.",
        )
    return await _roster(session, club)


@router.post(
    "/api/clubs/{club_id}/members",
    response_model=ClubMemberOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a person to the club",
)
async def add_club_member(
    club_id: int,
    request: ClubMemberIn,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> ClubMemberOut:
    """Story Z-5: the club's admin adds a person — by the address on their record or on
    their account — and they are a member at once, nobody has to accept: the club knows
    who is in it. A person already in another club only the league office adds, until
    they can be asked (step 4 of `docs/PLAN_PEOPLE.md`)."""
    club = await get_or_404(session, Club, club_id)
    authz.ensure(
        acting,
        Relation.ADMIN,
        on=club,
        code="membership-forbidden",
        title="Only the club's admin adds people to the club.",
    )
    email = request.email.strip().lower()
    person = (
        await session.execute(select(Person).where(Person.email == email))
    ).scalar_one_or_none()
    if person is None:
        account = (
            await session.execute(
                select(User).options(selectinload(User.grants)).where(User.email == email)
            )
        ).scalar_one_or_none()
        if account is not None:
            person = await people.person_for(session, account)
    if person is None:
        raise Problem(
            404,
            "membership-address-unknown",
            "Nobody here has this address.",
            email=email,
        )
    if club.id in person.club_ids:
        raise Problem(409, "membership-exists", "This person is already in the club.")
    if person.club_ids and not authz.check(acting, Relation.ADMIN):
        raise Problem(
            409,
            "membership-needs-consent",
            "This person is in another club; the league office adds them to a second one.",
            person_id=person.id,
        )
    connect_person(person, club.id)
    audit(session, EntityType.PERSON, person.id, "join_club", acting, club_id=club.id)
    await session.commit()
    return next(m for m in await _roster(session, club) if m.person_id == person.id)


@router.delete(
    "/api/clubs/{club_id}/members/{person_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="End a membership",
)
async def remove_club_member(
    club_id: int,
    person_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> None:
    """Story Z-5: a member leaves — their own account ends their own membership — or the
    club's admin removes one. The roles their account holds on the club are tuples and
    stay; whoever removes a member removes those one by one."""
    club = await get_or_404(session, Club, club_id)
    person = await get_or_404(session, Person, person_id)
    leaving = person.user_id is not None and person.user_id == acting.id
    if not leaving:
        authz.ensure(
            acting,
            Relation.ADMIN,
            on=club,
            code="membership-forbidden",
            title="Only the club's admin removes someone from the club.",
        )
    links = [link for link in person.club_memberships if link.club_id == club.id]
    if not links:
        raise Problem(404, "membership-not-found", "This person is not in the club.")
    person.club_memberships = [link for link in person.club_memberships if link.club_id != club.id]
    audit(session, EntityType.PERSON, person.id, "leave_club", acting, club_id=club.id)
    await session.commit()
