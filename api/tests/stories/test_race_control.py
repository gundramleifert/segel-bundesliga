"""User Story WL-3: start, recall and finish races from one screen.

Until now a race went from ``scheduled`` straight to ``finished`` when a result was saved;
``running`` and ``started_at`` were never set, and neither scoring nor the result PUT ever
looked at ``Race.status``. These tests pin down what makes the state machine real rather
than advisory:

* **Races run one at a time** — a second start, and a result for a *scheduled* race while
  another one runs, are refused. A correction to a *finished* race is not: that is the
  protest case.
* **Recall and abandon clear the entries**, so an abandoned race scores nothing because
  there is nothing to score, not because of a status flag.
* **A recalled first race leaves the event frozen** — the start's audit row outlives the
  recall.
* **Signals**: AP only while scheduled, X and S only while running, one at a time, hauled
  down with ``null``; the preparatory flag is stored with the start.
"""

from sqlalchemy import select

from app.db import SessionLocal
from app.live import hub
from app.models import AuditLog, Boat, Flight, Race, RaceEntry
from app.models.auth import Role
from app.services.event_readiness import configuration_frozen
from tests.stories.test_create_event import admin, event_with_participants
from tests.stories.test_event_lifecycle import draw
from tests.stories.test_login_and_roles import login_as, make_user
from tests.stories.test_registration import auth_headers


async def as_role(client, caplog, email: str, role: Role) -> dict[str, str]:
    await make_user(email, role)
    return auth_headers(await login_as(client, email, caplog))


async def live_event(client, headers, title: str, date: str) -> int:
    """Drawn and started: the state the race committee's screen begins in."""
    event_id = await event_with_participants(client, headers, title, date)
    await draw(client, headers, event_id)
    response = await client.post(f"/api/admin/events/{event_id}/start", headers=headers)
    assert response.status_code == 200, response.text
    return event_id


async def races_of(event_id: int) -> list[tuple[int, list[int]]]:
    """Every race of the event in sequence, with its boat numbers."""
    async with SessionLocal() as session:
        race_ids = list(
            (
                await session.execute(
                    select(Race.id)
                    .join(Flight, Race.flight_id == Flight.id)
                    .where(Flight.event_id == event_id)
                    .order_by(Race.sequence)
                )
            ).scalars()
        )
        out = []
        for race_id in race_ids:
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
            out.append((race_id, boats))
        return out


async def race_row(race_id: int) -> Race:
    async with SessionLocal() as session:
        return await session.get(Race, race_id)


async def entries_of(race_id: int) -> list[RaceEntry]:
    async with SessionLocal() as session:
        return list(
            (await session.execute(select(RaceEntry).where(RaceEntry.race_id == race_id))).scalars()
        )


async def audit_actions(race_id: int) -> list[str]:
    async with SessionLocal() as session:
        return list(
            (
                await session.execute(
                    select(AuditLog.action)
                    .where(AuditLog.entity_type == "race", AuditLog.entity_id == race_id)
                    .order_by(AuditLog.id)
                )
            ).scalars()
        )


def full_result(boats: list[int]) -> dict:
    return {
        "results": [
            {"boat_number": boat, "code": "FINISHED", "finish_position": position}
            for position, boat in enumerate(boats, start=1)
        ]
    }


class TestStartingARace:
    """WL-3: As race committee I start the current race with one tap."""

    async def test_the_gun_puts_the_race_on_the_water(self, client, caplog):
        headers = await admin(client, caplog, "rc1@example.com")
        event_id = await live_event(client, headers, "Control Cup", "2027-10-02")
        (race_id, _), *_ = await races_of(event_id)
        version_before = hub.version(f"event:{event_id}")

        response = await client.post(
            f"/api/admin/events/{event_id}/races/{race_id}/start", headers=headers
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "running"
        assert body["started_at"] is not None
        assert body["finished_at"] is None
        assert body["preparatory"] == "P"
        assert body["signal"] is None
        assert len(body["entries"]) == 6
        # The live page hears it (Story B-5), and the start is on record.
        assert hub.version(f"event:{event_id}") == version_before + 1
        assert await audit_actions(race_id) == ["start"]

    async def test_a_second_tap_on_start_is_not_an_error(self, client, caplog):
        headers = await admin(client, caplog, "rc2@example.com")
        event_id = await live_event(client, headers, "Double Tap Cup", "2027-10-03")
        (race_id, _), *_ = await races_of(event_id)
        url = f"/api/admin/events/{event_id}/races/{race_id}/start"

        first = await client.post(url, headers=headers)
        second = await client.post(url, headers=headers)

        assert second.status_code == 200, second.text
        assert second.json()["started_at"] == first.json()["started_at"]
        assert await audit_actions(race_id) == ["start"]

    async def test_races_run_one_at_a_time(self, client, caplog):
        headers = await admin(client, caplog, "rc3@example.com")
        event_id = await live_event(client, headers, "One At A Time Cup", "2027-10-04")
        (first, _), (second, _), *_ = await races_of(event_id)
        await client.post(f"/api/admin/events/{event_id}/races/{first}/start", headers=headers)

        response = await client.post(
            f"/api/admin/events/{event_id}/races/{second}/start", headers=headers
        )

        assert response.status_code == 409, response.text
        body = response.json()
        assert body["type"] == "/errors/race-already-running"
        assert body["race_id"] == first

    async def test_the_preparatory_flag_is_stored_with_the_start(self, client, caplog):
        headers = await admin(client, caplog, "rc4@example.com")
        event_id = await live_event(client, headers, "U Flag Cup", "2027-10-05")
        (race_id, _), *_ = await races_of(event_id)

        response = await client.post(
            f"/api/admin/events/{event_id}/races/{race_id}/start",
            headers=headers,
            json={"preparatory": "U"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["preparatory"] == "U"

        invalid = await client.post(
            f"/api/admin/events/{event_id}/races/{race_id}/start",
            headers=headers,
            json={"preparatory": "Q"},
        )
        assert invalid.status_code == 422

    async def test_a_race_needs_a_live_event(self, client, caplog):
        headers = await admin(client, caplog, "rc5@example.com")
        event_id = await event_with_participants(client, headers, "Planned Cup", "2027-10-06")
        await draw(client, headers, event_id)
        (race_id, _), *_ = await races_of(event_id)

        response = await client.post(
            f"/api/admin/events/{event_id}/races/{race_id}/start", headers=headers
        )

        assert response.status_code == 409, response.text
        assert response.json()["type"] == "/errors/event-not-live"

    async def test_an_editor_may_not_run_races(self, client, caplog):
        headers = await admin(client, caplog, "rc6@example.com")
        event_id = await live_event(client, headers, "Roles Cup", "2027-10-07")
        (race_id, _), *_ = await races_of(event_id)
        editor = await as_role(client, caplog, "rc6-editor@example.com", Role.EDITOR)
        officer = await as_role(client, caplog, "rc6-officer@example.com", Role.RACE_OFFICER)

        refused = await client.post(
            f"/api/admin/events/{event_id}/races/{race_id}/start", headers=editor
        )
        allowed = await client.post(
            f"/api/admin/events/{event_id}/races/{race_id}/start", headers=officer
        )

        assert refused.status_code == 403, refused.text
        assert allowed.status_code == 200, allowed.text


class TestRecallAndAbandon:
    """WL-3: First Substitute and N — the race is void, and the screen says so honestly."""

    async def test_a_general_recall_resets_the_race_and_clears_its_entries(self, client, caplog):
        headers = await admin(client, caplog, "rc7@example.com")
        event_id = await live_event(client, headers, "Recall Cup", "2027-10-09")
        (race_id, boats), *_ = await races_of(event_id)
        base = f"/api/admin/events/{event_id}/races/{race_id}"
        await client.post(f"{base}/start", headers=headers)
        # Two boats already over the line when the recall goes up.
        partial = await client.put(
            f"{base}/result",
            headers=headers,
            json={
                "results": [
                    {"boat_number": boats[0], "code": "FINISHED", "finish_position": 1},
                    {"boat_number": boats[1], "code": "OCS"},
                ]
            },
        )
        assert partial.status_code == 200, partial.text

        response = await client.post(f"{base}/recall", headers=headers)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "scheduled"
        assert body["started_at"] is None
        assert all(entry["code"] is None for entry in body["entries"])
        cleared = await entries_of(race_id)
        assert all(entry.code is None and entry.points is None for entry in cleared)
        assert await audit_actions(race_id) == ["start", "recall"]

    async def test_a_recalled_first_race_leaves_the_event_frozen(self, client, caplog):
        headers = await admin(client, caplog, "rc8@example.com")
        event_id = await live_event(client, headers, "Frozen Cup", "2027-10-10")
        (race_id, _), *_ = await races_of(event_id)
        base = f"/api/admin/events/{event_id}/races/{race_id}"
        await client.post(f"{base}/start", headers=headers)
        await client.post(f"{base}/recall", headers=headers)

        async with SessionLocal() as session:
            frozen = await configuration_frozen(session, event_id)
        assert frozen is not None
        assert frozen.races_started == 0
        assert frozen.results_recorded == 0
        assert frozen.races_started_once == 1

        # And the endpoints that change the setup say so.
        redraw = await client.post(
            f"/api/admin/events/{event_id}/pairing/from-catalog",
            headers=headers,
            json={"seed": 2},
        )
        assert redraw.status_code == 409, redraw.text
        assert redraw.json()["type"] == "/errors/event-configuration-frozen"

    async def test_recalling_a_race_that_is_not_running_is_refused(self, client, caplog):
        headers = await admin(client, caplog, "rc9@example.com")
        event_id = await live_event(client, headers, "Not Running Cup", "2027-10-11")
        (race_id, _), *_ = await races_of(event_id)

        response = await client.post(
            f"/api/admin/events/{event_id}/races/{race_id}/recall", headers=headers
        )

        assert response.status_code == 409, response.text
        assert response.json()["type"] == "/errors/race-not-running"

    async def test_abandon_with_resail_is_a_reset(self, client, caplog):
        headers = await admin(client, caplog, "rc10@example.com")
        event_id = await live_event(client, headers, "Resail Cup", "2027-10-12")
        (race_id, _), *_ = await races_of(event_id)
        base = f"/api/admin/events/{event_id}/races/{race_id}"
        await client.post(f"{base}/start", headers=headers)

        response = await client.post(f"{base}/abandon?resail=true", headers=headers)

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "scheduled"
        # …and it can be started again.
        again = await client.post(f"{base}/start", headers=headers)
        assert again.status_code == 200, again.text
        assert await audit_actions(race_id) == ["start", "abandon", "start"]

    async def test_abandon_without_resail_scores_nothing(self, client, caplog):
        headers = await admin(client, caplog, "rc11@example.com")
        event_id = await live_event(client, headers, "Void Cup", "2027-10-13")
        (race_id, boats), *_ = await races_of(event_id)
        base = f"/api/admin/events/{event_id}/races/{race_id}"
        await client.post(f"{base}/start", headers=headers)
        entered = await client.put(f"{base}/result", headers=headers, json=full_result(boats))
        assert entered.status_code == 200, entered.text
        # Finished — but the jury voids it afterwards? No: N is a committee signal on the
        # water. So the honest sequence is: start, boats finish, committee abandons.
        # The PUT above finished the race; put it back on the water for the abandonment.
        # (A finished race is abandoned through a correction, not through N.)
        assert (await race_row(race_id)).status == "finished"
        refused = await client.post(f"{base}/abandon?resail=false", headers=headers)
        assert refused.status_code == 409, refused.text

        # The realistic case: running, some results in, then N.
        (second_id, second_boats) = (await races_of(event_id))[1]
        second = f"/api/admin/events/{event_id}/races/{second_id}"
        await client.post(f"{second}/start", headers=headers)
        await client.put(
            f"{second}/result",
            headers=headers,
            json={
                "results": [
                    {"boat_number": second_boats[0], "code": "FINISHED", "finish_position": 1}
                ]
            },
        )
        scored_before = (await client.get(f"/api/events/{event_id}")).json()["races_scored"]

        response = await client.post(f"{second}/abandon?resail=false", headers=headers)

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "abandoned"
        assert all(entry.code is None for entry in await entries_of(second_id))
        # Only the first race counts: the abandoned one has nothing to score.
        after = (await client.get(f"/api/events/{event_id}")).json()
        assert after["races_scored"] == 1
        # Before the N a race with one result recorded already counted as "scored" for the
        # progress line (any code counts); the abandonment took it back out.
        assert scored_before == 2

        # Nothing can be entered for it any more.
        late = await client.put(f"{second}/result", headers=headers, json=full_result(second_boats))
        assert late.status_code == 409, late.text
        assert late.json()["type"] == "/errors/race-abandoned"
        # Idempotent: a second N on an abandoned race is not an error.
        again = await client.post(f"{second}/abandon?resail=false", headers=headers)
        assert again.status_code == 200, again.text


class TestFinishingThroughTheResult:
    """WL-3: the finish is the result PUT — and the PUT respects the state machine."""

    async def test_a_full_result_finishes_the_running_race(self, client, caplog):
        headers = await admin(client, caplog, "rc12@example.com")
        event_id = await live_event(client, headers, "Finish Cup", "2027-10-16")
        (race_id, boats), *_ = await races_of(event_id)
        base = f"/api/admin/events/{event_id}/races/{race_id}"
        await client.post(f"{base}/start", headers=headers)

        response = await client.put(f"{base}/result", headers=headers, json=full_result(boats))

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "finished"
        race = await race_row(race_id)
        assert race.started_at is not None
        assert race.finished_at is not None
        assert await audit_actions(race_id) == ["start", "finish"]

    async def test_no_result_for_a_scheduled_race_while_another_runs(self, client, caplog):
        headers = await admin(client, caplog, "rc13@example.com")
        event_id = await live_event(client, headers, "Queue Cup", "2027-10-17")
        (first, _), (second, second_boats), *_ = await races_of(event_id)
        await client.post(f"/api/admin/events/{event_id}/races/{first}/start", headers=headers)

        response = await client.put(
            f"/api/admin/events/{event_id}/races/{second}/result",
            headers=headers,
            json=full_result(second_boats),
        )

        assert response.status_code == 409, response.text
        assert response.json()["type"] == "/errors/race-already-running"

    async def test_a_finished_race_stays_correctable_while_another_runs(self, client, caplog):
        headers = await admin(client, caplog, "rc14@example.com")
        event_id = await live_event(client, headers, "Protest Cup", "2027-10-18")
        (first, first_boats), (second, _), *_ = await races_of(event_id)
        base = f"/api/admin/events/{event_id}/races"
        await client.post(f"{base}/{first}/start", headers=headers)
        await client.put(f"{base}/{first}/result", headers=headers, json=full_result(first_boats))
        await client.post(f"{base}/{second}/start", headers=headers)

        # The protest on race 1 is decided while race 2 is on the water.
        response = await client.put(
            f"{base}/{first}/result",
            headers=headers,
            json={"results": [{"boat_number": first_boats[0], "code": "DSQ"}]},
        )

        assert response.status_code == 200, response.text

    async def test_a_result_without_a_start_still_finishes_the_race(self, client, caplog):
        # The correction tab's flow from before WL-3 keeps working: nothing running, a
        # result lands, the race is finished — with a finished_at and no started_at.
        headers = await admin(client, caplog, "rc15@example.com")
        event_id = await live_event(client, headers, "Old Flow Cup", "2027-10-19")
        (race_id, boats), *_ = await races_of(event_id)

        response = await client.put(
            f"/api/admin/events/{event_id}/races/{race_id}/result",
            headers=headers,
            json=full_result(boats),
        )

        assert response.status_code == 200, response.text
        race = await race_row(race_id)
        assert race.status == "finished"
        assert race.started_at is None
        assert race.finished_at is not None


class TestSignals:
    """WL-3: AP, X and S are state on the race; hoisting one is an audit row."""

    async def test_ap_postpones_a_scheduled_race_and_comes_down_again(self, client, caplog):
        headers = await admin(client, caplog, "rc16@example.com")
        event_id = await live_event(client, headers, "AP Cup", "2027-10-23")
        (race_id, _), *_ = await races_of(event_id)
        base = f"/api/admin/events/{event_id}/races/{race_id}"

        up = await client.post(f"{base}/signal", headers=headers, json={"signal": "AP"})
        assert up.status_code == 200, up.text
        assert up.json()["signal"] == "AP"
        assert up.json()["status"] == "scheduled"

        down = await client.post(f"{base}/signal", headers=headers, json={"signal": None})
        assert down.status_code == 200, down.text
        assert down.json()["signal"] is None
        assert await audit_actions(race_id) == ["signal", "signal"]

    async def test_ap_needs_a_race_that_has_not_started(self, client, caplog):
        headers = await admin(client, caplog, "rc17@example.com")
        event_id = await live_event(client, headers, "Late AP Cup", "2027-10-24")
        (race_id, _), *_ = await races_of(event_id)
        base = f"/api/admin/events/{event_id}/races/{race_id}"
        await client.post(f"{base}/start", headers=headers)

        response = await client.post(f"{base}/signal", headers=headers, json={"signal": "AP"})

        assert response.status_code == 409, response.text
        assert response.json()["type"] == "/errors/race-not-scheduled"

    async def test_x_and_s_need_a_running_race(self, client, caplog):
        headers = await admin(client, caplog, "rc18@example.com")
        event_id = await live_event(client, headers, "X Cup", "2027-10-25")
        (race_id, _), *_ = await races_of(event_id)
        base = f"/api/admin/events/{event_id}/races/{race_id}"

        early = await client.post(f"{base}/signal", headers=headers, json={"signal": "X"})
        assert early.status_code == 409, early.text
        assert early.json()["type"] == "/errors/race-not-running"

        await client.post(f"{base}/start", headers=headers)
        x = await client.post(f"{base}/signal", headers=headers, json={"signal": "X"})
        assert x.status_code == 200, x.text
        assert x.json()["signal"] == "X"
        # One signal at a time: S replaces X.
        s = await client.post(f"{base}/signal", headers=headers, json={"signal": "S"})
        assert s.json()["signal"] == "S"

    async def test_the_start_clears_a_postponement(self, client, caplog):
        headers = await admin(client, caplog, "rc19@example.com")
        event_id = await live_event(client, headers, "AP Then Start Cup", "2027-10-26")
        (race_id, _), *_ = await races_of(event_id)
        base = f"/api/admin/events/{event_id}/races/{race_id}"
        await client.post(f"{base}/signal", headers=headers, json={"signal": "AP"})

        started = await client.post(f"{base}/start", headers=headers)

        assert started.json()["signal"] is None

    async def test_an_unknown_flag_is_refused(self, client, caplog):
        headers = await admin(client, caplog, "rc20@example.com")
        event_id = await live_event(client, headers, "Flag Cup", "2027-10-27")
        (race_id, _), *_ = await races_of(event_id)

        response = await client.post(
            f"/api/admin/events/{event_id}/races/{race_id}/signal",
            headers=headers,
            json={"signal": "Y"},
        )
        assert response.status_code == 422
