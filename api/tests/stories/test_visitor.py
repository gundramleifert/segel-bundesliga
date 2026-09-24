"""User stories of a visitor to the public website.

Each test describes what someone wants to achieve — not what function is called.
If one fails, something is broken that people will notice on the website.
"""

import pytest

from app.pairing.pdf import renderer_available
from tests.pages import all_items
from tests.stories.test_create_event import admin, event_with_participants, league_clubs

# Printing goes through the Java tool; without it the rest of the story still holds. The
# same function the API answers `pdf_available` with, so this suite is asking "can this
# machine print?" exactly once rather than re-deriving it from a JAR path and a PATH scan.
_RENDERER_HERE = renderer_available()
needs_pairing_jar = pytest.mark.skipif(
    not _RENDERER_HERE, reason="Java runtime or pairing-list JAR not available"
)


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
        assert [row["rank"] for row in table["rows"]] == list(range(1, len(table["rows"]) + 1))

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
        detail = (await client.get(f"/api/events/{ids.event('dsbl-1-2026-act-1')}")).json()

        assert detail["event"]["status"] == "final"
        assert detail["races_total"] == 48
        assert detail["races_scored"] == 48
        assert len(detail["standings"]) == 18

    async def test_each_team_sailed_once_in_each_of_sixteen_flights(self, client, ids):
        detail = (await client.get(f"/api/events/{ids.event('dsbl-1-2026-act-1')}")).json()
        for row in detail["standings"]:
            assert row["races_scored"] == 16, f"{row['team']['name']} is missing a race"

    async def test_points_per_race_are_traceable(self, client, ids):
        """When someone clicks on the table, they want to see where the points come from."""
        detail = (await client.get(f"/api/events/{ids.event('dsbl-1-2026-act-1')}")).json()
        row = detail["standings"][0]

        assert len(row["points_by_race"]) == 16
        # Keys are race numbers from the matchday, not internal IDs.
        numbers = [int(n) for n in row["points_by_race"]]
        assert all(1 <= n <= 48 for n in numbers)
        assert sum(row["points_by_race"].values()) == pytest.approx(row["total"])

    async def test_without_discards_net_equals_total_points(self, client, ids):
        """At a Bundesliga matchday, races are sailed without discards."""
        detail = (await client.get(f"/api/events/{ids.event('dsbl-1-2026-act-1')}")).json()
        for row in detail["standings"]:
            assert row["net"] == row["total"]
            assert row["discarded_races"] == []

    async def test_live_matchday_shows_interim_standing(self, client, ids):
        detail = (await client.get(f"/api/events/{ids.event('dsbl-1-2026-act-2')}")).json()

        assert detail["event"]["status"] == "live"
        assert 0 < detail["races_scored"] < detail["races_total"]
        assert len(detail["standings"]) == 18

    async def test_planned_matchday_has_no_results_yet(self, client, ids):
        detail = (await client.get(f"/api/events/{ids.event('dsbl-1-2026-act-3')}")).json()

        assert detail["event"]["status"] == "planned"
        assert detail["races_scored"] == 0
        assert all(row["races_scored"] == 0 for row in detail["standings"])


class TestPairingList:
    """As a sailor, I want to know before the matchday when I sail on which boat."""

    async def test_pairing_list_covers_all_forty_eight_races(self, client, ids):
        pairing = (await client.get(f"/api/events/{ids.event('dsbl-1-2026-act-3')}/pairing")).json()

        assert len(pairing["races"]) == 48
        assert [r["sequence"] for r in pairing["races"]] == list(range(1, 49))

    async def test_boats_are_identified_by_their_color(self, client, ids):
        pairing = (await client.get(f"/api/events/{ids.event('dsbl-1-2026-act-3')}/pairing")).json()
        assert [b["color"] for b in pairing["boats"]] == [
            "BLACK",
            "GREEN",
            "DARKBLUE",
            "RED",
            "GRAY",
            "ORANGE",
        ]

    async def test_each_boat_is_assigned_exactly_once_in_each_race(self, client, ids):
        pairing = (await client.get(f"/api/events/{ids.event('dsbl-1-2026-act-3')}/pairing")).json()
        for race in pairing["races"]:
            assert sorted(int(n) for n in race["teams_by_boat"]) == [1, 2, 3, 4, 5, 6]

    async def test_each_team_sails_exactly_once_in_each_flight(self, client, ids):
        pairing = (await client.get(f"/api/events/{ids.event('dsbl-1-2026-act-3')}/pairing")).json()

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
        pairing = (await client.get(f"/api/events/{ids.event('dsbl-1-2026-act-3')}/pairing")).json()
        assert pairing["event"]["status"] == "planned"
        assert all(race["status"] == "scheduled" for race in pairing["races"])

    async def test_the_list_says_whether_it_can_be_printed_here(self, client, ids):
        """Story B-3: a deployment may carry no renderer, and the page has to know.

        Without this the site offers a download whose only possible answer is 503 — which
        is what the free test instance did until Java was put in its image.
        """
        pairing = (await client.get(f"/api/events/{ids.event('dsbl-1-2026-act-3')}/pairing")).json()

        assert pairing["pdf_available"] is _RENDERER_HERE

    @needs_pairing_jar
    async def test_the_list_can_be_taken_to_the_dock_on_paper(self, client, ids):
        """The sheet that gets printed and pinned up — Story B-3."""
        response = await client.get(f"/api/events/{ids.event('dsbl-1-2026-act-3')}/pairing.pdf")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "dsbl-1-2026-act-3-pairing-list.pdf" in response.headers["content-disposition"]
        assert response.content.startswith(b"%PDF")

    @needs_pairing_jar
    async def test_a_club_entered_after_the_draw_does_not_break_the_sheet(self, client, caplog):
        """The sheet prints the teams that were **drawn**; the entry list can have moved on.

        A club entered afterwards has no seat in the list. Printing the current entry list
        instead would name one club too many and shift every index along it — whole flights
        on the wrong boat, on the sheet people sail by.
        """
        headers = await admin(client, caplog, "latecomer@sbl.example.com")
        event_id = await event_with_participants(client, headers, "Late entry", "2026-08-22")
        drawn = await client.post(
            f"/api/admin/events/{event_id}/pairing/from-catalog",
            headers=headers,
            json={"seed": 3},
        )
        assert drawn.status_code == 200, drawn.text

        created = await client.post(
            "/api/admin/clubs",
            headers=headers,
            json={"name": "Seglerverein Nachzuegler", "short_name": "SVN", "city": "Spaethafen"},
        )
        assert created.status_code == 201, created.text
        entered = await client.put(
            f"/api/admin/events/{event_id}/clubs",
            headers=headers,
            json={"clubs": [*await league_clubs(client), created.json()["id"]]},
        )
        assert entered.status_code == 200, entered.text

        response = await client.get(f"/api/events/{event_id}/pairing.pdf")

        assert response.status_code == 200, response.text
        assert response.content.startswith(b"%PDF")

    @needs_pairing_jar
    async def test_a_crew_can_print_its_own_sheet(self, client, ids):
        """Story B-3: one club's page, not the file with a page for every club in it."""
        from app.text import slugify

        event_id = ids.event("dsbl-1-2026-act-1")
        pairing = (await client.get(f"/api/events/{event_id}/pairing")).json()
        team = next(iter(pairing["races"][0]["teams_by_boat"].values()))

        response = await client.get(f"/api/events/{event_id}/pairing.pdf?team={team['id']}")

        assert response.status_code == 200
        assert response.content.startswith(b"%PDF")
        assert slugify(team["name"]) in response.headers["content-disposition"], (
            "the file is named after the club, so downloads stay apart"
        )

    async def test_a_club_that_does_not_sail_here_gets_no_sheet(self, client, ids):
        """Refused before anything is rendered — no team, no page."""
        response = await client.get(
            f"/api/events/{ids.event('dsbl-1-2026-act-1')}/pairing.pdf?team=999999"
        )

        assert response.status_code == 404
        assert response.json()["type"] == "/errors/team-not-in-pairing-list"

    async def test_a_matchday_without_a_draw_has_nothing_to_print(self, client, caplog):
        """An event whose list has not been drawn yet: no empty sheet."""
        headers = await admin(client, caplog, "print@sbl.example.com")
        event_id = await event_with_participants(client, headers, "Nothing drawn yet", "2026-08-15")

        response = await client.get(f"/api/events/{event_id}/pairing.pdf")

        assert response.status_code == 404
        assert response.json()["type"] == "/errors/pairing-list-missing"


class TestMatchdayCrew:
    """B-12: As a visitor, I want to see who sails for each team at one matchday.

    Deliberately the **finished** matchday, not the planned one the pairing-list tests use.
    Its configuration is frozen (Story VA-8), so no other story can enter a further club in
    it, and nothing else in the suite rewrites its lineups — `test_lineup.py` and
    `test_sailors_and_squads.py` both work on act 3. A count asserted against act 3 is green
    on its own and red in the full run, which reads as a bug in this endpoint and is not.
    """

    MATCHDAY = "dsbl-1-2026-act-1"

    async def test_every_team_sailing_today_is_listed_with_its_crew(self, client, ids):
        from app.seed import CREW

        lineups = (await client.get(f"/api/events/{ids.event(self.MATCHDAY)}/crew")).json()

        assert len(lineups["teams"]) == 18, "Every team entered in the event belongs here"
        for entry in lineups["teams"]:
            assert entry["team"]["club"]["name"]
            assert len(entry["crew"]) == CREW
            # Helm first — the order a crew is announced, as in the squad.
            assert entry["crew"][0]["role"] == "helm"

    async def test_a_team_without_a_lineup_is_listed_with_an_empty_crew(self, client, caplog):
        """Nobody named yet is the answer, not a missing row.

        A team left out would read as "this club is not sailing here", which is false —
        it is entered, the crew is simply not set (same rule as the club page, B-7).
        """
        headers = await admin(client, caplog, "b12@example.com")
        event_id = await event_with_participants(client, headers, "Crew Cup", "2026-09-05")

        lineups = (await client.get(f"/api/events/{event_id}/crew")).json()

        assert len(lineups["teams"]) == 18
        assert all(entry["crew"] == [] for entry in lineups["teams"])

    async def test_the_lineup_is_readable_without_a_login(self, client, ids):
        """Participation is public — the pairing list carries these names anyway."""
        response = await client.get(f"/api/events/{ids.event(self.MATCHDAY)}/crew")

        assert response.status_code == 200
        assert response.json()["event"]["id"] == ids.event(self.MATCHDAY)

    async def test_the_lineup_reveals_no_contact_data(self, client, ids):
        """Names are on every results list; email and birth year are not."""
        lineups = (await client.get(f"/api/events/{ids.event(self.MATCHDAY)}/crew")).json()

        for entry in lineups["teams"]:
            for member in entry["crew"]:
                assert set(member) == {"id", "first_name", "last_name", "role"}

    async def test_a_draft_matchday_has_no_public_lineup(self, client, caplog):
        """Publication is orthogonal to everything else — a draft is a 404 (Story VA-8)."""
        headers = await admin(client, caplog, "b12draft@example.com")
        created = await client.post(
            "/api/admin/events",
            headers=headers,
            json={"title": "Unpublished Cup", "starts_on": "2026-09-19"},
        )
        assert created.status_code == 201, created.text

        response = await client.get(f"/api/events/{created.json()['id']}/crew")
        assert response.status_code == 404


class TestClubs:
    """As a visitor, I want to find the participating clubs."""

    async def test_all_participating_clubs_are_listed(self, client):
        """All 18 league clubs must appear.

        Deliberately no check for exactly 18: other stories add clubs, and the point here
        is that none of the league clubs are missing — not that there are no others.
        """
        from app.seed import CLUBS

        listed = {c["short_name"] for c in await all_items(client, "/api/clubs")}
        missing = {shortname for _, shortname, _ in CLUBS} - listed
        assert not missing, f"These clubs are missing: {sorted(missing)}"

    async def test_club_is_accessible_via_its_id(self, client):
        clubs = await all_items(client, "/api/clubs")
        response = await client.get(f"/api/clubs/{clubs[0]['id']}")
        assert response.status_code == 200
        assert response.json()["name"] == clubs[0]["name"]

    async def test_events_are_sorted_chronologically(self, client):
        events = await all_items(client, "/api/events")
        assert [e["starts_on"] for e in events] == sorted(e["starts_on"] for e in events)
