"""What a tactician draws on the chart: laylines and the leader's line.

* A **layline** is the line a boat sails to fetch a mark on one tack without another
  manoeuvre. From the windward mark two of them run downwind, one each side of the wind
  axis at the polar's best upwind angle; from each gate mark two run upwind at the polar's
  best downwind angle. The wind is the course axis (``course.py``) until a wind source
  says otherwise; the angles come from the polar, so a different class draws different
  lines.
* The **leader's line** is the line through the leading boat square to the direction it
  gains in — the course axis, up or down its current leg. Every boat behind that line is
  behind in "distance to windward", the thing a commentator means by "ahead".

Both are derived, never stored, like everything else here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.tracking.course import Course, MarkRole, Waypoint
from app.tracking.geo import XY
from app.tracking.polar import Polar


@dataclass(frozen=True)
class Layline:
    mark: MarkRole
    #: From the mark outward, the length of the leg.
    points: tuple[XY, XY]


def rotate(v: XY, degrees: float) -> XY:
    """``v`` turned clockwise by ``degrees`` (compass sense: north to east)."""
    a = math.radians(degrees)
    return XY(v.x * math.cos(a) + v.y * math.sin(a), -v.x * math.sin(a) + v.y * math.cos(a))


def laylines(course: Course, polar: Polar, tws: float) -> list[Layline]:
    up = course.axis
    length = course.leg_length()
    beat, _ = polar.best_upwind(tws)
    run, _ = polar.best_downwind(tws)
    out: list[Layline] = []
    windward = course.marks[MarkRole.WINDWARD]
    # Approaching the windward mark close-hauled means sailing `beat` degrees off the wind;
    # the layline runs back down from the mark along that heading, reversed.
    for sign in (+1, -1):
        away = rotate(up.scale(-1), sign * beat)
        out.append(Layline(MarkRole.WINDWARD, (windward, windward + away.scale(length))))
    for role in (MarkRole.GATE_LEFT, MarkRole.GATE_RIGHT):
        if role not in course.marks:
            continue
        mark = course.marks[role]
        # Running at `run` degrees off the wind toward the mark: the layline goes back up
        # from the mark at 180 − run either side of the axis.
        for sign in (+1, -1):
            away = rotate(up, sign * (180.0 - run))
            out.append(Layline(role, (mark, mark + away.scale(length))))
    return out


def leader_line(position: XY, waypoint: Waypoint, axis: XY, half_length: float) -> tuple[XY, XY]:
    """The line through ``position`` square to the axis of the leg toward ``waypoint``."""
    across = axis.left().scale(half_length * waypoint.direction)
    return (position - across, position + across)
