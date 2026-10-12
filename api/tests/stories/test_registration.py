"""User story Z-4: register yourself.

Registration creates an account and verifies the email address. It does not make anyone
a club member — that is the club admin's `member` tuple (Story Z-5,
`test_club_members.py`).
"""

import logging

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Club
from app.models.auth import User
from tests.stories.test_login_and_roles import make_user

# A fixed club from the seed. Deliberately not the first: the club-page stories test that one,
# and these tests modify the membership list.
CLUB_SLUG = "fsc"


async def club_id(slug: str = CLUB_SLUG) -> int:
    async with SessionLocal() as session:
        return (await session.execute(select(Club.id).where(Club.slug == slug))).scalar_one()


async def account(email: str) -> User | None:
    async with SessionLocal() as session:
        return (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()


async def register(client, caplog, email: str, name: str) -> str:
    """Registers and immediately redeems the confirmation code. Returns the token."""
    with caplog.at_level(logging.WARNING, logger="app.mail"):
        response = await client.post(
            "/api/auth/register", json={"email": email, "display_name": name}
        )
    assert response.status_code == 202, response.text

    code = caplog.records[-1].args[-1]
    eingeloest = await client.post("/api/auth/email/verify", json={"email": email, "code": code})
    assert eingeloest.status_code == 200, eingeloest.text
    return eingeloest.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestRegistering:
    """As a sailor, I want to create an account myself."""

    async def test_the_code_proves_the_address(self, client, caplog):
        """With the code, the address is verified."""
        token = await register(client, caplog, "bestaetigt@example.com", "Bea Bestätigt")

        ich = (await client.get("/api/auth/me", headers=auth_headers(token))).json()
        assert ich["email_verified"] is True
        assert ich["roles"] == []
        assert ich["tuples"] == []

    async def test_a_known_address_gives_nothing_away(self, client, caplog):
        """A known address doesn't reveal itself — else we could enumerate accounts
        via registration — and registering overwrites no existing account. A new address
        is only claimed until confirmed: anyone could type someone else's."""
        await make_user("schon.da@example.com")

        with caplog.at_level(logging.WARNING, logger="app.mail"):
            bekannt = await client.post(
                "/api/auth/register",
                json={"email": "schon.da@example.com", "display_name": "Jemand"},
            )
            unbekannt = await client.post(
                "/api/auth/register",
                json={"email": "noch.nicht.da@example.com", "display_name": "Jemand"},
            )

        assert bekannt.status_code == unbekannt.status_code == 202
        assert bekannt.json() == unbekannt.json()

        bestand = await account("schon.da@example.com")
        assert bestand is not None
        assert bestand.display_name == "schon.da"
        neu = await account("noch.nicht.da@example.com")
        assert neu is not None
        assert neu.email_verified is False
