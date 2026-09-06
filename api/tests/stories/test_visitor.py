"""User stories of a visitor to the public website.

Each test describes what someone wants to achieve — not what function is called.
If one fails, something is broken that people will notice on the website.
"""

import pytest


class TestSeriesTable:
    """As a fan, I want to see how my team stands in the series."""

    async def test_table_lists_all_teams_without_gaps(self, client, ids):
        """At least the 18 from the seed; other stories add more.

        Deliberately no check for exactly 18: the point is that ranks are numbered
        continuously from one — not how many there are right now.
        """
        response = await client.get(f"/api/series/{ids.series('dsbl-1-2026')}/table")
        assert response.status_code == 200

        table = response.json()
        assert len(table["rows"]) >= 18
        assert [row["rank"] for row in table["rows"]] == list(
            range(1, len(table["rows"]) + 1)
        )

    async def test_fewer_points_means_higher_position(self, client, ids):
        """Sailing scoring is low-point scoring: lower is better."""
        table = (await client.get(f"/api/series/{ids.series('dsbl-1-2026')}/table")).json()
        punkte = [row["points"] for row in table["rows"]]
        assert punkte == sorted(punkte)

    async def test_table_shows_placement_for_each_sailed_matchday(self, client, ids):
        table = (await client.get(f"/api/series/{ids.series('dsbl-1-2026')}/table")).json()
        for row in table["rows"]:
            # Two matchdays have been sailed, the third is planned.
            assert sorted(row["ranks_by_matchday"]) == ["1", "2"]

    async def test_unraced_matchday_is_not_included(self, client, ids):
        table = (await client.get(f"/api/series/{ids.series('dsbl-1-2026')}/table")).json()
        planned = [m for m in table["events"] if m["status"] == "planned"]
        assert planned, "The seed should contain a planned matchday"
        for row in table["rows"]:
            assert str(planned[0]["matchday"]) not in row["ranks_by_matchday"]

    async def test_unknown_series_reports_clearly(self, client):
        response = await client.get("/api/series/999999/table")
        assert response.status_code == 404
        assert "999999" in response.json()["detail"]


class TestMatchdayResult:
    """As a fan, I want to look up how a matchday turned out."""

    async def test_sailed_matchday_shows_complete_event_standing(self, client, ids):
        detail = (
            await client.get(f"/api/events/{ids.event('dsbl-1-2026-act-1')}")
        ).json()

        assert detail["event"]["status"] == "final"
        assert detail["races_total"] == 48
        assert detail["races_scored"] == 48
        assert len(detail["standings"]) == 18

    async def test_each_team_sailed_once_in_each_of_sixteen_flights(self, client, ids):
        detail = (
            await client.get(f"/api/events/{ids.event('dsbl-1-2026-act-1')}")
        ).json()
        for row in detail["standings"]:
            assert row["races_scored"] == 16, f"{row['team']['name']} is missing a race"

    async def test_points_per_race_are_traceable(self, client, ids):
        """When someone clicks on the table, they want to see where the points come from."""
        detail = (
            await client.get(f"/api/events/{ids.event('dsbl-1-2026-act-1')}")
        ).json()
        row = detail["standings"][0]

        assert len(row["points_by_race"]) == 16
        # Keys are race numbers from the matchday, not internal IDs.
        numbers = [int(n) for n in row["points_by_race"]]
        assert all(1 <= n <= 48 for n in numbers)
        assert sum(row["points_by_race"].values()) == pytest.approx(row["total"])

    async def test_without_discards_net_equals_total_points(self, client, ids):
        """At a Bundesliga matchday, races are sailed without discards."""
        detail = (
            await client.get(f"/api/events/{ids.event('dsbl-1-2026-act-1')}")
        ).json()
        for row in detail["standings"]:
            assert row["net"] == row["total"]
            assert row["discarded_races"] == []

    async def test_live_matchday_shows_interim_standing(self, client, ids):
        detail = (
            await client.get(f"/api/events/{ids.event('dsbl-1-2026-act-2')}")
        ).json()

        assert detail["event"]["status"] == "live"
        assert 0 < detail["races_scored"] < detail["races_total"]
        assert len(detail["standings"]) == 18

    async def test_planned_matchday_has_no_results_yet(self, client, ids):
        detail = (
            await client.get(f"/api/events/{ids.event('dsbl-1-2026-act-3')}")
        ).json()

        assert detail["event"]["status"] == "planned"
        assert detail["races_scored"] == 0
        assert all(row["races_scored"] == 0 for row in detail["standings"])


class TestPairingList:
    """As a sailor, I want to know before the matchday when I sail on which boat."""

    async def test_pairing_list_covers_all_forty_eight_races(self, client, ids):
        pairing = (
            await client.get(f"/api/events/{ids.event('dsbl-1-2026-act-3')}/pairing")
        ).json()

        assert len(pairing["races"]) == 48
        assert [r["sequence"] for r in pairing["races"]] == list(range(1, 49))

    async def test_boats_are_identified_by_their_color(self, client, ids):
        pairing = (
            await client.get(f"/api/events/{ids.event('dsbl-1-2026-act-3')}/pairing")
        ).json()
        assert [b["color"] for b in pairing["boats"]] == [
            "BLACK", "GREEN", "DARKBLUE", "RED", "GRAY", "ORANGE"
        ]

    async def test_each_boat_is_assigned_exactly_once_in_each_race(self, client, ids):
        pairing = (
            await client.get(f"/api/events/{ids.event('dsbl-1-2026-act-3')}/pairing")
        ).json()
        for race in pairing["races"]:
            assert sorted(int(n) for n in race["teams_by_boat"]) == [1, 2, 3, 4, 5, 6]

    async def test_each_team_sails_exactly_once_in_each_flight(self, client, ids):
        pairing = (
            await client.get(f"/api/events/{ids.event('dsbl-1-2026-act-3')}/pairing")
        ).json()

        by_flight: dict[int, list[int]] = {}
        for race in pairing["races"]:
            for team in race["teams_by_boat"].values():
                by_flight.setdefault(race["flight"], []).append(team["id"])

        assert len(by_flight) == 16
        for flight, teams in by_flight.items():
            assert len(teams) == 18, f"Flight {flight} is not a complete round"
            assert len(set(teams)) == 18, f"Flight {flight} has a team twice"

    async def test_pairing_list_is_ready_before_matchday(self, client, ids):
        """Draw is one week prior — the list must be retrievable without results."""
        pairing = (
            await client.get(f"/api/events/{ids.event('dsbl-1-2026-act-3')}/pairing")
        ).json()
        assert pairing["event"]["status"] == "planned"
        assert all(race["status"] == "scheduled" for race in pairing["races"])


class TestClubs:
    """As a visitor, I want to find the participating clubs."""

    async def test_all_participating_clubs_are_listed(self, client):
        """All 18 league clubs must appear.

        Deliberately no check for exactly 18: other stories add clubs, and the point here
        is that none of the league clubs are missing — not that there are no others.
        """
        from app.seed import CLUBS

        listed = {c["short_name"] for c in (await client.get("/api/clubs")).json()}
        missing = {shortname for _, shortname, _ in CLUBS} - listed
        assert not missing, f"These clubs are missing: {sorted(missing)}"

    async def test_club_is_accessible_via_its_id(self, client):
        clubs = (await client.get("/api/clubs")).json()
        response = await client.get(f"/api/clubs/{clubs[0]['id']}")
        assert response.status_code == 200
        assert response.json()["name"] == clubs[0]["name"]

    async def test_events_are_sorted_chronologically(self, client):
        events = (await client.get("/api/events")).json()
        assert [e["starts_on"] for e in events] == sorted(e["starts_on"] for e in events)
