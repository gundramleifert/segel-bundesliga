"""A matchday scored live on SAP Sailing, from the send to the year's table.

Journey J-10 (``docs/journeys/sap-scored.md``) — each ``step(...)`` below is one of its
steps, in the table's order. SAP is **the local SAP Sailing** (`deploy/sap-local/`), the
double of SAP's hosted server: the real software takes what the site sends, and the race
committee and the jury enter their results on it the way SAP's own app does
(`tests/sap_double.py`) — the two offline steps, J-10.5 and J-10.13, happen there between
the walk's steps. Skipped when no local SAP answers; start it with
`deploy/sap-local/README.md`. Stories VA-14, VA-15, VA-8, WL-5, B-5, B-20, VA-10, B-1.

What this proves is the hand-over between the two systems: the event names its SAP
leaderboard by being sent, a result entered at SAP is the result on the act's page after
the next fetch — on the team and boat our draw gave it, with the points derived here —
and a protest decided at SAP weeks later still reaches the year's table. Branch J-10.9
(SAP's points differ from ours — SAP's series discards a race) is its own story test in
`test_sap_send.py`.

Through the HTTP API only, except the accounts (``make_user``). The starting point —
twelve clubs, the series, the act and its draw — is arranged the way Journey J-1 does it;
a matchday number of its own keeps every run's leaderboard on SAP a new one.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.config import settings
from app.live import event_topic, hub
from app.models.auth import Role
from tests import sap_double
from tests.journeys import step
from tests.sap_double import LocalSap
from tests.stories.test_create_event import admin
from tests.stories.test_login_and_roles import login_as, make_user
from tests.stories.test_registration import auth_headers

TEAMS = 12
BOATS = 6
FLIGHTS = 8
COLORS = ("BLACK", "GREEN", "DARKBLUE", "RED", "GRAY", "ORANGE")

pytestmark = pytest.mark.skipif(
    not sap_double.available(), reason="no local SAP Sailing (deploy/sap-local/README.md)"
)


@pytest.fixture
def at_sap():
    """The walk's events at the local SAP, deleted afterwards — pass or fail — so SAP
    holds only what someone sent on purpose."""
    sent: list[LocalSap] = []
    yield sent
    for sap in sent:
        sap.delete()
        sap.close()


@pytest.fixture
def site_on_local_sap(monkeypatch):
    """The site's SAP settings pointed at the local SAP and its six boats."""
    monkeypatch.setattr(settings, "sap_base_url", sap_double.API)
    monkeypatch.setattr(settings, "sap_user", sap_double.AUTH[0])
    monkeypatch.setattr(settings, "sap_password", sap_double.AUTH[1])
    monkeypatch.setattr(settings, "sap_boats", sap_double.boats())


async def finishing_order(client, officer, event_id: int, flight: int, race: int) -> list[str]:
    """The race's teams as our draw seats them, by boat number — their club codes."""
    races = (await client.get(f"/api/admin/events/{event_id}/races", headers=officer)).json()
    (seated,) = (
        r["entries"] for r in races["races"] if (r["flight"], r["race_in_flight"]) == (flight, race)
    )
    assert len(seated) == BOATS
    return [e["team"]["club"]["short_name"] for e in sorted(seated, key=lambda e: e["boat_number"])]


async def finish_by_boat(client, officer, sap: LocalSap, event_id: int, flight: int, race: int):
    """The race committee enters a race at SAP: the boats finish in their numbers' order."""
    ids = sap.competitors()
    order = await finishing_order(client, officer, event_id, flight, race)
    sap.enter(
        f"F{flight}", f"Race {race}", [(ids[code], n, "NONE") for n, code in enumerate(order, 1)]
    )


class TestAMatchdayScoredOnSap:
    """As the association I want a matchday scored on SAP Sailing and shown on our site."""

    async def test_from_the_send_to_the_years_table(
        self, client, caplog, monkeypatch, site_on_local_sap, at_sap
    ):
        tag = uuid4().hex[:6]
        matchday = 100 + int(tag, 16) % 900
        office = await admin(client, caplog, f"j10-office-{tag}@example.com")

        # ------------------------------------- the starting point, as Journey J-1 makes it
        clubs = []
        for n in range(TEAMS):
            created = await client.post(
                "/api/admin/clubs",
                headers=office,
                json={"name": f"J10 Club {n} {tag}", "short_name": f"J{n}{tag}", "city": "Kiel"},
            )
            assert created.status_code == 201, created.text
            clubs.append(created.json()["id"])
        # The name SAP's leaderboards are recognised by (`app/imports/sap.py`, ``_NAME``).
        series = await client.post(
            "/api/admin/series",
            headers=office,
            json={"name": "2. Segel-Bundesliga 2031", "year": 2031, "clubs": clubs},
        )
        assert series.status_code in (200, 201), series.text
        series_id = series.json()["id"]
        assert (
            await client.post(f"/api/admin/series/{series_id}/publish", headers=office)
        ).status_code == 200
        options = (await client.get("/api/admin/events/create-options", headers=office)).json()
        kiel = next(v["id"] for v in options["venues"] if v["name"] == "Kiel")
        event = await client.post(
            "/api/admin/events",
            headers=office,
            json={
                "title": f"Act {matchday} Kiel",
                "series": series_id,
                "matchday": matchday,
                "venue_id": kiel,
                "starts_on": "2031-05-09",
                "ends_on": "2031-05-11",
                "boats": [{"number": i, "color": c} for i, c in enumerate(COLORS, 1)],
            },
        )
        assert event.status_code == 201, event.text
        event_id = event.json()["id"]
        sized = await client.patch(
            f"/api/admin/events/{event_id}",
            headers=office,
            json={"team_count": TEAMS, "flight_count": FLIGHTS},
        )
        assert sized.status_code == 200, sized.text
        drawn = await client.post(
            f"/api/admin/events/{event_id}/pairing/from-catalog", headers=office, json={"seed": 3}
        )
        assert drawn.status_code == 200, drawn.text
        assert (
            await client.post(f"/api/admin/events/{event_id}/publish", headers=office)
        ).status_code == 200

        officer_email = f"j10-officer-{tag}@example.com"
        await make_user(officer_email, Role.RACE_OFFICER)
        officer = auth_headers(await login_as(client, officer_email, caplog))

        # ----------------------------------------------------------------- the walk
        step("J-10.1", "the organizer says the event is scored on SAP Sailing")
        scored = await client.patch(
            f"/api/admin/events/{event_id}", headers=office, json={"results_source": "sap"}
        )
        assert scored.status_code == 200, scored.text
        assert scored.json()["results_source"] == "sap"
        assert scored.json()["sap_leaderboard"] is None  # not sent yet

        step("J-10.16", "the organizer sends the event and its pairing list to SAP")
        sent = await client.post(f"/api/events/{event_id}/sap/send", headers=office)
        assert sent.status_code == 200, sent.text
        leaderboard = sent.json()["leaderboard"]
        assert leaderboard == f"2. Segel-Bundesliga 2031 - Kiel ({matchday})"
        assert (sent.json()["teams_created"], sent.json()["races"]) == (TEAMS, FLIGHTS * 2)
        sap = LocalSap(leaderboard)
        at_sap.append(sap)
        flights = next(s for s in sap.regatta()["series"] if s["name"] == "Flights")
        assert flights["races"] == [f"F{n}" for n in range(1, FLIGHTS + 1)]
        # Race 1 blue, race 2 yellow — SAP's colours for the races of a flight.
        assert [f["color"] for f in flights["fleets"]] == [
            {"r": 39, "g": 140, "b": 194},
            {"r": 251, "g": 186, "b": 0},
        ]
        detail = (await client.get(f"/api/events/{event_id}")).json()
        assert detail["event"]["sap_leaderboard"] == leaderboard

        step("J-10.4", "the organizer starts the event")
        started = await client.post(f"/api/admin/events/{event_id}/start", headers=office)
        assert started.status_code == 200, started.text
        assert started.json()["status"] == "live"

        # J-10.5 (offline): the race committee enters flight 1 at SAP.
        await finish_by_boat(client, officer, sap, event_id, 1, 1)
        await finish_by_boat(client, officer, sap, event_id, 1, 2)

        step("J-10.6", "a result entered here is refused — SAP is this event's source")
        races = (await client.get(f"/api/admin/events/{event_id}/races", headers=officer)).json()
        first = races["races"][0]
        typed = await client.put(
            f"/api/admin/events/{event_id}/races/{first['id']}/result",
            headers=officer,
            json={"results": [{"boat_number": 1, "code": "FINISHED", "finish_position": 1}]},
        )
        assert typed.status_code == 409, typed.text
        assert typed.json()["type"].endswith("/errors/event-scored-on-sap")
        assert typed.json()["leaderboard"] == leaderboard

        step("J-10.7", "the site takes the results from SAP and derives the points")
        version = hub.version(event_topic(event_id))
        fetched = await client.post(f"/api/events/{event_id}/sap/results", headers=officer)
        assert fetched.status_code == 200, fetched.text
        assert fetched.json()["results"] == 2 * BOATS
        assert fetched.json()["warnings"] == []  # SAP's points are ours
        races = (await client.get(f"/api/admin/events/{event_id}/races", headers=officer)).json()
        # SAP's leaderboard names each team's own boat; the event keeps its six (docs/gotchas).
        assert len(races["boats"]) == BOATS
        for race in races["races"][:2]:
            # On the boat our draw gave each team, in the order SAP was told.
            places = {e["boat_number"]: e["finish_position"] for e in race["entries"]}
            assert places == {n: n for n in range(1, BOATS + 1)}

        step("J-10.8", "SAP does not answer — the results already taken stay")
        monkeypatch.setattr(settings, "sap_base_url", "http://127.0.0.1:9/sailingserver/api")
        unreachable = await client.post(f"/api/events/{event_id}/sap/results", headers=officer)
        assert unreachable.status_code == 502, unreachable.text
        assert unreachable.json()["type"].endswith("/errors/sap-unreachable")
        assert (await client.get(f"/api/events/{event_id}")).json()["races_scored"] == 2
        monkeypatch.setattr(settings, "sap_base_url", sap_double.API)

        step("J-10.10", "a visitor's open pages are told, and show the result")
        assert hub.version(event_topic(event_id)) > version
        public = (await client.get(f"/api/events/{event_id}")).json()
        assert public["races_scored"] == 2
        assert sum(row["total"] for row in public["standings"]) == 2 * sum(range(1, BOATS + 1))

        step("J-10.11", "the act's page has SAP's live view of the event")
        viewer = public["event"]["sap_viewer_url"]
        # SAP's event page, its Leaderboard tab — the event the send created (B-21).
        assert viewer.startswith(f"{sap_double.ROOT}/gwt/Home.html#/regatta/leaderboard/:eventId=")

        # J-10.5 again for the rest of the day, fetched as the server's polling would.
        for flight in range(2, FLIGHTS + 1):
            await finish_by_boat(client, officer, sap, event_id, flight, 1)
            await finish_by_boat(client, officer, sap, event_id, flight, 2)
        rest = await client.post(f"/api/events/{event_id}/sap/results", headers=officer)
        assert rest.status_code == 200, rest.text
        assert (await client.get(f"/api/events/{event_id}")).json()["races_scored"] == 16

        step("J-10.12", "the race officer closes the day")
        closed = await client.post(f"/api/admin/events/{event_id}/finish", headers=officer)
        assert closed.status_code == 200, closed.text
        assert closed.json()["status"] == "final"

        # J-10.13 (offline): weeks later the jury disqualifies flight 1's race 1 winner at
        # SAP — on the black boat; the others keep their places.
        ids = sap.competitors()
        order = await finishing_order(client, officer, event_id, 1, 1)
        sap.enter(
            "F1",
            "Race 1",
            [(ids[order[0]], None, "DSQ")]
            + [(ids[code], n, "NONE") for n, code in enumerate(order[1:], 2)],
        )

        step("J-10.14", "the race officer asks the site to take the final event's results")
        protest = await client.post(f"/api/events/{event_id}/sap/results", headers=officer)
        assert protest.status_code == 200, protest.text
        races = (await client.get(f"/api/admin/events/{event_id}/races", headers=officer)).json()
        decided = {e["boat_number"]: e["code"] for e in races["races"][0]["entries"]}
        assert decided[1] == "DSQ"
        assert {decided[n] for n in range(2, BOATS + 1)} == {"FINISHED"}

        step("J-10.15", "a visitor reads the year's table with the act in it")
        table = (await client.get(f"/api/series/{series_id}/table")).json()
        assert event_id in {listed["id"] for listed in table["events"]}
        assert sorted(row["points"] for row in table["rows"]) == [
            float(rank) for rank in range(1, TEAMS + 1)
        ]
