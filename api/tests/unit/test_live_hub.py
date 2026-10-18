"""The SSE hub behind Story B-5: fan-out, bounded queues, the wire format."""

import asyncio

from app.live import Coalescer, Frame, Hub


async def collect(hub: Hub, topic: str, frames: int, **kwargs) -> list[bytes]:
    """Reads the stream until ``frames`` chunks have arrived (the ``retry:`` line included)."""
    chunks: list[bytes] = []
    stream = hub.stream(topic, **kwargs)
    try:
        async for chunk in stream:
            chunks.append(chunk)
            if len(chunks) == frames:
                break
    finally:
        # `break` leaves an async generator suspended, and its `finally` — the
        # unsubscribe — runs only when it is closed. Starlette closes the generator when
        # the client goes away; a test reading it directly has to do the same.
        await stream.aclose()
    return chunks


class TestFanOut:
    async def test_every_subscriber_hears_a_change(self):
        hub = Hub()
        first = asyncio.create_task(collect(hub, "event:1", 2))
        second = asyncio.create_task(collect(hub, "event:1", 2))
        while hub.subscribers("event:1") < 2:
            await asyncio.sleep(0)

        hub.publish("event:1")

        for chunks in (await first, await second):
            assert chunks[0] == b"retry: 3000\n\n"
            assert chunks[1] == b'event: change\nid: 1\ndata: {"topic":"event:1","version":1}\n\n'
        assert hub.version("event:1") == 1
        # Both streams have ended, so the topic has no listeners left.
        assert hub.subscribers("event:1") == 0

    async def test_publishing_several_topics_versions_each_on_its_own(self):
        hub = Hub()
        hub.publish("event:1", "series:2")
        hub.publish("event:1")
        assert hub.version("event:1") == 2
        assert hub.version("series:2") == 1
        assert hub.version("event:3") == 0

    async def test_a_slow_subscriber_loses_the_oldest_frame_and_the_writer_never_waits(self):
        hub = Hub(queue_size=2)
        reader = asyncio.create_task(collect(hub, "event:1", 3))
        while hub.subscribers("event:1") < 1:
            await asyncio.sleep(0)

        # Three changes before the reader gets a turn: the queue holds two.
        hub.publish("event:1")
        hub.publish("event:1")
        hub.publish("event:1")

        chunks = await reader
        assert hub.dropped == 1
        # Versions 2 and 3 arrive; version 1 was the one dropped.
        assert b'"version":2' in chunks[1]
        assert b'"version":3' in chunks[2]


class TestWireFormat:
    def test_a_payload_frame_has_no_id(self):
        frame = Frame("positions", {"race": 5, "boats": []})
        assert frame.encode() == b'event: positions\ndata: {"race":5,"boats":[]}\n\n'

    async def test_a_reconnecting_browser_behind_the_hub_gets_one_change_at_once(self):
        hub = Hub()
        hub.publish("event:1")
        hub.publish("event:1")

        chunks = await collect(hub, "event:1", 2, last_event_id=1)
        assert chunks[1] == b'event: change\nid: 2\ndata: {"topic":"event:1","version":2}\n\n'

    async def test_a_reconnecting_browser_that_is_current_waits_quietly(self):
        hub = Hub()
        hub.publish("event:1")

        chunks = await collect(hub, "event:1", 2, last_event_id=1, heartbeat=0.01)
        # Nothing to catch up on: the next thing after `retry:` is the heartbeat — the
        # comment a quiet stream sends so proxies keep it open.
        assert chunks[1] == b": keep-alive\n\n"


class TestShutdown:
    async def test_shutdown_ends_every_stream_and_the_hub_stays_usable(self):
        hub = Hub()

        async def drain(topic: str) -> int:
            return len([chunk async for chunk in hub.stream(topic)])

        readers = [asyncio.create_task(drain("event:1")), asyncio.create_task(drain("series:2"))]
        while hub.subscribers("event:1") + hub.subscribers("series:2") < 2:
            await asyncio.sleep(0)

        await hub.shutdown()
        assert await asyncio.wait_for(asyncio.gather(*readers), 1) == [1, 1]

        # A new subscriber after shutdown gets a live stream, not a closed one.
        later = asyncio.create_task(collect(hub, "event:1", 2))
        while hub.subscribers("event:1") < 1:
            await asyncio.sleep(0)
        hub.publish("event:1")
        assert b'"version":1' in (await later)[1]


class FakeTime:
    """A clock that only moves when the coalescer sleeps — no test waits for real time."""

    def __init__(self) -> None:
        self.now = 0.0

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.now += seconds
        await asyncio.sleep(0)


class TestCoalescing:
    """Story L-1: one live snapshot per event per interval, however many phones post."""

    def coalescer(self, time: FakeTime, calls: list[tuple[int, float]], during=None):
        async def work(key: int) -> None:
            calls.append((key, time.now))
            if during is not None:
                during(key)

        return Coalescer(work, lambda: 1.0, clock=time.clock, sleep=time.sleep)

    async def test_the_first_request_runs_at_once_and_a_burst_runs_once(self):
        time, calls = FakeTime(), []
        coalescer = self.coalescer(time, calls)
        for _ in range(7):
            coalescer.request(1)
        await coalescer.drain()
        assert calls == [(1, 0.0)]

    async def test_requests_during_the_work_run_once_more_after_the_interval(self):
        time, calls = FakeTime(), []
        coalescer = None

        def burst(key: int) -> None:
            if len(calls) == 1:
                for _ in range(6):
                    coalescer.request(key)

        coalescer = self.coalescer(time, calls, during=burst)
        coalescer.request(1)
        await coalescer.drain()
        assert calls == [(1, 0.0), (1, 1.0)]

    async def test_a_request_soon_after_waits_for_the_rest_of_the_interval(self):
        time, calls = FakeTime(), []
        coalescer = self.coalescer(time, calls)
        coalescer.request(1)
        await coalescer.drain()
        time.now = 0.25
        coalescer.request(1)
        await coalescer.drain()
        assert calls == [(1, 0.0), (1, 1.0)]

    async def test_events_do_not_hold_each_other_back(self):
        time, calls = FakeTime(), []
        coalescer = self.coalescer(time, calls)
        coalescer.request(1)
        coalescer.request(2)
        await coalescer.drain()
        assert sorted(calls) == [(1, 0.0), (2, 0.0)]

    async def test_a_failing_run_does_not_stop_the_next(self):
        time, calls = FakeTime(), []

        async def work(key: int) -> None:
            calls.append((key, time.now))
            raise RuntimeError("snapshot failed")

        coalescer = Coalescer(work, lambda: 1.0, clock=time.clock, sleep=time.sleep)
        coalescer.request(1)
        await coalescer.drain()
        coalescer.request(1)
        await coalescer.drain()
        assert calls == [(1, 0.0), (1, 1.0)]
