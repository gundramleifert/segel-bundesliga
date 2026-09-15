"""When a boat passed which waypoint (Story L-2).

``SequentialCourseDetector`` needs no candidate graph: on a windward/leeward course only
the *next expected* waypoint can be passed, so the course order does the disambiguation
SAP's Dijkstra does for arbitrary courses.

* A line or a gate is passed when the track segment crosses it in the leg's direction.
* The windward mark is passed when the boat is within ``mark_radius`` of it and has turned
  downwind — a port rounding arrives upwind and leaves downwind, and the turn is the moment
  the rounding is done.

Which way the boat is going comes from the fix's own course over ground, not from the
difference of two positions: at one fix a second a boat moves about three metres, which is
the size of a phone's position noise, so a displacement points anywhere. A receiver's COG
is computed from Doppler and is good to a few degrees whenever the boat is moving; below a
knot it is meaningless, and the displacement is used instead.

If real data breaks this, the port of SAP's ``CandidateFinder``/``CandidateChooser`` is the
fallback, not the start. Every implementation is admitted by the same contract test against
the emulator's ground truth (``tests/unit/test_tracking_contract.py``).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from app.tracking.course import Waypoint
from app.tracking.geo import (
    XY,
    crossing_fraction,
    distance,
    heading_vector,
    segment_crosses_line,
)
from app.tracking.settings import tracking_settings


@dataclass(frozen=True)
class TrackPoint:
    """A fix, projected: when, where in metres, speed in m/s, course in degrees."""

    t: datetime
    xy: XY
    sog: float
    cog: float


@dataclass(frozen=True)
class Passing:
    waypoint: int
    t: datetime


class PassingDetector(Protocol):
    def detect(
        self, track: Sequence[TrackPoint], waypoints: Sequence[Waypoint], axis: XY
    ) -> list[Passing]: ...


@dataclass(frozen=True)
class SequentialCourseDetector:
    #: Inside this, a boat is "at" the mark (`SBL_TRACKING_MARK_RADIUS_M`).
    mark_radius: float = field(default_factory=lambda: tracking_settings.mark_radius_m)
    #: How far a line or a gate counts beyond its ends (`SBL_TRACKING_LINE_MARGIN_M`,
    #: `SBL_TRACKING_GATE_MARGIN_M`): a finite segment plus the size of the noise.
    line_margin: float = field(default_factory=lambda: tracking_settings.line_margin_m)
    gate_margin: float = field(default_factory=lambda: tracking_settings.gate_margin_m)

    def detect(
        self, track: Sequence[TrackPoint], waypoints: Sequence[Waypoint], axis: XY
    ) -> list[Passing]:
        passings: list[Passing] = []
        for i in range(1, len(track)):
            expected = len(passings)
            if expected >= len(waypoints):
                break
            target = waypoints[expected]
            p0, p1 = track[i - 1].xy, track[i].xy
            if target.kind in ("line", "gate"):
                # Judged by the heading the boat *approached* with: a boat through a gate
                # rounds the mark at once, and at one fix a second the arrival fix's course
                # is already upwind — read there, a clean crossing looks like the wrong way.
                move = _direction(track[i - 1], p1 - p0)
                margin = self.gate_margin if target.kind == "gate" else self.line_margin
                a, b = _extended(target.points[0], target.points[1], margin)
                if segment_crosses_line(p0, p1, a, b) and move.dot(axis) * target.direction > 0:
                    # The exact moment within the tick, so close finishes order correctly.
                    fraction = crossing_fraction(p0, p1, a, b)
                    t0, t1 = track[i - 1].t, track[i].t
                    passings.append(Passing(expected, t0 + (t1 - t0) * fraction))
            else:
                move = _direction(track[i], p1 - p0)
                near = distance(p1, target.centre) < self.mark_radius
                turned_down = move.dot(axis) * target.direction < 0
                if near and turned_down:
                    passings.append(Passing(expected, track[i].t))
        return passings


#: Below this speed over ground (m/s) a receiver's course is noise; use the displacement.
_COG_MIN_SOG = 0.5


def _direction(point: TrackPoint, displacement: XY) -> XY:
    return heading_vector(point.cog) if point.sog >= _COG_MIN_SOG else displacement


def _extended(a: XY, b: XY, margin: float) -> tuple[XY, XY]:
    """The segment a — b, lengthened by ``margin`` at both ends."""
    along = (b - a).unit().scale(margin)
    return a - along, b + along
