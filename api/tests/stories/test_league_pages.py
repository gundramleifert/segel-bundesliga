"""User stories of the league pages — the public site's top level (docs/site-structure.md).

Each test describes what someone wants to achieve — not what function is called.
"""

from tests.stories.test_create_event import admin


class TestLeagueSeason:
    """As a fan, I want a league's page to show its current year — Story B-14."""

    async def test_the_leagues_are_listed_in_the_order_of_the_top_row(self, client):
        """B-14: the top row names whatever leagues exist, in their set order."""
        response = await client.get("/api/leagues")
        assert response.status_code == 200
        assert [league["slug"] for league in response.json()][:4] == [
            "1-liga",
            "2-liga",
            "junioren-liga",
            "dsl-pokal",
        ]

    async def test_the_first_and_second_division_are_two_leagues(self, client):
        """B-14: the 1. and 2. Liga are each a league of their own, one series a year.

        Its events are the year's, in date order, each with its matchday — an act is the
        events that share one.
        """
        season = (await client.get("/api/leagues/1-liga")).json()

        assert season["league"]["short_name"] == "1. Liga"
        assert season["year"] == 2026
        assert [s["slug"] for s in season["series"]] == ["dsbl-1-2026"]
        assert 2026 in season["years"]

        events = season["events"]
        assert events, "the seed sails acts in the 1. Liga"
        assert all(e["matchday"] is not None for e in events)
        dates = [e["starts_on"] for e in events]
        assert dates == sorted(dates)
        assert {e["series"]["league_id"] for e in events} == {season["league"]["id"]}

        second = (await client.get("/api/leagues/2-liga")).json()
        assert [s["slug"] for s in second["series"]] == ["dsbl-2-2026"]
        assert second["series"][0]["level"] == 2
        assert (await client.get("/api/leagues/dsbl")).status_code == 404

    async def test_an_unknown_league_is_not_found(self, client):
        response = await client.get("/api/leagues/no-such-league")
        assert response.status_code == 404
        assert response.json()["type"].endswith("/league-not-found")

    async def test_a_league_without_series_is_an_empty_year_not_an_error(self, client):
        """B-14: the DSL-Pokal's page exists before anyone has set up its series."""
        season = (await client.get("/api/leagues/dsl-pokal")).json()
        assert season["series"] == []
        assert season["events"] == []

    async def test_a_draft_series_stays_off_the_league_page(self, client, caplog):
        """B-14, VA-8: next year's series is planned in the league long before it shows."""
        headers = await admin(client, caplog, "league-draft@sbl.example.com")
        first = next(
            league
            for league in (await client.get("/api/leagues")).json()
            if league["slug"] == "1-liga"
        )
        created = await client.post(
            "/api/admin/series",
            json={"name": "1. Segel-Bundesliga 2025 Draft", "year": 2025, "league_id": first["id"]},
            headers=headers,
        )
        assert created.status_code == 201, created.text

        season = (await client.get("/api/leagues/1-liga")).json()
        assert 2025 not in season["years"]
        assert (await client.get("/api/leagues/1-liga?year=2025")).json()["series"] == []

    async def test_a_series_cannot_name_a_league_that_does_not_exist(self, client, caplog):
        headers = await admin(client, caplog, "league-missing@sbl.example.com")
        response = await client.post(
            "/api/admin/series",
            json={"name": "Nowhere League 2026", "year": 2026, "league_id": 999999},
            headers=headers,
        )
        assert response.status_code == 422
        assert response.json()["type"].endswith("/league-not-found")
