"""A sailor joins their club: from no account at all to a member with a sailor record.

Every step is covered on its own elsewhere — registering in ``test_registration.py``, the
password in ``test_password_login.py``, membership and the roster in
``test_club_members.py``, my space in ``test_my_space.py``, the sailor record in
``test_sailors_and_squads.py`` and ``test_sailor_profile.py``. What this adds is the
**order**: the club manager cannot add someone before they register, the account a person
registers is the one the membership lands on, and the sailor record a club manager
creates later is the one the person then edits — linked by nothing but the verified
address.

Journey J-3 (``docs/journeys/member.md``) — each ``step(...)`` below is one of its steps,
in the table's order, the branches included; Stories V-9, Z-4, Z-9, Z-5, Z-8, V-10, V-4,
S-2.
"""

import logging
from uuid import uuid4

from app.models.auth import Role
from tests.journeys import step
from tests.stories.test_club_members import _fresh_club
from tests.stories.test_login_and_roles import _headers, latest_code, make_user
from tests.stories.test_registration import account, auth_headers

PASSWORD = "a long enough password for the pontoon"


class TestASailorJoinsTheirClub:
    """As a club I want a new sailor to become a member with their own sailor record."""

    async def test_from_no_account_to_a_member_with_a_sailor_record(self, client, caplog):
        tag = uuid4().hex[:8]
        club = await _fresh_club()
        await make_user(f"j3-admin-{tag}@example.com", Role.CLUB_ADMIN, club_id=club)
        await make_user(f"j3-manager-{tag}@example.com", Role.CLUB_MANAGER, club_id=club)
        club_admin = await _headers(client, caplog, f"j3-admin-{tag}@example.com")
        club_manager = await _headers(client, caplog, f"j3-manager-{tag}@example.com")
        email = f"j3-nina-{tag}@example.com"
        membership = {"user": email, "relation": "member", "object": f"club:{club}"}

        step("J-3.1", "the club manager adds the person before they have an account — not found")
        refused = await client.post("/api/auth/tuples", headers=club_admin, json=membership)
        assert refused.status_code == 404, refused.text
        assert await account(email) is None

        step("J-3.2", "the person registers with email and name")
        with caplog.at_level(logging.WARNING, logger="app.mail"):
            registered = await client.post(
                "/api/auth/register", json={"email": email, "display_name": "Nina Neu"}
            )
        assert registered.status_code == 202, registered.text
        code = caplog.records[-1].args[-1]
        claimed = await account(email)
        assert claimed is not None and claimed.email_verified is False
        assert await latest_code(email) is not None

        step("J-3.3", "the person redeems the code; verified, no role, no club")
        redeemed = await client.post("/api/auth/email/verify", json={"email": email, "code": code})
        assert redeemed.status_code == 200, redeemed.text
        person = auth_headers(redeemed.json()["access_token"])
        me = (await client.get("/api/auth/me", headers=person)).json()
        assert me["email_verified"] is True
        assert me["roles"] == [] and me["tuples"] == []

        step("J-3.4", "the person sets a password and signs in with it")
        set_password = await client.put(
            "/api/auth/password", headers=person, json={"new_password": PASSWORD}
        )
        assert set_password.status_code == 204, set_password.text
        signed_in = await client.post(
            "/api/auth/password/login", json={"email": email, "password": PASSWORD}
        )
        assert signed_in.status_code == 200, signed_in.text
        person = auth_headers(signed_in.json()["access_token"])

        step("J-3.5", "the club manager adds the person as a member, by email")
        added = await client.post("/api/auth/tuples", headers=club_admin, json=membership)
        assert added.status_code == 201, added.text
        assert (added.json()["relation"], added.json()["object"]) == ("member", f"club:{club}")

        step("J-3.6", "the new member finds the club in my space")
        contexts = await client.get("/api/me/contexts", headers=person)
        assert contexts.status_code == 200, contexts.text
        card = next(
            c for c in contexts.json()["contexts"] if c["kind"] == "club" and c["id"] == club
        )
        assert card["relations"] == ["member"]
        # Membership creates no sailor record — that is the club manager's step.
        unlinked = await client.get("/api/sailors/me", headers=person)
        assert unlinked.status_code == 404, unlinked.text
        assert unlinked.json()["type"].endswith("/no-linked-sailor-record")

        step("J-3.7", "the member sees the roster — names, no email")
        roster = await client.get(f"/api/clubs/{club}/members", headers=person)
        assert roster.status_code == 200, roster.text
        assert "Nina Neu" in {m["display_name"] for m in roster.json()}
        assert all("email" not in m for m in roster.json())

        step("J-3.8", "the club manager creates the sailor record with email and date of birth")
        created = await client.post(
            "/api/admin/sailors",
            headers=club_manager,
            json={
                "first_name": "Nina",
                "last_name": "Neuu",
                "email": email.upper(),
                "birth_date": "2001-04-03",
            },
        )
        assert created.status_code == 201, created.text
        assert created.json()["email"] == email

        step("J-3.9", "the member corrects their own name and date of birth")
        mine = await client.get("/api/sailors/me", headers=person)
        assert mine.status_code == 200, mine.text
        assert mine.json()["id"] == created.json()["id"]
        corrected = await client.patch(
            "/api/sailors/me",
            headers=person,
            json={"last_name": "Neu", "birth_date": "2001-03-04"},
        )
        assert corrected.status_code == 200, corrected.text
        assert (corrected.json()["last_name"], corrected.json()["birth_date"]) == (
            "Neu",
            "2001-03-04",
        )

        step("J-3.10", "the member leaves the club by deleting their own tuple")
        me = (await client.get("/api/auth/me", headers=person)).json()
        own = next(
            t for t in me["tuples"] if t["relation"] == "member" and t["object"] == f"club:{club}"
        )
        left = await client.delete(f"/api/auth/tuples/{own['id']}", headers=person)
        assert left.status_code == 204, left.text
        contexts = (await client.get("/api/me/contexts", headers=person)).json()["contexts"]
        assert not any(c["kind"] == "club" and c["id"] == club for c in contexts)
        # The sailor record is the person's, not the club's — it stays.
        assert (await client.get("/api/sailors/me", headers=person)).status_code == 200
