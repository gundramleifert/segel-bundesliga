"""Request and response models for tracking: the course, the trackers, the live picture."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.public import TeamOut

MarkRoleName = Literal[
    "committee_boat", "start_pin", "windward", "gate_left", "gate_right", "finish_pin"
]


class MarkIn(BaseModel):
    role: MarkRoleName
    lat: float
    lon: float


class CourseIn(BaseModel):
    """The course as the committee laid it: six marks, laps, where the finish is."""

    marks: list[MarkIn] = Field(min_length=6, max_length=6)
    laps: int = Field(default=1, ge=1, le=6)
    finish_upwind: bool = False
    #: "right": the finish pin on the other side of the committee boat than the start
    #: pin — the usual case; "left": the finish through the start line.
    finish_pin_side: Literal["left", "right"] = "right"
    tws_kn: float | None = Field(default=None, ge=0, le=60)
    wind_from_deg: float | None = Field(default=None, ge=0, lt=360)


class DefaultCourseIn(BaseModel):
    """Lay the textbook course around a point — what a button and the emulator do."""

    lat: float | None = None
    lon: float | None = None
    wind_from_deg: float | None = None
    leg_length_m: float | None = Field(default=None, ge=50, le=5000)
    laps: int = Field(default=1, ge=1, le=6)
    finish_upwind: bool = False
    #: "right": the finish pin on the other side of the committee boat than the start
    #: pin — the usual case; "left": the finish through the start line.
    finish_pin_side: Literal["left", "right"] = "right"


class MarkOut(BaseModel):
    role: str
    lat: float
    lon: float


class CourseOut(BaseModel):
    id: int
    event_id: int
    laps: int
    finish_upwind: bool
    finish_pin_side: str
    tws_kn: float | None
    wind_from_deg: float | None
    marks: list[MarkOut]
    #: The waypoints in passing order, by name — what the side panel calls a leg.
    waypoints: list[str]
    created_at: datetime


class TrackerOut(BaseModel):
    id: int
    boat_number: int | None
    mark_role: str | None
    device_token: str
    active_from: datetime


class FixIn(BaseModel):
    t: datetime
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    #: Speed over ground in m/s.
    sog: float = Field(ge=0)
    #: Course over ground, degrees true.
    cog: float = Field(ge=0, lt=360)


class FixBatchIn(BaseModel):
    token: str
    fixes: list[FixIn] = Field(min_length=1, max_length=1000)


class FixBatchOut(BaseModel):
    stored: int
    #: Fixes the server already had — a retried batch is not an error.
    duplicates: int


class LiveBoatOut(BaseModel):
    boat_number: int
    color: str | None
    team: TeamOut | None
    t: datetime
    lat: float
    lon: float
    #: Speed over ground in knots — the unit anyone on the water thinks in.
    sog_kn: float
    cog: float
    #: Index of the waypoint the boat heads for; equals the waypoint count once finished.
    leg: int | None
    leg_name: str | None
    to_go_m: float | None
    time_to_go_s: float | None
    #: Axis metres behind the leading boat: 0 for the leader, None once finished.
    to_leader_m: float | None
    rank: int | None
    finished_at: datetime | None
    #: The last minute of positions, oldest first, as [lat, lon].
    trail: list[list[float]]


class LiveRaceInfo(BaseModel):
    id: int
    sequence: int
    flight: int
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    signal: str | None


class LaylineOut(BaseModel):
    mark: str
    #: From the mark outward, as [lat, lon].
    points: list[list[float]]


class LiveRaceOut(BaseModel):
    """Everything the live page draws, in one answer; also the payload of a `positions` frame."""

    event_id: int
    course: CourseOut | None
    #: Waypoints on the course — the denominator of "leg 2/4"; None without a course.
    leg_count: int | None
    #: Where the wind comes from, degrees true — the course axis until a wind source exists.
    wind_from_deg: float | None
    #: Laylines to the windward mark and from the gate marks, from the polar's angles.
    laylines: list[LaylineOut]
    #: Through the leading boat, square to its leg, as two [lat, lon]; None between races.
    leader_line: list[list[float]] | None
    #: Whose line it is, so the map can keep it on the boat as the boat is animated.
    leader_boat: int | None
    #: The race on the water, else None.
    race: LiveRaceInfo | None
    #: The first race not yet sailed — "next up".
    next_race: LiveRaceInfo | None
    boats: list[LiveBoatOut]
    #: Boat numbers in the order the analysis saw them finish — the committee's suggestion.
    detected_finish_order: list[int]
    #: Hull length and beam of the class sailed, so the map draws boats at their true size.
    boat_length_m: float
    boat_beam_m: float
    #: Radius of the zone around every rounding mark (RRS 18: three hull lengths).
    zone_radius_m: float
    #: When this picture was taken.
    t: datetime
