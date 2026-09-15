"""A whole race, simulated against the real system (Story L-4, decision 13; the goal of
2026-09-15: "simulate a whole race on a real map").

The job takes a live event, lays the default course if none is laid, issues trackers,
starts the current race through the same service the committee's screen uses, streams the
emulator's fixes through the same ingest path the phones will use — so the live page hears
``positions`` frames exactly as it will on the water — and, when every boat has finished,
enters the result in the emulator's ground-truth finish order and finishes the race. Then
the next one, if asked.

Speed is a factor on wall time: at 10 the boats sail ten seconds per real second, so a
short course takes half a minute. Fixes are stamped with wall-clock time, because that is
what a phone would do.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db import SessionLocal
from app.jobs import Job
from app.live import event_topic, hub
from app.models import Boat, Event, EventStatus, Flight, Race, RaceEntry, RaceStatus, ResultCode
from app.schemas.tracking import DefaultCourseIn, FixIn
from app.services import race_state, recompute_event, recompute_series
from app.tracking import service
from app.tracking.emulate import emulated_race
from app.tracking.polar import J70, Polar

logger = logging.getLogger(__name__)

EMULATOR_ACTOR = "emulator@sbl.example.com"
#: Wall seconds between commits of the emulated fixes, and between `positions` frames.
FLUSH_SECONDS = 0.25
PUBLISH_SECONDS = 0.5


async def _flush(pending: dict[int, list[FixIn]], tokens: dict[int, str]) -> None:
    if not any(pending.values()):
        return
    async with SessionLocal() as session:
        for boat, fixes in pending.items():
            if fixes:
                await service.ingest_fixes(session, tokens[boat], fixes)
                fixes.clear()
        await session.commit()


class EmulationError(RuntimeError):
    pass


async def emulate_event(
    event_id: int,
    *,
    speed: float = 10.0,
    races: int = 1,
    seed: int = 1,
    leg_length_m: float | None = None,
    job: Job | None = None,
) -> dict[str, object]:
    """Sails ``races`` races of the event, one after the other. Returns what happened."""
    polar = Polar.load(J70)
    sailed: list[dict[str, object]] = []
    for n in range(races):
        prepared = await _prepare(event_id, leg_length_m)
        if prepared is None:
            break
        race_id, boats, tokens, geometry, projection, tws = prepared
        emulation = emulated_race(
            geometry,
            projection,
            boats=boats,
            start=datetime.now(UTC),
            polar=polar,
            tws=tws,
            seed=seed + n,
        )
        total = geometry.waypoints()
        last_publish = 0.0
        # Fixes are stamped from a monotonic clock, not `datetime.now()` per tick: the wall
        # clock on WSL2 steps backwards (docs/gotchas), and at high speed two ticks are
        # milliseconds apart — a step reorders them, and the track then jumps back and
        # forth. A phone's GPS time never runs backwards either.
        loop = asyncio.get_running_loop()
        base_wall = datetime.now(UTC)
        base_mono = loop.time()
        # Fixes are batched like a phone batches them (Story L-4): one commit per
        # FLUSH_SECONDS of wall time, whatever the speed. At ×25 a commit per tick was
        # twenty-five commits a second per emulation, and two of them at once made every
        # other request on the machine wait for the disk.
        pending: dict[int, list[FixIn]] = {boat: [] for boat in boats}
        last_flush = loop.time()
        for tick_index, (_sim_t, fixes) in enumerate(emulation.ticks()):
            now = base_wall + timedelta(seconds=loop.time() - base_mono)
            for boat, fix in fixes:
                pending[boat].append(
                    FixIn(t=now, lat=fix.lat, lon=fix.lon, sog=fix.sog, cog=fix.cog)
                )
            loop_now = loop.time()
            if loop_now - last_flush >= FLUSH_SECONDS:
                last_flush = loop_now
                await _flush(pending, tokens)
            if loop_now - last_publish >= PUBLISH_SECONDS:
                last_publish = loop_now
                await _flush(pending, tokens)
                async with SessionLocal() as session:
                    event = await session.get(Event, event_id)
                    assert event is not None
                    await service.publish_positions(session, event)
            if job is not None:
                done = sum(b.target for b in emulation.fleet)
                job.report(
                    (n + done / (len(boats) * len(total))) / races,
                    f"race {n + 1}/{races}, tick {tick_index}",
                )
            await asyncio.sleep(emulation.tick_seconds / speed)
        await _flush(pending, tokens)
        far = datetime.max.replace(tzinfo=UTC)
        order = sorted(emulation.fleet, key=lambda b: b.finished_at or far)
        finish_order = [b.number for b in order]
        finish_times = {
            b.number: (b.finished_at - emulation.start).total_seconds()
            for b in order
            if b.finished_at is not None
        }
        await _finish(event_id, race_id, finish_order)
        async with SessionLocal() as session:
            event = await session.get(Event, event_id)
            assert event is not None
            await service.publish_positions(session, event)
        sailed.append(
            {"race_id": race_id, "finish_order": finish_order, "finish_times": finish_times}
        )
        if n + 1 < races:
            await asyncio.sleep(10.0 / speed)
    return {"races": sailed}


async def _prepare(event_id: int, leg_length_m: float | None):
    async with SessionLocal() as session:
        event = await session.get(Event, event_id)
        if event is None:
            raise EmulationError(f"event {event_id} does not exist")
        if event.status != EventStatus.LIVE:
            raise EmulationError("the event is not live — start the matchday first")
        course = await service.active_course(session, event.id)
        if course is None:
            await service.lay_default_course(
                session, event, DefaultCourseIn(leg_length_m=leg_length_m)
            )
            await session.commit()
            course = await service.active_course(session, event.id)
            assert course is not None
        trackers = await service.ensure_trackers(session, event)
        await session.commit()

        running = await race_state.running_race(session, event.id)
        race = running
        if race is None:
            race = (
                await session.execute(
                    select(Race)
                    .join(Flight, Race.flight_id == Flight.id)
                    .where(Flight.event_id == event.id, Race.status == RaceStatus.SCHEDULED)
                    .order_by(Race.sequence)
                    .limit(1)
                )
            ).scalar_one_or_none()
            if race is None:
                return None
            await race_state.start_race(session, event, race, actor=EMULATOR_ACTOR)
            race.course_id = course.id
            await session.commit()
            hub.publish(event_topic(event.id))

        boats = list(
            (
                await session.execute(
                    select(Boat.number)
                    .join(RaceEntry, RaceEntry.boat_id == Boat.id)
                    .where(RaceEntry.race_id == race.id)
                    .order_by(Boat.number)
                )
            ).scalars()
        )
        numbers = dict(
            (
                await session.execute(select(Boat.id, Boat.number).where(Boat.event_id == event.id))
            ).all()
        )
        tokens = {numbers[t.boat_id]: t.device_token for t in trackers if t.boat_id is not None}
        geometry, projection = service.course_geometry(course)
        return race.id, boats, tokens, geometry, projection, course.tws_kn


async def _finish(event_id: int, race_id: int, finish_order: list[int]) -> None:
    """The committee confirms the detected order: every boat FINISHED in that order."""
    async with SessionLocal() as session:
        event = await session.get(Event, event_id)
        race = await session.get(Race, race_id)
        assert event is not None and race is not None
        rows = (
            await session.execute(
                select(RaceEntry, Boat.number)
                .join(Boat, RaceEntry.boat_id == Boat.id)
                .where(RaceEntry.race_id == race.id)
            )
        ).all()
        by_number = {number: entry for entry, number in rows}
        for position, number in enumerate(finish_order, start=1):
            entry = by_number[number]
            entry.code = ResultCode.FINISHED
            entry.finish_position = position
            entry.redress_points = None
        race.version += 1
        race_state.finish_race(session, race, actor=EMULATOR_ACTOR)
        await recompute_event(session, event.id)
        if event.series_id is not None:
            await recompute_series(session, event.series_id)
        await session.commit()
        hub.publish(event_topic(event.id))
