"""User stories Z-4 and Z-5: register and get accepted into a club.

Two steps that must not be confused: **Registration** creates an account and verifies the
email address. It does not make anyone a club member — the club decides that.
"""

import logging

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Club, ClubMemberStatus
from app.models.auth import User
from tests.stories.test_login_and_roles import make_user

# A fixed club from the seed. Deliberately not the first: the club-page stories test that one,
# and these tests modify the membership list.
CLUB_SLUG = "fsc"


async def club_id(slug: str = CLUB_SLUG) -> int:
    async with SessionLocal() as session:
        return (
            await session.execute(select(Club.id).where(Club.slug == slug))
        ).scalar_one()


async def account(email: str) -> User | None:
    async with SessionLocal() as session:
        return (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()


async def register(client, caplog, email: str, name: str) -> str:
    """Registers and immediately redeems the confirmation code. Returns the token."""
    with caplog.at_level(logging.WARNING, logger="app.mail"):
        antwort = await client.post(
            "/api/auth/register", json={"email": email, "display_name": name}
        )
    assert antwort.status_code == 202, antwort.text

    code = caplog.records[-1].args[-1]
    eingeloest = await client.post(
        "/api/auth/email/verify", json={"email": email, "code": code}
    )
    assert eingeloest.status_code == 200, eingeloest.text
    return eingeloest.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestRegistrierung:
    """As a sailor, I want to create an account myself."""

    async def test_die_registrierung_legt_ein_konto_mit_meiner_adresse_an(
        self, client, caplog
    ):
        """Registration creates an account with my email address."""
        with caplog.at_level(logging.WARNING, logger="app.mail"):
            antwort = await client.post(
                "/api/auth/register",
                json={"email": "neu.anna@example.com", "display_name": "Anna Neu"},
            )
        assert antwort.status_code == 202

        person = await account("neu.anna@example.com")
        assert person is not None
        assert person.display_name == "Anna Neu"

    async def test_vor_der_bestaetigung_gilt_die_adresse_als_bloss_behauptet(
        self, client, caplog
    ):
        """Before confirmation, the address is only claimed — anyone could type someone else's."""
        with caplog.at_level(logging.WARNING, logger="app.mail"):
            await client.post(
                "/api/auth/register",
                json={"email": "unbestaetigt@example.com", "display_name": "Uwe Unbestätigt"},
            )
        person = await account("unbestaetigt@example.com")
        assert person is not None
        assert person.email_verified is False

    async def test_mit_dem_code_ist_die_adresse_nachgewiesen(self, client, caplog):
        """With the code, the address is verified."""
        token = await register(client, caplog, "bestaetigt@example.com", "Bea Bestätigt")

        ich = (await client.get("/api/auth/me", headers=auth_headers(token))).json()
        assert ich["email_verified"] is True
        assert ich["roles"] == []
        assert ich["club_id"] is None

    async def test_ohne_namen_geht_es_nicht(self, client):
        """Registration requires a name."""
        antwort = await client.post(
            "/api/auth/register", json={"email": "namenlos@example.com", "display_name": ""}
        )
        assert antwort.status_code == 422

    async def test_eine_bekannte_adresse_verraet_sich_nicht(self, client, caplog):
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

    async def test_die_registrierung_ueberschreibt_kein_bestehendes_konto(
        self, client, caplog
    ):
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


class TestAufnahmeAntrag:
    """As a registered person, I want to request membership in a club."""

    async def test_die_anfrage_wartet_auf_den_verein(self, client, caplog):
        """The request waits for the club's decision."""
        token = await register(client, caplog, "antrag1@example.com", "Anne Antrag")
        club = await club_id()

        antwort = await client.post(
            "/api/club-memberships", headers=auth_headers(token), json={"club_id": club}
        )
        assert antwort.status_code == 201, antwort.text
        assert antwort.json()["status"] == ClubMemberStatus.PENDING_CLUB
        assert antwort.json()["waiting_for"] == "club"

    async def test_eine_anfrage_macht_noch_kein_mitglied(self, client, caplog):
        """A request doesn't make you a member yet — the other side must agree."""
        token = await register(client, caplog, "antrag2@example.com", "Bert Antrag")
        club = await club_id()
        await client.post(
            "/api/club-memberships", headers=auth_headers(token), json={"club_id": club}
        )

        ich = (await client.get("/api/auth/me", headers=auth_headers(token))).json()
        assert ich["club_id"] is None

    async def test_ohne_bestaetigte_adresse_geht_das_nicht(self, client, caplog):
        """Without a verified address, you cannot request membership — else someone
        could flood clubs with requests using fake addresses."""
        await make_user("ohnenachweis@example.com")
        async with SessionLocal() as session:
            person = (
                await session.execute(
                    select(User).where(User.email == "ohnenachweis@example.com")
                )
            ).scalar_one()
            person.email_verified = False
            await session.commit()

        # Deliberately not via the sign-in path: that would verify the address right away.
        from app.auth import create_access_token

        token, _ = create_access_token(person)
        antwort = await client.post(
            "/api/club-memberships",
            headers=auth_headers(token),
            json={"club_id": await club_id()},
        )
        assert antwort.status_code == 403
        assert "verify" in antwort.json()["detail"].lower()

    async def test_ohne_anmeldung_gar_nicht(self, client):
        """Without sign-in, you cannot request membership."""
        antwort = await client.post(
            "/api/club-memberships", json={"club_id": await club_id()}
        )
        assert antwort.status_code == 401
