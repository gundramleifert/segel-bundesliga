"""An organizer sets up a series, from the league office's draft to the public table.

Journey J-4 (``docs/journeys/series.md``) — each ``step(...)`` below is one of its steps,
in the table's order. Every step is covered on its own elsewhere — the series in
``test_create_series.py``, the tuple in ``test_login_and_roles.py``, applications in
``test_participation.py``, the event in ``test_create_event.py``; what this test proves is
the hand-over: the league office creates the series and names its manager, and from then
on the **series manager** does the rest with the one `manager` tuple — dates, clubs, the
first matchday, the applications, publication. Stories A-6, Z-2, V-5, A-9, VA-6, VA-8, B-1.

Through the HTTP API only. Year 2026, the current one, and no league: a series in no league
keeps its own page and leaves the league pages other tests read alone.
"""

from uuid import uuid4

from app.models.auth import Role
from tests.journeys import step
from tests.pages import all_items
from tests.stories.test_create_event import admin
from tests.stories.test_login_and_roles import login_as, make_user
from tests.stories.test_registration import auth_headers


class TestAnOrganizerSetsUpASeries:
    """As the association I want a series handed to its own organizer, who sets it up."""

    async def test_from_a_draft_to_the_public_table(self, client, caplog):
        tag = uuid4().hex[:6]
        office = await admin(client, caplog, f"j4-office-{tag}@example.com")

        clubs = []
        for n in range(3):
            created = await client.post(
                "/api/admin/clubs",
                headers=office,
                json={"name": f"J4 Club {n} {tag}", "short_name": f"J4{n}{tag}", "city": "Kiel"},
            )
            assert created.status_code == 201, created.text
            clubs.append(created.json()["id"])

        # -------------------------------------------------------------- the draft (A-6)
        step("J-4.1", "league office creates the series as a draft, with its squad limits")
        created = await client.post(
            "/api/admin/series",
            headers=office,
            json={"name": f"Club Cup {tag} 2026", "year": 2026, "squad_min": 5, "squad_max": 8},
        )
        assert created.status_code == 201, created.text
        series = created.json()
        series_id = series["id"]
        assert series["published"] is False
        assert (series["squad_min"], series["squad_max"]) == (5, 8)
        assert series["clubs"] == []
        # A draft does not exist publicly (Story VA-8).
        assert (await client.get(f"/api/series/{series_id}/table")).status_code == 404

        # ------------------------------------------------------ its manager (Z-2)
        step("J-4.2", "league office names the series manager")
        manager_email = f"j4-manager-{tag}@example.com"
        await make_user(manager_email)
        written = await client.post(
            "/api/auth/tuples",
            headers=office,
            json={"user": manager_email, "relation": "manager", "object": f"series:{series_id}"},
        )
        assert written.status_code == 201, written.text
        manager = auth_headers(await login_as(client, manager_email, caplog))
        me = (await client.get("/api/auth/me", headers=manager)).json()
        assert "series_manager" in me["roles"]

        # --------------------------------------------- dates and clubs (A-6)
        step("J-4.3", "series manager sets the dates and the clubs")
        # Their admin list is narrowed to the one series they hold.
        theirs = await all_items(client, "/api/admin/series", headers=manager)
        assert [s["id"] for s in theirs] == [series_id]
        dated = await client.patch(
            f"/api/admin/series/{series_id}",
            headers=manager,
            json={"starts_on": "2026-06-01", "ends_on": "2026-09-30"},
        )
        assert dated.status_code == 200, dated.text
        assert dated.json()["starts_on"] == "2026-06-01"
        chosen = await client.put(
            f"/api/admin/series/{series_id}/clubs", headers=manager, json={"clubs": clubs[:2]}
        )
        assert chosen.status_code == 200, chosen.text
        assert {c["id"] for c in chosen.json()["clubs"]} == set(clubs[:2])
        # Creating a series stays the league office's.
        refused = await client.post(
            "/api/admin/series", headers=manager, json={"name": f"Own Cup {tag}", "year": 2026}
        )
        assert refused.status_code == 403

        # ------------------------------------------- a club applies (V-5)
        step("J-4.4", "a team manager applies for the series")
        team_manager_email = f"j4-club-{tag}@example.com"
        await make_user(team_manager_email, Role.TEAM_MANAGER, club_id=clubs[2])
        team_manager = auth_headers(await login_as(client, team_manager_email, caplog))
        applied = await client.post(
            "/api/applications",
            headers=team_manager,
            json={"club_id": clubs[2], "series_id": series_id},
        )
        assert applied.status_code == 201, applied.text
        application = applied.json()
        assert application["status"] == "requested"
        # Requested is nothing yet: not among the series' clubs.
        listed = await all_items(client, "/api/admin/series", headers=manager)
        assert clubs[2] not in {c["id"] for c in listed[0]["clubs"]}

        # ------------------------------------ the series manager decides (A-9)
        step("J-4.5", "series manager accepts the application")
        accepted = await client.post(
            f"/api/admin/applications/{application['team_id']}/accept", headers=manager
        )
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["status"] == "accepted"
        listed = await all_items(client, "/api/admin/series", headers=manager)
        assert {c["id"] for c in listed[0]["clubs"]} == set(clubs)

        # ------------------------------------------ the first matchday (VA-6)
        step("J-4.6", "series manager creates the first matchday, hosted by a club")
        event = await client.post(
            "/api/admin/events",
            headers=manager,
            json={
                "title": f"Club Cup {tag} — Act 1",
                "starts_on": "2026-06-13",
                "series": series_id,
                "host_club_id": clubs[0],
                "team_count": 3,
            },
        )
        assert event.status_code in (200, 201), event.text
        event_id = event.json()["id"]
        assert event.json()["matchday"] == 1
        # The series' registrations are the event's entries — the accepted club among them.
        entries = await client.get(f"/api/admin/events/{event_id}/clubs", headers=manager)
        assert entries.status_code == 200, entries.text
        assert {e["club"]["id"] for e in entries.json()} == set(clubs)
        assert {e["status"] for e in entries.json()} == {"accepted"}

        # ------------------------------------------------ publication (VA-8)
        step("J-4.7", "series manager publishes the series")
        published = await client.post(f"/api/admin/series/{series_id}/publish", headers=manager)
        assert published.status_code == 200, published.text
        assert published.json()["published"] is True

        # ------------------------------------------------- the public (B-1)
        step("J-4.8", "a visitor finds the series of the year and opens its table")
        public = (await client.get("/api/series", params={"year": 2026})).json()
        assert series_id in {s["id"] for s in public}
        table = await client.get(f"/api/series/{series_id}/table")
        assert table.status_code == 200, table.text
        assert table.json()["series"]["name"] == f"Club Cup {tag} 2026"
