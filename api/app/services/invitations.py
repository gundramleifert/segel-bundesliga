"""A club invites someone to an account — Story V-16, Journey J-3's branch "invited by the
club".

**Account first, then the club** (decided 2026-10-28): the club's admin sends a mail with a
link; until it is opened the person is on record with the membership ``invited`` — which
grants nothing (V-15) — and opening it creates the account, its address verified by the
link having reached it, linked to that person, and makes the membership ``active``. A
person the club already has on record without an account (J-3.11) is invited from their
row; then the link only adds the account.

The invitation lives **on the membership row** (``ClubMembership.invitation_*``): whatever
ends the row — withdrawn, declined, removed, left — ends the link with it.

**One valid invitation per address at a time**: whoever else tries is refused with
``invitation-pending``, which names no club — that a person is being invited elsewhere is
none of another club's business. An expired one blocks nobody. Only the inviting club's
admin (and the site's) resends or withdraws it.

The token is 32 random bytes in the link and a SHA-256 hash in the table: found by its
hash, so no salted hash, and random enough not to need one.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import authz
from app.config import settings
from app.mail import MailError, send_invitation
from app.models import Club, ClubMembership, InvitationState, MembershipStatus, Person
from app.models.auth import Relation, User
from app.models.base import as_utc, utcnow
from app.problems import Problem
from app.schemas.public import InvitationOut
from app.services.audit import EntityType, audit
from app.services.participation import connect_person, membership_of


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def state_of(row: ClubMembership, now: datetime | None = None) -> InvitationState | None:
    """Where the row's invitation stands — ``None`` when it carries none."""
    if row.invitation_token_hash is None or row.invitation_expires_at is None:
        return None
    if row.invitation_used_at is not None:
        return InvitationState.USED
    if as_utc(row.invitation_expires_at) <= (now or utcnow()):
        return InvitationState.EXPIRED
    return InvitationState.PENDING


def out(row: ClubMembership) -> InvitationOut | None:
    """The row's open invitation as the club sees it — ``None`` without one."""
    state = state_of(row)
    if state is None or state == InvitationState.USED or row.invitation_expires_at is None:
        return None
    return InvitationOut(
        club_id=row.club_id,
        person_id=row.person_id,
        expires_at=as_utc(row.invitation_expires_at),
        state=state,
    )


def _sent(row: ClubMembership) -> InvitationOut:
    """A row just issued carries a pending invitation."""
    sent = out(row)
    assert sent is not None
    return sent


def _ensure_admin(acting: User, club: Club) -> None:
    authz.ensure(
        acting,
        Relation.ADMIN,
        on=club,
        code="invitation-forbidden",
        title="Only the club's admin invites someone to an account.",
    )


def _refuse_account(has_account: bool) -> None:
    if has_account:
        raise Problem(
            409,
            "invitation-has-account",
            "This address has an account — add the person by email, or they ask to join.",
        )


def _refuse_pending(person: Person, but: ClubMembership | None = None) -> None:
    """``invitation-pending`` while any invitation to this person works — but ``but``."""
    now = utcnow()
    for row in person.club_memberships:
        if row is not but and state_of(row, now) == InvitationState.PENDING:
            raise Problem(
                409,
                "invitation-pending",
                "This address has a pending invitation; another can be sent once it lapses.",
            )


async def invite(
    session: AsyncSession,
    club: Club,
    acting: User,
    *,
    email: str,
    first_name: str,
    last_name: str,
) -> InvitationOut:
    """J-3.14: an address no account has. The person on record under it, or a new one
    made for the invitation; their row in the club ``invited`` unless they are in it."""
    _ensure_admin(acting, club)
    email = email.strip().lower()
    account = (await session.execute(select(User.id).where(User.email == email))).first()
    person = (
        await session.execute(select(Person).where(Person.email == email))
    ).scalar_one_or_none()
    _refuse_account(account is not None or (person is not None and person.user_id is not None))
    created = person is None
    if person is None:
        person = Person(
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            email=email,
            club_memberships=[],
        )
        session.add(person)
    return await _invite(session, club, person, acting, created=created)


async def invite_person(
    session: AsyncSession, club: Club, person: Person, acting: User
) -> InvitationOut:
    """J-3.12: a person of the club on record without an account, from their row."""
    _ensure_admin(acting, club)
    if membership_of(person, club.id) is None:
        raise Problem(404, "membership-not-found", "This person is not in the club.")
    _refuse_account(person.user_id is not None)
    if not person.email:
        raise Problem(
            422, "invitation-no-address", "This person has no address to send an invitation to."
        )
    return await _invite(session, club, person, acting, created=False)


async def _invite(
    session: AsyncSession, club: Club, person: Person, acting: User, *, created: bool
) -> InvitationOut:
    _refuse_pending(person)
    row = membership_of(person, club.id)
    if row is None:
        row = ClubMembership(
            club_id=club.id, status=MembershipStatus.INVITED, created_for_invitation=created
        )
        person.club_memberships.append(row)
    token = _issue(row, acting)
    await session.flush()
    audit(session, EntityType.PERSON, person.id, "invitation_sent", acting, club_id=club.id)
    await session.commit()
    await _mail(club, person, acting, token)
    return _sent(row)


def _issue(row: ClubMembership, acting: User) -> str:
    """A fresh link, valid for the lifetime again — the previous one is dead."""
    token = secrets.token_urlsafe(32)
    row.invitation_token_hash = hash_token(token)
    row.invitation_expires_at = utcnow() + timedelta(days=settings.invitation_lifetime_days)
    row.invitation_used_at = None
    row.invited_by_id = acting.id
    return token


async def _mail(club: Club, person: Person, acting: User, token: str) -> None:
    try:
        await send_invitation(
            person.email or "",
            club=club.name,
            inviter=acting.display_name,
            first_name=person.first_name,
            link=f"{settings.site_url}/invitation/{token}",
        )
    except MailError as exc:
        # The invitation stands and can be resent; the admin must know the mail did not go.
        raise Problem(
            502, "invitation-mail-failed", "The invitation is saved but its mail could not be sent."
        ) from exc


class _Open(NamedTuple):
    """A person and their row carrying this club's unused invitation."""

    person: Person
    row: ClubMembership


async def _open(session: AsyncSession, club: Club, person_id: int, acting: User) -> _Open:
    _ensure_admin(acting, club)
    person = await session.get(Person, person_id)
    row = membership_of(person, club.id) if person is not None else None
    if person is None or row is None or out(row) is None:
        raise Problem(404, "invitation-not-found", "There is no such invitation.")
    return _Open(person, row)


async def resend(session: AsyncSession, club: Club, person_id: int, acting: User) -> InvitationOut:
    """J-3.16: a new link for the lifetime again; the earlier one is dead."""
    person, row = await _open(session, club, person_id, acting)
    _refuse_account(person.user_id is not None)
    _refuse_pending(person, but=row)
    token = _issue(row, acting)
    audit(session, EntityType.PERSON, person.id, "invitation_resent", acting, club_id=club.id)
    await session.commit()
    await _mail(club, person, acting, token)
    return _sent(row)


async def withdraw(session: AsyncSession, club: Club, person_id: int, acting: User) -> None:
    """The invitation goes, with the pending row — and the person record, when it was made
    only for this invitation and nothing else holds it. A row already active (J-3.12)
    stays, without its link."""
    person, row = await _open(session, club, person_id, acting)
    audit(session, EntityType.PERSON, person.id, "invitation_withdrawn", acting, club_id=club.id)
    if row.status == MembershipStatus.ACTIVE:
        row.invitation_token_hash = row.invitation_expires_at = row.invited_by_id = None
    else:
        person.club_memberships = [link for link in person.club_memberships if link is not row]
        if row.created_for_invitation and person.user_id is None and not person.club_memberships:
            await session.delete(person)
    await session.commit()


class Link(NamedTuple):
    """What a link names: the row, its person and its club."""

    row: ClubMembership
    person: Person
    club: Club


async def find(session: AsyncSession, token: str) -> Link:
    row = (
        await session.execute(
            select(ClubMembership)
            .options(selectinload(ClubMembership.person))
            .where(ClubMembership.invitation_token_hash == hash_token(token))
        )
    ).scalar_one_or_none()
    club = await session.get(Club, row.club_id) if row is not None else None
    if row is None or club is None:
        raise Problem(
            404, "invitation-not-found", "This link is not valid — perhaps a newer one was sent."
        )
    return Link(row, row.person, club)


def refuse_unless_pending(link: Link) -> None:
    """An expired or used link says so and names the club to ask."""
    match state_of(link.row):
        case InvitationState.USED:
            raise Problem(
                410, "invitation-used", "This link was used already.", club=link.club.name
            )
        case InvitationState.EXPIRED:
            raise Problem(
                410,
                "invitation-expired",
                "This link has lapsed; ask the club to send it again.",
                club=link.club.name,
            )
    if link.person.user_id is not None:
        raise Problem(
            409,
            "invitation-has-account",
            "This address has an account now — sign in; the invitation waits under My clubs.",
            club=link.club.name,
        )


async def redeem(session: AsyncSession, token: str, *, first_name: str, last_name: str) -> User:
    """J-3.13: the account, verified by the link, linked to the club's person record; the
    membership ``active``. Works with registration closed and self-signup off: the
    invitation is the explicit enrollment the club asks for, not a sign-up."""
    from app.services.login import sign_in_invited  # login imports the people service

    link = await find(session, token)
    refuse_unless_pending(link)
    person = link.person
    person.first_name, person.last_name = first_name.strip(), last_name.strip()
    user = await sign_in_invited(session, person.email or "", person.full_name)
    connect_person(person, link.club.id)
    link.row.invitation_used_at = utcnow()
    # Every other club's lapsed link to this address is moot now; their rows stay, to be
    # accepted under My clubs (V-15).
    for other in person.club_memberships:
        if other is not link.row:
            other.invitation_token_hash = other.invitation_expires_at = None
    audit(session, EntityType.PERSON, person.id, "invitation_redeemed", user, club_id=link.club.id)
    await session.commit()
    return user
