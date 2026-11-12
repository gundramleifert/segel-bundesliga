"""The transitions of one event's status — Stories VA-8 and VA-10.

``planned`` → ``live`` (start), ``live`` → ``final`` (finish), ``planned``/``live`` →
``cancelled`` (cancel), and back again (reopen). These functions are the **only** writers
of ``Event.status``: the event's PATCH carries no status, because there it once skipped
every rule below — an organizer could set a planned event without a pairing list to
``live``, or a never-started one to ``final``.

The rules, each of which has a reason:

* **Starting is a decision, and it needs something to sail.** The event has to be ready
  (the same reasons as the draw, ``require_ready``) and must have a pairing list. The
  catalog reason is exempt: what matters is that a list *exists*, not where it came from.
* **Finishing is a declaration, never a consequence** — only from ``live``, and it does
  not require a complete race list: a day that loses its last flights to dying wind is
  still over. A day where nothing was sailed is a cancellation.
* **Cancelling deletes nothing**, from ``planned`` or ``live``; the event leaves the
  scored set, so a called-off day costs nobody "participants + 1".
* **Reopening goes back to where the event honestly was:** ``final`` → ``live`` (it was
  being sailed), ``cancelled`` → ``planned`` (a reinstated day is prepared again) — or
  ``live`` when racing had started before it was called off (review 3.2: as ``planned``
  it took in new clubs and its results dropped out of the table).
* **Cancelling works from every state**, ``final`` included: calling off a day declared
  over is a correction, not a contradiction.
* **An import records what happened elsewhere** (``record_imported``): a planned event
  with results becomes ``live``, or ``final`` once its last day has passed — the same
  field, through this module.
* **Every transition is idempotent** — a second tap answers with the event, unchanged.
* **Publication is untouched.** ``published`` alone decides who sees an event.
* **Nothing here commits.** The router commits and then publishes on the live stream
  (``app/live.py``: after the commit, never inside the transaction).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event, EventStatus, Flight, Race
from app.problems import Problem
from app.services.event_readiness import CATALOG_REASON, racing_started, require_ready


async def has_pairing_list(session: AsyncSession, event_id: int) -> bool:
    """Whether a draw has been stored for this event — at least one race exists."""
    hit = (
        await session.execute(
            select(Race.id)
            .join(Flight, Race.flight_id == Flight.id)
            .where(Flight.event_id == event_id)
            .limit(1)
        )
    ).scalar_one_or_none()
    return hit is not None


async def start_event(session: AsyncSession, event: Event) -> None:
    """``planned`` → ``live``, once the event is ready and drawn."""
    if event.status == EventStatus.LIVE:
        return
    await require_ready(session, event, ignore={CATALOG_REASON})
    if not await has_pairing_list(session, event.id):
        raise Problem(
            409,
            "event-without-pairing-list",
            "This event has no pairing list yet, so there is nothing to sail.",
            event_id=event.id,
        )
    event.status = EventStatus.LIVE


def finish_event(event: Event) -> None:
    """``live`` → ``final``; refused for an event that never started."""
    if event.status == EventStatus.FINAL:
        return
    if event.status != EventStatus.LIVE:
        raise Problem(
            409,
            "event-not-started",
            "This event has not been started, so there is nothing to declare over.",
            event_id=event.id,
            event_status=event.status,
        )
    event.status = EventStatus.FINAL


def cancel_event(event: Event) -> None:
    """→ ``cancelled``, from any state — a ``final`` one included: calling off a day
    declared over is a correction, not a contradiction. Deletes nothing."""
    event.status = EventStatus.CANCELLED


async def reopen_event(session: AsyncSession, event: Event) -> None:
    """``final`` → ``live``; ``cancelled`` → ``planned``, or ``live`` if racing had
    started; anything else is refused."""
    if event.status == EventStatus.FINAL:
        event.status = EventStatus.LIVE
    elif event.status == EventStatus.CANCELLED:
        started = await racing_started(session, event.id)
        event.status = EventStatus.LIVE if started else EventStatus.PLANNED
    else:
        raise Problem(
            409,
            "event-not-closed",
            "This event is neither finished nor cancelled, so there is nothing to reopen.",
            event_id=event.id,
            event_status=event.status,
        )


def record_imported(event: Event, *, over: bool) -> None:
    """An import found results for a ``planned`` event: it was sailed elsewhere — ``live``,
    or ``final`` once its last day has passed. Any other state is the committee's and
    stays as it is."""
    if event.status == EventStatus.PLANNED:
        event.status = EventStatus.FINAL if over else EventStatus.LIVE
