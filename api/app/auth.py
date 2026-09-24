"""Access tokens and role checking.

We do not manage passwords — identity comes from Google, Microsoft, or a one-time code via email
(see ``app.services.login``). This module only issues our own session tokens and checks roles.

Everything fails closed: without a configured signing secret, no token is issued and none is
accepted.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import Event, Series
from app.models.auth import Relation, Role, User

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
        # `leeway`: a token is checked against the clock of whatever host verifies it, and a
        # clock that is stepped back a second by time sync (WSL2 does this) turns a token
        # issued a moment ago into "not yet valid". Thirty seconds tolerates that and
        # changes nothing about a genuinely expired session.
        payload = jwt.decode(credentials.credentials, _secret(), algorithms=[ALGORITHM], leeway=30)
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


def require_site(*relations: Relation | str):
    """A dependency for the league office's screens: one of these relations **on the
    site**, through the rewrite rules (an admin passes an editor gate). A tuple on one
    club, series or event does not pass here — routes about *one* event use
    :func:`require_on_event`.
    """
    wanted = tuple(Relation(r) for r in relations)

    async def dependency(user: User = Depends(current_user)) -> User:
        if not user.can(*wanted):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "You lack the permission for this. Required role(s): "
                    + ", ".join(sorted(r.value for r in wanted))
                ),
            )
        return user

    return dependency


def require_summary_roles(*roles: Role | str):
    """Passes anyone whose **summary** roles include one of these — a navigation-level
    gate for lists a person then narrows to their own objects (``managed_club_ids``)."""
    wanted = {str(r) for r in roles}

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


def _on_object(model, path_param: str, *relations: Relation | str):
    """A dependency for routes with ``{<path_param>}`` in their path: passes whoever holds
    one of these relations on that object — directly, or through its containers and the
    site (the model's rewrite rules). Reads the id from the path, so the handler need not
    repeat the check. An unknown object is a 404 here, before any permission question.
    """
    wanted = tuple(Relation(r) for r in relations)

    async def dependency(
        request: Request,
        user: User = Depends(current_user),
        session: AsyncSession = Depends(get_session),
    ) -> User:
        object_id = int(request.path_params[path_param])
        obj = await session.get(model, object_id)
        if obj is None:
            raise HTTPException(status_code=404, detail=f"{model.__name__} {object_id} not found")
        if user.can(*wanted, on=obj):
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"You lack the permission for this {model.__name__.lower()}. "
                "Required relation(s): " + ", ".join(sorted(r.value for r in wanted))
            ),
        )

    return dependency


def require_on_event(*relations: Relation | str):
    return _on_object(Event, "event_id", *relations)


def require_on_series(*relations: Relation | str):
    return _on_object(Series, "series_id", *relations)


# The site's gates.
require_admin = require_site(Relation.ADMIN)
require_editor = require_site(Relation.EDITOR)
require_race_officer = require_site(Relation.RACE_OFFICER)
# "Organizes some club": the route narrows to the club itself with `manages_club(...)`.
require_club_manager = require_summary_roles(Role.ADMIN, Role.CLUB_MANAGER)
# One event: its race committee (results, race control, trackers) …
require_event_officer = require_on_event(Relation.RACE_OFFICER)
# … its organizer (dates, clubs, boats, publication, people) …
require_event_manager_for = require_on_event(Relation.MANAGER)
# … and the declarations both may make: start, finish, cancel, reopen (Story VA-10).
require_event_control = require_on_event(Relation.MANAGER, Relation.RACE_OFFICER)
# One series: its organizer sets participants, dates and publication.
require_series_manager_for = require_on_series(Relation.MANAGER)
# Master data like clubs: admin and editorial.
require_master_data = require_site(Relation.ADMIN, Relation.EDITOR)
