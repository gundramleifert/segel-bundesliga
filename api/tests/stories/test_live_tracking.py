"""User Stories L-1 and L-2: the boats on the map, the course, passings and a live rank.

What these tests pin down, against emulated boats (the first data stage):

* **The committee lays a course and gets trackers** — one per boat plus the committee boat,
  tokens issued once and returned again unchanged.
* **Ingest is idempotent and token-gated** — a retried batch stores nothing twice and is
  not an error; a wrong token is refused.
* **A spectator sees the boats of a published event, and nothing of a draft.**
* **Positions ride the live stream inline** — the one payload that does not go through a
  refetch (Story B-5).
* **A whole race, simulated:** the emulation job starts the race, sails it, enters the
  detected finish order, finishes the race — and the next race is the one up.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Race
from app.tracking.emulate_job import emulate_event
from tests.stories.test_create_event import admin, event_with_participants
from tests.stories.test_event_lifecycle import draw
from tests.stories.test_live_updates import stream_until
from tests.stories.test_race_control import races_of


async def live_event(client, headers, title: str, date: str) -> int:
    event_id = await event_with_participants(client, headers, title, date)
    await draw(client, headers, event_id)
    response = await client.post(f"/api/admin/events/{event_id}/start", headers=headers)
    assert response.status_code == 200, response.text
    return event_id


async def trackers_of(client, headers, event_id: int) -> list[dict]:
    response = await client.get(f"/api/admin/events/{event_id}/trackers", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def batch(token: str, *, at: datetime, n: int = 3) -> dict:
    return {
        "token": token,
        "fixes": [
            {
                "t": (at + timedelta(seconds=i)).isoformat(),
                "lat": 54.42 + i * 1e-5,
                "lon": 10.19,
                "sog": 3.0,
                "cog": 20.0,
            }
            for i in range(n)
        ],
    }


class TestLayingTheCourse:
    """L-2: As race committee I lay the course with a few taps."""

    async def test_the_default_course_has_six_marks_and_five_waypoints(self, client, caplog):
        headers = await admin(client, caplog, "tr1@example.com")
        event_id = await live_event(client, headers, "Course Cup", "2027-11-06")

        missing = await client.get(f"/api/admin/events/{event_id}/course", headers=headers)
        assert missing.status_code == 404
        assert missing.json()["type"] == "/errors/course-not-laid"

        laid = await client.post(
            f"/api/admin/events/{event_id}/course/default",
            headers=headers,
            json={"lat": 54.42, "lon": 10.19, "wind_from_deg": 20, "leg_length_m": 300},
        )
        assert laid.status_code == 200, laid.text
        body = laid.json()
        assert sorted(m["role"] for m in body["marks"]) == sorted(
            ["committee_boat", "start_pin", "windward", "gate_left", "gate_right", "finish_pin"]
        )
        # The league's course, two laps: start – W – G – W – finish; no gate on the way in.
        assert body["waypoints"] == ["start", "windward 1", "gate 1", "windward 2", "finish"]
        assert body["wind_from_deg"] == 20

        again = await client.get(f"/api/admin/events/{event_id}/course", headers=headers)
        assert again.json()["id"] == body["id"]

    async def test_a_re_lay_is_a_new_course_and_a_started_race_keeps_its_own(self, client, caplog):
        headers = await admin(client, caplog, "tr2@example.com")
        event_id = await live_event(client, headers, "Relay Cup", "2027-11-07")
        first = (
            await client.post(f"/api/admin/events/{event_id}/course/default", headers=headers)
        ).json()
        (race_id, _), *_ = await races_of(event_id)
        started = await client.post(
            f"/api/admin/events/{event_id}/races/{race_id}/start", headers=headers
        )
        assert started.status_code == 200, started.text

        second = (
            await client.post(f"/api/admin/events/{event_id}/course/default", headers=headers)
        ).json()
        assert second["id"] != first["id"]
        async with SessionLocal() as session:
            race = await session.get(Race, race_id)
        assert race.course_id == first["id"]

    async def test_a_guest_may_not_lay_a_course(self, client, caplog):
        headers = await admin(client, caplog, "tr3@example.com")
        event_id = await live_event(client, headers, "Guest Cup", "2027-11-08")
        response = await client.post(f"/api/admin/events/{event_id}/course/default")
        assert response.status_code == 401


class TestTrackersAndIngest:
    """L-1: The tracker belongs to the boat; a batch of fixes is idempotent."""

    async def test_one_tracker_per_boat_plus_the_committee_boat(self, client, caplog):
        headers = await admin(client, caplog, "tr4@example.com")
        event_id = await live_event(client, headers, "Tracker Cup", "2027-11-13")
        trackers = await trackers_of(client, headers, event_id)
        assert [t["boat_number"] for t in trackers] == [1, 2, 3, 4, 5, 6, None]
        assert trackers[-1]["mark_role"] == "committee_boat"
        assert len({t["device_token"] for t in trackers}) == 7

        again = await trackers_of(client, headers, event_id)
        assert [t["device_token"] for t in again] == [t["device_token"] for t in trackers]

    async def test_a_batch_is_stored_once_however_often_it_arrives(self, client, caplog):
        headers = await admin(client, caplog, "tr5@example.com")
        event_id = await live_event(client, headers, "Idempotent Cup", "2027-11-14")
        token = (await trackers_of(client, headers, event_id))[0]["device_token"]
        payload = batch(token, at=datetime.now(UTC))

        first = await client.post("/api/track/fixes", json=payload)
        assert first.status_code == 200, first.text
        assert first.json() == {"stored": 3, "duplicates": 0}

        second = await client.post("/api/track/fixes", json=payload)
        assert second.json() == {"stored": 0, "duplicates": 3}

    async def test_an_unknown_token_is_refused(self, client):
        response = await client.post(
            "/api/track/fixes", json=batch("not-a-token", at=datetime.now(UTC))
        )
        assert response.status_code == 401
        assert response.json()["type"] == "/errors/tracker-unknown"


class TestTheLivePicture:
    """L-1: As a spectator I see the boats move."""

    async def test_positions_reach_a_spectator_inline_over_the_stream(self, client, caplog):
        headers = await admin(client, caplog, "tr6@example.com")
        event_id = await live_event(client, headers, "Stream Cup", "2027-11-20")
        trackers = await trackers_of(client, headers, event_id)
        token = trackers[2]["device_token"]

        sent = await stream_until(
            client,
            f"event:{event_id}",
            lambda: client.post("/api/track/fixes", json=batch(token, at=datetime.now(UTC))),
        )
        assert "event: positions" in sent
        assert f'"event_id":{event_id}' in sent
        assert '"boat_number":3' in sent

        live = await client.get(f"/api/events/{event_id}/live")
        assert live.status_code == 200, live.text
        body = live.json()
        assert body["race"] is None
        assert body["next_race"]["sequence"] == 1
        boat = next(b for b in body["boats"] if b["boat_number"] == 3)
        assert abs(boat["sog_kn"] - 3.0 / (1852 / 3600)) < 0.01
        assert boat["cog"] == 20.0
        assert len(boat["trail"]) == 3

    async def test_the_picture_carries_hull_size_and_zone(self, client, caplog):
        """The map draws boats at 7 m and a zone of three lengths around every rounding mark;
        both numbers come from the server's settings, so the map never hard-codes a class."""
        headers = await admin(client, caplog, "tr6b@example.com")
        event_id = await live_event(client, headers, "Zone Cup", "2027-11-22")
        body = (await client.get(f"/api/events/{event_id}/live")).json()
        assert body["boat_length_m"] == 7.0
        assert body["boat_beam_m"] > 0
        assert body["zone_radius_m"] == 3 * body["boat_length_m"] == 21.0

    async def test_an_event_may_point_its_live_view_elsewhere(self, client, caplog):
        """External or internal live view: a `live_url` on the event sends the site's live
        links to a hosted viewer; cleared, the internal map is the live view again."""
        headers = await admin(client, caplog, "tr6c@example.com")
        event_id = await live_event(client, headers, "Hosted Cup", "2027-11-23")
        assert (await client.get(f"/api/events/{event_id}")).json()["event"]["live_url"] is None

        external = await client.patch(
            f"/api/admin/events/{event_id}",
            headers=headers,
            json={"live_url": "https://example.sapsailing.com/gwt/RaceBoard.html?event=1"},
        )
        assert external.status_code == 200, external.text
        shown = (await client.get(f"/api/events/{event_id}")).json()["event"]["live_url"]
        assert shown == "https://example.sapsailing.com/gwt/RaceBoard.html?event=1"

        not_a_url = await client.patch(
            f"/api/admin/events/{event_id}", headers=headers, json={"live_url": "sapsailing"}
        )
        assert not_a_url.status_code == 422

        internal = await client.patch(
            f"/api/admin/events/{event_id}", headers=headers, json={"live_url": None}
        )
        assert internal.status_code == 200
        assert (await client.get(f"/api/events/{event_id}")).json()["event"]["live_url"] is None


        headers = await admin(client, caplog, "tr7@example.com")
        created = await client.post(
            "/api/admin/events",
            headers=headers,
            json={"title": "Hidden Boats", "starts_on": "2027-11-21", "published": False},
        )
        response = await client.get(f"/api/events/{created.json()['id']}/live")
        assert response.status_code == 404


class TestAWholeRaceSimulated:
    """L-2 and the goal of 2026-09-15: start, sail the course, finish, next race."""

    async def test_the_emulator_sails_a_race_and_the_next_one_is_up(self, client, caplog):
        headers = await admin(client, caplog, "tr8@example.com")
        event_id = await live_event(client, headers, "Simulated Cup", "2027-11-27")
        (first_id, _), (second_id, _), *_ = await races_of(event_id)

        summary = await asyncio.wait_for(
            emulate_event(event_id, speed=1000.0, races=1, seed=3, leg_length_m=200.0),
            timeout=120,
        )

        assert summary["races"][0]["race_id"] == first_id
        finish_order = summary["races"][0]["finish_order"]
        assert sorted(finish_order) == [1, 2, 3, 4, 5, 6]

        # The race is finished with the emulator's finish order as its result...
        races = (await client.get(f"/api/admin/events/{event_id}/races", headers=headers)).json()
        first = next(r for r in races["races"] if r["id"] == first_id)
        assert first["status"] == "finished"
        assert first["started_at"] is not None and first["finished_at"] is not None
        by_position = sorted(first["entries"], key=lambda e: e["finish_position"])
        assert [e["boat_number"] for e in by_position] == finish_order
        assert all(e["code"] == "FINISHED" for e in first["entries"])
        # ...the standings know it...
        detail = (await client.get(f"/api/events/{event_id}")).json()
        assert detail["races_scored"] == 1
        # ...and the next race is the one up, with the course stamped on the first.
        live = (await client.get(f"/api/events/{event_id}/live")).json()
        # Between races the picture lingers on the one just sailed, so the finish stays on
        # the map until the next gun; "next up" already names the second race.
        assert live["race"]["id"] == first_id
        assert live["race"]["status"] == "finished"
        assert live["next_race"]["id"] == second_id
        assert live["course"] is not None
        # The detector sees noised positions, so two boats finishing within a couple of
        # seconds may swap; every pair further apart than that has to be in truth order.
        detected = live["detected_finish_order"]
        assert sorted(detected) == sorted(finish_order)
        times = summary["races"][0]["finish_times"]
        for ahead, behind in zip(finish_order, finish_order[1:], strict=False):
            if times[behind] - times[ahead] > 3.0:
                assert detected.index(ahead) < detected.index(behind), (ahead, behind, detected)
        assert len(live["boats"]) == 6
        async with SessionLocal() as session:
            race = await session.get(Race, first_id)
            assert race.course_id == live["course"]["id"]
            fixes = (await session.execute(select(Race.id).where(Race.id == first_id))).all()
            assert fixes

    async def test_the_live_picture_ranks_boats_while_they_sail(self, client, caplog):
        headers = await admin(client, caplog, "tr9@example.com")
        event_id = await live_event(client, headers, "Ranked Cup", "2027-11-28")
        snapshots: list[dict] = []

        async def watch() -> None:
            # Sample the public picture while the race runs.
            for _ in range(400):
                await asyncio.sleep(0.02)
                live = (await client.get(f"/api/events/{event_id}/live")).json()
                if live["race"] is not None and any(b["rank"] is not None for b in live["boats"]):
                    snapshots.append(live)
                    if len(snapshots) >= 3:
                        return

        watcher = asyncio.create_task(watch())
        await asyncio.wait_for(
            emulate_event(event_id, speed=300.0, races=1, seed=5, leg_length_m=200.0), timeout=180
        )
        await watcher
        assert snapshots, "never saw a ranked picture while the race ran"
        picture = snapshots[-1]
        ranks = sorted(b["rank"] for b in picture["boats"])
        assert ranks == [1, 2, 3, 4, 5, 6]
        assert all(b["leg_name"] is not None and b["sog_kn"] >= 0 for b in picture["boats"])
        # What the panel and the map draw beside the boats: "leg 2/4", the gap to the
        # leader, the wind, laylines from the polar, and the leader's line.
        assert picture["leg_count"] == 4  # start – W – G – W – finish: four legs, not five marks
        assert picture["wind_from_deg"] is not None
        assert len(picture["laylines"]) == 6
        assert all(len(line["points"]) == 2 for line in picture["laylines"])
        racing = [b for b in picture["boats"] if b["finished_at"] is None]
        assert min(b["to_leader_m"] for b in racing) == 0
        if any(0 < b["leg"] <= 4 for b in racing):
            assert picture["leader_line"] is not None and len(picture["leader_line"]) == 2
        assert picture["race"]["status"] == "running"
