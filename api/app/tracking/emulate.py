"""Six boats sailing a windward/leeward course, made up (decision 13, Story L-4).

The emulator is the first of the three data stages and the contract test for everything
downstream: it knows its own ground truth — the moment it decides to round a mark or crosses
a line with its exact, un-noised position — so a detector or a distance implementation is
judged against that, not argued about.

Each boat sails toward its next waypoint with the polar's optimum angles: upwind on a tack
until the layline (with a random overstand), then the other tack; downwind the same with
the gybe angle; a random gate side; speed from the polar with a per-boat skill factor. The
fixes it emits carry Gaussian GPS noise on position, course and speed. Deterministic by
seed. It posts nothing itself — ``app/tracking/emulate_client.py`` and the dev endpoint feed
its fixes through the real ingest path, the same one the phones will use.
"""

from __future__ import annotations

import math
import random
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.tracking.course import Course, Waypoint
from app.tracking.geo import (
    XY,
    Fix,
    LocalTangentPlane,
    angle_diff,
    bearing_deg,
    crossing_fraction,
    distance,
    heading_vector,
    segment_crosses_line,
)
from app.tracking.passings import Passing
from app.tracking.polar import KNOT, Polar
from app.tracking.settings import tracking_settings
from app.tracking.wind import Wind

#: Ticks a boat keeps sailing after the finish before its tracker goes quiet.
SAIL_ON_TICKS = 10


@dataclass
class EmulatedBoat:
    number: int
    position: XY
    heading: float
    #: +1: wind over starboard (heading = twd + angle), −1: over port.
    tack: int
    skill: float
    gate_side: int
    target: int = 0
    finished_at: datetime | None = None
    #: Ticks sailed on past the finish line before the boat stops reporting.
    sailed_on: int = 0
    #: How far past the layline this boat sails before tacking, in degrees.
    overstand: float = 0.0
    #: The boat holds station below the line until this moment, then goes for it.
    go_at: datetime | None = None
    truth: list[Passing] = field(default_factory=list)


@dataclass
class EmulatedRace:
    course: Course
    polar: Polar
    wind: Wind
    boats: Sequence[int]
    start: datetime
    projection: LocalTangentPlane
    seed: int = 1
    tick_seconds: float = field(default_factory=lambda: tracking_settings.emulator_tick_s)
    gps_noise: float = field(default_factory=lambda: tracking_settings.gps_noise_m)
    #: Boats set off this long before the gun, from below the line.
    warmup_seconds: float = field(default_factory=lambda: tracking_settings.emulator_warmup_s)
    rounding_distance: float = field(default_factory=lambda: tracking_settings.rounding_distance_m)
    rounding_offset: float = field(default_factory=lambda: tracking_settings.rounding_offset_m)
    max_seconds: float = 3600.0

    def __post_init__(self) -> None:
        self._random = random.Random(self.seed)
        self._waypoints = self.course.waypoints()
        self._axis = self.course.axis
        self._boats = [self._launch(number, i) for i, number in enumerate(self.boats)]

    @property
    def fleet(self) -> list[EmulatedBoat]:
        return self._boats

    @property
    def waypoints(self) -> list[Waypoint]:
        return self._waypoints

    def truth(self) -> dict[int, list[Passing]]:
        return {b.number: list(b.truth) for b in self._boats}

    def finished(self) -> bool:
        return all(b.finished_at is not None for b in self._boats)

    # ------------------------------------------------------------------ boats

    def _launch(self, number: int, index: int) -> EmulatedBoat:
        committee, pin = self.course.start_line
        along = (index + 0.5) / max(1, len(self.boats))
        on_line = committee + (pin - committee).scale(along)
        behind = 30.0 + self._random.uniform(0.0, 30.0)
        position = on_line - self._axis.scale(behind)
        # Timed to cross the line a few seconds after the gun: a start, not an OCS. The
        # approach is sailed close-hauled, so the speed made good is the polar's VMG.
        vmg = max(0.5, self.polar.vmg_upwind(self.wind.tws) * KNOT)
        late = self._random.uniform(2.0, 15.0)
        go_at = self.start + timedelta(seconds=late - behind / vmg)
        return EmulatedBoat(
            number=number,
            position=position,
            heading=bearing_deg(self._axis),
            tack=self._random.choice((-1, 1)),
            skill=self._random.uniform(0.94, 1.04),
            gate_side=self._random.choice((0, 1)),
            overstand=self._random.uniform(0.0, 6.0),
            go_at=go_at,
        )

    def _goal(self, boat: EmulatedBoat) -> XY:
        target = self._waypoints[boat.target]
        if target.kind == "mark":
            # Leave the mark to port: aim a little to the mark's right as seen going upwind.
            right = self._axis.left().scale(-1)
            return target.centre + right.scale(self.rounding_offset)
        if target.kind == "gate":
            mark = target.points[boat.gate_side]
            # Through the gate close to the chosen mark: the crossing has to be *between*
            # the two marks to count, so the aim is a little inside of the mark.
            inside = (target.centre - mark).unit()
            return mark + inside.scale(self.rounding_offset)
        if target.name == "start":
            committee, pin = target.points
            along = (self.boats.index(boat.number) + 0.5) / max(1, len(self.boats))
            return committee + (pin - committee).scale(along)
        # The finish: the nearest point on the line, well inside its ends. Aiming at the
        # centre from fifty metres away while zigzagging downwind crossed beyond the pin one
        # time in eight — a boat that can see the line does not do that.
        a, b = target.points
        span = b - a
        length = span.norm
        if length == 0:
            return target.centre
        fraction = (boat.position - a).dot(span) / (length * length)
        return a + span.scale(min(0.85, max(0.15, fraction)))

    def _steer(self, boat: EmulatedBoat) -> float:
        """The heading for this tick: straight at the goal when sailable, else the layline logic."""
        target = self._waypoints[boat.target]
        goal = self._goal(boat)
        to_goal = bearing_deg(goal - boat.position)
        twa_goal = angle_diff(
            to_goal, self.wind.twd
        )  # signed: + means goal is to the right of the wind
        beat, _ = self.polar.best_upwind(self.wind.tws)
        gybe, _ = self.polar.best_downwind(self.wind.tws)

        if target.upwind and abs(twa_goal) < beat:
            # Cannot point at it: sail the beat angle on the current tack; tack once the goal
            # bears further than the beat angle on the *other* side — the layline, overstood.
            if (twa_goal > 0) != (boat.tack > 0) and abs(twa_goal) >= beat - boat.overstand:
                boat.tack = -boat.tack
            return (self.wind.twd + boat.tack * beat) % 360.0
        if not target.upwind and abs(twa_goal) > gybe:
            if (twa_goal > 0) != (boat.tack > 0) and abs(twa_goal) <= gybe + boat.overstand:
                boat.tack = -boat.tack
            return (self.wind.twd + boat.tack * gybe) % 360.0
        # Fetching or reaching: point at it, and remember which side of the wind we are on.
        boat.tack = 1 if twa_goal >= 0 else -1
        return to_goal

    def _advance(self, boat: EmulatedBoat, t: datetime) -> None:
        if boat.finished_at is not None:
            # Sail on past the line for a while, as a real boat does. A boat that stops dead
            # on the line leaves a noised track that may never cross it — one finish in
            # eight went undetected that way.
            if boat.sailed_on < SAIL_ON_TICKS:
                boat.sailed_on += 1
                twa = abs(angle_diff(boat.heading, self.wind.twd))
                speed = self.polar.speed(self.wind.tws, twa) * KNOT * boat.skill
                boat.position = boat.position + heading_vector(boat.heading).scale(
                    speed * self.tick_seconds
                )
            return
        if boat.go_at is not None and t < boat.go_at:
            # Holding station below the line: a fix with no speed, pointing upwind.
            boat.heading = bearing_deg(self._axis)
            return
        heading = self._steer(boat)
        twa = abs(angle_diff(heading, self.wind.twd))
        speed = self.polar.speed(self.wind.tws, twa) * KNOT * boat.skill
        speed *= 1.0 + self._random.gauss(0.0, 0.02)
        previous = boat.position
        boat.heading = heading
        boat.position = previous + heading_vector(heading).scale(speed * self.tick_seconds)
        self._check_passing(boat, previous, t)

    def _check_passing(self, boat: EmulatedBoat, previous: XY, t: datetime) -> None:
        target = self._waypoints[boat.target]
        passed = False
        when = t
        if target.kind == "mark":
            passed = distance(boat.position, target.centre) < self.rounding_distance
        else:
            a, b = target.points
            moved = boat.position - previous
            passed = (
                segment_crosses_line(previous, boat.position, a, b)
                and moved.dot(self._axis) * target.direction > 0
            )
            if passed:
                # The exact crossing moment within the tick: the truth two boats finishing
                # in the same second are ordered by.
                fraction = crossing_fraction(previous, boat.position, a, b)
                when = t - timedelta(seconds=self.tick_seconds * (1.0 - fraction))
        if not passed:
            return
        boat.truth.append(Passing(boat.target, when))
        boat.target += 1
        if boat.target >= len(self._waypoints):
            boat.finished_at = t
        elif self._waypoints[boat.target].kind == "gate":
            boat.gate_side = self._random.choice((0, 1))
        boat.overstand = self._random.uniform(0.0, 6.0)

    def _fix(self, boat: EmulatedBoat, t: datetime, speed: float) -> Fix:
        noisy = boat.position + XY(
            self._random.gauss(0.0, self.gps_noise / 2), self._random.gauss(0.0, self.gps_noise / 2)
        )
        lat, lon = self.projection.to_geo(noisy)
        return Fix(
            t=t,
            lat=lat,
            lon=lon,
            sog=max(0.0, speed * (1.0 + self._random.gauss(0.0, 0.03))),
            cog=(boat.heading + self._random.gauss(0.0, 3.0)) % 360.0,
        )

    # -------------------------------------------------------------------- run

    def ticks(self) -> Iterator[tuple[datetime, list[tuple[int, Fix]]]]:
        """Every tick, the fixes of every boat still sailing (plus one last fix when done)."""
        t = self.start - timedelta(seconds=self.warmup_seconds)
        end = self.start + timedelta(seconds=self.max_seconds)
        reported_done: set[int] = set()
        while t <= end:
            fixes: list[tuple[int, Fix]] = []
            for boat in self._boats:
                if boat.finished_at is not None and boat.sailed_on >= SAIL_ON_TICKS:
                    if boat.number not in reported_done:
                        reported_done.add(boat.number)
                        fixes.append((boat.number, self._fix(boat, t, 0.0)))
                    continue
                before = boat.position
                self._advance(boat, t)
                speed = distance(before, boat.position) / self.tick_seconds
                fixes.append((boat.number, self._fix(boat, t, speed)))
            if fixes:
                yield t, fixes
            if self.finished() and len(reported_done) == len(self._boats):
                return
            t += timedelta(seconds=self.tick_seconds)

    def run(self) -> dict[int, list[Fix]]:
        """The whole race at once, per boat — what the contract test wants."""
        tracks: dict[int, list[Fix]] = {number: [] for number in self.boats}
        for _t, fixes in self.ticks():
            for number, fix in fixes:
                tracks[number].append(fix)
        return tracks


def emulated_race(
    course: Course,
    projection: LocalTangentPlane,
    *,
    boats: Sequence[int],
    start: datetime,
    polar: Polar,
    tws: float | None = None,
    seed: int = 1,
    **kwargs: object,
) -> EmulatedRace:
    """The usual setup: the wind is where the course points."""
    wind = Wind(tracking_settings.default_tws_kn if tws is None else tws, bearing_deg(course.axis))
    return EmulatedRace(
        course,
        polar,
        wind,
        list(boats),
        start,
        projection,
        seed=seed,
        **kwargs,  # type: ignore[arg-type]
    )


def knots(metres_per_second: float) -> float:
    return metres_per_second / KNOT


def degrees_true(vector: XY) -> float:
    return math.degrees(math.atan2(vector.x, vector.y)) % 360.0
