"""User Story VA-8: save a draft, publish it, start it — and freeze it once it sails.

Four states that are deliberately **not** one state machine:

* **Saving** never asks whether the event is complete. Half-filled is how one starts.
* **Publication** (``published``) is orthogonal to ``status``: it decides who can see the
  event, and it locks nothing.
* **Readiness** is computed from the setup and gates the *draw* and the *start*. It answers
  with a list of reasons, because the organizer has to be told what is missing.
* **The freeze** starts with the first race and covers the **configuration** only.
  Results — the entire point of the race-committee screens — stay editable forever.
"""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Boat, Event, Flight, Race, RaceEntry, RaceStatus
from app.models.auth import Role
from tests.stories.test_login_and_roles import login_as, make_user
from tests.stories.test_registrierung import auth_headers
from tests.stories.test_veranstaltung_anlegen import (
    admin,
    event_with_participants,
    league_clubs,
)

FINISHED_MATCHDAY = "dsbl-1-2026-act-1"


async def readiness(client, headers, event_id: int) -> dict:
    response = await client.get(f"/api/admin/events/{event_id}/readiness", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def codes(report: dict) -> set[str]:
    return {reason["code"] for reason in report["reasons"]}


async def draw(client, headers, event_id: int, seed: int = 1) -> None:
    response = await client.post(
        f"/api/admin/events/{event_id}/pairing/from-catalog",
        headers=headers,
        json={"seed": seed},
    )
    assert response.status_code == 200, response.text


async def first_race(event_id: int) -> tuple[int, list[int]]:
    """The first race of an event and its boat numbers."""
    async with SessionLocal() as session:
        race_id = (
            await session.execute(
                select(Race.id)
                .join(Flight, Race.flight_id == Flight.id)
                .where(Flight.event_id == event_id)
                .order_by(Race.sequence)
                .limit(1)
            )
        ).scalar_one()
        boats = list(
            (
                await session.execute(
                    select(Boat.number)
                    .join(RaceEntry, RaceEntry.boat_id == Boat.id)
                    .where(RaceEntry.race_id == race_id)
                    .order_by(Boat.number)
                )
            ).scalars()
        )
        return race_id, boats


async def enter_result(client, headers, event_id: int, race_id: int, boats: list[int]) -> None:
    response = await client.put(
        f"/api/admin/events/{event_id}/races/{race_id}/result",
        headers=headers,
        json={
            "results": [
                {"boat_number": boat, "code": "FINISHED", "finish_position": position}
                for position, boat in enumerate(boats, start=1)
            ]
        },
    )
    assert response.status_code == 200, response.text


class TestSavingAnIncompleteEvent:
    """VA-8: As an organizer I want to save an event that isn't finished yet."""

    async def test_a_title_alone_is_enough_to_save(self, client, caplog):
        """Not even a date is required — it is often the last thing to be settled."""
        headers = await admin(client, caplog, "lc1@example.com")
        response = await client.post(
            "/api/admin/events", headers=headers, json={"title": "Undated Cup"}
        )
        assert response.status_code == 201, response.text
        assert response.json()["starts_on"] is None

    async def test_readiness_names_every_missing_piece(self, client, caplog):
        """VA-8: the organizer must see *what* is missing, not just that something is."""
        headers = await admin(client, caplog, "lc2@example.com")
        created = (
            await client.post(
                "/api/admin/events", headers=headers, json={"title": "Unready Cup"}
            )
        ).json()

        report = await readiness(client, headers, created["id"])
        assert report["ready"] is False
        # No clubs entered yet, and no date.
        assert "pairing-team-count-mismatch" in codes(report)
        assert "event-dates-missing" in codes(report)
        mismatch = next(
            r for r in report["reasons"] if r["code"] == "pairing-team-count-mismatch"
        )
        assert mismatch["details"] == {"registered": 0, "configured": 18}
        assert report["has_pairing_list"] is False
        assert report["configuration_frozen"] is False

    async def test_a_setup_the_catalog_cannot_serve_is_a_reason_too(self, client, caplog):
        headers = await admin(client, caplog, "lc3@example.com")
        created = (
            await client.post(
                "/api/admin/events",
                headers=headers,
                json={
                    "title": "Odd Dimensions Cup",
                    "starts_on": "2027-03-06",
                    "team_count": 18,
                    "boat_count": 5,
                    "flight_count": 11,
                },
            )
        ).json()
        await client.put(
            f"/api/admin/events/{created['id']}/clubs",
            headers=headers,
            json={"clubs": await league_clubs(client)},
        )

        report = await readiness(client, headers, created["id"])
        catalog = next(r for r in report["reasons"] if r["code"] == "pairing-catalog-missing")
        assert (
            catalog["details"]["teams"],
            catalog["details"]["boats"],
            catalog["details"]["flights"],
        ) == (18, 5, 11)
        assert "18/6/16" in catalog["details"]["available"]

    async def test_a_complete_setup_reports_ready(self, client, caplog):
        headers = await admin(client, caplog, "lc4@example.com")
        event_id = await event_with_participants(
            client, headers, "Ready Cup", "2027-03-13"
        )
        report = await readiness(client, headers, event_id)
        assert report["ready"] is True
        assert report["reasons"] == []


class TestPublication:
    """VA-8: As an organizer I want to publish an event — and keep editing it."""

    async def test_a_draft_does_not_exist_for_visitors(self, client, caplog):
        headers = await admin(client, caplog, "lc5@example.com")
        created = (
            await client.post(
                "/api/admin/events",
                headers=headers,
                json={"title": "Secret Draft Cup", "starts_on": "2027-03-20"},
            )
        ).json()

        assert (await client.get(f"/api/events/{created['id']}")).status_code == 404
        calendar = {event["slug"] for event in (await client.get("/api/events")).json()}
        assert created["slug"] not in calendar

    async def test_publishing_shows_it_and_unpublishing_hides_it_again(
        self, client, caplog
    ):
        headers = await admin(client, caplog, "lc6@example.com")
        created = (
            await client.post(
                "/api/admin/events",
                headers=headers,
                json={"title": "Published Cup", "starts_on": "2027-03-27"},
            )
        ).json()

        published = await client.post(
            f"/api/admin/events/{created['id']}/publish", headers=headers
        )
        assert published.status_code == 200, published.text
        assert published.json()["published"] is True
        assert (await client.get(f"/api/events/{created['id']}")).status_code == 200

        withdrawn = await client.post(
            f"/api/admin/events/{created['id']}/unpublish", headers=headers
        )
        assert withdrawn.json()["published"] is False
        assert (await client.get(f"/api/events/{created['id']}")).status_code == 404

    async def test_publishing_needs_no_validity_and_locks_nothing(self, client, caplog):
        """The load-bearing half of the story: a published event stays a work in progress.

        Publishing an incomplete event is normal — the calendar entry is often what makes
        people ask about the missing pieces — and it must not turn the event read-only.
        """
        headers = await admin(client, caplog, "lc7@example.com")
        created = (
            await client.post(
                "/api/admin/events", headers=headers, json={"title": "Vague Cup"}
            )
        ).json()

        published = await client.post(
            f"/api/admin/events/{created['id']}/publish", headers=headers
        )
        assert published.status_code == 200, published.text
        assert published.json()["published"] is True
        # Published while plainly not ready — the two questions are unrelated.
        assert (await readiness(client, headers, created["id"]))["ready"] is False

        # Still editable in every respect, configuration included.
        changed = await client.patch(
            f"/api/admin/events/{created['id']}",
            headers=headers,
            json={
                "title": "Less Vague Cup",
                "starts_on": "2027-04-03",
                "team_count": 12,
            },
        )
        assert changed.status_code == 200, changed.text
        assert changed.json()["title"] == "Less Vague Cup"
        assert changed.json()["team_count"] == 12
        assert changed.json()["published"] is True

    async def test_a_visitor_cannot_publish(self, client, caplog):
        headers = await admin(client, caplog, "lc8@example.com")
        created = (
            await client.post(
                "/api/admin/events", headers=headers, json={"title": "Guarded Cup"}
            )
        ).json()
        assert (
            await client.post(f"/api/admin/events/{created['id']}/publish")
        ).status_code == 401

    async def test_a_series_is_published_the_same_way(self, client, caplog):
        """VA-8: a series is a draft until published, too — with its events."""
        await make_user("lc9@example.com", Role.ADMIN)
        headers = auth_headers(await login_as(client, "lc9@example.com", caplog))

        series = (
            await client.post(
                "/api/admin/series",
                headers=headers,
                json={"name": "Draft League 2027", "year": 2027},
            )
        ).json()
        assert series["published"] is False
        listed = {s["id"] for s in (await client.get("/api/series")).json()}
        assert series["id"] not in listed
        assert (await client.get(f"/api/series/{series['id']}/table")).status_code == 404

        published = await client.post(
            f"/api/admin/series/{series['id']}/publish", headers=headers
        )
        assert published.status_code == 200, published.text
        assert published.json()["published"] is True
        assert (await client.get(f"/api/series/{series['id']}/table")).status_code == 200
        by_year = {s["id"] for s in (await client.get("/api/series", params={"year": 2027})).json()}
        assert series["id"] in by_year

    async def test_a_published_event_of_a_draft_series_stays_hidden(self, client, caplog):
        """Otherwise one published matchday would give away the draft series behind it."""
        await make_user("lc10@example.com", Role.ADMIN)
        headers = auth_headers(await login_as(client, "lc10@example.com", caplog))

        series = (
            await client.post(
                "/api/admin/series",
                headers=headers,
                json={"name": "Hidden League 2027", "year": 2027},
            )
        ).json()
        created = (
            await client.post(
                "/api/admin/events",
                headers=headers,
                json={
                    "title": "Matchday of a draft",
                    "starts_on": "2027-04-10",
                    "series": series["id"],
                    "published": True,
                },
            )
        ).json()

        assert (await client.get(f"/api/events/{created['id']}")).status_code == 404
        await client.post(f"/api/admin/series/{series['id']}/publish", headers=headers)
        assert (await client.get(f"/api/events/{created['id']}")).status_code == 200


class TestStarting:
    """VA-8: As an organizer I want to start the event deliberately, once it is valid."""

    async def test_an_incomplete_event_cannot_be_started(self, client, caplog):
        headers = await admin(client, caplog, "ls1@example.com")
        created = (
            await client.post(
                "/api/admin/events", headers=headers, json={"title": "Nowhere Cup"}
            )
        ).json()

        response = await client.post(
            f"/api/admin/events/{created['id']}/start", headers=headers
        )
        assert response.status_code == 409, response.text
        problem = response.json()
        # More than one thing is missing, so the reasons travel as a list — the same shape
        # the readiness endpoint returns.
        assert problem["type"] == "/errors/event-not-ready"
        assert {reason["code"] for reason in problem["reasons"]} >= {
            "pairing-team-count-mismatch",
            "event-dates-missing",
        }

        async with SessionLocal() as session:
            assert (await session.get(Event, created["id"])).status == "planned"

    async def test_a_single_missing_piece_keeps_its_own_code(self, client, caplog):
        """One cause, one code — the frontend's existing wording keeps working."""
        headers = await admin(client, caplog, "ls2@example.com")
        created = (
            await client.post(
                "/api/admin/events",
                headers=headers,
                json={"title": "Nobody Entered Cup", "starts_on": "2027-04-17"},
            )
        ).json()

        response = await client.post(
            f"/api/admin/events/{created['id']}/start", headers=headers
        )
        assert response.status_code == 409, response.text
        assert response.json()["type"] == "/errors/pairing-team-count-mismatch"
        assert response.json()["registered"] == 0

    async def test_a_valid_event_still_needs_its_pairing_list(self, client, caplog):
        headers = await admin(client, caplog, "ls3@example.com")
        event_id = await event_with_participants(
            client, headers, "Undrawn Cup", "2027-04-24"
        )

        response = await client.post(f"/api/admin/events/{event_id}/start", headers=headers)
        assert response.status_code == 409, response.text
        assert response.json()["type"] == "/errors/event-without-pairing-list"

    async def test_starting_is_an_explicit_decision(self, client, caplog):
        headers = await admin(client, caplog, "ls4@example.com")
        event_id = await event_with_participants(
            client, headers, "Start Cup", "2027-05-01"
        )
        await draw(client, headers, event_id)

        response = await client.post(f"/api/admin/events/{event_id}/start", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "live"
        # Idempotent: a second tap on the same button is not an error.
        assert (
            await client.post(f"/api/admin/events/{event_id}/start", headers=headers)
        ).status_code == 200

    async def test_starting_does_not_publish_by_itself(self, client, caplog):
        """Status and visibility are orthogonal — starting decides nothing about the public."""
        headers = await admin(client, caplog, "ls5@example.com")
        created = (
            await client.post(
                "/api/admin/events",
                headers=headers,
                json={
                    "title": "Unpublished Start Cup",
                    "starts_on": "2027-05-08",
                    "team_count": 18,
                    "flight_count": 16,
                    "boat_count": 6,
                },
            )
        ).json()
        await client.put(
            f"/api/admin/events/{created['id']}/clubs",
            headers=headers,
            json={"clubs": await league_clubs(client)},
        )
        await draw(client, headers, created["id"])

        started = await client.post(
            f"/api/admin/events/{created['id']}/start", headers=headers
        )
        assert started.status_code == 200, started.text
        assert started.json()["status"] == "live"
        assert started.json()["published"] is False
        assert (await client.get(f"/api/events/{created['id']}")).status_code == 404


class TestFreezeAfterTheFirstRace:
    """VA-8: As an organizer I want the setup to hold still once racing has begun."""

    async def test_a_redraw_before_the_first_race_is_fine(self, client, caplog):
        """Nothing freezes on a schedule — only on a race actually starting."""
        headers = await admin(client, caplog, "lf1@example.com")
        event_id = await event_with_participants(
            client, headers, "Redraw Cup", "2027-05-15"
        )
        await draw(client, headers, event_id, seed=1)
        await draw(client, headers, event_id, seed=2)

        report = await readiness(client, headers, event_id)
        assert report["configuration_frozen"] is False
        assert report["has_pairing_list"] is True

    async def test_a_recorded_result_freezes_the_configuration(self, client, caplog):
        headers = await admin(client, caplog, "lf2@example.com")
        event_id = await event_with_participants(
            client, headers, "Frozen Cup", "2027-05-22"
        )
        await draw(client, headers, event_id)
        race_id, boats = await first_race(event_id)
        await enter_result(client, headers, event_id, race_id, boats)

        report = await readiness(client, headers, event_id)
        assert report["configuration_frozen"] is True
        assert report["results_recorded"] == len(boats)

        # The dimensions.
        patched = await client.patch(
            f"/api/admin/events/{event_id}", headers=headers, json={"team_count": 12}
        )
        assert patched.status_code == 409, patched.text
        assert patched.json()["type"] == "/errors/event-configuration-frozen"

        # The field of clubs.
        clubs = await client.put(
            f"/api/admin/events/{event_id}/clubs",
            headers=headers,
            json={"clubs": (await league_clubs(client))[:17]},
        )
        assert clubs.status_code == 409
        assert clubs.json()["type"] == "/errors/event-configuration-frozen"

        # And the pairing list itself.
        redraw = await client.post(
            f"/api/admin/events/{event_id}/pairing/from-catalog",
            headers=headers,
            json={"seed": 3},
        )
        assert redraw.status_code == 409
        assert redraw.json()["type"] == "/errors/event-configuration-frozen"

    async def test_results_stay_editable_after_the_freeze(self, client, caplog):
        """The point of the whole distinction: a protest decision must stay possible.

        The freeze covers the *configuration*. Entering, correcting and re-correcting
        results is what the race committee does all day, and a jury may rule weeks later
        (``docs/concepts.md``, "Points are derived, not entered").
        """
        headers = await admin(client, caplog, "lf3@example.com")
        event_id = await event_with_participants(
            client, headers, "Protest Cup", "2027-05-29"
        )
        await draw(client, headers, event_id)
        race_id, boats = await first_race(event_id)
        await enter_result(client, headers, event_id, race_id, boats)

        # A jury grants redress long after the freeze took hold.
        corrected = await client.put(
            f"/api/admin/events/{event_id}/races/{race_id}/result",
            headers=headers,
            json={"results": [{"boat_number": boats[0], "code": "RDG", "redress_points": 2.5}]},
        )
        assert corrected.status_code == 200, corrected.text

        async with SessionLocal() as session:
            entry = (
                await session.execute(
                    select(RaceEntry)
                    .join(Boat, RaceEntry.boat_id == Boat.id)
                    .where(RaceEntry.race_id == race_id, Boat.number == boats[0])
                )
            ).scalar_one()
            # Points are derived, and the correction went through the recomputation.
            assert entry.points == 2.5

    async def test_the_title_and_the_venue_stay_editable_while_racing(self, client, caplog):
        """A typo or a moved venue has to be fixable on a race day too."""
        headers = await admin(client, caplog, "lf4@example.com")
        event_id = await event_with_participants(
            client, headers, "Typo Cup", "2027-06-05"
        )
        await draw(client, headers, event_id)
        race_id, boats = await first_race(event_id)
        await enter_result(client, headers, event_id, race_id, boats)

        patched = await client.patch(
            f"/api/admin/events/{event_id}",
            headers=headers,
            json={"title": "Typo Cup (corrected)", "status": "final"},
        )
        assert patched.status_code == 200, patched.text
        assert patched.json()["title"] == "Typo Cup (corrected)"
        assert patched.json()["status"] == "final"

    async def test_a_started_race_freezes_even_without_a_result(self, client, caplog):
        """The trigger is the first start, not the first result — a race under way already
        depends on the list it was drawn from."""
        headers = await admin(client, caplog, "lf5@example.com")
        event_id = await event_with_participants(
            client, headers, "Under Way Cup", "2027-06-12"
        )
        await draw(client, headers, event_id)
        race_id, _ = await first_race(event_id)

        async with SessionLocal() as session:
            race = await session.get(Race, race_id)
            race.status = RaceStatus.RUNNING
            await session.commit()

        report = await readiness(client, headers, event_id)
        assert report["configuration_frozen"] is True
        assert report["races_started"] == 1
        assert report["results_recorded"] == 0

        patched = await client.patch(
            f"/api/admin/events/{event_id}", headers=headers, json={"flight_count": 8}
        )
        assert patched.status_code == 409
        assert patched.json()["type"] == "/errors/event-configuration-frozen"

    async def test_a_sailed_matchday_from_the_seed_is_frozen_too(self, client, caplog, ids):
        headers = await admin(client, caplog, "lf6@example.com")
        response = await client.patch(
            f"/api/admin/events/{ids.event(FINISHED_MATCHDAY)}",
            headers=headers,
            json={"boat_count": 4},
        )
        assert response.status_code == 409, response.text
        assert response.json()["type"] == "/errors/event-configuration-frozen"
        assert response.json()["results_recorded"] > 0
