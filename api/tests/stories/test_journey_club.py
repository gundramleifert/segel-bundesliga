"""A new club gets going and runs itself — the whole way once, through the HTTP API.

Journey J-2 (``docs/journeys/club.md``) — each ``step(...)`` below is one of its steps, in
the table's order; Stories A-1, A-7, A-8, Z-8, V-3, V-5, A-9, B-7. Every step is tested on
its own elsewhere (``test_master_data.py``, ``test_club_members.py``,
``test_club_crest.py``, ``test_participation.py``); this test is the order: the club the
league office creates is the one its admin then runs, the manager the admin names is the
one who may apply, and the acceptance is what makes it public.

A fresh club and fresh addresses, so it runs beside the rest of the suite.
"""

import io
from uuid import uuid4

from PIL import Image

from tests.journeys import step
from tests.pages import all_items
from tests.stories.test_create_event import admin
from tests.stories.test_login_and_roles import login_as
from tests.stories.test_registration import auth_headers, register


def _crest() -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", (300, 200), (12, 84, 160, 255)).save(buf, format="PNG")
    return buf.getvalue()


class TestANewClubRunsItself:
    """Journey J-2: as the association I want a club set up once and then running itself."""

    async def test_from_nothing_to_a_public_club(self, client, caplog, ids):
        tag = uuid4().hex[:6]
        office = await admin(client, caplog, f"office-{tag}@example.com")
        admin_email = f"chair-{tag}@example.com"
        manager_email = f"sport-{tag}@example.com"
        # The future team manager registered on their own (Story Z-4, Journey J-3).
        await register(client, caplog, manager_email, "Sam Sport")

        step("J-2.1", "league office creates the club")
        created = await client.post(
            "/api/admin/clubs",
            headers=office,
            json={"name": f"Segelclub Neustart {tag}", "short_name": f"SCN{tag}", "city": "Plön"},
        )
        assert created.status_code == 201, created.text
        club = created.json()
        club_id = club["id"]

        step("J-2.2", "the club is not public — it competes nowhere yet")
        assert club["slug"] not in {c["slug"] for c in await all_items(client, "/api/clubs")}
        listed = await all_items(client, "/api/admin/clubs", headers=office)
        assert club_id in {c["id"] for c in listed}

        step("J-2.3", "league office creates the first account and makes it the club's admin")
        account = await client.post(
            "/api/auth/users",
            headers=office,
            json={"email": admin_email, "display_name": "Clara Chair"},
        )
        assert account.status_code == 201, account.text
        granted = await client.post(
            "/api/auth/tuples",
            headers=office,
            json={"user": admin_email, "relation": "admin", "object": f"club:{club_id}"},
        )
        assert granted.status_code == 201, granted.text
        club_admin = auth_headers(await login_as(client, admin_email, caplog))

        step("J-2.4", "the club admin finds the club in my space")
        mine = (await client.get("/api/me/contexts", headers=club_admin)).json()
        card = next(c for c in mine["contexts"] if c["kind"] == "club" and c["id"] == club_id)
        assert "admin" in card["relations"]

        step("J-2.5", "the club admin uploads the crest")
        uploaded = await client.post(
            f"/api/admin/clubs/{club_id}/logo",
            headers=club_admin,
            files={"file": ("stander.png", _crest(), "image/png")},
        )
        assert uploaded.status_code == 200, uploaded.text
        assert uploaded.json()["logo_url"].startswith(f"/api/clubs/{club_id}/logo?v=")
        assert (await client.get(f"/api/clubs/{club_id}/logo")).status_code == 200

        step("J-2.6", "the only organizer cannot step down")
        me = (await client.get("/api/auth/me", headers=club_admin)).json()
        own = next(
            t for t in me["tuples"] if t["relation"] == "admin" and t["object"] == f"club:{club_id}"
        )
        refused = await client.delete(f"/api/auth/tuples/{own['id']}", headers=club_admin)
        assert refused.status_code == 409, refused.text
        assert refused.json()["type"].endswith("/last-organizer")

        step("J-2.7", "the club admin names the team manager by email")
        named = await client.post(
            "/api/auth/tuples",
            headers=club_admin,
            json={"user": manager_email, "relation": "manager", "object": f"club:{club_id}"},
        )
        assert named.status_code == 201, named.text
        team_manager = auth_headers(await login_as(client, manager_email, caplog))

        step("J-2.8", "the team manager applies for the series")
        series_id = ids.series("junioren-2026")
        applied = await client.post(
            "/api/applications",
            headers=team_manager,
            json={"club_id": club_id, "series_id": series_id},
        )
        assert applied.status_code in (200, 201), applied.text
        application = applied.json()
        assert application["status"] == "requested"
        # An application counts nowhere yet.
        assert club["slug"] not in {c["slug"] for c in await all_items(client, "/api/clubs")}

        step("J-2.9", "league office accepts the application")
        accepted = await client.post(
            f"/api/admin/applications/{application['team_id']}/accept", headers=office
        )
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["status"] == "accepted"

        step("J-2.10", "a visitor finds the club and opens its page")
        assert club["slug"] in {c["slug"] for c in await all_items(client, "/api/clubs")}
        page = await client.get(f"/api/clubs/{club_id}")
        assert page.status_code == 200, page.text
        assert series_id in {team["series"]["id"] for team in page.json()["teams"]}
