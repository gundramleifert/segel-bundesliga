"""A club invites someone to an account — Story V-16 (`app/services/invitations.py`).

Two halves: the club's admin sends, resends and withdraws (`/api/clubs/{id}/…`), and the
person opens the link (`/api/invitations/{token}`), signed in by nothing but the link.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token, current_user
from app.db import get_session
from app.models import Club, Person
from app.models.auth import User
from app.schemas.auth import TokenOut
from app.schemas.public import InvitationIn, InvitationOut
from app.services import invitations
from app.services.lookup import get_or_404

router = APIRouter(tags=["clubs"])


@router.post(
    "/api/clubs/{club_id}/invitations",
    response_model=InvitationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Invite someone to an account",
)
async def invite_to_account(
    club_id: int,
    request: InvitationIn,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> InvitationOut:
    """Story V-16, J-3.14: the club's admin invites an address no account has. The person
    is on record — created if the address had none — and *pending* (``invited``) until
    the link creates their account. ``invitation-has-account`` for an address with an
    account, ``invitation-pending`` while another invitation to it works."""
    club = await get_or_404(session, Club, club_id)
    invitation = await invitations.invite(
        session,
        club,
        acting,
        email=str(request.email),
        first_name=request.first_name,
        last_name=request.last_name,
    )
    return invitation


@router.post(
    "/api/clubs/{club_id}/people/{person_id}/invitation",
    response_model=InvitationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Invite a person of the club to an account",
)
async def invite_person_to_account(
    club_id: int,
    person_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> InvitationOut:
    """Story V-16, J-3.12: a person of the club on record without an account, from their
    row — the link then only adds the account."""
    club = await get_or_404(session, Club, club_id)
    person = await get_or_404(session, Person, person_id)
    return await invitations.invite_person(session, club, person, acting)


@router.post(
    "/api/clubs/{club_id}/people/{person_id}/invitation/resend",
    response_model=InvitationOut,
    summary="Send an invitation again",
)
async def resend_invitation(
    club_id: int,
    person_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> InvitationOut:
    """Story V-16, J-3.16: a new link, valid for 14 days again; the earlier one is dead.
    The inviting club's admin's, or the site's."""
    club = await get_or_404(session, Club, club_id)
    return await invitations.resend(session, club, person_id, acting)


@router.delete(
    "/api/clubs/{club_id}/people/{person_id}/invitation",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Withdraw an invitation",
)
async def withdraw_invitation(
    club_id: int,
    person_id: int,
    session: AsyncSession = Depends(get_session),
    acting: User = Depends(current_user),
) -> None:
    """Story V-16: the invitation goes, with the pending row and a person record created
    only for it."""
    club = await get_or_404(session, Club, club_id)
    await invitations.withdraw(session, club, person_id, acting)


class InvitationLinkOut(BaseModel):
    """What the link's page shows: the club and the name as the club entered it."""

    club_id: int
    club_name: str
    first_name: str
    last_name: str
    email: str


class InvitationRedeem(BaseModel):
    """The name as the person confirms or corrects it."""

    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)


@router.get(
    "/api/invitations/{token}", response_model=InvitationLinkOut, summary="Open an invitation"
)
async def read_invitation(
    token: str, session: AsyncSession = Depends(get_session)
) -> InvitationLinkOut:
    """Story V-16: for the link's page. A lapsed or used link answers 410 naming the club
    to ask (``invitation-expired``, ``invitation-used``); one replaced by a resend 404."""
    link = await invitations.find(session, token)
    invitations.refuse_unless_pending(link)
    person = link.person
    return InvitationLinkOut(
        club_id=link.club.id,
        club_name=link.club.name,
        first_name=person.first_name,
        last_name=person.last_name,
        email=person.email or "",
    )


@router.post(
    "/api/invitations/{token}/redeem", response_model=TokenOut, summary="Accept an invitation"
)
async def redeem_invitation(
    token: str, request: InvitationRedeem, session: AsyncSession = Depends(get_session)
) -> TokenOut:
    """Story V-16, J-3.13: the account, its address verified by the link, linked to the
    club's person record; the membership ``active``; signed in."""
    user = await invitations.redeem(
        session, token, first_name=request.first_name, last_name=request.last_name
    )
    access_token, expires_in = create_access_token(user)
    return TokenOut(access_token=access_token, expires_in=expires_in)
