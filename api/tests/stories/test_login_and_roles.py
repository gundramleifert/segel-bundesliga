"""User stories about sign-in and permissions.

We do not manage passwords: identity comes from Google, Microsoft, or a one-time code via email.
"""

import pytest
from sqlalchemy import delete, select

from app.db import SessionLocal
from app.models import ClubMember
from app.models.auth import IdentityProvider, LoginCode, Role, User, UserRole


async def make_user(
    email: str, *roles: str, active: bool = True, club_id: int | None = None
) -> int:
    async with SessionLocal() as session:
        existing = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if existing is not None:
            # Memberships point to the account. SQLite reuses deleted ids —
            # if a row remains, it would suddenly belong to the next person.
            await session.execute(
                delete(ClubMember).where(ClubMember.user_id == existing.id)
            )
            await session.delete(existing)
            await session.commit()

        user = User(
            email=email,
            display_name=email.split("@")[0],
            is_active=active,
            club_id=club_id,
        )
        user.role_rows = [UserRole(role=role) for role in roles]
        session.add(user)
        await session.commit()
        return user.id


async def latest_code(email: str) -> str | None:
    """The code is stored only as a hash in the database — in tests we read it from the log."""
    async with SessionLocal() as session:
        return (
            await session.execute(
                select(LoginCode).where(LoginCode.email == email).order_by(LoginCode.id.desc())
            )
        ).scalars().first()


async def login_as(client, email: str, caplog) -> str:
    """Signs in and returns the access token."""
    import logging

    with caplog.at_level(logging.WARNING, logger="app.mail"):
        response = await client.post("/api/auth/email/request", json={"email": email})
    assert response.status_code == 202

    code = caplog.records[-1].args[-1]
    response = await client.post(
        "/api/auth/email/verify", json={"email": email, "code": code}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


class TestAnmeldung:
    """As a user, I want to sign in without a password."""

    async def test_die_seite_sagt_welche_anmeldewege_offenstehen(self, client):
        """The page tells which sign-in methods are available."""
        wege = (await client.get("/api/auth/providers")).json()
        # Email always works; providers only with configured application ID.
        assert wege[IdentityProvider.EMAIL] is True
        assert IdentityProvider.GOOGLE in wege and IdentityProvider.MICROSOFT in wege

    async def test_mit_einem_einmalcode_komme_ich_hinein(self, client, caplog):
        """I can sign in with a one-time code."""
        await make_user("seglerin@example.org", Role.CLUB_MANAGER)
        token = await login_as(client, "seglerin@example.org", caplog)

        response = await client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json()["roles"] == [Role.CLUB_MANAGER]

    async def test_der_code_gilt_nur_einmal(self, client, caplog):
        """The code can only be used once."""
        import logging

        await make_user("einmal@example.org")
        with caplog.at_level(logging.WARNING, logger="app.mail"):
            await client.post("/api/auth/email/request", json={"email": "einmal@example.org"})
        code = caplog.records[-1].args[-1]

        payload = {"email": "einmal@example.org", "code": code}
        assert (await client.post("/api/auth/email/verify", json=payload)).status_code == 200
        zweiter = await client.post("/api/auth/email/verify", json=payload)
        assert zweiter.status_code == 401

    async def test_ein_falscher_code_kommt_nicht_durch(self, client, caplog):
        """A wrong code is rejected."""
        await make_user("falsch@example.org")
        await client.post("/api/auth/email/request", json={"email": "falsch@example.org"})

        response = await client.post(
            "/api/auth/email/verify", json={"email": "falsch@example.org", "code": "000000"}
        )
        assert response.status_code == 401

    async def test_eine_unbekannte_adresse_verraet_nichts(self, client):
        """An unknown address reveals nothing — otherwise we could enumerate accounts."""
        response = await client.post(
            "/api/auth/email/request", json={"email": "gibtsnicht@example.org"}
        )
        assert response.status_code == 202
        assert await latest_code("gibtsnicht@example.org") is None

    async def test_ohne_anmeldung_ist_der_eigene_bereich_zu(self, client):
        """Without sign-in, the personal area is locked."""
        assert (await client.get("/api/auth/me")).status_code == 401


class TestRollen:
    """As an admin, I want to grant and revoke roles."""

    async def test_ohne_verwaltungsrolle_bleibt_die_verwaltung_zu(self, client, caplog):
        """Without an admin role, the admin area stays locked."""
        await make_user("gast@example.org")
        token = await login_as(client, "gast@example.org", caplog)

        response = await client.get(
            "/api/auth/users", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403
        assert "lack the permission" in response.json()["detail"]

    async def test_die_verwaltung_kann_konten_anlegen_und_rollen_vergeben(self, client, caplog):
        """Admin can create accounts and assign roles."""
        await make_user("chefin@example.org", Role.ADMIN)
        token = await login_as(client, "chefin@example.org", caplog)
        headers = {"Authorization": f"Bearer {token}"}

        angelegt = await client.post(
            "/api/auth/users",
            headers=headers,
            json={"email": "wl@example.org", "display_name": "Wettfahrtleitung"},
        )
        assert angelegt.status_code == 201
        assert angelegt.json()["roles"] == []

        user_id = angelegt.json()["id"]
        geaendert = await client.put(
            f"/api/auth/users/{user_id}/roles",
            headers=headers,
            json={"roles": [Role.RACE_OFFICER]},
        )
        assert geaendert.status_code == 200
        assert geaendert.json()["roles"] == [Role.RACE_OFFICER]

    async def test_die_eigene_verwaltungsrolle_laesst_sich_nicht_selbst_entziehen(
        self, client, caplog
    ):
        """Cannot revoke your own admin role — otherwise the last admin could
        lock themselves out."""
        user_id = await make_user("allein@example.org", Role.ADMIN)
        token = await login_as(client, "allein@example.org", caplog)

        response = await client.put(
            f"/api/auth/users/{user_id}/roles",
            headers={"Authorization": f"Bearer {token}"},
            json={"roles": [Role.EDITOR]},
        )
        assert response.status_code == 409

    async def test_ein_gesperrtes_konto_kommt_nicht_hinein(self, client):
        """A suspended account cannot sign in."""
        await make_user("gesperrt@example.org", Role.ADMIN, active=False)
        response = await client.post(
            "/api/auth/email/request", json={"email": "gesperrt@example.org"}
        )
        assert response.status_code == 202
        assert await latest_code("gesperrt@example.org") is None


class TestRemoveAccount:
    """Removing an account deactivates it — the row and its history stay in the DB."""

    async def test_removing_deactivates_not_deletes(self, client, caplog):
        from sqlalchemy import select

        from app.db import SessionLocal
        from app.models.auth import User

        admin = await make_user("rm-admin@example.org", Role.ADMIN)
        assert admin
        token = await login_as(client, "rm-admin@example.org", caplog)
        victim_id = await make_user("rm-victim@example.org", Role.EDITOR)

        response = await client.delete(
            f"/api/auth/users/{victim_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["is_active"] is False

        async with SessionLocal() as session:
            still_there = (
                await session.execute(select(User).where(User.id == victim_id))
            ).scalar_one_or_none()
        assert still_there is not None, "the row must remain"
        assert still_there.is_active is False

    async def test_a_deactivated_account_cannot_sign_in(self, client, caplog):
        await make_user("rm-admin2@example.org", Role.ADMIN)
        admin_token = await login_as(client, "rm-admin2@example.org", caplog)
        victim_id = await make_user("rm-victim2@example.org")
        victim_token = await login_as(client, "rm-victim2@example.org", caplog)

        await client.delete(
            f"/api/auth/users/{victim_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        # The still-valid token no longer works — is_active is checked per request.
        response = await client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {victim_token}"}
        )
        assert response.status_code == 401

    async def test_i_cannot_remove_my_own_account(self, client, caplog):
        own_id = await make_user("rm-self@example.org", Role.ADMIN)
        token = await login_as(client, "rm-self@example.org", caplog)

        response = await client.delete(
            f"/api/auth/users/{own_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 409
        assert "own account" in response.json()["detail"]

    async def test_only_admin_can_remove_an_account(self, client, caplog):
        await make_user("rm-editor@example.org", Role.EDITOR)
        token = await login_as(client, "rm-editor@example.org", caplog)
        victim_id = await make_user("rm-victim3@example.org")

        response = await client.delete(
            f"/api/auth/users/{victim_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestZuschnittDesSpieltags:
    """Team count and boat count determine the races per flight."""

    @pytest.mark.parametrize(
        ("teams", "boats", "erwartet"),
        [(18, 6, 3), (17, 6, 3), (12, 6, 2), (12, 4, 3), (7, 4, 2)],
    )
    def test_die_rennen_je_flight_ergeben_sich_aus_teams_und_booten(
        self, teams, boats, erwartet
    ):
        """Races per flight are derived from team count and boat count."""
        from app.models import Event

        event = Event(team_count=teams, boat_count=boats, flight_count=16)
        assert event.races_per_flight == erwartet
        assert event.races_total == erwartet * 16

    async def test_der_gesegelte_spieltag_kennt_seinen_zuschnitt(self, client, ids):
        """A raced matchday knows its configuration."""
        detail = (await client.get(f"/api/events/{ids.event('dsbl-1-2026-act-1')}")).json()
        assert detail["races_total"] == 48


class TestVereinszuordnung:
    """As a club manager, I want to assign users to a club — permanently."""

    async def _clubs(self, client) -> list[dict]:
        return (await client.get("/api/clubs")).json()

    async def test_die_zuordnung_gilt_ueber_spieltage_hinweg(self, client, caplog):
        """Assignment persists across matchdays — it attaches to the account, not the event."""
        clubs = await self._clubs(client)
        await make_user("chef@example.org", Role.ADMIN)
        token = await login_as(client, "chef@example.org", caplog)
        headers = {"Authorization": f"Bearer {token}"}

        user_id = await make_user("neuling@example.org")
        response = await client.put(
            f"/api/auth/users/{user_id}/club",
            headers=headers,
            json={"club_id": clubs[0]["id"]},
        )
        assert response.status_code == 200
        assert response.json()["club_id"] == clubs[0]["id"]

        # Auch nach einem erneuten Abruf steht sie noch — kein Bezug zu einem Spieltag.
        erneut = await client.get(
            "/api/auth/users", headers=headers, params={"club_id": clubs[0]["id"]}
        )
        assert user_id in [u["id"] for u in erneut.json()]

    async def test_ein_vereinsverantwortlicher_ordnet_dem_eigenen_verein_zu(
        self, client, caplog
    ):
        """A club manager can assign users to their own club."""
        clubs = await self._clubs(client)
        async with SessionLocal() as session:
            manager_id = await make_user("manager@example.org", Role.CLUB_MANAGER)
            manager = await session.get(User, manager_id)
            manager.club_id = clubs[0]["id"]
            await session.commit()

        token = await login_as(client, "manager@example.org", caplog)
        user_id = await make_user("crew@example.org")

        response = await client.put(
            f"/api/auth/users/{user_id}/club",
            headers={"Authorization": f"Bearer {token}"},
            json={"club_id": clubs[0]["id"]},
        )
        assert response.status_code == 200
        assert response.json()["club_id"] == clubs[0]["id"]

    async def test_ein_fremder_verein_laesst_sich_nicht_zuordnen(self, client, caplog):
        """A club manager cannot assign users to other clubs — else they could seize teams."""
        clubs = await self._clubs(client)
        async with SessionLocal() as session:
            manager_id = await make_user("manager2@example.org", Role.CLUB_MANAGER)
            manager = await session.get(User, manager_id)
            manager.club_id = clubs[0]["id"]
            await session.commit()

        token = await login_as(client, "manager2@example.org", caplog)
        user_id = await make_user("fremd@example.org")

        response = await client.put(
            f"/api/auth/users/{user_id}/club",
            headers={"Authorization": f"Bearer {token}"},
            json={"club_id": clubs[1]["id"]},
        )
        assert response.status_code == 403

    async def test_wer_schon_woanders_ist_wird_nicht_abgeworben(self, client, caplog):
        """Users already assigned to another club cannot be poached."""
        clubs = await self._clubs(client)
        async with SessionLocal() as session:
            manager_id = await make_user("manager3@example.org", Role.CLUB_MANAGER)
            manager = await session.get(User, manager_id)
            manager.club_id = clubs[0]["id"]
            besetzt_id = await make_user("besetzt@example.org")
            besetzt = await session.get(User, besetzt_id)
            besetzt.club_id = clubs[1]["id"]
            await session.commit()

        token = await login_as(client, "manager3@example.org", caplog)
        response = await client.put(
            f"/api/auth/users/{besetzt_id}/club",
            headers={"Authorization": f"Bearer {token}"},
            json={"club_id": clubs[0]["id"]},
        )
        assert response.status_code == 403

    async def test_ohne_rolle_geht_gar_nichts(self, client, caplog):
        """Without a role, a user cannot assign anyone to a club."""
        clubs = await self._clubs(client)
        await make_user("niemand@example.org")
        token = await login_as(client, "niemand@example.org", caplog)
        user_id = await make_user("opfer@example.org")

        response = await client.put(
            f"/api/auth/users/{user_id}/club",
            headers={"Authorization": f"Bearer {token}"},
            json={"club_id": clubs[0]["id"]},
        )
        assert response.status_code == 403

    async def test_ein_unbekannter_verein_wird_abgewiesen(self, client, caplog):
        """An unknown club is rejected."""
        await make_user("chef2@example.org", Role.ADMIN)
        token = await login_as(client, "chef2@example.org", caplog)
        user_id = await make_user("egal@example.org")

        response = await client.put(
            f"/api/auth/users/{user_id}/club",
            headers={"Authorization": f"Bearer {token}"},
            json={"club_id": 999999},
        )
        assert response.status_code == 404

    async def test_die_zuordnung_wird_protokolliert(self, client, caplog):
        """Club assignment is logged — entries, posts, and check-in depend on it."""
        from app.models import AuditLog

        clubs = await self._clubs(client)
        await make_user("chef3@example.org", Role.ADMIN)
        token = await login_as(client, "chef3@example.org", caplog)
        user_id = await make_user("protokoll@example.org")

        await client.put(
            f"/api/auth/users/{user_id}/club",
            headers={"Authorization": f"Bearer {token}"},
            json={"club_id": clubs[0]["id"]},
        )

        async with SessionLocal() as session:
            eintrag = (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.entity_type == "app_user", AuditLog.entity_id == user_id
                    )
                )
            ).scalars().first()
        assert eintrag is not None
        assert eintrag.actor == "chef3@example.org"
        assert eintrag.payload["to"] == clubs[0]["id"]
