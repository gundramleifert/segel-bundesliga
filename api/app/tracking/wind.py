"""Where the wind comes from, and how hard.

On a windward/leeward course the direction is the course axis (``CourseAxisWind``) — the
committee lays the course square to the wind, and that is a better estimate than anything a
few phones could compute. The strength is typed in by the committee (``ManualWind``) until
``TrackEstimatedWind`` exists; ranking needs it only to pick the polar column, and a few
knots either way change no rank.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from app.tracking.course import Course
from app.tracking.geo import bearing_deg
from app.tracking.settings import tracking_settings


@dataclass(frozen=True)
class Wind:
    #: True wind speed in knots.
    tws: float
    #: True wind direction, degrees the wind comes *from*.
    twd: float


class WindSource(Protocol):
    def wind_at(self, t: datetime) -> Wind | None: ...


@dataclass(frozen=True)
class CourseAxisWind:
    course: Course
    tws: float = field(default_factory=lambda: tracking_settings.default_tws_kn)

    def wind_at(self, t: datetime) -> Wind | None:
        return Wind(self.tws, bearing_deg(self.course.axis))


@dataclass(frozen=True)
class ManualWind:
    wind: Wind

    def wind_at(self, t: datetime) -> Wind | None:
        return self.wind
