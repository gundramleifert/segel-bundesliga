"""User-Story A-6: As admin, create a series and select clubs.

A series is a set of events scored together. When creating, you select from existing clubs
which ones participate — this generates the teams.
"""

from app.models.auth import Role
from tests.stories.test_login_and_roles import login_as, make_user


async def als(client, caplog, email: str, *rollen: str) -> dict[str, str]:
    await make_user(email, *rollen)
    return {"Authorization": f"Bearer {await login_as(client, email, caplog)}"}


async def clubs(client, count: int = 3) -> list[dict]:
    return (await client.get("/api/clubs")).json()[:count]


class TestSeriesCreation:
    async def test_name_and_year_suffice(self, client, caplog):
        headers = await als(client, caplog, "se1@example.com", Role.ADMIN)
        response = await client.post(
            "/api/admin/series",
            headers=headers,
            json={"name": "Test Series 2028", "year": 2028},
        )
        assert response.status_code == 201, response.text
        series = response.json()

        assert series["slug"] == "test-series-2028"
        assert series["year"] == 2028
        # Without its own abbreviation, the name is used.
        assert series["short_name"] == "Test Series 2028"
        assert series["clubs"] == []
        assert series["event_count"] == 0

    async def test_clubs_can_be_selected_immediately(self, client, caplog):
        headers = await als(client, caplog, "se2@example.com", Role.ADMIN)
        selected = await clubs(client, 3)

        response = await client.post(
            "/api/admin/series",
            headers=headers,
            json={
                "name": "Selection Series 2028",
                "year": 2028,
                "clubs": [v["id"] for v in selected],
            },
        )
        assert response.status_code == 201, response.text
        series = response.json()

        assert {c["id"] for c in series["clubs"]} == {v["id"] for v in selected}

    async def test_selected_clubs_appear_in_series(self, client, caplog):
        headers = await als(client, caplog, "se3@example.com", Role.ADMIN)
        selected = await clubs(client, 2)

        series = (
            await client.post(
                "/api/admin/series",
                headers=headers,
                json={
                    "name": "Visible Series 2026",
                    "year": 2026,
                    "clubs": [v["id"] for v in selected],
                },
            )
        ).json()

        public = (await client.get("/api/clubs", params={"series": series["id"]})).json()
        assert {c["id"] for c in public} == {v["id"] for v in selected}

    async def test_participants_can_be_changed_later(self, client, caplog):
        headers = await als(client, caplog, "se4@example.com", Role.ADMIN)
        all_clubs = await clubs(client, 4)

        series = (
            await client.post(
                "/api/admin/series",
                headers=headers,
                json={"name": "Changing Series 2028", "year": 2028,
                      "clubs": [all_clubs[0]["id"], all_clubs[1]["id"]]},
            )
        ).json()

        changed = await client.put(
            f"/api/admin/series/{series['id']}/clubs",
            headers=headers,
            json={"clubs": [all_clubs[2]["id"], all_clubs[3]["id"]]},
        )
        assert changed.status_code == 200
        club_ids = {c["id"] for c in changed.json()["clubs"]}
        assert club_ids == {all_clubs[2]["id"], all_clubs[3]["id"]}

    async def test_club_with_results_cannot_be_removed(self, client, caplog, ids):
        """Results are attached to a team that raced under it."""
        headers = await als(client, caplog, "se5@example.com", Role.ADMIN)

        response = await client.put(
            f"/api/admin/series/{ids.series('dsbl-1-2026')}/clubs",
            headers=headers,
            json={"clubs": []},
        )
        assert response.status_code == 409
        assert "race results" in response.json()["detail"]

    async def test_unknown_club_is_reported(self, client, caplog):
        headers = await als(client, caplog, "se6@example.com", Role.ADMIN)
        response = await client.post(
            "/api/admin/series",
            headers=headers,
            json={"name": "Wrong Series 2028", "year": 2028, "clubs": [999999]},
        )
        assert response.status_code == 404
        assert "999999" in response.json()["detail"]

    async def test_taken_url_is_detected(self, client, caplog):
        headers = await als(client, caplog, "se7@example.com", Role.ADMIN)
        data = {"name": "Duplicate Series 2028", "year": 2028}
        assert (
            await client.post("/api/admin/series", headers=headers, json=data)
        ).status_code == 201

        second = await client.post("/api/admin/series", headers=headers, json=data)
        assert second.status_code == 409
        assert "taken" in second.json()["detail"]

    async def test_admin_sees_all_years(self, client, caplog):
        """They plan ahead — not just the current year counts."""
        headers = await als(client, caplog, "se8@example.com", Role.ADMIN)
        await client.post(
            "/api/admin/series",
            headers=headers,
            json={"name": "Future 2030", "year": 2030},
        )

        all_series = (await client.get("/api/admin/series", headers=headers)).json()
        years = {s["year"] for s in all_series}
        assert 2026 in years and 2030 in years

        # Publicly, only the current year appears.
        public = {s["year"] for s in (await client.get("/api/series")).json()}
        assert public == {2026}

    async def test_description_round_trips_through_the_api(self, client, caplog):
        """The free-text, Markdown description is set on creation and can be edited."""
        headers = await als(client, caplog, "se11@example.com", Role.ADMIN)
        series = (
            await client.post(
                "/api/admin/series",
                headers=headers,
                json={
                    "name": "Described Series 2028",
                    "year": 2028,
                    "description": "## Welcome\n\nSee you on the water.",
                },
            )
        ).json()
        assert series["description"] == "## Welcome\n\nSee you on the water."

        changed = await client.patch(
            f"/api/admin/series/{series['id']}",
            headers=headers,
            json={"description": "Updated text."},
        )
        assert changed.status_code == 200
        assert changed.json()["description"] == "Updated text."

        table = await client.get(f"/api/series/{series['id']}/table")
        assert table.status_code == 200
        assert table.json()["series"]["description"] == "Updated text."

    async def test_series_can_be_renamed(self, client, caplog):
        headers = await als(client, caplog, "se9@example.com", Role.ADMIN)
        series = (
            await client.post(
                "/api/admin/series",
                headers=headers,
                json={"name": "Provisional 2028", "year": 2028},
            )
        ).json()

        changed = await client.patch(
            f"/api/admin/series/{series['id']}",
            headers=headers,
            json={"name": "Final 2028", "level": 1},
        )
        assert changed.status_code == 200
        assert changed.json()["name"] == "Final 2028"
        assert changed.json()["level"] == 1

    async def test_editors_cannot_create_series(self, client, caplog):
        headers = await als(client, caplog, "se10@example.com", Role.EDITOR)
        response = await client.post(
            "/api/admin/series",
            headers=headers,
            json={"name": "Forbidden Series 2028", "year": 2028},
        )
        assert response.status_code == 403

    async def test_unauthenticated_access_fails(self, client):
        response = await client.post(
            "/api/admin/series", json={"name": "Anonymous Series 2028", "year": 2028}
        )
        assert response.status_code == 401
