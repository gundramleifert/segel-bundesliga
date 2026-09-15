"""One race, analysed: tracks in, a ranked list of boat states out.

``RaceAnalysis`` is the composition of the interchangeable parts — projection, leg
distance, passing detector, ranker — and ``default_pipeline`` is the **one** place the
concrete classes are named. Swap an implementation here, or run several against one
recorded track with ``compare.py``, and nothing else moves.

Everything here is derived and nothing is stored (decision 12): legs, passings, distance
and time to go, rank — the same rule as points.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from app.tracking.course import Course
from app.tracking.distance import AxisProjectionDistance, LegDistance
from app.tracking.geo import Fix, LocalTangentPlane, Projection
from app.tracking.passings import PassingDetector, SequentialCourseDetector, TrackPoint
from app.tracking.polar import J70, Polar
from app.tracking.ranking import BoatState, ByTimeToGo, Ranked, Ranker
from app.tracking.settings import tracking_settings


@dataclass(frozen=True)
class RaceAnalysis:
    projection: Projection
    distance: LegDistance
    detector: PassingDetector
    ranker: Ranker
    #: True wind speed in knots, for the polar column the ranking uses.
    tws: float = field(default_factory=lambda: tracking_settings.default_tws_kn)

    def project(self, fixes: Sequence[Fix]) -> list[TrackPoint]:
        return [TrackPoint(f.t, self.projection.to_xy(f.lat, f.lon), f.sog, f.cog) for f in fixes]

    def state_of(self, boat: int, fixes: Sequence[Fix], course: Course) -> BoatState | None:
        if not fixes:
            return None
        waypoints = course.waypoints()
        axis = course.axis
        track = self.project(fixes)
        passings = tuple(self.detector.detect(track, waypoints, axis))
        last = track[-1]
        leg = len(passings)
        to_go = 0.0 if leg >= len(waypoints) else self.distance.to_go(last.xy, waypoints[leg], axis)
        return BoatState(boat, last.t, last.xy, last.sog, last.cog, passings, to_go)

    def analyse(self, tracks: Mapping[int, Sequence[Fix]], course: Course) -> list[Ranked]:
        states = [
            state
            for boat, fixes in tracks.items()
            if (state := self.state_of(boat, fixes, course)) is not None
        ]
        return self.ranker.rank(states, course.waypoints(), course.axis, self.tws)


def default_pipeline(
    origin: tuple[float, float], *, polar: Polar | None = None, tws: float | None = None
) -> RaceAnalysis:
    """What the live page runs: the plan's defaults, named once."""
    return RaceAnalysis(
        projection=LocalTangentPlane(*origin),
        distance=AxisProjectionDistance(),
        detector=SequentialCourseDetector(),
        ranker=ByTimeToGo(polar or Polar.load(J70)),
        tws=tracking_settings.default_tws_kn if tws is None else tws,
    )
