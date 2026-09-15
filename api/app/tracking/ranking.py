"""Who is ahead (decision 10).

``ByTimeToGo`` turns every boat's remaining distance into seconds using the polar's best
VMG for each remaining leg, so an upwind boat and a downwind boat are comparable in one
number. It depends on the polar's *shape*, not its absolute speeds: scaling every speed by
1.2 changes no rank (tested). ``ByLegThenDistance`` is the simpler second implementation —
further leg first, then less to go — and what the page falls back to without a polar.

Finished boats come first in either, in the order they finished.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.tracking.course import Waypoint
from app.tracking.geo import XY
from app.tracking.passings import Passing
from app.tracking.polar import KNOT, Polar


@dataclass(frozen=True)
class BoatState:
    boat: int
    t: datetime
    position: XY
    #: m/s and degrees true, as last reported.
    sog: float
    cog: float
    passings: tuple[Passing, ...]
    #: Metres still to go on the current leg (0 when finished).
    to_go: float

    @property
    def leg(self) -> int:
        """Index of the waypoint the boat is heading for; equals the waypoint count once done."""
        return len(self.passings)

    @property
    def finished_at(self) -> datetime | None:
        return None


@dataclass(frozen=True)
class Ranked:
    state: BoatState
    rank: int
    #: Seconds to the finish at the polar's best VMG; None for a finished boat.
    time_to_go: float | None
    finished_at: datetime | None


class Ranker(Protocol):
    def rank(
        self, boats: Sequence[BoatState], waypoints: Sequence[Waypoint], axis: XY, tws: float
    ) -> list[Ranked]: ...


def _leg_lengths(waypoints: Sequence[Waypoint], axis: XY) -> list[float]:
    """Length along the axis of each leg *to* waypoint i (leg 0, to the start line, is 0)."""
    lengths = [0.0]
    for i in range(1, len(waypoints)):
        along = (waypoints[i].centre - waypoints[i - 1].centre).dot(axis) * waypoints[i].direction
        lengths.append(max(0.0, along))
    return lengths


def _finished_at(state: BoatState, waypoints: Sequence[Waypoint]) -> datetime | None:
    return state.passings[-1].t if state.leg >= len(waypoints) and state.passings else None


def _order(boats: Sequence[BoatState], waypoints: Sequence[Waypoint], key) -> list[Ranked]:
    finished = sorted(
        (b for b in boats if _finished_at(b, waypoints) is not None),
        key=lambda b: _finished_at(b, waypoints),  # type: ignore[arg-type, return-value]
    )
    racing = sorted((b for b in boats if _finished_at(b, waypoints) is None), key=key)
    out: list[Ranked] = []
    for b in finished:
        out.append(Ranked(b, len(out) + 1, None, _finished_at(b, waypoints)))
    for b in racing:
        out.append(Ranked(b, len(out) + 1, key(b), None))
    return out


@dataclass(frozen=True)
class ByTimeToGo:
    polar: Polar

    def seconds_to_go(
        self, state: BoatState, waypoints: Sequence[Waypoint], axis: XY, tws: float
    ) -> float:
        up = self.polar.vmg_upwind(tws) * KNOT
        down = self.polar.vmg_downwind(tws) * KNOT
        lengths = _leg_lengths(waypoints, axis)
        total = 0.0
        for i in range(state.leg, len(waypoints)):
            metres = state.to_go if i == state.leg else lengths[i]
            speed = up if waypoints[i].upwind else down
            total += metres / max(speed, 0.1)
        return total

    def rank(
        self, boats: Sequence[BoatState], waypoints: Sequence[Waypoint], axis: XY, tws: float
    ) -> list[Ranked]:
        return _order(boats, waypoints, lambda b: self.seconds_to_go(b, waypoints, axis, tws))


class ByLegThenDistance:
    def rank(
        self, boats: Sequence[BoatState], waypoints: Sequence[Waypoint], axis: XY, tws: float
    ) -> list[Ranked]:
        # Encoded as one number so `_order` can report it: whole legs ahead count more than
        # any distance within a leg.
        lengths = _leg_lengths(waypoints, axis)
        remaining_after = [sum(lengths[i + 1 :]) for i in range(len(waypoints))]

        def key(b: BoatState) -> float:
            return b.to_go + (remaining_after[b.leg] if b.leg < len(waypoints) else 0.0)

        return _order(boats, waypoints, key)
