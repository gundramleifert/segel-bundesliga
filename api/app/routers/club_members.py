"""Club membership — Stories Z-5, V-8, and V-9.

Membership can be created in two ways, and **both require consent from the other side**:

* The person applies (``POST /api/club-memberships``) — the club leadership accepts.
* The club invites (``POST /api/admin/clubs/{id}/members``) — the person accepts.

This differs from participation in a series or event: there admin can assign unilaterally
because they run the competition, and only the reverse path needs consent. Here two equal
parties face each other — no one becomes a member without being asked, and no club gets
members without asking.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import current_user
from app.db import get_session
from app.i18n import Locale, resolve_locale, tr
from app.models import AuditLog, Club, ClubMember, ClubMemberStatus
from app.models.auth import Role, User, UserRole
from app.schemas.public import ClubOut

router = APIRouter(tags=["membership"])


class MembershipRequest(BaseModel):
    club_id: int


class MembershipInvitation(BaseModel):
    email: EmailStr = Field(description="Email address of the account to be admitted")


class MembershipDecision(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class MembershipOut(BaseModel):
    id: int
    status: str
    decision_note: str | None = None
    club: ClubOut
    user_id: int
    display_name: str
    email: str
    # Who is next in line — the UI should not have to guess.
    waiting_for: str | None = None
    # Whether this member also organizes the club (holds `club_manager` for it). Only
    # meaningful once the membership is active.
    organizer: bool = False


def _format_membership(row: ClubMember) -> MembershipOut:
    """Format a membership record for API response."""
    return MembershipOut(
        id=row.id,
        status=row.status,
        decision_note=row.decision_note,
        club=ClubOut.model_validate(row.club),
        user_id=row.user_id,
        display_name=row.user.display_name,
        email=row.user.email,
        waiting_for=(
            "club"
            if row.status == ClubMemberStatus.PENDING_CLUB
            else "user"
            if row.status == ClubMemberStatus.PENDING_USER
            else None
        ),
        organizer=row.user.club_id == row.club_id and row.user.has_any(Role.CLUB_MANAGER),
    )


@router.post(
    "/api/club-memberships",
    response_model=MembershipOut,
    status_code=status.HTTP_201_CREATED,
    summary="Request club membership",
)
async def request_membership(
    request: MembershipRequest,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
    locale: Locale = Depends(resolve_locale),
) -> MembershipOut:
    """Requests membership from a club. Only the club's acceptance makes it a membership."""
    if not acting.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=tr(
                locale,
                (
                    "Please verify your email address first — using the code sent"
                    " during registration."
                ),
                (
                    "Bitte zuerst die E-Mail-Adresse bestätigen — mit dem Code,"
                    " der bei der Registrierung verschickt wurde."
                ),
            ),
        )

    club = await _get_club(session, request.club_id, locale)
    row = await _get_existing_membership(session, club.id, acting.id)

    if row is None:
        row = ClubMember(
            club_id=club.id, user_id=acting.id, status=ClubMemberStatus.PENDING_CLUB
        )
        session.add(row)
    elif row.status == ClubMemberStatus.REJECTED:
        # A new attempt after rejection is allowed.
        row.status = ClubMemberStatus.PENDING_CLUB
        row.decision_note = None
        row.decided_at = None
    elif row.status == ClubMemberStatus.PENDING_USER:
        # The club had already invited — this request is acceptance.
        await _activate_membership(session, row, acting)
    else:
        raise HTTPException(
            status_code=409,
            detail=tr(
                locale,
                f"Something already exists for this club (status: {row.status}).",
                f"Für diesen Verein liegt bereits etwas vor (Stand: {row.status}).",
            ),
        )

    await session.commit()
    return _format_membership(await _load_with_relations(session, row.id))


@router.get(
    "/api/club-memberships",
    response_model=list[MembershipOut],
    summary="Own memberships",
)
async def list_own_memberships(
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> list[MembershipOut]:
    """Pending applications, invitations, and active memberships.

    A person can belong to multiple clubs.
    """
    rows = (
        await session.execute(
            _with_relations(select(ClubMember).where(ClubMember.user_id == acting.id))
            .order_by(ClubMember.id)
        )
    ).scalars()
    return [_format_membership(row) for row in rows]


@router.post(
    "/api/club-memberships/{membership_id}/accept",
    response_model=MembershipOut,
    summary="Accept",
)
async def accept_membership(
    membership_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
    locale: Locale = Depends(resolve_locale),
) -> MembershipOut:
    """Accepts membership — only from the side whose turn it is.

    Those who applied cannot accept themselves; those who invited cannot accept on behalf
    of the other.
    """
    row = await _load_with_relations(session, membership_id, locale)
    _check_authorization_to_decide(acting, row, locale)
    await _activate_membership(session, row, acting)
    await session.commit()
    return _format_membership(await _load_with_relations(session, row.id))


@router.post(
    "/api/club-memberships/{membership_id}/reject",
    response_model=MembershipOut,
    summary="Reject",
)
async def reject_membership(
    membership_id: int,
    request: MembershipDecision | None = None,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
    locale: Locale = Depends(resolve_locale),
) -> MembershipOut:
    """Rejects a membership request or invitation."""
    row = await _load_with_relations(session, membership_id, locale)
    _check_authorization_to_decide(acting, row, locale)

    previous = row.status
    row.status = ClubMemberStatus.REJECTED
    row.decision_note = request.note if request else None
    row.decided_at = datetime.now(UTC)
    _log_decision(session, row, previous, acting)

    await session.commit()
    return _format_membership(await _load_with_relations(session, row.id))


@router.delete(
    "/api/club-memberships/{membership_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Withdraw or leave",
)
async def withdraw_membership(
    membership_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
    locale: Locale = Depends(resolve_locale),
) -> None:
    """Both sides can dissolve what they initiated — and end a membership."""
    row = await _load_with_relations(session, membership_id)
    if not _is_the_user(acting, row) and not _is_club_leadership(acting, row):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=tr(
                locale,
                "This is neither your membership nor your club.",
                "Das ist weder Ihre Mitgliedschaft noch Ihr Verein.",
            ),
        )

    if row.user.club_id == row.club_id:
        row.user.club_id = None
    await session.delete(row)
    await session.commit()


@router.get(
    "/api/admin/clubs/{club_id}/members",
    response_model=list[MembershipOut],
    summary="Club members",
)
async def list_club_members(
    club_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
    locale: Locale = Depends(resolve_locale),
) -> list[MembershipOut]:
    """Includes pending requests — the club must see what it's deciding on."""
    club = await _get_club(session, club_id, locale)
    _check_club_leadership(acting, club.id, locale)
    rows = (
        await session.execute(
            _with_relations(select(ClubMember).where(ClubMember.club_id == club.id))
            .order_by(ClubMember.id)
        )
    ).scalars()
    return [_format_membership(row) for row in rows]


@router.post(
    "/api/admin/clubs/{club_id}/members/{user_id}/organizer",
    response_model=MembershipOut,
    summary="Make a member an organizer",
)
async def grant_organizer(
    club_id: int,
    user_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
    locale: Locale = Depends(resolve_locale),
) -> MembershipOut:
    """An organizer can appoint further organizers for their own club — Story A-8.

    Grants `club_manager` to an active member. A person only ever organizes **one**
    club (`User.club_id`), so this fails if they already organize a different one.
    """
    club = await _get_club(session, club_id, locale)
    _check_club_leadership(acting, club.id, locale)
    row = await _active_membership(session, club.id, user_id, locale)

    target = row.user
    if target.club_id is not None and target.club_id != club.id:
        raise HTTPException(
            status_code=409,
            detail=tr(
                locale,
                en="This person already organizes a different club.",
                de="Diese Person leitet bereits einen anderen Verein.",
            ),
        )

    if not target.has_any(Role.CLUB_MANAGER):
        # Change the collection, not a bare INSERT — otherwise the in-memory user still
        # looks role-less to the response we build below (expire_on_commit is off).
        target.role_rows.append(UserRole(role=Role.CLUB_MANAGER))
    target.club_id = club.id
    session.add(
        AuditLog(
            entity_type="user",
            entity_id=target.id,
            action="grant_organizer",
            actor=acting.email,
            payload={"club_id": club.id},
        )
    )
    await session.commit()
    return _format_membership(await _load_with_relations(session, row.id))


@router.delete(
    "/api/admin/clubs/{club_id}/members/{user_id}/organizer",
    response_model=MembershipOut,
    summary="Revoke organizer status",
)
async def revoke_organizer(
    club_id: int,
    user_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
    locale: Locale = Depends(resolve_locale),
) -> MembershipOut:
    """Revokes `club_manager` for this club — but **at least one organizer must remain**.

    A club with no organizer left could no longer manage its own squad or members, so
    the last one can't step down (or be stepped down) until someone else has taken over.
    """
    club = await _get_club(session, club_id, locale)
    _check_club_leadership(acting, club.id, locale)
    row = await _active_membership(session, club.id, user_id, locale)

    target = row.user
    if target.club_id != club.id or not target.has_any(Role.CLUB_MANAGER):
        raise HTTPException(
            status_code=409,
            detail=tr(
                locale,
                en="This person doesn't organize this club.",
                de="Diese Person ist keine Organisatorin oder kein Organisator dieses Vereins.",
            ),
        )

    if await _organizer_count(session, club.id, excluding_user_id=target.id) < 1:
        raise HTTPException(
            status_code=409,
            detail=tr(
                locale,
                en="At least one organizer must remain for this club.",
                de="Mindestens eine Person muss diesen Verein weiter organisieren.",
            ),
        )

    # Reassign the collection so the in-memory user is consistent for the response;
    # delete-orphan cascade removes the dropped row on flush.
    target.role_rows = [r for r in target.role_rows if r.role != Role.CLUB_MANAGER]
    session.add(
        AuditLog(
            entity_type="user",
            entity_id=target.id,
            action="revoke_organizer",
            actor=acting.email,
            payload={"club_id": club.id},
        )
    )
    await session.commit()
    return _format_membership(await _load_with_relations(session, row.id))


@router.post(
    "/api/admin/clubs/{club_id}/members",
    response_model=MembershipOut,
    status_code=status.HTTP_201_CREATED,
    summary="Invite person to club",
)
async def invite_member(
    club_id: int,
    request: MembershipInvitation,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
    locale: Locale = Depends(resolve_locale),
) -> MembershipOut:
    """Invites an account to the club. Only their acceptance makes it a membership.

    The person is addressed by email — that is the ID they know themselves by. An account
    must exist: anyone without one must register first.
    """
    club = await _get_club(session, club_id, locale)
    _check_club_leadership(acting, club.id, locale)

    email = request.email.strip().lower()
    person = (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if person is None:
        raise HTTPException(
            status_code=404,
            detail=tr(
                locale,
                (
                    f"No account exists for {email}. The person must register"
                    " first; then they can be admitted."
                ),
                (
                    f"Zu {email} gibt es kein Konto. Die Person muss sich zuerst"
                    " registrieren; danach lässt sie sich aufnehmen."
                ),
            ),
        )

    row = await _get_existing_membership(session, club.id, person.id)
    if row is None:
        row = ClubMember(
            club_id=club.id, user_id=person.id, status=ClubMemberStatus.PENDING_USER
        )
        session.add(row)
    elif row.status == ClubMemberStatus.REJECTED:
        row.status = ClubMemberStatus.PENDING_USER
        row.decision_note = None
        row.decided_at = None
    elif row.status == ClubMemberStatus.PENDING_CLUB:
        # The person had already applied — the invitation is acceptance.
        await _activate_membership(session, row, acting)
    else:
        raise HTTPException(
            status_code=409,
            detail=tr(
                locale,
                f"Something already exists for this person (status: {row.status}).",
                f"Für diese Person liegt bereits etwas vor (Stand: {row.status}).",
            ),
        )

    await session.commit()
    return _format_membership(await _load_with_relations(session, row.id))


# ------------------------------------------------------------------ Helper functions


def _with_relations(stmt):
    """Add eager loading of club and user relations."""
    return stmt.options(selectinload(ClubMember.club), selectinload(ClubMember.user))


async def _get_club(session: AsyncSession, club_id: int, locale: Locale) -> Club:
    """Fetch a club by ID, raising 404 if not found."""
    club = (
        await session.execute(select(Club).where(Club.id == club_id))
    ).scalar_one_or_none()
    if club is None:
        raise HTTPException(
            status_code=404,
            detail=tr(
                locale, f"Club {club_id} not found", f"Verein {club_id} nicht gefunden"
            ),
        )
    return club


async def _active_membership(
    session: AsyncSession, club_id: int, user_id: int, locale: Locale
) -> ClubMember:
    """The active membership a club's organizer role changes act on — not a pending one."""
    row = await _get_existing_membership(session, club_id, user_id)
    if row is None or row.status != ClubMemberStatus.ACTIVE:
        raise HTTPException(
            status_code=404,
            detail=tr(
                locale,
                en="This person is not an active member of this club.",
                de="Diese Person ist kein aktives Mitglied dieses Vereins.",
            ),
        )
    return await _load_with_relations(session, row.id, locale)


async def _organizer_count(
    session: AsyncSession, club_id: int, *, excluding_user_id: int | None = None
) -> int:
    """How many accounts organize this club — i.e. hold `club_manager` and represent it."""
    stmt = (
        select(func.count(func.distinct(User.id)))
        .join(UserRole, UserRole.user_id == User.id)
        .where(User.club_id == club_id, UserRole.role == Role.CLUB_MANAGER)
    )
    if excluding_user_id is not None:
        stmt = stmt.where(User.id != excluding_user_id)
    return int((await session.execute(stmt)).scalar_one())


async def _get_existing_membership(
    session: AsyncSession, club_id: int, user_id: int
) -> ClubMember | None:
    """Check if a membership record already exists for this club-user pair."""
    return (
        await session.execute(
            select(ClubMember).where(
                ClubMember.club_id == club_id, ClubMember.user_id == user_id
            )
        )
    ).scalar_one_or_none()


async def _load_with_relations(
    session: AsyncSession, membership_id: int, locale: Locale | None = None
) -> ClubMember:
    """Fetch a membership with club and user relations, raising 404 if not found."""
    row = (
        await session.execute(
            _with_relations(select(ClubMember).where(ClubMember.id == membership_id))
        )
    ).scalar_one_or_none()
    if row is None:
        detail = "This membership does not exist."
        if locale:
            detail = tr(locale, detail, "Diese Mitgliedschaft gibt es nicht.")
        raise HTTPException(status_code=404, detail=detail)
    return row


def _is_the_user(acting: User, row: ClubMember) -> bool:
    """Check if the acting user is the user in this membership."""
    return acting.id == row.user_id


def _is_club_leadership(acting: User, row: ClubMember) -> bool:
    """Check if the acting user is leadership of the club in this membership."""
    if acting.has_any(Role.ADMIN):
        return True
    return acting.has_any(Role.CLUB_MANAGER) and acting.club_id == row.club_id


def _check_club_leadership(acting: User, club_id: int, locale: Locale) -> None:
    """Verify that the acting user can manage this club's members."""
    if acting.has_any(Role.ADMIN):
        return
    if acting.has_any(Role.CLUB_MANAGER) and acting.club_id == club_id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=tr(
            locale,
            "Members are managed by the leadership of their own club.",
            "Mitglieder verwaltet die Vereinsleitung des eigenen Vereins.",
        ),
    )


def _check_authorization_to_decide(acting: User, row: ClubMember, locale: Locale) -> None:
    """Check if the acting user can make a decision on this membership.

    Only the side that hasn't yet agreed can make a decision.
    """
    if row.status == ClubMemberStatus.PENDING_CLUB:
        if not _is_club_leadership(acting, row):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=tr(
                    locale,
                    "The club decides on this request.",
                    "Über diese Anfrage entscheidet der Verein.",
                ),
            )
        return
    if row.status == ClubMemberStatus.PENDING_USER:
        if not _is_the_user(acting, row):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=tr(
                    locale,
                    "The invited person decides on this invitation.",
                    "Über diese Einladung entscheidet die eingeladene Person.",
                ),
            )
        return
    raise HTTPException(
        status_code=409,
        detail=tr(
            locale,
            f"Nothing more to decide here (status: {row.status}).",
            f"Hier ist nichts mehr zu entscheiden (Stand: {row.status}).",
        ),
    )


async def _activate_membership(session: AsyncSession, row: ClubMember, acting: User) -> None:
    """Activate a membership and update the user's primary club if needed."""
    previous = row.status
    row.status = ClubMemberStatus.ACTIVE
    row.decision_note = None
    row.decided_at = datetime.now(UTC)
    # The first club becomes the one the account acts for. Additional memberships don't change
    # this: a person can belong to multiple clubs but acts for only one.
    person = await session.get(User, row.user_id)
    if person is not None and person.club_id is None:
        person.club_id = row.club_id
    _log_decision(session, row, previous, acting)


def _log_decision(session: AsyncSession, row: ClubMember, previous: str, acting: User) -> None:
    """Record a membership decision in the audit log."""
    session.add(
        AuditLog(
            entity_type="club_member",
            entity_id=row.id,
            action="decide_membership",
            actor=acting.email,
            payload={"from": previous, "to": row.status, "note": row.decision_note},
        )
    )
