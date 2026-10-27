"""A club hosts its own event, from the empty form to the public results.

Journey J-8 (``docs/journeys/hosted-event.md``) — each ``step(...)`` below is one of its
steps, in the table's order. Every step is covered on its own elsewhere — who may create in
``test_create_event.py``, applications in ``test_participation.py``, a club's second team in
``test_teams_per_club.py``, the four states in ``test_event_lifecycle.py`` and
``test_event_closing.py``, result entry in ``test_result_entry.py``. What this test proves
is the service the association offers other clubs: a club's own people run an event outside
any series, with no step taken by the league office. The host club's **manager** organizes
it, the host club's **admin** names its race officer, other clubs ask to take part and the
host decides. Stories VA-6, Z-2, VA-8, VA-13, V-6, A-9, VA-7, WL-2, VA-10, B-2.

Through the HTTP API only, except the accounts (``make_user``), which no endpoint creates
with a relation already held. The catalog's smallest list: 12 teams, 6 boats, 8 flights.
"""

from uuid import uuid4

from app.models.auth import Role
from tests.journeys import step
from tests.pages import all_items
from tests.stories.test_create_event import admin
from tests.stories.test_login_and_roles import login_as, make_user
from tests.stories.test_registration import auth_headers

TEAMS = 12
BOATS = 6
FLIGHTS = 8
TOTAL_RACES = FLIGHTS * 2  # ceil(12 / 6) races per flight


def codes(readiness: dict) -> set[str]:
    return {reason["code"] for reason in readiness["reasons"]}


class TestAClubHostsItsOwnEvent:
    """As a club I want to run my own regatta on the association's site, outside any series."""

    async def test_from_the_form_to_the_public_results(self, client, caplog):
        tag = uuid4().hex[:6]
        office = await admin(client, caplog, f"j8-office-{tag}@example.com")

        # The clubs exist already — creating them is the league office's (Journey J-2).
        clubs = []
        for n in range(12):
            created = await client.post(
                "/api/admin/clubs",
                headers=office,
                json={"name": f"J8 Club {n} {tag}", "short_name": f"J8{n}{tag}", "city": "Kiel"},
            )
            assert created.status_code == 201, created.text
            clubs.append(created.json()["id"])
        host, invited, applicant, refused_club = clubs[0], clubs[1:10], clubs[10], clubs[11]

        organizer_email = f"j8-organizer-{tag}@example.com"
        await make_user(organizer_email, Role.TEAM_MANAGER, club_id=host)
        organizer = auth_headers(await login_as(client, organizer_email, caplog))

        # ------------------------------------- a club places no act in a series (VA-6)
        step("J-8.1", "the host's team manager tries to add an act to a series — refused")
        a_series = (await client.get("/api/series", params={"year": 2026})).json()[0]["id"]
        refused = await client.post(
            "/api/admin/events",
            headers=organizer,
            json={"title": f"Sneaky Act {tag}", "series": a_series, "host_club_id": host},
        )
        assert refused.status_code == 403, refused.text
        assert refused.json()["type"].endswith("/errors/series-not-mine")

        # ------------------------------------------- the event outside a series (VA-6)
        step("J-8.2", "the host's team manager creates the event their club hosts")
        created = await client.post(
            "/api/admin/events",
            headers=organizer,
            json={
                "title": f"Kiel Club Cup {tag}",
                "host_club_id": host,
                "team_count": TEAMS,
                "boat_count": BOATS,
                "flight_count": FLIGHTS,
                "teams_per_club": 2,
            },
        )
        assert created.status_code == 201, created.text
        event = created.json()
        event_id = event["id"]
        assert event["series"] is None
        assert event["matchday"] is None
        assert event["teams_per_club"] == 2
        assert event["published"] is False
        # No series, so nobody was adopted: the field is the organizer's to name.
        entries = await client.get(f"/api/admin/events/{event_id}/clubs", headers=organizer)
        assert entries.status_code == 200, entries.text
        assert entries.json() == []
        # A stand-alone event may take any club.
        candidates = await client.get(
            f"/api/admin/events/{event_id}/candidate-clubs", headers=organizer
        )
        assert set(clubs) <= {c["id"] for c in candidates.json()}

        # ------------------------------------------- its race officer (Z-2)
        step("J-8.3", "the host club's admin names the event's race officer")
        club_admin_email = f"j8-board-{tag}@example.com"
        await make_user(club_admin_email, Role.CLUB_ADMIN, club_id=host)
        club_admin = auth_headers(await login_as(client, club_admin_email, caplog))
        officer_email = f"j8-officer-{tag}@example.com"
        await make_user(officer_email)
        # The host club's manager organizes the event but is not its admin — the access
        # list is the club admin's (`admin from host_club`).
        assert (
            await client.post(
                "/api/auth/tuples",
                headers=organizer,
                json={
                    "user": officer_email,
                    "relation": "race_officer",
                    "object": f"event:{event_id}",
                },
            )
        ).status_code == 403
        written = await client.post(
            "/api/auth/tuples",
            headers=club_admin,
            json={"user": officer_email, "relation": "race_officer", "object": f"event:{event_id}"},
        )
        assert written.status_code == 201, written.text
        officer = auth_headers(await login_as(client, officer_email, caplog))

        # ------------------------------------------ in the calendar early (VA-8)
        step("J-8.4", "the organizer publishes the event — in the calendar, in no series")
        published = await client.post(f"/api/admin/events/{event_id}/publish", headers=organizer)
        assert published.status_code == 200, published.text
        listed = {e["id"]: e for e in await all_items(client, "/api/events")}
        assert event_id in listed
        assert listed[event_id]["series"] is None

        # ---------------------------------- the host's own field, two teams (VA-13)
        step("J-8.5", "the organizer enters the invited clubs, and the host club twice")
        too_many = await client.put(
            f"/api/admin/events/{event_id}/clubs",
            headers=organizer,
            json={"clubs": [host, host, host, *invited]},
        )
        assert too_many.status_code in (409, 422), too_many.text
        assert too_many.json()["type"].endswith("/errors/too-many-teams-per-club")
        entered = await client.put(
            f"/api/admin/events/{event_id}/clubs",
            headers=organizer,
            json={"clubs": [host, host, *invited]},
        )
        assert entered.status_code == 200, entered.text
        own = sorted((p["number"], p["name"]) for p in entered.json() if p["club"]["id"] == host)
        assert own == [(1, f"J80{tag}"), (2, f"J80{tag} 2")]
        assert len(entered.json()) == TEAMS - 1

        # ------------------------------------------- another club asks (V-6)
        step("J-8.6", "a team manager of another club asks to take part")
        applicant_email = f"j8-applicant-{tag}@example.com"
        await make_user(applicant_email, Role.TEAM_MANAGER, club_id=applicant)
        applicant_manager = auth_headers(await login_as(client, applicant_email, caplog))
        applied = await client.post(
            "/api/applications",
            headers=applicant_manager,
            json={"club_id": applicant, "event_id": event_id},
        )
        assert applied.status_code == 201, applied.text
        application = applied.json()
        assert application["status"] == "requested"
        assert application["event"]["id"] == event_id
        # A request is not an entry: the event is still one team short.
        report = (
            await client.get(f"/api/admin/events/{event_id}/readiness", headers=organizer)
        ).json()
        assert "pairing-team-count-mismatch" in codes(report)

        # ----------------------------------------- the host decides (A-9)
        step("J-8.7", "the organizer accepts the request")
        pending = await client.get(
            "/api/admin/applications", headers=organizer, params={"event_id": event_id}
        )
        assert pending.status_code == 200, pending.text
        assert application["team_id"] in {a["team_id"] for a in pending.json()}
        accepted = await client.post(
            f"/api/admin/applications/{application['team_id']}/accept", headers=organizer
        )
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["status"] == "accepted"

        # --------------------------------------- branch: a request turned down
        step("J-8.8", "a second club asks to take part")
        refused_email = f"j8-late-{tag}@example.com"
        await make_user(refused_email, Role.TEAM_MANAGER, club_id=refused_club)
        late_manager = auth_headers(await login_as(client, refused_email, caplog))
        late = await client.post(
            "/api/applications",
            headers=late_manager,
            json={"club_id": refused_club, "event_id": event_id},
        )
        assert late.status_code == 201, late.text

        step("J-8.9", "the organizer turns it down, saying why")
        rejected = await client.post(
            f"/api/admin/applications/{late.json()['team_id']}/reject",
            headers=organizer,
            json={"note": "The field is full."},
        )
        assert rejected.status_code == 200, rejected.text
        theirs = (await client.get("/api/applications", headers=late_manager)).json()
        mine = next(a for a in theirs if a["team_id"] == late.json()["team_id"])
        assert (mine["status"], mine["decision_note"]) == ("rejected", "The field is full.")

        # ------------------------------------------- ready, then the draw (VA-8, VA-7)
        step("J-8.10", "the organizer sets the date; the event is ready")
        report = (
            await client.get(f"/api/admin/events/{event_id}/readiness", headers=organizer)
        ).json()
        assert codes(report) == {"event-dates-missing"}, report
        dated = await client.patch(
            f"/api/admin/events/{event_id}",
            headers=organizer,
            json={"starts_on": "2026-11-07", "ends_on": "2026-11-08"},
        )
        assert dated.status_code == 200, dated.text
        report = (
            await client.get(f"/api/admin/events/{event_id}/readiness", headers=organizer)
        ).json()
        assert report["ready"] is True, report

        step("J-8.11", "the league office draws the pairing list from the catalog")
        # The draw is the site admin's alone today (`require_admin`), though Stories VA-6
        # and VA-7 give it to the event's organizer — the journey's Open: says so.
        drawn = await client.post(
            f"/api/admin/events/{event_id}/pairing/from-catalog",
            headers=office,
            json={"seed": 1240},
        )
        assert drawn.status_code == 200, drawn.text
        pairing = (await client.get(f"/api/events/{event_id}/pairing")).json()
        drawn_names = {
            team["name"] for race in pairing["races"] for team in race["teams_by_boat"].values()
        }
        assert {f"J80{tag}", f"J80{tag} 2", f"J810{tag}"} <= drawn_names
        assert f"J811{tag}" not in drawn_names

        step("J-8.12", "the organizer starts the event")
        started = await client.post(f"/api/admin/events/{event_id}/start", headers=organizer)
        assert started.status_code == 200, started.text
        assert started.json()["status"] == "live"

        # ---------------------------------------------- the races (WL-2)
        step("J-8.13", "the race officer enters every race")
        races = (await client.get(f"/api/admin/events/{event_id}/races", headers=officer)).json()
        assert len(races["races"]) == TOTAL_RACES
        first = races["races"][0]
        # Organizing is not racing: the host's manager enters no result.
        assert (
            await client.put(
                f"/api/admin/events/{event_id}/races/{first['id']}/result",
                headers=organizer,
                json={"results": [{"boat_number": 1, "code": "FINISHED", "finish_position": 1}]},
            )
        ).status_code == 403
        for race in races["races"]:
            boats_in_race = sorted(entry["boat_number"] for entry in race["entries"])
            entered_result = await client.put(
                f"/api/admin/events/{event_id}/races/{race['id']}/result",
                headers=officer,
                json={
                    "results": [
                        {"boat_number": number, "code": "FINISHED", "finish_position": position}
                        for position, number in enumerate(boats_in_race, start=1)
                    ]
                },
            )
            assert entered_result.status_code == 200, entered_result.text

        step("J-8.14", "the race officer declares the event final")
        final = await client.post(f"/api/admin/events/{event_id}/finish", headers=officer)
        assert final.status_code == 200, final.text
        assert final.json()["status"] == "final"

        # ------------------------------------------------- the public (B-2)
        step("J-8.15", "a visitor reads the results, both host teams in them, no series")
        detail = (await client.get(f"/api/events/{event_id}")).json()
        assert detail["event"]["series"] is None
        assert detail["event"]["host_club"]["id"] == host
        assert detail["races_scored"] == TOTAL_RACES
        assert len(detail["standings"]) == TEAMS
        names = {row["team"]["name"] for row in detail["standings"]}
        assert {f"J80{tag}", f"J80{tag} 2", f"J810{tag}"} <= names
        assert sum(row["total"] for row in detail["standings"]) == TOTAL_RACES * sum(
            range(1, BOATS + 1)
        )
