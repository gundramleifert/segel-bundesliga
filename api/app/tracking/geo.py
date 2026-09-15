"""Flat geometry around the course (decision 8 of the plan).

One projection turns latitude/longitude into metres on a local tangent plane around the
course centre, and everything downstream is 2-D: lines cross or they do not, a boat is on
one side of a line or the other, a distance is a subtraction. Exact to centimetres at the
two kilometres a course spans; haversine everywhere would be the mistake.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

#: Mean earth radius in metres (IUGG).
EARTH_RADIUS = 6_371_008.8


@dataclass(frozen=True)
class XY:
    x: float
    y: float

    def __add__(self, other: XY) -> XY:
        return XY(self.x + other.x, self.y + other.y)

    def __sub__(self, other: XY) -> XY:
        return XY(self.x - other.x, self.y - other.y)

    def scale(self, factor: float) -> XY:
        return XY(self.x * factor, self.y * factor)

    def dot(self, other: XY) -> float:
        return self.x * other.x + self.y * other.y

    def cross(self, other: XY) -> float:
        return self.x * other.y - self.y * other.x

    @property
    def norm(self) -> float:
        return math.hypot(self.x, self.y)

    def unit(self) -> XY:
        n = self.norm
        return XY(self.x / n, self.y / n) if n else XY(0.0, 0.0)

    def left(self) -> XY:
        """The vector rotated 90° counter-clockwise — "to port of" a direction."""
        return XY(-self.y, self.x)


def midpoint(a: XY, b: XY) -> XY:
    return XY((a.x + b.x) / 2, (a.y + b.y) / 2)


def distance(a: XY, b: XY) -> float:
    return (b - a).norm


@dataclass(frozen=True)
class Fix:
    """One GPS fix: when, where, how fast (m/s) and which way (degrees true)."""

    t: datetime
    lat: float
    lon: float
    sog: float
    cog: float


class Projection(Protocol):
    def to_xy(self, lat: float, lon: float) -> XY: ...

    def to_geo(self, xy: XY) -> tuple[float, float]: ...


@dataclass(frozen=True)
class LocalTangentPlane:
    """Equirectangular projection around an origin: x east, y north, in metres."""

    lat0: float
    lon0: float

    def to_xy(self, lat: float, lon: float) -> XY:
        k = EARTH_RADIUS * math.cos(math.radians(self.lat0))
        return XY(k * math.radians(lon - self.lon0), EARTH_RADIUS * math.radians(lat - self.lat0))

    def to_geo(self, xy: XY) -> tuple[float, float]:
        k = EARTH_RADIUS * math.cos(math.radians(self.lat0))
        return (
            self.lat0 + math.degrees(xy.y / EARTH_RADIUS),
            self.lon0 + math.degrees(xy.x / k),
        )


def heading_vector(degrees_true: float) -> XY:
    """Unit vector of a compass heading: 0° is north (+y), 90° is east (+x)."""
    rad = math.radians(degrees_true)
    return XY(math.sin(rad), math.cos(rad))


def bearing_deg(vector: XY) -> float:
    """Compass bearing of a vector, 0..360, north-up."""
    return math.degrees(math.atan2(vector.x, vector.y)) % 360.0


def angle_diff(a: float, b: float) -> float:
    """Signed smallest difference a − b in degrees, in (−180, 180]."""
    d = (a - b + 180.0) % 360.0 - 180.0
    return 180.0 if d == -180.0 else d


def side_of_line(a: XY, b: XY, p: XY) -> float:
    """Positive when ``p`` lies to the left of the directed line a → b, negative right."""
    return (b - a).cross(p - a)


def segment_crosses_line(p0: XY, p1: XY, a: XY, b: XY) -> bool:
    """Whether the track segment p0 → p1 crosses the *segment* a — b (not its extension).

    A start line is finite: crossing its extension beyond the pin is not a start.
    """
    s0 = side_of_line(a, b, p0)
    s1 = side_of_line(a, b, p1)
    if s0 == 0 and s1 == 0:
        return False
    if (s0 > 0) == (s1 > 0) and s0 != 0 and s1 != 0:
        return False
    # The two sides flipped; now the same test with the roles swapped says whether the
    # crossing lies between a and b rather than beyond one end.
    t0 = side_of_line(p0, p1, a)
    t1 = side_of_line(p0, p1, b)
    return (t0 > 0) != (t1 > 0) or t0 == 0 or t1 == 0


def crossing_fraction(p0: XY, p1: XY, a: XY, b: XY) -> float:
    """Where along p0 → p1 the line a — b is crossed, 0..1 — for a sub-tick passing time.

    Two boats finishing within the same second would otherwise tie on the tick's time and
    be ordered arbitrarily; the sides' magnitudes give the exact crossing moment.
    """
    s0 = abs(side_of_line(a, b, p0))
    s1 = abs(side_of_line(a, b, p1))
    total = s0 + s1
    return s0 / total if total else 1.0
