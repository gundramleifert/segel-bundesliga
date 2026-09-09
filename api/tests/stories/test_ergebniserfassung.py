"""User Story WL-2: enter and correct results easily.

The race committee fills in ``code``/``finish_position`` (and, for a redress, the awarded
``redress_points``) after a race. These raw fields are authoritative; ``points`` and
``is_discarded`` are always recomputed from them — never set by hand — so a protest
decision is a one-row data change, not a data migration (``docs/concepts.md``).

Tests use the *live* matchday (``dsbl-1-2026-act-2``) for entering fresh results: it is
two-thirds sailed, so races beyond that point still have no result — exactly the
situation the race committee is in mid-event. Each test claims its own, still-untouched
race so the tests don't interfere with each other. The *finished* matchday
(``dsbl-1-2026-act-1``) stands in for the protest-decision scenario: it already has
stored points, and a correction there must recompute them.
"""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import AuditLog, Boat, Event, Flight, Race, RaceEntry, RaceStatus, ResultCode
from app.models.auth import Role
from tests.stories.test_login_and_roles import login_as, make_user
from tests.stories.test_registrierung import auth_headers

LIVE_MATCHDAY = "dsbl-1-2026-act-2"
FINISHED_MATCHDAY = "dsbl-1-2026-act-1"


async def _race_officer(client, caplog, email: str) -> dict[str, str]:
    await make_user(email, Role.RACE_OFFICER)
    return auth_headers(await login_as(client, email, caplog))


async def _admin(client, caplog, email: str) -> dict[str, str]:
    await make_user(email, Role.ADMIN)
    return auth_headers(await login_as(client, email, caplog))


async def _club_manager(client, caplog, email: str) -> dict[str, str]:
    await make_user(email, Role.CLUB_MANAGER)
    return auth_headers(await login_as(client, email, caplog))


async def _unfinished_race(offset: int) -> tuple[int, int, list[int]]:
    """A race of the live matchday that hasn't been sailed yet: (event_id, race_id, boats).

    ``offset`` picks the n-th such race so different tests each get their own, still
    untouched race.
    """
    async with SessionLocal() as session:
        event_id = (
            await session.execute(select(Event.id).where(Event.slug == LIVE_MATCHDAY))
        ).scalar_one()
        race_ids = list(
            (
                await session.execute(
                    select(Race.id)
                    .join(Flight, Race.flight_id == Flight.id)
                    .where(
                        Flight.event_id == event_id,
                        Race.status == RaceStatus.SCHEDULED,
                    )
                    .order_by(Race.sequence)
                )
            ).scalars()
        )
        race_id = race_ids[offset]
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
        return event_id, race_id, boats


def _finished_payload(boats: list[int]) -> dict:
    return {
        "results": [
            {"boat_number": boat, "code": "FINISHED", "finish_position": position}
            for position, boat in enumerate(boats, start=1)
        ]
    }


async def _entries(race_id: int) -> list[RaceEntry]:
    async with SessionLocal() as session:
        return list(
            (
                await session.execute(select(RaceEntry).where(RaceEntry.race_id == race_id))
            ).scalars()
        )


class TestErgebniserfassung:
    """WL-2: race committee enters and corrects results."""

    async def test_race_officer_can_enter_results_and_points_are_recomputed(
        self, client, caplog
    ):
        event_id, race_id, boats = await _unfinished_race(offset=0)
        headers = await _race_officer(client, caplog, "wl-ro1@example.com")

        response = await client.put(
            f"/api/admin/events/{event_id}/races/{race_id}/result",
            headers=headers,
            json=_finished_payload(boats),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["applied"] is True
        assert body["version"] == 1
        # Every boat has now finished -> the race is complete.
        assert body["status"] == "finished"

        entries = await _entries(race_id)
        assert {entry.code for entry in entries} == {ResultCode.FINISHED}
        assert all(entry.points is not None for entry in entries)
        winner = next(entry for entry in entries if entry.finish_position == 1)
        # Low-point scoring: first place scores 1 point.
        assert winner.points == 1.0

    async def test_admin_can_also_enter_results(self, client, caplog):
        event_id, race_id, boats = await _unfinished_race(offset=1)
        headers = await _admin(client, caplog, "wl-admin1@example.com")

        response = await client.put(
            f"/api/admin/events/{event_id}/races/{race_id}/result",
            headers=headers,
            json=_finished_payload(boats),
        )
        assert response.status_code == 200, response.text

    async def test_club_manager_is_rejected(self, client, caplog):
        event_id, race_id, boats = await _unfinished_race(offset=2)
        headers = await _club_manager(client, caplog, "wl-cm1@example.com")

        response = await client.put(
            f"/api/admin/events/{event_id}/races/{race_id}/result",
            headers=headers,
            json=_finished_payload(boats),
        )
        assert response.status_code == 403

        # The rejected request left no mark.
        entries = await _entries(race_id)
        assert all(entry.code is None for entry in entries)

    async def test_anonymous_is_rejected(self, client):
        event_id, race_id, boats = await _unfinished_race(offset=3)

        response = await client.put(
            f"/api/admin/events/{event_id}/races/{race_id}/result",
            json=_finished_payload(boats),
        )
        assert response.status_code == 401

        entries = await _entries(race_id)
        assert all(entry.code is None for entry in entries)

    async def test_duplicate_finish_position_is_rejected(self, client, caplog):
        event_id, race_id, boats = await _unfinished_race(offset=4)
        headers = await _race_officer(client, caplog, "wl-ro2@example.com")

        payload = _finished_payload(boats)
        # Two boats both claim first place.
        payload["results"][1]["finish_position"] = 1

        response = await client.put(
            f"/api/admin/events/{event_id}/races/{race_id}/result",
            headers=headers,
            json=payload,
        )
        assert response.status_code == 422, response.text
        problem = response.json()
        assert problem["type"] == "/errors/race-result-duplicate-position"

        # Rejected as a whole: nothing was written.
        entries = await _entries(race_id)
        assert all(entry.code is None for entry in entries)

    async def test_finish_position_is_required_for_a_finish(self, client, caplog):
        event_id, race_id, boats = await _unfinished_race(offset=5)
        headers = await _race_officer(client, caplog, "wl-ro3@example.com")

        response = await client.put(
            f"/api/admin/events/{event_id}/races/{race_id}/result",
            headers=headers,
            json={"results": [{"boat_number": boats[0], "code": "FINISHED"}]},
        )
        assert response.status_code == 422, response.text
        assert response.json()["type"] == "/errors/race-result-position-required"

    async def test_a_protest_decision_corrects_an_already_scored_race(self, client, caplog):
        """A finished matchday's result is amended — points must move, not just the flag."""
        async with SessionLocal() as session:
            event_id = (
                await session.execute(
                    select(Event.id).where(Event.slug == FINISHED_MATCHDAY)
                )
            ).scalar_one()
            # finish_position == 2, deliberately not 1: another test in this suite
            # (test_scoring_storage) independently disqualifies a race's *winner* — picking
            # the runner-up here keeps the two tests from ever touching the same row.
            entry = (
                await session.execute(
                    select(RaceEntry)
                    .join(Race, RaceEntry.race_id == Race.id)
                    .join(Flight, Race.flight_id == Flight.id)
                    .where(
                        Flight.event_id == event_id,
                        RaceEntry.code == ResultCode.FINISHED,
                        RaceEntry.finish_position == 2,
                    )
                    .limit(1)
                )
            ).scalar_one()
            race_id = entry.race_id
            boat_number = (
                await session.execute(select(Boat.number).where(Boat.id == entry.boat_id))
            ).scalar_one()
            original_points = entry.points

        headers = await _race_officer(client, caplog, "wl-ro4@example.com")

        # The jury grants redress: this boat now scores 2.5 points instead of its finish.
        response = await client.put(
            f"/api/admin/events/{event_id}/races/{race_id}/result",
            headers=headers,
            json={
                "results": [
                    {"boat_number": boat_number, "code": "RDG", "redress_points": 2.5}
                ]
            },
        )
        assert response.status_code == 200, response.text

        async with SessionLocal() as session:
            corrected = await session.get(RaceEntry, entry.id)
            assert corrected.code == ResultCode.RDG
            assert corrected.finish_position is None
            assert corrected.points == 2.5
            assert corrected.points != original_points

    async def test_a_stale_submission_still_wins_but_the_discarded_state_is_logged(
        self, client, caplog
    ):
        """Two race officers edit the same race; the later submission applies (this is a
        rocking boat, not a place for a hard conflict error) but per WL-2 ("the overridden
        status is not lost but logged") the state it replaces is written to AuditLog."""
        event_id, race_id, boats = await _unfinished_race(4)
        headers = await _race_officer(client, caplog, "wl-ro5@example.com")

        first = await client.put(
            f"/api/admin/events/{event_id}/races/{race_id}/result",
            headers=headers,
            json=_finished_payload(boats),
        )
        assert first.status_code == 200, first.text
        stale_version = first.json()["version"] - 1  # what the second officer last saw

        second = await client.put(
            f"/api/admin/events/{event_id}/races/{race_id}/result",
            headers=headers,
            json={**_finished_payload(list(reversed(boats))), "version": stale_version},
        )
        assert second.status_code == 200, second.text
        assert second.json()["overwrote_existing"] is True

        async with SessionLocal() as session:
            logged = (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.entity_type == "race",
                        AuditLog.entity_id == race_id,
                        AuditLog.action == "result_overwrite",
                    )
                )
            ).scalar_one()
            assert logged.payload["submitted_on_version"] == stale_version
            assert logged.payload["actual_version"] == stale_version + 1
            discarded = logged.payload["discarded_entries"]
            # The first submission's finish order — exactly what the second one replaced.
            assert discarded[str(boats[0])]["finish_position"] == 1
