"""The SSE hub behind Story B-5: fan-out, bounded queues, the wire format."""

import asyncio

from app.live import Frame, Hub


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
    def test_a_frame_is_event_id_and_one_json_data_line(self):
        frame = Frame("change", {"topic": "event:1", "version": 7}, id=7)
        assert frame.encode() == b'event: change\nid: 7\ndata: {"topic":"event:1","version":7}\n\n'

    def test_a_payload_frame_has_no_id(self):
        frame = Frame("positions", {"race": 5, "boats": []})
        assert frame.encode() == b'event: positions\ndata: {"race":5,"boats":[]}\n\n'

    async def test_a_quiet_stream_sends_a_heartbeat_comment(self):
        hub = Hub()
        chunks = await collect(hub, "event:1", 2, heartbeat=0.01)
        assert chunks[1] == b": keep-alive\n\n"

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
        # Nothing to catch up on: the next thing after `retry:` is the heartbeat.
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
