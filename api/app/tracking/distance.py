"""How far a boat still has to go on its leg (decision 9).

Two implementations are known today, hence the ``Protocol``:

* ``AxisProjectionDistance`` — the distance *along the course axis*: ``(target − boat) · a``
  with ``a`` the axis in the leg's direction. A boat on port and one on starboard at the same
  height rank equal, which is exactly the "distance to windward" a commentator means, and
  on a windward/leeward course the axis is the wind axis, so it needs no wind estimate.
* ``StraightLineDistance`` — plain distance to the target; better on the last hundred metres
  to a mark, worse everywhere else.

Which one the live page uses is decided in ``analysis.default_pipeline``, and can be decided
on recorded data with ``compare.py`` rather than argued.
"""

from __future__ import annotations

from typing import Protocol

from app.tracking.course import Waypoint
from app.tracking.geo import XY, distance


class LegDistance(Protocol):
    def to_go(self, boat: XY, target: Waypoint, axis: XY) -> float: ...


class AxisProjectionDistance:
    def to_go(self, boat: XY, target: Waypoint, axis: XY) -> float:
        along = (target.centre - boat).dot(axis) * target.direction
        return max(0.0, along)


class StraightLineDistance:
    def to_go(self, boat: XY, target: Waypoint, axis: XY) -> float:
        return distance(boat, target.centre)
