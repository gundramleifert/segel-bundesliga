"""The flat geometry every tracking algorithm stands on (Story L-2, decision 8)."""

import math

from app.tracking.geo import (
    XY,
    LocalTangentPlane,
    angle_diff,
    bearing_deg,
    heading_vector,
    segment_crosses_line,
    side_of_line,
)


def test_projection_round_trips_and_is_metres():
    plane = LocalTangentPlane(54.4, 10.2)
    xy = plane.to_xy(54.401, 10.202)
    # A thousandth of a degree of latitude is about 111 m; two thousandths of longitude at
    # 54° north about 130 m (a degree of longitude shrinks with the cosine of the latitude).
    assert 110 < xy.y < 112
    assert 128 < xy.x < 131
    lat, lon = plane.to_geo(xy)
    assert math.isclose(lat, 54.401, abs_tol=1e-9)
    assert math.isclose(lon, 10.202, abs_tol=1e-9)


def test_headings_are_north_up_compass_bearings():
    assert bearing_deg(XY(0, 1)) == 0
    assert bearing_deg(XY(1, 0)) == 90
    assert math.isclose(heading_vector(90).x, 1.0)
    assert angle_diff(10, 350) == 20
    assert angle_diff(350, 10) == -20


def test_side_of_line_is_positive_to_the_left():
    a, b = XY(0, 0), XY(0, 10)  # pointing north
    assert side_of_line(a, b, XY(-1, 5)) > 0  # west of it: left
    assert side_of_line(a, b, XY(1, 5)) < 0


def test_a_segment_crosses_the_line_only_between_its_ends():
    a, b = XY(-40, 0), XY(40, 0)  # a start line 80 m long
    assert segment_crosses_line(XY(0, -5), XY(0, 5), a, b)
    # Beyond the pin is not a start.
    assert not segment_crosses_line(XY(60, -5), XY(60, 5), a, b)
    # Same side: no crossing.
    assert not segment_crosses_line(XY(0, -5), XY(0, -1), a, b)
