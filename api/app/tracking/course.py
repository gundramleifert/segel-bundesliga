"""The one course family: windward/leeward with a leeward gate (decision 7).

Waypoints in order: ``START`` (a line, committee boat to pin, pin to port of the boat when
looking upwind), ``WINDWARD`` (one mark, rounded to port), ``GATE`` (two marks, either
one), repeated per lap, and ``FINISH`` (a line, committee boat to finish pin). Parameters:
``laps``, finish upwind or downwind, finish pin left or right of the committee boat.
Nothing else is modelled until real data asks for it.

The course axis — gate centre toward the windward mark — *is* the wind axis on this
family, which is what lets distance-to-go and the emulator do without a wind estimate.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from app.tracking.geo import XY, midpoint
from app.tracking.settings import tracking_settings


class MarkRole(StrEnum):
    COMMITTEE_BOAT = "committee_boat"
    START_PIN = "start_pin"
    WINDWARD = "windward"
    GATE_LEFT = "gate_left"
    GATE_RIGHT = "gate_right"
    FINISH_PIN = "finish_pin"


WaypointKind = Literal["line", "mark", "gate"]


@dataclass(frozen=True)
class Waypoint:
    name: str
    kind: WaypointKind
    #: A line's two ends, a mark, or a gate's two marks.
    points: tuple[XY, ...]
    #: +1 when the leg *to* this waypoint goes upwind (along the axis), −1 downwind.
    direction: int

    @property
    def centre(self) -> XY:
        return self.points[0] if len(self.points) == 1 else midpoint(self.points[0], self.points[1])

    @property
    def upwind(self) -> bool:
        return self.direction > 0


@dataclass(frozen=True)
class Course:
    marks: dict[MarkRole, XY]
    laps: int = 2
    finish_upwind: bool = False
    finish_pin_side: Literal["left", "right"] = "right"

    @property
    def axis(self) -> XY:
        """Unit vector pointing upwind: gate centre → windward mark."""
        top = self.marks[MarkRole.WINDWARD]
        bottom = (
            midpoint(self.marks[MarkRole.GATE_LEFT], self.marks[MarkRole.GATE_RIGHT])
            if MarkRole.GATE_LEFT in self.marks and MarkRole.GATE_RIGHT in self.marks
            else midpoint(self.marks[MarkRole.COMMITTEE_BOAT], self.marks[MarkRole.START_PIN])
        )
        return (top - bottom).unit()

    @property
    def start_line(self) -> tuple[XY, XY]:
        return self.marks[MarkRole.COMMITTEE_BOAT], self.marks[MarkRole.START_PIN]

    @property
    def finish_line(self) -> tuple[XY, XY]:
        """Committee boat to finish pin — or, finishing upwind, windward mark to finish pin.

        The committee boat cannot be at both ends of the course; a finish at the top is
        taken by a separate boat next to the windward mark, and the pin is set beside it.
        """
        anchor = MarkRole.WINDWARD if self.finish_upwind else MarkRole.COMMITTEE_BOAT
        return self.marks[anchor], self.marks[MarkRole.FINISH_PIN]

    @property
    def gate(self) -> tuple[XY, XY]:
        return self.marks[MarkRole.GATE_LEFT], self.marks[MarkRole.GATE_RIGHT]

    def waypoints(self) -> list[Waypoint]:
        """START, WINDWARD, then GATE and WINDWARD again per further lap, then FINISH.

        The gate is rounded *between* laps, never on the way to the finish: the league's
        course is start – W – G – W – finish, and after the last windward mark the boats
        run straight down to the line. So a one-lap course is start – W – finish and the
        gate marks are on the water but not on the way.
        """
        out = [Waypoint("start", "line", self.start_line, +1)]
        for lap in range(1, self.laps + 1):
            if lap > 1:
                out.append(Waypoint(f"gate {lap - 1}", "gate", self.gate, -1))
            out.append(Waypoint(f"windward {lap}", "mark", (self.marks[MarkRole.WINDWARD],), +1))
        out.append(Waypoint("finish", "line", self.finish_line, +1 if self.finish_upwind else -1))
        return out

    def leg_length(self) -> float:
        return (self.marks[MarkRole.WINDWARD] - midpoint(*self.gate)).norm


def lay_course(
    centre: XY,
    *,
    wind_from_deg: float,
    leg_length: float | None = None,
    line_length: float | None = None,
    gate_width: float | None = None,
    laps: int = 2,
    finish_upwind: bool = False,
    finish_pin_side: Literal["left", "right"] = "right",
) -> Course:
    """A textbook W/L course around ``centre``: what the emulator lays when nobody has.

    The start line sits at the centre, square to the wind, the pin to port of the committee
    boat (looking upwind); the windward mark ``leg_length`` upwind; the leeward gate a
    little *above* the line, so the downwind leg to a finish at the committee boat is a
    downwind leg; the finish pin on the chosen side of the committee boat — or, finishing
    upwind, of the windward mark.
    """
    from app.tracking.geo import heading_vector

    leg_length = tracking_settings.default_leg_length_m if leg_length is None else leg_length
    line_length = tracking_settings.default_line_length_m if line_length is None else line_length
    gate_width = tracking_settings.default_gate_width_m if gate_width is None else gate_width
    up = heading_vector(wind_from_deg)  # toward where the wind comes from = upwind
    port = up.left()
    committee = centre - port.scale(line_length / 2)
    pin = centre + port.scale(line_length / 2)
    gate_centre = centre + up.scale(50.0)
    windward = centre + up.scale(leg_length)
    finish_side = port if finish_pin_side == "left" else port.scale(-1)
    finish_anchor = windward if finish_upwind else committee
    marks = {
        MarkRole.COMMITTEE_BOAT: committee,
        MarkRole.START_PIN: pin,
        MarkRole.WINDWARD: windward,
        MarkRole.GATE_LEFT: gate_centre + port.scale(gate_width / 2),
        MarkRole.GATE_RIGHT: gate_centre - port.scale(gate_width / 2),
        MarkRole.FINISH_PIN: finish_anchor + finish_side.scale(line_length),
    }
    return Course(marks, laps=laps, finish_upwind=finish_upwind, finish_pin_side=finish_pin_side)
