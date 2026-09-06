"""Development aids for trying out different roles.

**This router is off by default.** It is only included when ``SBL_DEV_LOGIN=true``
is set, and it issues access tokens **without any verification**. In a reachable
environment this would be a wide-open door — that's why it has its own setting instead of
being coupled to ``debug``, and why the server warns on startup.

Purpose: while developing, move through the interface as admin, editor, race officer, or club
manager without fetching a one-time code from the log each time.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token
from app.db import get_session
from app.i18n import Locale, resolve_locale, tr
from app.models import Club
from app.models.auth import User

router = APIRouter(prefix="/api/dev", tags=["development"])


class TestUserOut(BaseModel):
    id: int
    email: str
    display_name: str
    roles: list[str]
    club: str | None = None
    description: str


class DevLogin(BaseModel):
    email: EmailStr


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


DESCRIPTION: dict[str, str] = {
    "admin": "Sees and can do everything: master data, accounts, roles, pairing lists.",
    "editor": "Editorial: write messages, approve club posts.",
    "race_officer": "Race officer: record and correct results.",
    "club_manager": "Club account: own roster, submit posts, club assignment.",
}


@router.get("/users", response_model=list[TestUserOut], summary="List test accounts")
async def list_test_users(
    session: AsyncSession = Depends(get_session),
    locale: Locale = Depends(resolve_locale),
) -> list[TestUserOut]:
    users = (
        await session.execute(select(User).order_by(User.display_name))
    ).scalars().all()
    clubs = {
        club.id: club.short_name
        for club in (await session.execute(select(Club))).scalars()
    }

    return [
        TestUserOut(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            roles=sorted(user.roles),
            club=clubs.get(user.club_id) if user.club_id else None,
            description=tr(
                locale,
                en=" ".join(
                    DESCRIPTION[rolle] for rolle in sorted(user.roles) if rolle in DESCRIPTION
                )
                or "Signed in, but no special permissions.",
                de=" ".join(
                    DESCRIPTION[rolle] for rolle in sorted(user.roles) if rolle in DESCRIPTION
                )
                or "Angemeldet, aber ohne besondere Rechte.",
            ),
        )
        for user in users
    ]


@router.post("/login", response_model=TokenOut, summary="Sign in without verification")
async def dev_login(
    request: DevLogin,
    session: AsyncSession = Depends(get_session),
    locale: Locale = Depends(resolve_locale),
) -> TokenOut:
    user = (
        await session.execute(select(User).where(User.email == request.email.lower()))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=404,
            detail=tr(
                locale,
                en="This test account does not exist.",
                de="Dieses Testkonto gibt es nicht."
            )
        )

    # Like a real sign-in: whoever passes through here is considered verified. Otherwise
    # the role switcher couldn't be used for membership stories.
    user.email_verified = True
    await session.commit()

    token, expires_in = create_access_token(user)
    return TokenOut(access_token=token, expires_in=expires_in)
