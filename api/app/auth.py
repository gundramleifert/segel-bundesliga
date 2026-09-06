"""Access tokens and role checking.

We do not manage passwords — identity comes from Google, Microsoft, or a one-time code via email
(see ``app.services.login``). This module only issues our own session tokens and checks roles.

Everything fails closed: without a configured signing secret, no token is issued and none is
accepted.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models.auth import Role, User

ALGORITHM = "HS256"

_scheme = HTTPBearer(auto_error=False)


def _secret() -> str:
    if not settings.jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No signing secret is configured (SBL_JWT_SECRET).",
        )
    return settings.jwt_secret


def create_access_token(user: User) -> tuple[str, int]:
    """Returns token and validity duration in seconds."""
    lifetime = timedelta(minutes=settings.jwt_lifetime_minutes)
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "name": user.display_name,
        "roles": sorted(user.roles),
        "iat": int(now.timestamp()),
        "exp": int((now + lifetime).timestamp()),
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM), int(lifetime.total_seconds())


async def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign-in is required for this area.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(credentials.credentials, _secret(), algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has expired. Please sign in again.",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token."
        ) from exc

    # Roles are deliberately fetched fresh from the database: a revoked permission should
    # take effect immediately, not only when the token expires.
    user = (
        await session.execute(select(User).where(User.id == int(payload["sub"])))
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="This account is not active."
        )
    return user


async def optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_scheme),
    session: AsyncSession = Depends(get_session),
) -> User | None:
    """The signed-in user — or ``None``.

    The public site serves both: club people, race officers, and editors are signed in; fans
    and guests are not. Endpoints that are open to everyone but should show more to signed-in
    users use this instead of ``current_user``.

    An **invalid** token is treated as "not signed in", not as an error: otherwise the public
    site would be unusable for someone with an expired session, instead of simply treating them
    as a guest.
    """
    if credentials is None:
        return None
    try:
        return await current_user(credentials, session)
    except HTTPException:
        return None


def require_roles(*roles: Role | str):
    """Creates a dependency that requires one of these roles."""
    wanted = {str(role) for role in roles}

    async def dependency(user: User = Depends(current_user)) -> User:
        if not user.has_any(*wanted):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "You lack the permission for this. Required role(s): "
                    + ", ".join(sorted(wanted))
                ),
            )
        return user

    return dependency


# Admin can be involved everywhere it needs to intervene.
require_admin = require_roles(Role.ADMIN)
require_race_officer = require_roles(Role.ADMIN, Role.RACE_OFFICER)
require_editor = require_roles(Role.ADMIN, Role.EDITOR)
require_club_manager = require_roles(Role.ADMIN, Role.CLUB_MANAGER)
# Create and manage matchdays: all three roles that carry an event.
require_event_manager = require_roles(Role.ADMIN, Role.EDITOR, Role.RACE_OFFICER)
# Master data like clubs: admin and editorial.
require_master_data = require_roles(Role.ADMIN, Role.EDITOR)
