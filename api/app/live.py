"""Live updates over Server-Sent Events, fanned out in this process (Story B-5).

The page a spectator has open must change within seconds of the race committee entering a
result — without a reload, and without every visitor polling the standings. This module is
the server half of that: a ``Hub`` of topics, each with the queues of the browsers
currently listening.

**Live is an event.** The one topic is ``event:{id}``: a series is never "live", it only
has an event that is, and a result changes the series table *because* it changes that
event. A page showing a series table therefore listens on the series' running event (or
the next planned one, so it hears the start) and refetches its own table — there is no
``series:`` topic to keep in step with the event's. Boat positions (Story L-1) will ride
the same topic.

Four rules, decided in ``docs/PLAN_LIVE_IMPLEMENTATION.md`` §3 and worth restating where
they are enforced:

* **SSE, not WebSocket.** Traffic is one-directional, ``EventSource`` reconnects by itself
  with ``Last-Event-ID``, it rides the plain HTTP path through every proxy, and it needs no
  bearer token — which it *cannot* send, and live spectator data is public anyway.
* **A ``change`` frame carries a version token, not the payload.** The browser invalidates
  the query keys it holds and refetches through the generated client, so the stream never
  ships a second serialization of a table that could disagree with the first. Boat
  positions (Story L-1) are the one inline payload, sent with :meth:`Hub.send`.
* **Publish after the commit, never inside the transaction.** A subscriber that refetches
  while the writer's transaction is still open reads the *old* rows and stays stale until
  the next change. Routers therefore call :meth:`Hub.publish` on the line *after*
  ``await session.commit()``; nothing here can enforce that, so it is said here.
* **The cost, stated openly** (the same as ``app/jobs.py``): the hub lives in one uvicorn
  process. A second worker would have subscribers the first one's writes never reach. As
  long as the server is one process this is properly dimensioned; when that changes, this
  file is where Redis pub/sub or Postgres ``LISTEN/NOTIFY`` goes, and nothing else moves.

A slow subscriber never stalls a writer: queues are bounded and the oldest frame is
dropped — a ``change`` frame is idempotent (refetch once), so losing one to a newer one
costs nothing. A heartbeat comment every :data:`HEARTBEAT_SECONDS` keeps proxies from
closing a stream that happens to be quiet between races.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from collections.abc import AsyncIterator
from dataclasses import dataclass

logger = logging.getLogger(__name__)

#: Frames a subscriber may fall behind before the oldest is dropped.
QUEUE_SIZE = 64
#: Seconds between heartbeat comments on an otherwise quiet stream.
HEARTBEAT_SECONDS = 15.0
#: What the browser is told to wait before reconnecting, in milliseconds.
RETRY_MILLIS = 3000


@dataclass(frozen=True)
class Frame:
    """One SSE message: an ``event:`` name, a JSON ``data:`` line, optionally an ``id:``."""

    event: str
    data: dict[str, object]
    id: int | None = None

    def encode(self) -> bytes:
        lines = [f"event: {self.event}"]
        if self.id is not None:
            lines.append(f"id: {self.id}")
        lines.append(f"data: {json.dumps(self.data, separators=(',', ':'))}")
        return ("\n".join(lines) + "\n\n").encode()


def change_frame(topic: str, version: int) -> Frame:
    return Frame("change", {"topic": topic, "version": version}, id=version)


class Hub:
    def __init__(self, queue_size: int = QUEUE_SIZE) -> None:
        self._queues: dict[str, set[asyncio.Queue[Frame | None]]] = defaultdict(set)
        self._versions: dict[str, int] = defaultdict(int)
        self._queue_size = queue_size
        #: Frames dropped because a subscriber fell behind. Observability, and the unit
        #: test's proof that a slow reader costs the writer nothing.
        self.dropped = 0

    def version(self, topic: str) -> int:
        """The topic's change counter — what the last ``change`` frame carried."""
        return self._versions[topic]

    def subscribers(self, topic: str) -> int:
        return len(self._queues.get(topic, ()))

    def publish(self, *topics: str) -> None:
        """Something about each topic changed: bump its version, tell every listener.

        Call this **after** ``await session.commit()`` — see the module docstring.
        """
        for topic in topics:
            self._versions[topic] += 1
            self._deliver(topic, change_frame(topic, self._versions[topic]))

    def send(self, topic: str, event: str, data: dict[str, object]) -> None:
        """A payload frame — boat positions. Leaves the version alone: nothing to refetch."""
        self._deliver(topic, Frame(event, data))

    def _deliver(self, topic: str, frame: Frame | None) -> None:
        for queue in list(self._queues.get(topic, ())):
            if queue.full():
                queue.get_nowait()
                self.dropped += 1
            queue.put_nowait(frame)

    async def stream(
        self,
        topic: str,
        *,
        last_event_id: int | None = None,
        heartbeat: float = HEARTBEAT_SECONDS,
    ) -> AsyncIterator[bytes]:
        """The bytes of one subscriber's stream, until shutdown or the client goes away.

        ``last_event_id`` is what a reconnecting browser sends. When it differs from the
        version the hub knows, a ``change`` frame goes out first: the browser missed
        something while it was away — or the server restarted and counts from zero again,
        which to the browser is the same thing — and one refetch settles it.
        """
        queue: asyncio.Queue[Frame | None] = asyncio.Queue(self._queue_size)
        self._queues[topic].add(queue)
        try:
            yield f"retry: {RETRY_MILLIS}\n\n".encode()
            current = self.version(topic)
            if last_event_id is not None and last_event_id != current:
                yield change_frame(topic, current).encode()
            while True:
                try:
                    frame = await asyncio.wait_for(queue.get(), heartbeat)
                except TimeoutError:
                    yield b": keep-alive\n\n"
                    continue
                if frame is None:
                    return
                yield frame.encode()
        finally:
            queues = self._queues.get(topic)
            if queues is not None:
                queues.discard(queue)
                if not queues:
                    del self._queues[topic]

    async def shutdown(self) -> None:
        """Ends every open stream, so the server stops instead of waiting on them.

        The hub stays usable afterwards — a new subscriber simply starts a new stream —
        which is what lets a test end the streams it opened without a server restart.
        """
        for topic in list(self._queues):
            self._deliver(topic, None)


def event_topic(event_id: int) -> str:
    """The topic of one event — the only shape a topic has, written in one place."""
    return f"event:{event_id}"


hub = Hub()
