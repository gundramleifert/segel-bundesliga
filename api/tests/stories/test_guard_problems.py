"""Story Z-2: every refusal of a route guard is a typed RFC 9457 problem.

The guards in `app/auth.py` answer for most routes at once, so their refusals are the
errors a screen meets most often. Each carries its own code — never the generic
`/errors/http-401` a plain HTTPException would get — so the client can word it.
"""

import re
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.dependencies.models import Dependant
from fastapi.routing import RouteContext, iter_route_contexts
from sqlalchemy import select

from app.auth import ALGORITHM, create_access_token, current_user
from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models.auth import User

PROBLEM = "application/problem+json"
# An account holding no relation at all, created on first use.
GUEST = "guard-guest@example.com"


def _uses(dependant: Dependant, call) -> bool:
    return any(d.call is call or _uses(d, call) for d in dependant.dependencies)


def _guarded_routes() -> list[RouteContext]:
    """Every route that needs a signed-in person — through any guard in `app/auth.py`,
    router-level dependencies included. An included router's routes, with their prefix
    and dependencies, are only seen through `iter_route_contexts`: `app.routes` holds
    the routers, not their routes."""
    return [
        route
        for route in iter_route_contexts(app.routes)
        if getattr(route, "dependant", None) is not None and _uses(route.dependant, current_user)
    ]


def _path(route: RouteContext) -> str:
    """The route's path with every parameter filled with a plausible id."""
    return re.sub(r"\{[^}]+\}", "1", route.path)


async def _token(email: str) -> str:
    async with SessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None:
            user = User(email=email, display_name=email.split("@")[0])
            session.add(user)
            await session.commit()
        return create_access_token(user).token


def _assert_typed(response, code: str | None = None) -> dict:
    assert response.headers["content-type"].startswith(PROBLEM), response.text
    body = response.json()
    assert body["type"].startswith("/errors/"), body
    assert not body["type"].startswith("/errors/http-"), body
    if code is not None:
        assert body["type"] == f"/errors/{code}", body
    return body


class TestGuardProblems:
    """Story Z-2: who is refused learns why, as a code."""

    def test_the_sweep_finds_the_guarded_routes(self):
        """A sweep over nothing would pass; the guard must be found on many routes."""
        assert len(_guarded_routes()) > 50

    def test_the_api_document_declares_the_refusals_as_problems(self):
        """The generated client reads its error type from here."""
        responses = app.openapi()["paths"]["/api/admin/events/{event_id}/races"]["get"]["responses"]
        for status in ("401", "403", "404"):
            schema = responses[status]["content"][PROBLEM]["schema"]
            assert schema == {"$ref": "#/components/schemas/ProblemDetails"}

    @pytest.mark.parametrize(
        "route", _guarded_routes(), ids=lambda r: f"{sorted(r.methods)[0]} {r.path}"
    )
    async def test_every_guarded_route_answers_a_stranger_with_not_signed_in(self, client, route):
        method = sorted(route.methods)[0]
        response = await client.request(method, _path(route))
        assert response.status_code == 401
        _assert_typed(response, "not-signed-in")
        assert response.headers["www-authenticate"] == "Bearer"

    async def test_every_guarded_read_refuses_a_guest_with_a_typed_problem(self, client):
        """A signed-in person holding no relation at all: whatever a guarded page answers
        them — 403, a 404 for an id that does not exist, a validation error — is typed."""
        headers = {"Authorization": f"Bearer {await _token(GUEST)}"}
        refused = 0
        for route in _guarded_routes():
            if "GET" not in route.methods:
                continue
            response = await client.get(_path(route), headers=headers)
            if response.status_code >= 400:
                _assert_typed(response)
                refused += 1
        assert refused > 10

    async def test_a_missing_relation_names_what_was_required(self, client):
        headers = {"Authorization": f"Bearer {await _token(GUEST)}"}
        response = await client.get("/api/admin/clubs", headers=headers)
        assert response.status_code == 403
        body = _assert_typed(response, "forbidden")
        assert body["required"] == ["admin"]

    async def test_an_unknown_event_is_not_found_before_any_permission_question(self, client):
        headers = {"Authorization": f"Bearer {await _token(GUEST)}"}
        response = await client.get("/api/admin/events/999999/races", headers=headers)
        assert response.status_code == 404
        body = _assert_typed(response, "event-not-found")
        assert body["id"] == 999999

    async def test_an_expired_session_says_so(self, client):
        past = datetime.now(UTC) - timedelta(hours=2)
        token = jwt.encode(
            {"sub": "1", "iat": int(past.timestamp()), "exp": int(past.timestamp()) + 60},
            settings.jwt_secret,
            algorithm=ALGORITHM,
        )
        response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
        _assert_typed(response, "session-expired")

    async def test_a_forged_token_is_invalid(self, client):
        token = jwt.encode({"sub": "1"}, "not-our-secret", algorithm=ALGORITHM)
        response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
        _assert_typed(response, "token-invalid")

    async def test_a_blocked_account_is_inactive(self, client):
        async with SessionLocal() as session:
            user = User(email="blocked-guard@example.com", display_name="Blocked")
            user.is_active = False
            session.add(user)
            await session.commit()
            token = create_access_token(user).token
        response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
        _assert_typed(response, "account-inactive")
