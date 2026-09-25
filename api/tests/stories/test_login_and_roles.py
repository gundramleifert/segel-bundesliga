"""User stories about sign-in and permissions.

We do not manage passwords: identity comes from Google, Microsoft, or a one-time code via email.
"""

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import (
    AuditLog,
    Club,
    Sailor,
    WaiverConfirmation,
    WaiverText,
)
from app.models.auth import Grant, IdentityProvider, LoginCode, Relation, Role, User
from tests.pages import all_items


async def make_user(
    email: str, *roles: str, active: bool = True, club_id: int | None = None
) -> int:
    async with SessionLocal() as session:
        existing = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if existing is not None:
            # The account's tuples go with it (ORM cascade on `User.grants`). SQLite
            # reuses deleted ids — a row left behind would belong to the next person.
            await session.delete(existing)
            await session.commit()

        user = User(
            email=email,
            display_name=email.split("@")[0],
            is_active=active,
            club_id=club_id,
        )
        # `Role.CLUB_MANAGER` with `club_id` means "manager of this club" — one tuple on
        # the club; every other role here is a site relation (Story Z-2). A club manager
        # without a club named organizes the first seeded club: a manager tuple needs an
        # object, and these tests only care that the person organizes *some* club.
        if (Role.CLUB_MANAGER in roles or Role.CLUB_ADMIN in roles) and club_id is None:
            club_id = (
                await session.execute(select(Club.id).order_by(Club.id).limit(1))
            ).scalar_one()
        user.grants = [
            Grant(relation=Relation.MANAGER, club_id=club_id)
            if role == Role.CLUB_MANAGER
            else Grant(relation=Relation.ADMIN, club_id=club_id)
            if role == Role.CLUB_ADMIN
            else Grant(relation=Relation(role))
            for role in roles
        ]
        session.add(user)
        await session.commit()
        return user.id


async def latest_code(email: str) -> str | None:
    """The code is stored only as a hash in the database — in tests we read it from the log."""
    async with SessionLocal() as session:
        return (
            (
                await session.execute(
                    select(LoginCode).where(LoginCode.email == email).order_by(LoginCode.id.desc())
                )
            )
            .scalars()
            .first()
        )


async def login_as(client, email: str, caplog) -> str:
    """Signs in and returns the access token."""
    import logging

    with caplog.at_level(logging.WARNING, logger="app.mail"):
        response = await client.post("/api/auth/email/request", json={"email": email})
    assert response.status_code == 202

    code = caplog.records[-1].args[-1]
    response = await client.post("/api/auth/email/verify", json={"email": email, "code": code})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


class TestSigningIn:
    """As a user, I want to sign in without a password."""

    async def test_the_page_says_which_sign_in_methods_are_open(self, client):
        """The page tells which sign-in methods are available."""
        wege = (await client.get("/api/auth/providers")).json()
        # Email always works; providers only with configured application ID.
        assert wege[IdentityProvider.EMAIL]["available"] is True
        assert IdentityProvider.GOOGLE in wege and IdentityProvider.MICROSOFT in wege
        assert "allow_registration" in wege

    async def test_a_one_time_code_signs_me_in(self, client, caplog):
        """I can sign in with a one-time code."""
        await make_user("seglerin@example.org", Role.CLUB_MANAGER)
        token = await login_as(client, "seglerin@example.org", caplog)

        response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["roles"] == [Role.CLUB_MANAGER]

    async def test_a_code_works_only_once(self, client, caplog):
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

    async def test_a_wrong_code_does_not_get_through(self, client, caplog):
        """A wrong code is rejected."""
        await make_user("falsch@example.org")
        await client.post("/api/auth/email/request", json={"email": "falsch@example.org"})

        response = await client.post(
            "/api/auth/email/verify", json={"email": "falsch@example.org", "code": "000000"}
        )
        assert response.status_code == 401

    async def test_an_unknown_address_gives_nothing_away(self, client):
        """An unknown address reveals nothing — otherwise we could enumerate accounts."""
        response = await client.post(
            "/api/auth/email/request", json={"email": "gibtsnicht@example.org"}
        )
        assert response.status_code == 202
        assert await latest_code("gibtsnicht@example.org") is None

    async def test_the_own_area_is_closed_without_signing_in(self, client):
        """Without sign-in, the personal area is locked."""
        assert (await client.get("/api/auth/me")).status_code == 401


class TestRoles:
    """As an admin, I want to grant and revoke roles."""

    async def test_the_admin_area_stays_closed_without_an_admin_role(self, client, caplog):
        """Without an admin role, the admin area stays locked."""
        await make_user("gast@example.org")
        token = await login_as(client, "gast@example.org", caplog)

        response = await client.get("/api/auth/users", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403
        assert "lack the permission" in response.json()["detail"]

    async def test_administration_can_create_accounts_and_grant_roles(self, client, caplog):
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
        written = await client.post(
            "/api/auth/tuples",
            headers=headers,
            json={"user": "wl@example.org", "relation": "race_officer", "object": "site"},
        )
        assert written.status_code == 201, written.text
        assert written.json()["object"] == "site"
        user = await client.get(f"/api/auth/users/{user_id}", headers=headers)
        assert user.json()["roles"] == [Role.RACE_OFFICER]

    async def test_nobody_can_revoke_their_own_admin_role(self, client, caplog):
        """Cannot revoke your own admin role — otherwise the last admin could
        lock themselves out."""
        await make_user("allein@example.org", Role.ADMIN)
        token = await login_as(client, "allein@example.org", caplog)
        headers = {"Authorization": f"Bearer {token}"}

        me = await client.get("/api/auth/me", headers=headers)
        (admin_tuple,) = [t for t in me.json()["tuples"] if t["relation"] == "admin"]
        response = await client.delete(f"/api/auth/tuples/{admin_tuple['id']}", headers=headers)
        assert response.status_code == 409

    async def test_a_disabled_account_cannot_sign_in(self, client):
        """A suspended account cannot sign in."""
        await make_user("gesperrt@example.org", Role.ADMIN, active=False)
        response = await client.post(
            "/api/auth/email/request", json={"email": "gesperrt@example.org"}
        )
        assert response.status_code == 202
        assert await latest_code("gesperrt@example.org") is None


class TestAdminWhitelist:
    """As a deployment operator, I want a whitelisted address to become admin on its
    first sign-in — otherwise a fresh deployment has no one who can grant any role."""

    async def test_a_listed_address_becomes_admin_on_first_sign_in(
        self, client, caplog, monkeypatch
    ):
        """A whitelisted address becomes admin on its first sign-in."""
        monkeypatch.setattr(settings, "admin_emails", ["Chef@Example.org"])
        await make_user("chef@example.org")

        token = await login_as(client, "chef@example.org", caplog)
        response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.json()["roles"] == [Role.ADMIN]

    async def test_an_unlisted_address_stays_without_a_role(self, client, caplog):
        """An address not on the list gets no role, as before."""
        await make_user("niemand@example.org")
        token = await login_as(client, "niemand@example.org", caplog)

        response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.json()["roles"] == []

    async def test_a_role_is_never_granted_twice(self, client, caplog, monkeypatch):
        """Signing in twice doesn't create a duplicate role row."""
        monkeypatch.setattr(settings, "admin_emails", ["chef@example.org"])
        await make_user("chef@example.org")

        await login_as(client, "chef@example.org", caplog)
        token = await login_as(client, "chef@example.org", caplog)

        response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.json()["roles"] == [Role.ADMIN]


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


class TestDeleteMyAccount:
    """Story Z-7: a signed-in person can delete their own account outright — a
    testing-phase convenience, unlike administration removing someone else (Z-6, which
    deactivates and keeps the row)."""

    async def test_deleting_removes_the_row(self, client, caplog):
        user_id = await make_user("del-self@example.org")
        token = await login_as(client, "del-self@example.org", caplog)

        response = await client.delete("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 204

        async with SessionLocal() as session:
            gone = (
                await session.execute(select(User).where(User.id == user_id))
            ).scalar_one_or_none()
        assert gone is None

    async def test_the_token_stops_working_immediately(self, client, caplog):
        await make_user("del-self2@example.org")
        token = await login_as(client, "del-self2@example.org", caplog)

        await client.delete("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

        response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401

    async def test_the_accounts_tuples_go_with_it(self, client, caplog, ids):
        """Membership is a tuple now (Story Z-5), and every tuple of the account goes with
        it — SQLite reuses ids, so a leftover row would belong to the next account."""
        user_id = await make_user("del-member@example.org")
        token = await login_as(client, "del-member@example.org", caplog)
        async with SessionLocal() as session:
            session.add(Grant(user_id=user_id, relation=Relation.MEMBER, club_id=ids.club("fsc")))
            session.add(Grant(user_id=user_id, relation=Relation.RACE_OFFICER))
            await session.commit()

        response = await client.delete("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 204

        async with SessionLocal() as session:
            leftover = (
                (await session.execute(select(Grant).where(Grant.user_id == user_id)))
                .scalars()
                .all()
            )
        assert leftover == []

    async def test_waiver_confirmations_survive_with_recorder_cleared(self, client, caplog, ids):
        """A waiver confirmation is someone else's evidence — it must outlive the staff
        account that happened to record it, with only the reference cleared."""
        recorder_id = await make_user("del-recorder@example.org", Role.ADMIN)
        token = await login_as(client, "del-recorder@example.org", caplog)

        async with SessionLocal() as session:
            sailor = Sailor(
                first_name="Del",
                last_name="Tester",
                email="del-tester-sailor@example.com",
            )
            session.add(sailor)
            await session.flush()
            waiver = (
                await session.execute(select(WaiverText).where(WaiverText.version == 1))
            ).scalar_one()
            confirmation = WaiverConfirmation(
                sailor_id=sailor.id,
                waiver_text_id=waiver.id,
                series_id=ids.series("dsbl-1-2026"),
                method="online",
                recorded_by_user_id=recorder_id,
            )
            session.add(confirmation)
            await session.commit()
            confirmation_id = confirmation.id

        response = await client.delete("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 204

        async with SessionLocal() as session:
            still_there = (
                await session.execute(
                    select(WaiverConfirmation).where(WaiverConfirmation.id == confirmation_id)
                )
            ).scalar_one()
        assert still_there.recorded_by_user_id is None


class TestTheShapeOfAMatchday:
    """Team count and boat count determine the races per flight."""

    @pytest.mark.parametrize(
        ("teams", "boats", "erwartet"),
        [(18, 6, 3), (17, 6, 3), (12, 6, 2), (12, 4, 3), (7, 4, 2)],
    )
    def test_races_per_flight_follow_from_teams_and_boats(self, teams, boats, erwartet):
        """Races per flight are derived from team count and boat count."""
        from app.models import Event

        event = Event(team_count=teams, boat_count=boats, flight_count=16)
        assert event.races_per_flight == erwartet
        assert event.races_total == erwartet * 16

    async def test_a_sailed_matchday_knows_its_own_shape(self, client, ids):
        """A raced matchday knows its configuration."""
        detail = (await client.get(f"/api/events/{ids.event('dsbl-1-2026-act-1')}")).json()
        assert detail["races_total"] == 48


class TestAssigningAClub:
    """As a club manager, I want to assign users to a club — permanently."""

    async def _clubs(self, client) -> list[dict]:
        return await all_items(client, "/api/clubs")

    async def test_the_assignment_holds_across_matchdays(self, client, caplog):
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

        # Still there when read again — the assignment hangs off no single matchday.
        again = await client.get(
            "/api/auth/users", headers=headers, params={"club_id": clubs[0]["id"]}
        )
        assert user_id in [u["id"] for u in again.json()["items"]]

    async def test_a_club_manager_assigns_to_their_own_club(self, client, caplog):
        """A club manager can assign users to their own club."""
        clubs = await self._clubs(client)
        await make_user("manager@example.org", Role.CLUB_ADMIN, club_id=clubs[0]["id"])

        token = await login_as(client, "manager@example.org", caplog)
        user_id = await make_user("crew@example.org")

        response = await client.put(
            f"/api/auth/users/{user_id}/club",
            headers={"Authorization": f"Bearer {token}"},
            json={"club_id": clubs[0]["id"]},
        )
        assert response.status_code == 200
        assert response.json()["club_id"] == clubs[0]["id"]

    async def test_nobody_assigns_a_club_that_is_not_theirs(self, client, caplog):
        """A club manager cannot assign users to other clubs — else they could seize teams."""
        clubs = await self._clubs(client)
        await make_user("manager2@example.org", Role.CLUB_ADMIN, club_id=clubs[0]["id"])

        token = await login_as(client, "manager2@example.org", caplog)
        user_id = await make_user("fremd@example.org")

        response = await client.put(
            f"/api/auth/users/{user_id}/club",
            headers={"Authorization": f"Bearer {token}"},
            json={"club_id": clubs[1]["id"]},
        )
        assert response.status_code == 403

    async def test_someone_already_elsewhere_is_not_poached(self, client, caplog):
        """Users already assigned to another club cannot be poached."""
        clubs = await self._clubs(client)
        await make_user("manager3@example.org", Role.CLUB_ADMIN, club_id=clubs[0]["id"])
        besetzt_id = await make_user("besetzt@example.org")
        async with SessionLocal() as session:
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

    async def test_nothing_works_without_a_role(self, client, caplog):
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

    async def test_an_unknown_club_is_refused(self, client, caplog):
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

    async def test_the_assignment_is_recorded_in_the_audit_log(self, client, caplog):
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
            entry = (
                (
                    await session.execute(
                        select(AuditLog).where(
                            AuditLog.entity_type == "app_user", AuditLog.entity_id == user_id
                        )
                    )
                )
                .scalars()
                .first()
            )
        assert entry is not None
        assert entry.actor == "chef3@example.org"
        assert entry.payload["to"] == clubs[0]["id"]


class TestActiveClub:
    """Story V-12: a person in several clubs picks the one they act for, and the choice is
    remembered on the account (`User.club_id`) instead of living in a URL."""

    async def _club_ids(self, *slugs: str) -> list[int]:
        from app.models import Club

        async with SessionLocal() as session:
            return [
                (await session.execute(select(Club.id).where(Club.slug == slug))).scalar_one()
                for slug in slugs
            ]

    async def test_the_chosen_club_is_remembered(self, client, caplog):
        nrv, kyc, dtyc = await self._club_ids("nrv", "kyc", "dtyc")
        email = "active-two-clubs@example.com"
        user_id = await make_user(email, Role.CLUB_MANAGER, club_id=nrv)
        async with SessionLocal() as session:
            # Organizes a second club as well — `club_manager` is granted per club.
            session.add(Grant(user_id=user_id, relation=Relation.MANAGER, club_id=kyc))
            await session.commit()
        headers = {"Authorization": f"Bearer {await login_as(client, email, caplog)}"}

        assert (await client.get("/api/auth/me", headers=headers)).json()["club_id"] == nrv

        chosen = await client.patch("/api/auth/me", headers=headers, json={"club_id": kyc})
        assert chosen.status_code == 200, chosen.text
        assert chosen.json()["club_id"] == kyc
        assert (await client.get("/api/auth/me", headers=headers)).json()["club_id"] == kyc

        # Not one of theirs: refused, and nothing moves.
        refused = await client.patch("/api/auth/me", headers=headers, json={"club_id": dtyc})
        assert refused.status_code == 422, refused.text
        assert refused.json()["type"] == "/errors/active-club-not-mine"
        assert (await client.get("/api/auth/me", headers=headers)).json()["club_id"] == kyc

        cleared = await client.patch("/api/auth/me", headers=headers, json={"club_id": None})
        assert cleared.status_code == 200, cleared.text
        assert cleared.json()["club_id"] is None

    async def test_a_plain_member_may_pick_their_club_too(self, client, caplog):
        """A `member` tuple alone is enough to act for the club (Stories Z-5, V-12)."""
        from tests.stories.test_my_clubs import _make_member

        (fsc,) = await self._club_ids("fsc")
        email = "active-member@example.com"
        await make_user(email)
        headers = {"Authorization": f"Bearer {await login_as(client, email, caplog)}"}
        await _make_member(email, fsc)

        chosen = await client.patch("/api/auth/me", headers=headers, json={"club_id": fsc})
        assert chosen.status_code == 200, chosen.text
        assert chosen.json()["club_id"] == fsc


async def _admin_headers(client, caplog, email: str = "chefin@example.org") -> dict[str, str]:
    await make_user(email, Role.ADMIN)
    token = await login_as(client, email, caplog)
    return {"Authorization": f"Bearer {token}"}


async def _headers(client, caplog, email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {await login_as(client, email, caplog)}"}


async def _write(client, headers, user: str, relation: str, obj: str) -> dict:
    """FGA's write: user · relation · object."""
    response = await client.post(
        "/api/auth/tuples",
        headers=headers,
        json={"user": user, "relation": relation, "object": obj},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _problem_code(response) -> str:
    return response.json()["type"].rsplit("/", 1)[-1]


class TestTuples:
    """Story Z-2: permissions are relation tuples — user · relation · object — written
    and deleted one at a time, checked through the model's rewrite rules."""

    async def test_a_site_tuple_is_what_a_role_used_to_be(self, client, caplog):
        headers = await _admin_headers(client, caplog)
        user_id = await make_user("wl2@example.org")

        row = await _write(client, headers, "wl2@example.org", "race_officer", "site")
        assert (row["object"], row["object_type"], row["object_id"]) == ("site", "site", None)
        user = (await client.get(f"/api/auth/users/{user_id}", headers=headers)).json()
        assert user["roles"] == [Role.RACE_OFFICER]
        assert [t["relation"] for t in user["tuples"]] == ["race_officer"]

    async def test_the_model_decides_which_relations_an_object_has(self, client, caplog, ids):
        """`manager` has no meaning on the site, `jury` none on a club (the schema)."""
        headers = await _admin_headers(client, caplog)
        await make_user("schema@example.org")

        def write(relation: str, obj: str):
            return client.post(
                "/api/auth/tuples",
                headers=headers,
                json={"user": "schema@example.org", "relation": relation, "object": obj},
            )

        response = await write("manager", "site")
        assert response.status_code == 422, response.text
        assert _problem_code(response) == "tuple-relation-invalid"

        response = await write("jury", f"club:{ids.club('nrv')}")
        assert response.status_code == 422, response.text
        assert _problem_code(response) == "tuple-relation-invalid"

        response = await write("race_officer", "event:987654")
        assert response.status_code == 404
        assert _problem_code(response) == "tuple-object-missing"

        response = await write("race_officer", "boat:1")
        assert response.status_code == 422
        assert _problem_code(response) == "tuple-object-invalid"

        model = (await client.get("/api/auth/model", headers=headers)).json()
        assert "define manager: [user]" in model["dsl"]
        by_type = {entry["type"]: entry["relations"] for entry in model["types"]}
        assert by_type["site"] == ["admin", "editor", "race_officer"]
        assert by_type["event"] == ["admin", "manager", "race_officer", "jury"]

    async def test_the_same_tuple_twice_is_refused(self, client, caplog, ids):
        headers = await _admin_headers(client, caplog)
        await make_user("doppelt@example.org")
        obj = f"event:{ids.event('dsbl-1-2026-act-1')}"

        await _write(client, headers, "doppelt@example.org", "race_officer", obj)
        response = await client.post(
            "/api/auth/tuples",
            headers=headers,
            json={"user": "doppelt@example.org", "relation": "race_officer", "object": obj},
        )
        assert response.status_code == 409
        assert _problem_code(response) == "tuple-exists"

    async def test_a_race_officer_of_one_event_stays_out_of_the_others(self, client, caplog, ids):
        """An event tuple is that event: results there, 403 next door, no setup rights,
        and the admin event list shows only what the tuples reach."""
        headers = await _admin_headers(client, caplog)
        await make_user("regatta@example.org")
        mine, other = ids.event("dsbl-1-2026-act-1"), ids.event("dsbl-1-2026-act-2")
        await _write(client, headers, "regatta@example.org", "race_officer", f"event:{mine}")

        officer = await _headers(client, caplog, "regatta@example.org")
        get = client.get
        assert (await get(f"/api/admin/events/{mine}/races", headers=officer)).status_code == 200
        assert (await get(f"/api/admin/events/{other}/races", headers=officer)).status_code == 403
        # Setup is the organizer's; a race officer appointed for one event does not get it.
        patched = await client.patch(
            f"/api/admin/events/{mine}", headers=officer, json={"title": "Act 1 Tutzing"}
        )
        assert patched.status_code == 403, patched.text

        listed = await all_items(client, "/api/admin/events", headers=officer)
        assert [e["id"] for e in listed] == [mine]

        # The league-wide gates stay shut: an event's race officer is not the league office.
        assert (await get("/api/auth/users", headers=officer)).status_code == 403

    async def test_a_tuple_on_a_series_or_a_club_covers_its_events(self, client, caplog, ids):
        """Containers rewrite downwards: series → its events, host club → what it hosts."""
        headers = await _admin_headers(client, caplog)
        act_2 = ids.event("dsbl-1-2026-act-2")

        await make_user("serie@example.org")
        await _write(
            client,
            headers,
            "serie@example.org",
            "race_officer",
            f"series:{ids.series('dsbl-1-2026')}",
        )
        response = await client.get(
            f"/api/admin/events/{act_2}/races",
            headers=await _headers(client, caplog, "serie@example.org"),
        )
        assert response.status_code == 200, response.text

        # The seed leaves the host open, as most events start out; name one for this test.
        host = ids.club("nrv")
        patched = await client.patch(
            f"/api/admin/events/{act_2}", headers=headers, json={"host_club_id": host}
        )
        assert patched.status_code == 200, patched.text
        await make_user("gastgeber@example.org")
        await _write(client, headers, "gastgeber@example.org", "race_officer", f"club:{host}")
        response = await client.get(
            f"/api/admin/events/{act_2}/races",
            headers=await _headers(client, caplog, "gastgeber@example.org"),
        )
        assert response.status_code == 200, response.text

    async def test_deleting_one_tuple_leaves_the_others_alone(self, client, caplog, ids):
        """A person is manager of two clubs and race officer of two events — four rows;
        deleting one is one row. The old set-roles endpoint rebuilt them all."""
        headers = await _admin_headers(client, caplog)
        nrv, byc = ids.club("nrv"), ids.club("byc")
        act_1, act_3 = ids.event("dsbl-1-2026-act-1"), ids.event("dsbl-1-2026-act-3")
        user_id = await make_user("vier@example.org", Role.CLUB_MANAGER, club_id=nrv)
        await _write(client, headers, "vier@example.org", "manager", f"club:{byc}")
        await _write(client, headers, "vier@example.org", "race_officer", f"event:{act_1}")
        gone = await _write(client, headers, "vier@example.org", "race_officer", f"event:{act_3}")

        response = await client.delete(f"/api/auth/tuples/{gone['id']}", headers=headers)
        assert response.status_code == 204, response.text
        user = (await client.get(f"/api/auth/users/{user_id}", headers=headers)).json()
        assert sorted(user["roles"]) == [Role.CLUB_MANAGER, Role.RACE_OFFICER]
        assert sorted((t["relation"], t["object"]) for t in user["tuples"]) == sorted(
            [
                ("manager", f"club:{byc}"),
                ("manager", f"club:{nrv}"),
                ("race_officer", f"event:{act_1}"),
            ]
        )

    async def test_the_last_organizer_of_a_club_cannot_be_deleted_here_either(
        self, client, caplog, ids
    ):
        """A-8's rule holds on the Accounts tab too — the club could not manage itself."""
        headers = await _admin_headers(client, caplog)
        club = await _lonely_club()
        user_id = await make_user("einzig@example.org", Role.CLUB_MANAGER, club_id=club)
        me = await client.get(f"/api/auth/users/{user_id}", headers=headers)
        (row,) = me.json()["tuples"]

        response = await client.delete(f"/api/auth/tuples/{row['id']}", headers=headers)
        assert response.status_code == 409
        assert _problem_code(response) == "last-organizer"

    async def test_every_write_and_delete_is_audited(self, client, caplog, ids):
        headers = await _admin_headers(client, caplog)
        user_id = await make_user("protokoll@example.org")
        event_id = ids.event("dsbl-1-2026-act-3")
        row = await _write(
            client, headers, "protokoll@example.org", "race_officer", f"event:{event_id}"
        )
        await client.delete(f"/api/auth/tuples/{row['id']}", headers=headers)

        async with SessionLocal() as session:
            rows = (
                (
                    await session.execute(
                        select(AuditLog)
                        .where(AuditLog.entity_type == "user", AuditLog.entity_id == user_id)
                        .order_by(AuditLog.id)
                    )
                )
                .scalars()
                .all()
            )
        assert [(r.action, r.payload["relation"], r.payload["object_id"]) for r in rows] == [
            ("grant", "race_officer", event_id),
            ("revoke", "race_officer", event_id),
        ]


class TestOrganizers:
    """Story Z-2: `manager` is the organizer relation — of a club, a series or an event.
    The manager runs the setup and names the event's people; the host club's manager is
    the event's manager without a second tuple."""

    async def test_an_event_manager_runs_the_setup_but_not_the_races(self, client, caplog, ids):
        headers = await _admin_headers(client, caplog)
        event_id = ids.event("dsbl-1-2026-act-3")
        await make_user("orga@example.org")
        await _write(client, headers, "orga@example.org", "manager", f"event:{event_id}")
        orga = await _headers(client, caplog, "orga@example.org")

        patched = await client.patch(
            f"/api/admin/events/{event_id}", headers=orga, json={"title": "Act 3 Friedrichshafen"}
        )
        assert patched.status_code == 200, patched.text
        assert (
            await client.get(f"/api/admin/events/{event_id}/races", headers=orga)
        ).status_code == 403
        assert (
            await client.get(f"/api/admin/events/{event_id}/readiness", headers=orga)
        ).status_code == 200
        me = (await client.get("/api/auth/me", headers=orga)).json()
        assert me["roles"] == [Role.EVENT_MANAGER]

    async def test_the_host_clubs_admin_is_the_events_admin_and_names_its_people(
        self, client, caplog, ids
    ):
        """No second tuple needed: `admin from host_club` makes a club's admin the admin
        of the events the club hosts — setup and people alike — but nothing elsewhere."""
        headers = await _admin_headers(client, caplog)
        host = ids.club("nrv")
        created = await client.post(
            "/api/admin/events",
            headers=headers,
            json={"title": "Z-2 club regatta", "host_club_id": host},
        )
        assert created.status_code == 201, created.text
        event_id = created.json()["id"]
        await make_user("nrv-orga@example.org", Role.CLUB_ADMIN, club_id=host)
        await make_user("nrv-wl@example.org")
        orga = await _headers(client, caplog, "nrv-orga@example.org")

        patched = await client.patch(
            f"/api/admin/events/{event_id}",
            headers=orga,
            json={"title": "Z-2 club regatta, day 1"},
        )
        assert patched.status_code == 200, patched.text

        written = await _write(
            client, orga, "nrv-wl@example.org", "race_officer", f"event:{event_id}"
        )
        listed = await client.get(f"/api/auth/tuples?object=event:{event_id}", headers=orga)
        assert listed.status_code == 200, listed.text
        assert [(t["user"], t["relation"]) for t in listed.json()] == [
            ("nrv-wl@example.org", "race_officer")
        ]
        officer = await _headers(client, caplog, "nrv-wl@example.org")
        assert (
            await client.get(f"/api/admin/events/{event_id}/races", headers=officer)
        ).status_code == 200

        foreign = ids.event("dsbl-1-2026-act-1")
        refused = await client.post(
            "/api/auth/tuples",
            headers=orga,
            json={
                "user": "nrv-wl@example.org",
                "relation": "race_officer",
                "object": f"event:{foreign}",
            },
        )
        assert refused.status_code == 403
        assert _problem_code(refused) == "tuple-forbidden"
        assert (
            await client.get(f"/api/auth/tuples?object=event:{foreign}", headers=orga)
        ).status_code == 403

        deleted = await client.delete(f"/api/auth/tuples/{written['id']}", headers=orga)
        assert deleted.status_code == 204, deleted.text

    async def test_a_clubs_admin_names_anyone_its_manager_nobody(self, client, caplog, ids):
        """On the club itself its admin writes tuples — for any account, member or not
        (Story A-8: an organizer need not be a member). The manager decides who sails,
        not who belongs, so they cannot write here at all."""
        headers = await _admin_headers(client, caplog)
        club = ids.club("byc")
        await make_user("byc-orga@example.org", Role.CLUB_ADMIN, club_id=club)
        await make_user("byc-sport@example.org", Role.CLUB_MANAGER, club_id=club)
        await make_user("stranger@example.org")
        orga = await _headers(client, caplog, "byc-orga@example.org")
        sport = await _headers(client, caplog, "byc-sport@example.org")
        body = {
            "user": "stranger@example.org",
            "relation": "race_officer",
            "object": f"club:{club}",
        }

        refused = await client.post("/api/auth/tuples", headers=sport, json=body)
        assert refused.status_code == 403, refused.text
        assert _problem_code(refused) == "tuple-forbidden"

        written = await client.post("/api/auth/tuples", headers=orga, json=body)
        assert written.status_code == 201, written.text
        assert written.json()["relation"] == "race_officer"

        model = (await client.get("/api/auth/model", headers=headers)).json()
        by_type = {entry["type"]: entry["relations"] for entry in model["types"]}
        assert by_type["club"] == ["admin", "manager", "race_officer", "member"]
        me = (await client.get("/api/auth/me", headers=orga)).json()
        assert sorted(me["roles"]) == [Role.CLUB_ADMIN, Role.CLUB_MANAGER]
        await client.delete(f"/api/auth/tuples/{written.json()['id']}", headers=orga)

    async def test_an_event_manager_sets_up_but_its_admin_names_the_people(
        self, client, caplog, ids
    ):
        headers = await _admin_headers(client, caplog)
        event_id = ids.event("dsbl-1-2026-act-3")
        await make_user("ev-manager@example.org")
        await make_user("ev-admin@example.org")
        await make_user("ev-jury@example.org")
        await _write(client, headers, "ev-manager@example.org", "manager", f"event:{event_id}")
        await _write(client, headers, "ev-admin@example.org", "admin", f"event:{event_id}")
        manager = await _headers(client, caplog, "ev-manager@example.org")
        admin = await _headers(client, caplog, "ev-admin@example.org")

        body = {"user": "ev-jury@example.org", "relation": "jury", "object": f"event:{event_id}"}
        refused = await client.post("/api/auth/tuples", headers=manager, json=body)
        assert refused.status_code == 403, refused.text
        written = await client.post("/api/auth/tuples", headers=admin, json=body)
        assert written.status_code == 201, written.text
        # The event's admin is everything within it: setup and results as well.
        assert (
            await client.get(f"/api/admin/events/{event_id}/races", headers=admin)
        ).status_code == 200
        me = (await client.get("/api/auth/me", headers=admin)).json()
        assert me["roles"] == [Role.EVENT_MANAGER]
        await client.delete(f"/api/auth/tuples/{written.json()['id']}", headers=admin)

    async def test_a_series_manager_sets_clubs_and_events_a_series_admin_everything(
        self, client, caplog, ids
    ):
        headers = await _admin_headers(client, caplog)
        series_id = ids.series("scl-2026")
        await make_user("scl-manager@example.org")
        await make_user("scl-admin@example.org")
        await _write(client, headers, "scl-manager@example.org", "manager", f"series:{series_id}")
        await _write(client, headers, "scl-admin@example.org", "admin", f"series:{series_id}")
        manager = await _headers(client, caplog, "scl-manager@example.org")
        admin = await _headers(client, caplog, "scl-admin@example.org")

        # The manager: this series' participants and events, and only this series.
        clubs = (await client.get(f"/api/admin/series/{series_id}", headers=headers)).status_code
        assert clubs in (200, 405)
        listed = await all_items(client, "/api/admin/series", headers=manager)
        assert [entry["id"] for entry in listed] == [series_id]
        patched = await client.patch(
            f"/api/admin/series/{series_id}", headers=manager, json={"squad_max": 12}
        )
        assert patched.status_code == 200, patched.text
        other = ids.series("dsbl-1-2026")
        assert (
            await client.patch(
                f"/api/admin/series/{other}", headers=manager, json={"squad_max": 12}
            )
        ).status_code == 403
        created = await client.post(
            "/api/admin/events",
            headers=manager,
            json={"title": "Z-2 cup act", "series": series_id},
        )
        assert created.status_code == 201, created.text
        event_id = created.json()["id"]
        assert (
            await client.post(
                "/api/admin/series", headers=manager, json={"name": "x", "short_name": "x"}
            )
        ).status_code == 403

        # The series' admin names the series' and its events' people, and runs races.
        assert (
            await client.get(f"/api/auth/tuples?object=series:{series_id}", headers=manager)
        ).status_code == 403
        assert (
            await client.get(f"/api/auth/tuples?object=series:{series_id}", headers=admin)
        ).status_code == 200
        assert (
            await client.get(f"/api/admin/events/{event_id}/races", headers=admin)
        ).status_code == 200
        assert (
            await client.get(f"/api/admin/events/{event_id}/races", headers=manager)
        ).status_code == 403
        me = (await client.get("/api/auth/me", headers=admin)).json()
        assert me["roles"] == [Role.SERIES_MANAGER]


async def _lonely_club() -> int:
    """A fresh club nobody organizes yet, so its first organizer is also its last."""
    async with SessionLocal() as session:
        club = Club(
            slug=f"einsam-{uuid4().hex[:6]}",
            name="Einsamer Segelverein",
            short_name="ESV",
            city="Nirgendwo",
        )
        session.add(club)
        await session.commit()
        return club.id
