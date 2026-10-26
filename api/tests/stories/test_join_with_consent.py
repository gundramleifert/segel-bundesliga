"""Story V-15: a second club takes someone in only with consent, either way round.

The club's admin invites a person active in another club (``invited``), the person
accepts or declines in *Me › My clubs*; or the person asks (``requested``) and the club's
admin accepts or declines. Waiting rows grant nothing. Someone in another club without an
account could not answer, so only the league office adds them.

Each test works on fresh clubs and fresh people (docs/gotchas: counts against seed rows).
"""

from uuid import uuid4

from sqlalchemy import select

from app.db import SessionLocal
from app.models import AuditLog
from app.models.auth import Role
from tests.stories.test_club_members import _add, _club_with_admin, _fresh_club, _roster
from tests.stories.test_login_and_roles import _admin_headers, _headers, _problem_code, make_user

MINE = "/api/me/memberships"


def _tag() -> str:
    return uuid4().hex[:6]


async def _in_club(client, caplog, club: int, admin: dict[str, str]) -> tuple[str, dict]:
    """A fresh account, an active member of ``club``; returns its address and headers."""
    email = f"v15-{_tag()}@example.org"
    await make_user(email)
    headers = await _headers(client, caplog, email)
    await _add(client, admin, email, club)
    return email, headers


async def _mine(client, headers) -> dict[int, str]:
    response = await client.get(MINE, headers=headers)
    assert response.status_code == 200, response.text
    return {m["club_id"]: m["status"] for m in response.json()}


async def _todo(client, headers, kind: str, code: str, object_id: int | None = None) -> int:
    """The count of one to-do on one card of my space (0 when there is none)."""
    body = (await client.get("/api/me/contexts", headers=headers)).json()
    if kind == "me":
        needs = body["me"]["needs"]
    else:
        card = next(c for c in body["contexts"] if c["kind"] == kind and c["id"] == object_id)
        needs = card["needs"]
    return next((n["count"] for n in needs if n["code"] == code), 0)


class TestTheClubInvites:
    async def test_an_invitation_grants_nothing_until_accepted(self, client, caplog):
        """Story V-15: the second club's admin adds someone active elsewhere → invited;
        they are no member, their new club's organizers cannot change them, and the
        invitation is a to-do in *Me › My clubs* until they accept."""
        home, home_admin = await _club_with_admin(client, caplog, f"v15-ha-{_tag()}@example.org")
        second, second_admin = await _club_with_admin(
            client, caplog, f"v15-sa-{_tag()}@example.org"
        )
        email, me = await _in_club(client, caplog, home, home_admin)

        invited = await _add(client, second_admin, email, second)
        assert (invited["status"], invited["relations"]) == ("invited", [])
        assert await _mine(client, me) == {home: "active", second: "invited"}
        # Waiting grants nothing: no roster, and not the second club's to change.
        refused = await client.get(f"/api/clubs/{second}/members", headers=me)
        assert refused.status_code == 403, refused.text
        changed = await client.patch(
            f"/api/admin/people/{invited['person_id']}",
            headers=second_admin,
            json={"birth_date": "1990-01-01"},
        )
        assert changed.status_code == 403, changed.text
        assert await _todo(client, me, "me", "membership_invited") == 1
        # The club's admin sees the invitation waiting; its members do not.
        assert {
            m["person_id"]: m["status"] for m in await _roster(client, second_admin, second)
        } == {invited["person_id"]: "invited"}

        accepted = await client.post(f"{MINE}/{second}/accept", headers=me)
        assert accepted.status_code == 200, accepted.text
        assert await _mine(client, me) == {home: "active", second: "active"}
        assert await _todo(client, me, "me", "membership_invited") == 0
        names = [m["person_id"] for m in await _roster(client, me, second)]
        assert names == [invited["person_id"]]

    async def test_declining_deletes_the_invitation(self, client, caplog):
        """Story V-15: declined, the row is gone — the club may invite again."""
        home, home_admin = await _club_with_admin(client, caplog, f"v15-hb-{_tag()}@example.org")
        second, second_admin = await _club_with_admin(
            client, caplog, f"v15-sb-{_tag()}@example.org"
        )
        email, me = await _in_club(client, caplog, home, home_admin)
        await _add(client, second_admin, email, second)

        declined = await client.delete(f"{MINE}/{second}", headers=me)
        assert declined.status_code == 204, declined.text
        assert await _mine(client, me) == {home: "active"}
        assert (await _add(client, second_admin, email, second))["status"] == "invited"

    async def test_inviting_twice_is_refused(self, client, caplog):
        home, home_admin = await _club_with_admin(client, caplog, f"v15-hc-{_tag()}@example.org")
        second, second_admin = await _club_with_admin(
            client, caplog, f"v15-sc-{_tag()}@example.org"
        )
        email, _ = await _in_club(client, caplog, home, home_admin)
        await _add(client, second_admin, email, second)
        again = await client.post(
            f"/api/clubs/{second}/members", headers=second_admin, json={"email": email}
        )
        assert again.status_code == 409, again.text
        assert _problem_code(again) == "membership-exists"

    async def test_someone_without_an_account_takes_the_league_office(self, client, caplog):
        """Story V-15: a person in another club with no account could not accept — only
        the league office adds them to a second club."""
        home, home_admin = await _club_with_admin(client, caplog, f"v15-hd-{_tag()}@example.org")
        second, second_admin = await _club_with_admin(
            client, caplog, f"v15-sd-{_tag()}@example.org"
        )
        email = f"v15-kid-{_tag()}@example.org"
        created = await client.post(
            "/api/admin/people",
            headers=home_admin,
            json={"first_name": "Kim", "last_name": "Kind", "email": email, "club_id": home},
        )
        assert created.status_code == 201, created.text

        refused = await client.post(
            f"/api/clubs/{second}/members", headers=second_admin, json={"email": email}
        )
        assert refused.status_code == 409, refused.text
        assert _problem_code(refused) == "membership-needs-league-office"

        site = await _admin_headers(client, caplog, f"v15-site-{_tag()}@example.org")
        assert (await _add(client, site, email, second))["status"] == "active"


class TestThePersonAsks:
    async def test_the_clubs_admin_accepts_a_request(self, client, caplog):
        """Story V-15: I ask to join; the club's admin sees it as a to-do in its members
        section and accepts — a member now."""
        home, home_admin = await _club_with_admin(client, caplog, f"v15-he-{_tag()}@example.org")
        second, second_admin = await _club_with_admin(
            client, caplog, f"v15-se-{_tag()}@example.org"
        )
        _, me = await _in_club(client, caplog, home, home_admin)

        asked = await client.post(MINE, headers=me, json={"club_id": second})
        assert asked.status_code == 201, asked.text
        assert await _mine(client, me) == {home: "active", second: "requested"}
        assert await _todo(client, second_admin, "club", "membership_requested", second) == 1
        (waiting,) = await _roster(client, second_admin, second)
        assert waiting["status"] == "requested"

        accepted = await client.post(
            f"/api/clubs/{second}/members/{waiting['person_id']}/accept", headers=second_admin
        )
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["relations"] == ["member"]
        assert await _mine(client, me) == {home: "active", second: "active"}
        assert await _todo(client, second_admin, "club", "membership_requested", second) == 0

    async def test_someone_in_no_club_asks_the_same_way(self, client, caplog):
        """Story V-15: a person in no club may ask too (decided on #43); declined, the
        request is gone."""
        club, admin = await _club_with_admin(client, caplog, f"v15-hf-{_tag()}@example.org")
        email = f"v15-new-{_tag()}@example.org"
        await make_user(email)
        me = await _headers(client, caplog, email)

        assert (await client.post(MINE, headers=me, json={"club_id": club})).status_code == 201
        (waiting,) = await _roster(client, admin, club)
        declined = await client.delete(
            f"/api/clubs/{club}/members/{waiting['person_id']}", headers=admin
        )
        assert declined.status_code == 204, declined.text
        assert await _mine(client, me) == {}

    async def test_a_request_meets_an_invitation(self, client, caplog):
        """Story V-15: both sides want it — asking where I am invited accepts, and the
        club adding someone who asked accepts too."""
        home, home_admin = await _club_with_admin(client, caplog, f"v15-hg-{_tag()}@example.org")
        second, second_admin = await _club_with_admin(
            client, caplog, f"v15-sg-{_tag()}@example.org"
        )
        third, third_admin = await _club_with_admin(client, caplog, f"v15-tg-{_tag()}@example.org")
        email, me = await _in_club(client, caplog, home, home_admin)

        await _add(client, second_admin, email, second)
        assert (await client.post(MINE, headers=me, json={"club_id": second})).status_code == 201
        assert (await _mine(client, me))[second] == "active"

        await client.post(MINE, headers=me, json={"club_id": third})
        assert (await _add(client, third_admin, email, third))["status"] == "active"

    async def test_a_member_does_not_ask_again(self, client, caplog):
        club, admin = await _club_with_admin(client, caplog, f"v15-hh-{_tag()}@example.org")
        _, me = await _in_club(client, caplog, club, admin)
        again = await client.post(MINE, headers=me, json={"club_id": club})
        assert again.status_code == 409, again.text
        assert _problem_code(again) == "membership-exists"

    async def test_only_the_clubs_admin_accepts(self, client, caplog):
        """Story V-15: a club's manager decides who sails, not who is in."""
        club = await _fresh_club()
        manager = f"v15-mgr-{_tag()}@example.org"
        await make_user(manager, Role.TEAM_MANAGER, club_id=club)
        manager_headers = await _headers(client, caplog, manager)
        email = f"v15-ask-{_tag()}@example.org"
        await make_user(email)
        me = await _headers(client, caplog, email)
        await client.post(MINE, headers=me, json={"club_id": club})
        person = (await client.get("/api/people/me", headers=me)).json()["id"]

        refused = await client.post(
            f"/api/clubs/{club}/members/{person}/accept", headers=manager_headers
        )
        assert refused.status_code == 403, refused.text
        assert _problem_code(refused) == "membership-forbidden"


class TestEveryChangeIsLogged:
    async def test_invite_accept_and_leave_are_in_the_audit_log(self, client, caplog):
        """Story V-15: every change of a membership is in the audit log."""
        home, home_admin = await _club_with_admin(client, caplog, f"v15-hi-{_tag()}@example.org")
        second, second_admin = await _club_with_admin(
            client, caplog, f"v15-si-{_tag()}@example.org"
        )
        email, me = await _in_club(client, caplog, home, home_admin)
        person = (await _add(client, second_admin, email, second))["person_id"]
        await client.post(f"{MINE}/{second}/accept", headers=me)
        await client.delete(f"{MINE}/{second}", headers=me)

        async with SessionLocal() as session:
            actions = [
                row.action
                for row in (
                    await session.execute(
                        select(AuditLog)
                        .where(AuditLog.entity_type == "person", AuditLog.entity_id == person)
                        .order_by(AuditLog.id)
                    )
                ).scalars()
            ]
        assert actions == ["join_club", "invite", "accept", "end_membership"]
