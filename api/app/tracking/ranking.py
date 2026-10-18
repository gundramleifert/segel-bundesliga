"""Who is ahead (decision 10).

``ByTimeToGo`` turns every boat's remaining distance into seconds using the polar's best
VMG for each remaining leg, so an upwind boat and a downwind boat are comparable in one
number. It depends on the polar's *shape*, not its absolute speeds: scaling every speed by
1.2 changes no rank (tested). ``ByLegThenDistance`` is the simpler second implementation —
further leg first, then less to go — and what the page falls back to without a polar.

Finished boats come first in either, in the order they finished.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from app.tracking.course import Waypoint
from app.tracking.geo import XY
from app.tracking.passings import Passing
from app.tracking.polar import KNOT, Polar
from app.tracking.settings import tracking_settings


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


@dataclass(frozen=True)
class Ranked:
    state: BoatState
    rank: int
    #: Seconds to the finish at the polar's best VMG; None for a finished boat, and from a
    #: ranker that has no time (``ByLegThenDistance``).
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


def _order(
    boats: Sequence[BoatState],
    waypoints: Sequence[Waypoint],
    key: Callable[[BoatState], float],
    seconds: Callable[[BoatState], float] | None = None,
) -> list[Ranked]:
    """Finished boats first, by finish time; then the rest by ``key``, smallest first.

    ``seconds`` is what a racing boat's ``time_to_go`` reports — None when the ranker has no
    time, as ``key`` need not be one. Passing the same function as ``key`` reuses its value.
    """
    done: list[tuple[datetime, BoatState]] = []
    racing: list[tuple[float, BoatState]] = []
    for b in boats:
        at = _finished_at(b, waypoints)
        if at is None:
            racing.append((key(b), b))
        else:
            done.append((at, b))
    done.sort(key=lambda pair: pair[0])
    racing.sort(key=lambda pair: pair[0])
    out = [Ranked(b, rank, None, at) for rank, (at, b) in enumerate(done, start=1)]
    for value, b in racing:
        time_to_go = value if seconds is key else (seconds(b) if seconds else None)
        out.append(Ranked(b, len(out) + 1, time_to_go, None))
    return out


@dataclass(frozen=True)
class ByTimeToGo:
    polar: Polar
    #: Speed floor in m/s (`SBL_TRACKING_MIN_VMG_MS`).
    min_speed: float = field(default_factory=lambda: tracking_settings.min_vmg_ms)

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
            total += metres / max(speed, self.min_speed)
        return total

    def rank(
        self, boats: Sequence[BoatState], waypoints: Sequence[Waypoint], axis: XY, tws: float
    ) -> list[Ranked]:
        def seconds(b: BoatState) -> float:
            return self.seconds_to_go(b, waypoints, axis, tws)

        return _order(boats, waypoints, seconds, seconds)


def metres_to_go(state: BoatState, waypoints: Sequence[Waypoint], axis: XY) -> float:
    """Axis metres left to the finish: the rest of this leg plus every leg after it. Whole
    legs ahead therefore count more than any distance within a leg — and the difference
    between two boats' values is the gap the live page shows."""
    if state.leg >= len(waypoints):
        return 0.0
    lengths = _leg_lengths(waypoints, axis)
    return state.to_go + sum(lengths[state.leg + 1 :])


class ByLegThenDistance:
    def rank(
        self, boats: Sequence[BoatState], waypoints: Sequence[Waypoint], axis: XY, tws: float
    ) -> list[Ranked]:
        return _order(boats, waypoints, lambda b: metres_to_go(b, waypoints, axis))
