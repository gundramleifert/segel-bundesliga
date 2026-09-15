"""Story L-2: laylines from the polar's angles, and the leader's line square to the leg."""

import math

from app.tracking.course import MarkRole, lay_course
from app.tracking.geo import XY, bearing_deg
from app.tracking.polar import J70, Polar
from app.tracking.tactics import laylines, leader_line, rotate

WIND_FROM = 20.0


def _course():
    return lay_course(
        XY(0, 0), wind_from_deg=WIND_FROM, leg_length=300, line_length=80, gate_width=40
    )


def test_rotate_turns_clockwise_in_compass_sense():
    north = XY(0, 1)
    assert math.isclose(bearing_deg(rotate(north, 90)), 90, abs_tol=1e-9)
    assert math.isclose(bearing_deg(rotate(north, -45)), 315, abs_tol=1e-9)


def test_windward_laylines_leave_the_mark_at_the_beat_angle_either_side_of_downwind():
    course = _course()
    polar = Polar.load(J70)
    beat, _ = polar.best_upwind(10)
    lines = [line for line in laylines(course, polar, 10) if line.mark == MarkRole.WINDWARD]
    assert len(lines) == 2
    downwind = (WIND_FROM + 180) % 360
    bearings = sorted(
        (bearing_deg(line.points[1] - line.points[0]) - downwind + 540) % 360 - 180
        for line in lines
    )
    assert math.isclose(bearings[0], -beat, abs_tol=1e-6)
    assert math.isclose(bearings[1], beat, abs_tol=1e-6)
    for line in lines:
        assert line.points[0] == course.marks[MarkRole.WINDWARD]
        length = (line.points[1] - line.points[0]).norm
        assert math.isclose(length, course.leg_length(), rel_tol=1e-9)


def test_gate_laylines_run_upwind_at_the_gybe_angle_from_each_gate_mark():
    course = _course()
    polar = Polar.load(J70)
    run, _ = polar.best_downwind(10)
    lines = [line for line in laylines(course, polar, 10) if line.mark != MarkRole.WINDWARD]
    assert {line.mark for line in lines} == {MarkRole.GATE_LEFT, MarkRole.GATE_RIGHT}
    assert len(lines) == 4
    for line in lines:
        off_axis = abs((bearing_deg(line.points[1] - line.points[0]) - WIND_FROM + 540) % 360 - 180)
        assert math.isclose(off_axis, 180 - run, abs_tol=1e-6)


def test_the_leaders_line_is_square_to_the_axis_and_centred_on_the_boat():
    course = _course()
    boat = XY(10, 120)
    upwind_leg = course.waypoints()[1]
    a, b = leader_line(boat, upwind_leg, course.axis, 100)
    assert math.isclose((a - b).norm, 200, rel_tol=1e-9)
    assert math.isclose((b - a).dot(course.axis), 0, abs_tol=1e-9)
    assert math.isclose(((a + b).scale(0.5) - boat).norm, 0, abs_tol=1e-9)
