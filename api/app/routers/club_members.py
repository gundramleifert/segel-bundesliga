"""Who is in a club — Stories Z-5, V-10, V-15, and #40.

Membership is a ``ClubMembership`` of a person (`docs/PLAN_PEOPLE.md`): a person, with or
without an account, in a club — ``active``, or waiting for the other side. The club's
admin adds a person in no club at once; a person **already in another club** joins only
with consent, either way round (V-15): the club invites (``invited``) and the person
accepts, or the person asks (``requested``) and the club's admin accepts. Either side
ends any of it — declines, withdraws, leaves, removes — by deleting the row. What each
member *is* to the club besides — admin, manager, treasurer — stays a tuple on their
account (`app/services/grants.py`).

Two halves: the club's (`/api/clubs/{id}/members`) and the person's
(`/api/me/memberships`), each changing a row only as its own side may.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import authz
from app.auth import current_user
from app.db import get_session
from app.filters import ClubPersonFilter
from app.listing import ListDepends
from app.models import Club, ClubMembership, MembershipStatus, Person
from app.models.auth import Grant, ObjectType, Relation, User
from app.pagination import Page, PageInput, PageParams, page_of, paginate
from app.problems import Problem
from app.schemas.public import ClubMemberIn, ClubMemberOut, ClubPersonOut
from app.services import grants, people
from app.services.audit import EntityType, audit
from app.services.contexts import require_linked_person
from app.services.lookup import get_or_404
from app.services.participation import connect_person
from app.services.waivers import is_minor

router = APIRouter(tags=["clubs"])


async def _roster(
    session: AsyncSession, club: Club, *, pending: bool = False
) -> list[ClubMemberOut]:
    """The club's active members, each with what else their account is to the club — and
    with ``pending``, the invitations and requests too (the club's admin's view)."""
    statuses = list(MembershipStatus) if pending else [MembershipStatus.ACTIVE]
    rows = (
        await session.execute(
            select(Person, ClubMembership.status)
            .join(ClubMembership, ClubMembership.person_id == Person.id)
            .where(ClubMembership.club_id == club.id, ClubMembership.status.in_(statuses))
        )
    ).all()
    roles: dict[int, list[str]] = {}
    for row in await grants.grants_on(session, ObjectType.CLUB, club.id):
        roles.setdefault(row.user_id, []).append(row.relation)
    order = list(Relation).index
    members = []
    for person, standing in rows:
        held = roles.get(person.user_id, []) if person.user_id is not None else []
        active = standing == MembershipStatus.ACTIVE
        relations = sorted({Relation.MEMBER, *held} if active else set(held), key=order)
        members.append(
            ClubMemberOut(
                person_id=person.id,
                user_id=person.user_id,
                display_name=person.full_name,
                status=standing,
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
    stranger, or a member of a *different* club, gets 403. The club's admin also sees
    the invitations and requests waiting (Story V-15), each with its ``status``.
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
    return await _roster(session, club, pending=authz.check(acting, Relation.ADMIN, on=club))


@router.get(
    "/api/clubs/{club_id}/people",
    response_model=Page[ClubPersonOut],
    summary="The club's people",
)
async def list_club_people(
    club_id: int,
    filters: ClubPersonFilter = ListDepends(ClubPersonFilter),
    params: PageParams = PageInput,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> Page[ClubPersonOut]:
    """*Club › People* (#45, `docs/PLAN_PEOPLE.md` §4): one page of the club's people,
    searched, filtered and sorted on the server (Story A-13).

    The club's organizers — and the site's admin — see everyone with a row here, the
    invitations and requests too, and everyone whose account holds a role on the club
    without being a member (``status`` empty: organizers often never sail), with address
    and date of birth. A plain member sees
    the roster (Story V-10): the active members, by name, account and role — no address,
    no date of birth, and so no filter on either (`club-people-filter-forbidden`).
    """
    club = await get_or_404(session, Club, club_id)
    organizer = authz.check(acting, Relation.ADMIN, Relation.MANAGER, on=club)
    if not organizer and not authz.check(acting, Relation.MEMBER, on=club):
        raise Problem(
            403,
            "club-members-restricted-to-members",
            "Only members and organizers of this club, or staff, can see its people.",
        )
    if not organizer and (
        filters.minor is not None
        or filters.no_birth_date is not None
        or filters.status not in (None, MembershipStatus.ACTIVE)
    ):
        raise Problem(
            403,
            "club-people-filter-forbidden",
            "Dates of birth and waiting rows are the club's organizers' to filter by.",
        )
    holders = select(Grant.user_id).where(Grant.club_id == club.id)
    stmt = select(Person).outerjoin(
        ClubMembership,
        and_(ClubMembership.person_id == Person.id, ClubMembership.club_id == club.id),
    )
    if organizer:
        stmt = stmt.where(or_(ClubMembership.id.is_not(None), Person.user_id.in_(holders)))
    else:
        stmt = stmt.where(ClubMembership.status == MembershipStatus.ACTIVE)
    filters.for_club(club.id)
    persons, total = await paginate(session, filters.sort(filters.filter(stmt)), params)
    roles: dict[int, list[str]] = {}
    for grant in await grants.grants_on(session, ObjectType.CLUB, club.id):
        roles.setdefault(grant.user_id, []).append(grant.relation)
    order = list(Relation).index
    today = date.today()
    return page_of(
        [
            ClubPersonOut(
                person_id=person.id,
                user_id=person.user_id,
                first_name=person.first_name,
                last_name=person.last_name,
                status=row.status if (row := _row(person, club.id)) else None,
                roles=sorted(roles.get(person.user_id, []), key=order)
                if person.user_id is not None
                else [],
                email=person.email if organizer else None,
                birth_date=person.birth_date if organizer else None,
                minor=is_minor(person.birth_date, today) if organizer else None,
            )
            for person in persons
        ],
        total,
        params,
    )


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
    their account. Someone in no club is a member at once, nobody has to accept: the club
    knows who is in it. Someone **already in another club** is invited (Story V-15) and
    becomes a member when they accept — or at once if they had asked to join. Someone in
    another club without an account could not accept: the league office adds them."""
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
    row = _row(person, club.id)
    if row is not None and row.status != MembershipStatus.REQUESTED:
        raise Problem(
            409,
            "membership-exists",
            "This person is already in the club, or invited.",
            membership_status=row.status,
        )
    others = [c for c in person.club_ids if c != club.id]
    if row is not None or not others or authz.check(acting, Relation.ADMIN):
        # Asked themselves, in no club, or the league office: a member now.
        connect_person(person, club.id)
        audit(session, EntityType.PERSON, person.id, "join_club", acting, club_id=club.id)
    elif person.user_id is None:
        raise Problem(
            409,
            "membership-needs-league-office",
            "This person is in another club and has no account to accept an invitation; "
            "the league office adds them.",
            person_id=person.id,
        )
    else:
        person.club_memberships.append(
            ClubMembership(club_id=club.id, status=MembershipStatus.INVITED)
        )
        audit(session, EntityType.PERSON, person.id, "invite", acting, club_id=club.id)
    await session.commit()
    roster = await _roster(session, club, pending=True)
    return next(m for m in roster if m.person_id == person.id)


@router.post(
    "/api/clubs/{club_id}/members/{person_id}/accept",
    response_model=ClubMemberOut,
    summary="Accept a request to join",
)
async def accept_club_member(
    club_id: int,
    person_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> ClubMemberOut:
    """Story V-15: the club's admin accepts a person's request — a member now."""
    club = await get_or_404(session, Club, club_id)
    authz.ensure(
        acting,
        Relation.ADMIN,
        on=club,
        code="membership-forbidden",
        title="Only the club's admin accepts a request to join.",
    )
    person = await get_or_404(session, Person, person_id)
    row = _row(person, club.id)
    if row is None or row.status != MembershipStatus.REQUESTED:
        raise Problem(404, "membership-request-not-found", "This person has not asked to join.")
    row.status = MembershipStatus.ACTIVE
    audit(session, EntityType.PERSON, person.id, "accept", acting, club_id=club.id)
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
    club's admin removes one; the same for an invitation or a request (V-15): withdrawn
    or declined by either side, the row is gone. The roles their account holds on the
    club are tuples and stay; whoever removes a member removes those one by one."""
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
    _end(person, club.id, acting, session)
    await session.commit()


def _row(person: Person, club_id: int) -> ClubMembership | None:
    """The person's row for this club, whatever its status."""
    return next((link for link in person.club_memberships if link.club_id == club_id), None)


def _end(person: Person, club_id: int, acting: User, session: AsyncSession) -> None:
    """Deletes the person's row for the club — leaving, removing, declining, withdrawing."""
    row = _row(person, club_id)
    if row is None:
        raise Problem(404, "membership-not-found", "This person is not in the club.")
    person.club_memberships = [link for link in person.club_memberships if link is not row]
    audit(
        session, EntityType.PERSON, person.id, "end_membership", acting,
        club_id=club_id, status=row.status,
    )  # fmt: skip


# ---------------------------------------------------------------- the person's side


class MyMembershipOut(BaseModel):
    """One club I am in, invited to, or asked to join (Story V-15)."""

    club_id: int
    club_name: str
    club_short_name: str
    status: MembershipStatus


class MembershipAsk(BaseModel):
    """Which club I ask to join."""

    club_id: int = Field(description="The club to ask.")


me_router = APIRouter(prefix="/api/me/memberships", tags=["clubs"])


async def _mine(session: AsyncSession, person: Person) -> list[MyMembershipOut]:
    clubs = {
        club.id: club
        for club in (
            await session.execute(
                select(Club).where(Club.id.in_([m.club_id for m in person.club_memberships]))
            )
        ).scalars()
    }
    order = list(MembershipStatus).index
    return sorted(
        (
            MyMembershipOut(
                club_id=m.club_id,
                club_name=clubs[m.club_id].name,
                club_short_name=clubs[m.club_id].short_name,
                status=m.status,
            )
            for m in person.club_memberships
        ),
        key=lambda m: (order(m.status), m.club_name),
    )


@me_router.get("", response_model=list[MyMembershipOut], summary="My clubs")
async def list_my_memberships(
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> list[MyMembershipOut]:
    """Story V-15: my memberships, the invitations to answer and my open requests —
    *Me › My clubs*."""
    return await _mine(session, await require_linked_person(session, acting))


@me_router.post(
    "",
    response_model=list[MyMembershipOut],
    status_code=status.HTTP_201_CREATED,
    summary="Ask to join a club",
)
async def ask_to_join(
    request: MembershipAsk,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> list[MyMembershipOut]:
    """Story V-15: I ask to join a club; its admin accepts or declines. Asking where I am
    invited accepts the invitation. Only from a verified address (Story Z-4): an address
    merely typed at registration proves nobody."""
    if not acting.email_verified:
        raise Problem(
            403, "membership-unverified", "Confirm your address before asking to join a club."
        )
    club = await get_or_404(session, Club, request.club_id)
    person = await require_linked_person(session, acting)
    row = _row(person, club.id)
    if row is not None and row.status != MembershipStatus.INVITED:
        raise Problem(
            409,
            "membership-exists",
            "You are in this club, or have asked.",
            membership_status=row.status,
        )
    if row is not None:
        row.status = MembershipStatus.ACTIVE
        audit(session, EntityType.PERSON, person.id, "accept", acting, club_id=club.id)
    else:
        person.club_memberships.append(
            ClubMembership(club_id=club.id, status=MembershipStatus.REQUESTED)
        )
        audit(session, EntityType.PERSON, person.id, "ask", acting, club_id=club.id)
    await session.commit()
    return await _mine(session, person)


@me_router.post(
    "/{club_id}/accept", response_model=list[MyMembershipOut], summary="Accept an invitation"
)
async def accept_invitation(
    club_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> list[MyMembershipOut]:
    """Story V-15: I accept a club's invitation — a member now."""
    person = await require_linked_person(session, acting)
    row = _row(person, club_id)
    if row is None or row.status != MembershipStatus.INVITED:
        raise Problem(
            404, "membership-invitation-not-found", "There is no invitation from this club."
        )
    row.status = MembershipStatus.ACTIVE
    audit(session, EntityType.PERSON, person.id, "accept", acting, club_id=club_id)
    await session.commit()
    return await _mine(session, person)


@me_router.delete(
    "/{club_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Leave, decline or withdraw"
)
async def end_my_membership(
    club_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> None:
    """Story V-15: I leave a club, decline its invitation or withdraw my request — the
    row is gone either way."""
    person = await require_linked_person(session, acting)
    _end(person, club_id, acting, session)
    await session.commit()
