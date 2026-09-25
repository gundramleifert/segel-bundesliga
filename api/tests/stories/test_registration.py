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

    async def test_registering_creates_an_account_for_my_address(self, client, caplog):
        """Registration creates an account with my email address."""
        with caplog.at_level(logging.WARNING, logger="app.mail"):
            response = await client.post(
                "/api/auth/register",
                json={"email": "neu.anna@example.com", "display_name": "Anna Neu"},
            )
        assert response.status_code == 202

        person = await account("neu.anna@example.com")
        assert person is not None
        assert person.display_name == "Anna Neu"

    async def test_before_confirmation_the_address_is_merely_claimed(self, client, caplog):
        """Before confirmation, the address is only claimed — anyone could type someone else's."""
        with caplog.at_level(logging.WARNING, logger="app.mail"):
            await client.post(
                "/api/auth/register",
                json={"email": "unbestaetigt@example.com", "display_name": "Uwe Unbestätigt"},
            )
        person = await account("unbestaetigt@example.com")
        assert person is not None
        assert person.email_verified is False

    async def test_the_code_proves_the_address(self, client, caplog):
        """With the code, the address is verified."""
        token = await register(client, caplog, "bestaetigt@example.com", "Bea Bestätigt")

        ich = (await client.get("/api/auth/me", headers=auth_headers(token))).json()
        assert ich["email_verified"] is True
        assert ich["roles"] == []
        assert ich["tuples"] == []

    async def test_a_name_is_required(self, client):
        """Registration requires a name."""
        response = await client.post(
            "/api/auth/register", json={"email": "namenlos@example.com", "display_name": ""}
        )
        assert response.status_code == 422

    async def test_a_known_address_gives_nothing_away(self, client, caplog):
        """A known address doesn't reveal itself — else we could enumerate accounts
        via registration."""
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

    async def test_registering_overwrites_no_existing_account(self, client, caplog):
        """Registration does not overwrite an existing account."""
        await make_user("bestand@example.com")
        with caplog.at_level(logging.WARNING, logger="app.mail"):
            await client.post(
                "/api/auth/register",
                json={"email": "bestand@example.com", "display_name": "Fremder Name"},
            )
        person = await account("bestand@example.com")
        assert person is not None
        assert person.display_name == "bestand"
