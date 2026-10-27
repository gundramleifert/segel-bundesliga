"""A fan follows an act, from the league's page to the crews, a sailor and the standings.

Journey J-9 (``docs/journeys/fan.md``) — each ``step(...)`` below is one of its steps, in
the table's order. Every step is covered on its own elsewhere — the league page in
``test_league_pages.py``, results, pairing list, crews and the series table in
``test_visitor.py``, the sailor page in ``test_club_page.py``, the hidden profile in
``test_profile_visibility.py``, the missed act in ``test_scoring_storage.py``. What this
test proves is that they are **one season**: the act the league page offers is the act
whose results, draw and crews the fan then reads, a name in a crew leads to that person's
page (or, for a hidden profile, to nothing), and the same act is a column of the year's
table — where the clubs that sat it out carry its field size + 1. Stories B-14, B-15, B-2,
B-3, B-12, B-8, S-4, B-1, A-5.

The visitor's side is through the public HTTP API only, with no token. Arranging the
season uses the organizers' endpoints, except for the **league**: no endpoint creates
one (leagues are seeded), so this test inserts its own, which keeps the seeded leagues'
pages — read by other tests — untouched.
"""

from datetime import date, timedelta
from uuid import uuid4

from app.db import SessionLocal
from app.models import League
from app.models.auth import Role
from tests.journeys import step
from tests.stories.test_create_event import admin
from tests.stories.test_login_and_roles import login_as, make_user
from tests.stories.test_registration import auth_headers

BOATS = [
    {"number": 1, "color": "BLACK", "name": "Black"},
    {"number": 2, "color": "GREEN", "name": "Green"},
    {"number": 3, "color": "DARKBLUE", "name": "Blue"},
    {"number": 4, "color": "RED", "name": "Red"},
    {"number": 5, "color": "GRAY", "name": "Gray"},
    {"number": 6, "color": "ORANGE", "name": "Orange"},
]
CLUBS = 12
# Act 2 is sailed by ten of the twelve: the catalog's 10 teams / 5 boats / 16 flights.
ACT_2_TEAMS = 10
ADULT = "1990-04-01"
# Under 18 on any reference date this year: a minor's profile starts hidden (Story S-4).
MINOR = (date.today() - timedelta(days=15 * 365)).isoformat()


async def _sail(client, headers, event_id: int, count: int | None = None) -> None:
    """Enters the first ``count`` races (all when None), finishing order = boat order."""
    races = (await client.get(f"/api/admin/events/{event_id}/races", headers=headers)).json()
    for race in races["races"][:count]:
        boats = sorted(entry["boat_number"] for entry in race["entries"])
        entered = await client.put(
            f"/api/admin/events/{event_id}/races/{race['id']}/result",
            headers=headers,
            json={
                "results": [
                    {"boat_number": number, "code": "FINISHED", "finish_position": place}
                    for place, number in enumerate(boats, start=1)
                ]
            },
        )
        assert entered.status_code == 200, entered.text


async def _act(
    client, headers, *, series_id, title, matchday, starts_on, teams, boats, flights, clubs
):
    """One act of the series: configured, its clubs entered, drawn, published, started."""
    created = await client.post(
        "/api/admin/events",
        headers=headers,
        json={
            "title": title,
            "series": series_id,
            "matchday": matchday,
            "starts_on": starts_on,
            "team_count": teams,
            "boat_count": boats,
            "flight_count": flights,
            "boats": BOATS[:boats],
        },
    )
    assert created.status_code == 201, created.text
    event_id = created.json()["id"]
    entered = await client.put(
        f"/api/admin/events/{event_id}/clubs", headers=headers, json={"clubs": clubs}
    )
    assert entered.status_code == 200, entered.text
    for action, body in (("pairing/from-catalog", {"seed": 3}), ("publish", None), ("start", None)):
        done = await client.post(
            f"/api/admin/events/{event_id}/{action}", headers=headers, json=body
        )
        assert done.status_code == 200, f"{action}: {done.text}"
    return event_id


class TestAFanFollowsAnAct:
    """Journey J-9: a fan follows an act."""

    async def test_from_the_league_page_to_the_standings(self, client, caplog):
        tag = uuid4().hex[:6]
        office = await admin(client, caplog, f"j9-office-{tag}@example.com")

        # ---------------------------------------------------- the season, arranged
        async with SessionLocal() as session:
            # No endpoint creates a league — they are seeded (see the module docstring).
            league = League(
                slug=f"j9-{tag}", short_name=f"J9 {tag}", name=f"Fan League {tag}", position=900
            )
            session.add(league)
            await session.commit()
            league_id = league.id

        clubs = []
        for n in range(CLUBS):
            created = await client.post(
                "/api/admin/clubs",
                headers=office,
                json={"name": f"J9 Club {n} {tag}", "short_name": f"J9{n}{tag}", "city": "Kiel"},
            )
            assert created.status_code == 201, created.text
            clubs.append(created.json()["id"])
        series = await client.post(
            "/api/admin/series",
            headers=office,
            json={
                "name": f"Fan League {tag} 2026",
                "year": 2026,
                "league_id": league_id,
                "clubs": clubs,
                "published": True,
            },
        )
        assert series.status_code == 201, series.text
        series_id = series.json()["id"]

        # Act 1, sailed to the end by all twelve.
        act_1 = await _act(
            client,
            office,
            series_id=series_id,
            title=f"Fan League {tag} Act 1",
            matchday=1,
            starts_on="2026-05-09",
            teams=CLUBS,
            boats=6,
            flights=8,
            clubs=clubs,
        )
        await _sail(client, office, act_1)
        assert (
            await client.post(f"/api/admin/events/{act_1}/finish", headers=office)
        ).status_code == 200

        # Act 2, under way: ten clubs entered — the last two sit it out — and the first
        # flight sailed.
        act_2 = await _act(
            client,
            office,
            series_id=series_id,
            title=f"Fan League {tag} Act 2",
            matchday=2,
            starts_on="2026-06-13",
            teams=ACT_2_TEAMS,
            boats=5,
            flights=16,
            clubs=clubs[:ACT_2_TEAMS],
        )
        await _sail(client, office, act_2, count=2)

        # The first club's crew for act 2, from its squad (Stories V-4, V-1, V-2): two
        # adults and a minor, whose profile is hidden by default.
        manager_email = f"j9-manager-{tag}@example.com"
        await make_user(manager_email, Role.TEAM_MANAGER, club_id=clubs[0])
        manager = auth_headers(await login_as(client, manager_email, caplog))
        people = []
        for n, born in enumerate((ADULT, ADULT, MINOR)):
            created = await client.post(
                "/api/admin/people",
                headers=manager,
                json={
                    "first_name": f"Fan{n}",
                    "last_name": tag,
                    "email": f"j9-sailor-{n}-{tag}@example.com",
                    "birth_date": born,
                    "club_id": clubs[0],
                },
            )
            assert created.status_code == 201, created.text
            people.append(created.json()["id"])
        helm, crew, minor = people
        mine = (await client.get("/api/clubs/mine", headers=manager)).json()
        entry = next(
            e
            for c in mine
            if c["club"]["id"] == clubs[0]
            for e in c["events"]
            if e["event_id"] == act_2
        )
        roles = [
            {"person_id": helm, "role": "helm"},
            {"person_id": crew, "role": "crew"},
            {"person_id": minor, "role": "crew"},
        ]
        squad = await client.put(
            f"/api/admin/teams/{entry['squad_team_id']}/members",
            headers=manager,
            json={"members": roles},
        )
        assert squad.status_code == 200, squad.text
        named = await client.put(
            f"/api/admin/events/{act_2}/crew",
            headers=manager,
            json={"team_id": entry["team_id"], "members": roles},
        )
        assert named.status_code == 200, named.text
        team_id = entry["team_id"]

        # --------------------------------------------------------- the fan (B-14)
        step("J-9.1", "a fan opens the league's page — the act being sailed comes first")
        season = await client.get(f"/api/leagues/j9-{tag}")
        assert season.status_code == 200, season.text
        season = season.json()
        assert season["year"] == 2026
        assert [s["id"] for s in season["series"]] == [series_id]
        # The page's Results chapter is the live act; the finished one is in the strip.
        assert [(e["matchday"], e["status"]) for e in season["events"]] == [
            (1, "final"),
            (2, "live"),
        ]
        assert {c["id"] for c in season["clubs"]} == set(clubs)

        step("J-9.2", "the fan opens the act's page — its tab in the address")
        # An act is the year's events sharing a matchday number (`/:league/:year/act-2`);
        # here one event. Racing has begun, so the page opens on its results.
        (act,) = [e for e in season["events"] if e["matchday"] == 2]
        assert act["id"] == act_2
        detail = await client.get(f"/api/events/{act_2}")
        assert detail.status_code == 200, detail.text
        detail = detail.json()
        assert detail["event"]["status"] == "live"

        step("J-9.3", "the fan reads the interim results, by flight")
        # One flight of two races sailed: every team has one race and one flight scored.
        assert detail["races_scored"] == 2
        assert detail["event"]["races_per_flight"] == 2
        standings = detail["standings"]
        assert len(standings) == ACT_2_TEAMS
        assert [row["rank"] for row in standings] == list(range(1, ACT_2_TEAMS + 1))
        assert all(set(row["points_by_flight"]) == {"1"} for row in standings)

        step("J-9.4", "the fan looks up the pairing list — which boat, which race")
        pairing = (await client.get(f"/api/events/{act_2}/pairing")).json()
        assert len(pairing["races"]) == 16 * 2
        assert [boat["number"] for boat in pairing["boats"]] == [1, 2, 3, 4, 5]
        for flight in range(1, 17):
            sailing = [
                t["id"]
                for race in pairing["races"]
                if race["flight"] == flight
                for t in race["teams_by_boat"].values()
            ]
            # Every team once per flight.
            assert sorted(sailing) == sorted({row["team"]["id"] for row in standings})
        # The two that sat it out have no seat in the draw.
        assert {
            t["club"]["id"] for race in pairing["races"] for t in race["teams_by_boat"].values()
        } == set(clubs[:ACT_2_TEAMS])

        step("J-9.5", "the fan sees who sails for each team — a crew not named yet says so")
        crews = await client.get(f"/api/events/{act_2}/crew")
        assert crews.status_code == 200, crews.text
        teams = {t["team"]["id"]: t["crew"] for t in crews.json()["teams"]}
        assert len(teams) == ACT_2_TEAMS
        ours = teams.pop(team_id)
        # Helm first, the order a crew is announced; names only, no contact details.
        assert [m["id"] for m in ours] == [helm, crew, minor]
        assert set(ours[0]) == {"id", "first_name", "last_name", "role", "profile_public"}
        # Nobody named yet is an empty crew, not a missing team.
        assert all(crew_ == [] for crew_ in teams.values())

        step("J-9.6", "the fan follows a name to the sailor's page")
        assert ours[0]["profile_public"] is True
        page = await client.get(f"/api/people/{helm}")
        assert page.status_code == 200, page.text
        page = page.json()
        # The series registration and the matchday lineup — two levels, both shown.
        assert [(t["series"]["id"], t["club"]["id"]) for t in page["teams"]] == [
            (series_id, clubs[0])
        ]
        assert [(e["event"]["id"], e["role"]) for e in page["events"]] == [(act_2, "helm")]

        step("J-9.7", "a hidden profile's name is plain text, and its page is not there")
        hidden = next(m for m in ours if m["id"] == minor)
        # The name stays in the crew — never hidden, never "anonymous" ...
        assert (hidden["first_name"], hidden["last_name"]) == ("Fan2", tag)
        assert hidden["profile_public"] is False
        # ... but the page answers like nobody at all.
        gone = await client.get(f"/api/people/{minor}")
        assert gone.status_code == 404
        assert gone.json()["type"].endswith("/person-not-found")

        step("J-9.8", "the fan opens the year's standings — the running act counts")
        table = await client.get(f"/api/series/{series_id}/table")
        assert table.status_code == 200, table.text
        table = table.json()
        assert [e["id"] for e in table["events"]] == [act_1, act_2]
        assert len(table["rows"]) == CLUBS
        assert [row["rank"] for row in table["rows"]] == sorted(
            row["rank"] for row in table["rows"]
        )
        sailed = [row for row in table["rows"] if row["team"]["club"]["id"] in clubs[:ACT_2_TEAMS]]
        assert all(set(row["ranks_by_matchday"]) == {"1", "2"} for row in sailed)

        step("J-9.9", "a club that sat an act out carries the field size + 1 for it")
        absent = [row for row in table["rows"] if row["team"]["club"]["id"] in clubs[ACT_2_TEAMS:]]
        assert len(absent) == CLUBS - ACT_2_TEAMS
        for row in absent:
            assert row["missed_matchdays"] == [2]
            # Ten sailed act 2, so missing it scores 11 — worse than finishing last there.
            assert row["points"] == row["ranks_by_matchday"]["1"] + ACT_2_TEAMS + 1
        assert all(not row["missed_matchdays"] for row in sailed)
