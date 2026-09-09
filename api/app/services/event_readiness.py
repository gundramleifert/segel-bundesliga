"""Is this event ready to be raced — and may its setup still be changed?

Two questions with two different answers, and both are **computed, never stored**:

*Readiness* asks whether the setup is complete and consistent enough to draw a pairing
list and start racing. It is deliberately not a boolean: the organizer has to be told
*what* is missing, so the answer is a list of :class:`ReadinessReason` — a stable code plus
the numbers involved, which the client turns into a sentence in its own language (see
``docs/concepts.md``, "Errors"). Saving an event never consults this: an event with no
clubs, no boats and no date is the normal early state, not an error.

*Frozen* asks the opposite question: whether racing has begun, after which the setup must
no longer move. It covers the **configuration** — the dimensions, the boats, the entered
clubs, the pairing list — and emphatically **not the results**. Entering and correcting
results is the whole point of the race committee screens, and a protest decision must stay
possible months later (see ``docs/concepts.md``, "Scoring").
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Boat, Event, Flight, Race, RaceEntry, RaceStatus
from app.pairing.catalog import CatalogError, catalog_entries, load_entry
from app.problems import Problem
from app.services.participation import event_entries

# The one reason that only binds the catalog path — see `require_ready(ignore=...)`.
CATALOG_REASON = "pairing-catalog-missing"

# A single-cause failure keeps its own status, so it reads exactly as it did before this
# module existed: a missing catalog entry is a 404 (nothing is stored for these
# dimensions), everything else a 409 (the setup contradicts itself).
_STATUS = {CATALOG_REASON: 404}

_TITLES = {
    "pairing-team-count-mismatch": (
        "The number of registered teams does not match this event's setup."
    ),
    CATALOG_REASON: "No pre-computed pairing list is stored for this size.",
    "event-boat-count-mismatch": "The boats set up do not match this event's boat count.",
    "event-dates-missing": "This event has no date yet.",
}


@dataclass(frozen=True)
class ReadinessReason:
    """One reason an event isn't ready — machine-readable, not an English sentence.

    ``code`` is the contract (the same code a ``Problem`` would carry, so the frontend
    maps it in its ``errors`` namespace); ``details`` carries the facts needed to phrase
    it — how many teams are registered against how many are configured, which sizes the
    catalog does have.
    """

    code: str
    details: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "details": self.details}


@dataclass(frozen=True)
class FrozenConfiguration:
    """Why the setup can no longer be changed: racing has started."""

    races_started: int
    results_recorded: int

    def as_dict(self) -> dict[str, int]:
        return {
            "races_started": self.races_started,
            "results_recorded": self.results_recorded,
        }


async def event_readiness(session: AsyncSession, event: Event) -> list[ReadinessReason]:
    """Everything that still stands between this event and its first race.

    An empty list means ready. The order is the order in which an organizer fixes them:
    first the entered clubs, then the boats, then the dimensions as a whole, then the date.
    """
    reasons: list[ReadinessReason] = []

    registered = len(await event_entries(session, event.id))
    if registered != event.team_count:
        # Same code the pairing draw has always raised — a draw asks exactly this
        # question, so it must not answer it a second way.
        reasons.append(
            ReadinessReason(
                "pairing-team-count-mismatch",
                {"registered": registered, "configured": event.team_count},
            )
        )

    boats = int(
        (
            await session.execute(
                select(func.count(Boat.id)).where(Boat.event_id == event.id)
            )
        ).scalar_one()
    )
    if boats != event.boat_count:
        reasons.append(
            ReadinessReason(
                "event-boat-count-mismatch",
                {"configured_boats": boats, "boat_count": event.boat_count},
            )
        )

    # The draw itself: without a stored list for these dimensions there is nothing to take
    # from the catalog, and computing one is a job of minutes (see `docs/findings.md`).
    try:
        load_entry(event.team_count, event.boat_count, event.flight_count)
    except CatalogError:
        reasons.append(
            ReadinessReason(
                CATALOG_REASON,
                {
                    "teams": event.team_count,
                    "boats": event.boat_count,
                    "flights": event.flight_count,
                    "available": [
                        f"{entry.teams}/{entry.boats}/{entry.flights}"
                        for entry in catalog_entries()
                    ],
                },
            )
        )

    if event.starts_on is None or event.ends_on is None:
        reasons.append(
            ReadinessReason(
                "event-dates-missing",
                {
                    "starts_on": event.starts_on.isoformat() if event.starts_on else None,
                    "ends_on": event.ends_on.isoformat() if event.ends_on else None,
                },
            )
        )

    return reasons


async def configuration_frozen(
    session: AsyncSession, event_id: int
) -> FrozenConfiguration | None:
    """Whether racing has begun, so the setup must stay as it is.

    The trigger is precise and does not depend on ``Event.status``, which someone can set
    by hand: **any race that has left ``scheduled``** (running, finished, abandoned) or
    **any result already recorded**. Either one means the pairing list is being sailed, and
    swapping boats or clubs underneath it would orphan results.

    A redraw before the first start therefore keeps working — that is the point of drawing
    twice while the fleet is still at the dock.
    """
    started = int(
        (
            await session.execute(
                select(func.count(Race.id))
                .join(Flight, Race.flight_id == Flight.id)
                .where(Flight.event_id == event_id, Race.status != RaceStatus.SCHEDULED)
            )
        ).scalar_one()
    )
    recorded = int(
        (
            await session.execute(
                select(func.count(RaceEntry.id))
                .join(Race, RaceEntry.race_id == Race.id)
                .join(Flight, Race.flight_id == Flight.id)
                .where(Flight.event_id == event_id, RaceEntry.code.is_not(None))
            )
        ).scalar_one()
    )
    if started or recorded:
        return FrozenConfiguration(races_started=started, results_recorded=recorded)
    return None


async def require_editable_configuration(session: AsyncSession, event_id: int) -> None:
    """Refuses a change to the setup once racing has started.

    Called by every endpoint that changes the **configuration**: the event's dimensions,
    its boats, the clubs entered, the pairing list. Never by result entry — see the module
    docstring.
    """
    frozen = await configuration_frozen(session, event_id)
    if frozen is not None:
        raise Problem(
            409,
            "event-configuration-frozen",
            "Racing has started for this event; its setup can no longer be changed.",
            **frozen.as_dict(),
        )


async def require_ready(
    session: AsyncSession, event: Event, *, ignore: Collection[str] = ()
) -> None:
    """Refuses when the event isn't ready to be drawn or started.

    The reasons travel with the error, in the same shape ``GET
    /api/admin/events/{id}/readiness`` returns them, so a client renders one list either
    way. A single reason keeps **its own** code and status — a missing catalog entry has
    always been a 404 and stays one, so the frontend's existing handling of
    ``pairing-catalog-missing`` and ``pairing-team-count-mismatch`` is untouched.

    ``ignore`` drops reasons a particular caller has no business insisting on:
    ``CATALOG_REASON`` is the precondition of *taking* a list from the catalog, so the
    paths that don't — the optimizer job, an imported draw, and the start of an event whose
    list already exists — pass it here rather than being blocked by the one thing they are
    the answer to.
    """
    reasons = [
        reason for reason in await event_readiness(session, event) if reason.code not in ignore
    ]
    if not reasons:
        return

    if len(reasons) == 1:
        reason = reasons[0]
        raise Problem(
            _STATUS.get(reason.code, 409),
            reason.code,
            _TITLES.get(reason.code, "This event is not ready yet."),
            **reason.details,
        )

    raise Problem(
        409,
        "event-not-ready",
        "This event's setup is incomplete.",
        reasons=[reason.as_dict() for reason in reasons],
    )
