"""The whole way through, once: from an empty database to a scored matchday.

Every step here is covered on its own elsewhere — clubs in ``test_stammdaten.py``, series
in ``test_serie_anlegen.py``, the draw in ``test_veranstaltung_anlegen.py``, the four
states in ``test_event_lifecycle.py``, result entry in ``test_ergebniserfassung.py``. What
none of them covers is the **order**: that the output of each step is really the input of
the next, through the HTTP API only, with nothing reached around into the database.

That is what breaks in practice. A draw keyed on registered teams while the clubs are
added *after* creation, an event saved without a date because the date is agreed later, a
series whose registrations gate who may enter its events — each of those is fine in
isolation and wrong in sequence. This test is the sequence, and it is deliberately one
long test rather than several: a step that only makes sense after the previous one has
happened does not belong in a test that can run on its own.

The configuration is the catalog's smallest: **12 clubs, 6 boats, 8 flights** — two races
per flight, 16 races in all, small enough to actually sail to the end here and still a
real pairing list. Stories A-1, A-4, VA-6, VA-7, VA-8, WL-2, B-1.
"""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Event, EventStatus
from app.models.auth import Role
from tests.stories.test_login_and_roles import login_as, make_user
from tests.stories.test_registrierung import auth_headers
from tests.stories.test_veranstaltung_anlegen import admin

# The catalog's smallest entry (`app/pairing/schedules/t12-b6-f8.yml`).
TEAMS = 12
BOATS = 6
FLIGHTS = 8
RACES_PER_FLIGHT = 2  # ceil(12 / 6)
TOTAL_RACES = FLIGHTS * RACES_PER_FLIGHT

BOAT_SPECS = [
    {"number": 1, "color": "BLACK", "name": "Black Seven"},
    {"number": 2, "color": "GREEN", "name": "Green Henry"},
    {"number": 3, "color": "DARKBLUE", "name": "Blue Peter"},
    {"number": 4, "color": "RED", "name": "Red Baron"},
    {"number": 5, "color": "GRAY", "name": "Gray Mouse"},
    {"number": 6, "color": "#f5d000", "name": "Yellow Submarine"},
]


def codes(readiness: dict) -> set[str]:
    return {reason["code"] for reason in readiness["reasons"]}


class TestTheCompleteLifecycle:
    """As the association I want to run an event end to end, in the order it happens."""

    async def test_from_an_empty_series_to_a_scored_matchday(self, client, caplog):
        headers = await admin(client, caplog, "lifecycle@example.com")

        # ---------------------------------------------------------- 1. Clubs (A-1)
        club_ids: list[int] = []
        for index in range(TEAMS):
            created = await client.post(
                "/api/admin/clubs",
                headers=headers,
                json={
                    "name": f"Lifecycle Sailing Club {index + 1}",
                    "short_name": f"LSC{index + 1}",
                    "city": "Kiel",
                },
            )
            assert created.status_code in (200, 201), created.text
            club_ids.append(created.json()["id"])

        # A brand-new club is not public yet — it becomes visible through a series
        # ("A club appears publicly only when enrolled", docs/concepts.md).
        public_clubs = {club["id"] for club in (await client.get("/api/clubs")).json()}
        assert not set(club_ids) & public_clubs

        # ------------------------------------------------- 2. A series, as a draft (A-4)
        series = await client.post(
            "/api/admin/series",
            headers=headers,
            json={
                "name": "Lifecycle Trophy 2026",
                "year": 2026,
                "clubs": club_ids,
                "published": False,
            },
        )
        assert series.status_code in (200, 201), series.text
        series_id = series.json()["id"]
        assert len(series.json()["clubs"]) == TEAMS

        # A draft series does not exist publicly — 404, not 403: its existence is itself
        # not public (Story VA-8).
        listed = {s["id"] for s in (await client.get("/api/series?year=2026")).json()}
        assert series_id not in listed
        assert (await client.get(f"/api/series/{series_id}/table")).status_code == 404

        published = await client.post(f"/api/admin/series/{series_id}/publish", headers=headers)
        assert published.status_code == 200, published.text
        assert published.json()["published"] is True
        listed = {s["id"] for s in (await client.get("/api/series?year=2026")).json()}
        assert series_id in listed

        # ------------------------------- 3. An event with nothing but a name (VA-6, VA-8)
        # Deliberately no date and the wrong dimensions: the host has not confirmed the
        # weekend yet, and this is what an organizer actually has at this point.
        event = await client.post(
            "/api/admin/events",
            headers=headers,
            json={"title": "Lifecycle Trophy Act 1", "series": series_id, "boats": BOAT_SPECS},
        )
        assert event.status_code == 201, event.text
        event_id = event.json()["id"]
        assert event.json()["starts_on"] is None
        assert event.json()["published"] is False
        # The series' registrations were adopted, so the clubs are already entered.
        entered = (await client.get(f"/api/admin/events/{event_id}/clubs", headers=headers)).json()
        assert {row["club"]["id"] for row in entered} == set(club_ids)

        # The draft is on the admin list — the very screen whose job is to finish it — and
        # not on the public one.
        admin_list = (await client.get("/api/admin/events", headers=headers)).json()
        assert event_id in {row["id"] for row in admin_list}
        assert event_id not in {row["id"] for row in (await client.get("/api/events")).json()}

        # ------------------------------------------- 4. What is missing, and fixing it
        report = (
            await client.get(f"/api/admin/events/{event_id}/readiness", headers=headers)
        ).json()
        assert report["ready"] is False
        # 12 clubs are entered but the event still says 18, no catalog list exists for
        # 18/6/16-with-12-teams, and there is no date.
        assert "pairing-team-count-mismatch" in codes(report)
        assert "event-dates-missing" in codes(report)

        # The draw refuses for exactly those reasons, in the same shape — the screen and
        # the error can never disagree.
        refused = await client.post(
            f"/api/admin/events/{event_id}/pairing/from-catalog",
            headers=headers,
            json={"seed": 7},
        )
        assert refused.status_code == 409, refused.text
        assert refused.json()["type"].endswith("/errors/event-not-ready")

        sized = await client.patch(
            f"/api/admin/events/{event_id}",
            headers=headers,
            json={"team_count": TEAMS, "boat_count": BOATS, "flight_count": FLIGHTS},
        )
        assert sized.status_code == 200, sized.text

        report = (
            await client.get(f"/api/admin/events/{event_id}/readiness", headers=headers)
        ).json()
        assert codes(report) == {"event-dates-missing"}, report

        dated = await client.patch(
            f"/api/admin/events/{event_id}",
            headers=headers,
            json={"starts_on": "2026-08-15", "ends_on": "2026-08-16"},
        )
        assert dated.status_code == 200, dated.text

        report = (
            await client.get(f"/api/admin/events/{event_id}/readiness", headers=headers)
        ).json()
        assert report["ready"] is True, report
        assert report["has_pairing_list"] is False
        assert report["configuration_frozen"] is False

        # ------------------------------------------------------ 5. The draw (VA-7)
        drawn = await client.post(
            f"/api/admin/events/{event_id}/pairing/from-catalog",
            headers=headers,
            json={"seed": 7},
        )
        assert drawn.status_code == 200, drawn.text
        report = (
            await client.get(f"/api/admin/events/{event_id}/readiness", headers=headers)
        ).json()
        assert report["has_pairing_list"] is True

        # Nothing has been sailed, so a second draw is still allowed — that is the point
        # of being able to draw twice while the fleet is at the dock.
        assert (
            await client.post(
                f"/api/admin/events/{event_id}/pairing/from-catalog",
                headers=headers,
                json={"seed": 8},
            )
        ).status_code == 200

        # ------------------------------------------- 6. Publish, then start (VA-8)
        assert (
            await client.post(f"/api/admin/events/{event_id}/publish", headers=headers)
        ).status_code == 200
        assert event_id in {row["id"] for row in (await client.get("/api/events")).json()}

        started = await client.post(f"/api/admin/events/{event_id}/start", headers=headers)
        assert started.status_code == 200, started.text
        assert started.json()["status"] == "live"

        # ------------------------------------------------- 7. Sail all 16 races (WL-2)
        races = (
            await client.get(f"/api/admin/events/{event_id}/races", headers=headers)
        ).json()
        assert len(races["races"]) == TOTAL_RACES, len(races["races"])
        assert len(races["boats"]) == BOATS
        # The custom hull colour survived creation as typed — the column is a free string.
        assert races["boats"][5]["color"] == "#f5d000"

        for race in races["races"]:
            boats_in_race = [entry["boat_number"] for entry in race["entries"]]
            # Every race is one full flight of boats, each sailed by a different team.
            assert len(boats_in_race) == BOATS
            assert len({entry["team"]["id"] for entry in race["entries"]}) == BOATS
            entered_result = await client.put(
                f"/api/admin/events/{event_id}/races/{race['id']}/result",
                headers=headers,
                json={
                    "results": [
                        # Finishing order = boat order. Arbitrary, but it makes the
                        # expected point total below arithmetic rather than a fixture.
                        {"boat_number": number, "code": "FINISHED", "finish_position": position}
                        for position, number in enumerate(sorted(boats_in_race), start=1)
                    ]
                },
            )
            assert entered_result.status_code == 200, entered_result.text

        # Every team sailed once per flight, so everyone has 8 races scored.
        detail = (await client.get(f"/api/events/{event_id}")).json()
        assert detail["races_total"] == TOTAL_RACES
        assert detail["races_scored"] == TOTAL_RACES
        standings = detail["standings"]
        assert len(standings) == TEAMS
        assert {row["races_scored"] for row in standings} == {FLIGHTS}
        # Points are derived, never entered: each race hands out 1..6, and every one of the
        # 16 races was scored, so the whole fleet's totals must add up to that sum.
        assert sum(row["total"] for row in standings) == TOTAL_RACES * sum(range(1, BOATS + 1))
        assert [row["rank"] for row in standings] == list(range(1, TEAMS + 1))

        # ...and the series table now has this act in it (Story B-1). The series scores
        # *placements*, not race points: one act, so every club's series points are its
        # rank in it, and nobody missed the act.
        table = (await client.get(f"/api/series/{series_id}/table")).json()
        assert len(table["rows"]) == TEAMS
        assert event_id in {listed_event["id"] for listed_event in table["events"]}
        assert sorted(row["points"] for row in table["rows"]) == [
            float(rank) for rank in range(1, TEAMS + 1)
        ]
        assert all(not row["missed_matchdays"] for row in table["rows"])

        # -------------------------------------- 8. The configuration is frozen (VA-8)
        frozen = await client.patch(
            f"/api/admin/events/{event_id}",
            headers=headers,
            json={"flight_count": FLIGHTS + 1},
        )
        assert frozen.status_code == 409, frozen.text
        assert frozen.json()["type"].endswith("/errors/event-configuration-frozen")
        assert frozen.json()["results_recorded"] == TOTAL_RACES * BOATS

        assert (
            await client.put(
                f"/api/admin/events/{event_id}/clubs",
                headers=headers,
                json={"clubs": club_ids[:-1]},
            )
        ).status_code == 409

        # But the title still is not — a typo has to be fixable on a race day too.
        renamed = await client.patch(
            f"/api/admin/events/{event_id}",
            headers=headers,
            json={"title": "Lifecycle Trophy · Act 1"},
        )
        assert renamed.status_code == 200, renamed.text

        # ------------------------------- 9. A protest decision, months later (WL-2)
        # The freeze deliberately never covers results. This is the whole purpose of the
        # race-committee screens, so it has to work after the event is over.
        first_race = races["races"][0]
        winner = min(first_race["entries"], key=lambda entry: entry["boat_number"])
        corrected = await client.put(
            f"/api/admin/events/{event_id}/races/{first_race['id']}/result",
            headers=headers,
            json={
                "results": [{"boat_number": winner["boat_number"], "code": "DSQ"}],
            },
        )
        assert corrected.status_code == 200, corrected.text

        after = (await client.get(f"/api/events/{event_id}")).json()
        disqualified = next(
            row for row in after["standings"] if row["team"]["id"] == winner["team"]["id"]
        )
        # A DSQ scores participants + 1 in that race, so the total went up by more than the
        # 1 point the win was worth — and the recount happened on write, not on a nightly job.
        assert disqualified["total"] > 1 * FLIGHTS

        # ------------------------------------------------------- 10. Wrapping up
        final = await client.patch(
            f"/api/admin/events/{event_id}", headers=headers, json={"status": "final"}
        )
        assert final.status_code == 200, final.text
        assert final.json()["status"] == "final"

        async with SessionLocal() as session:
            stored = (
                await session.execute(select(Event).where(Event.id == event_id))
            ).scalar_one()
        assert stored.status == EventStatus.FINAL
        assert stored.published is True


class TestTheAdminEventList:
    """As an organizer I want to see my drafts on the screen that finishes them."""

    async def test_the_admin_list_shows_drafts_the_public_one_hides(self, client, caplog):
        """Story VA-8: the public list is the wrong list for the publishing screen.

        `GET /api/events` shows published events only — correct for the calendar, and
        exactly wrong for the page whose job is to finish a draft, where it would make the
        one event being worked on the one event not shown.
        """
        headers = await admin(client, caplog, "adminlist@example.com")
        draft = await client.post(
            "/api/admin/events", headers=headers, json={"title": "Quietly Planned Cup"}
        )
        assert draft.status_code == 201, draft.text
        event_id = draft.json()["id"]

        managed = await client.get("/api/admin/events", headers=headers)
        assert managed.status_code == 200, managed.text
        assert event_id in {row["id"] for row in managed.json()}
        assert event_id not in {row["id"] for row in (await client.get("/api/events")).json()}

    async def test_a_visitor_cannot_read_the_admin_list(self, client):
        """Which events are being planned is not public — not even their titles."""
        assert (await client.get("/api/admin/events")).status_code == 401

    async def test_a_club_account_without_a_role_cannot_read_it_either(self, client, caplog):
        """A `club_manager` may create an event their own club hosts (Story VA-6), which
        is deliberately *not* permission to read everyone else's planning."""
        await make_user("clubmanager-list@example.com", Role.CLUB_MANAGER)
        headers = auth_headers(await login_as(client, "clubmanager-list@example.com", caplog))
        assert (await client.get("/api/admin/events", headers=headers)).status_code == 403
