"""The polar loader on the J/70 fixture (Story L-2, decision 10)."""

import math

import pytest

from app.tracking.polar import J70, Polar


@pytest.fixture(scope="module")
def j70() -> Polar:
    return Polar.load(J70)


def test_the_optimum_rows_are_the_beat_and_gybe_points(j70):
    angle, speed = j70.best_upwind(10)
    assert angle == 39.9
    assert speed == 5.47
    angle, speed = j70.best_downwind(10)
    assert angle == 151.6
    assert speed == 5.9


def test_table_values_are_read_back_exactly(j70):
    assert j70.speed(10, 90) == 6.68
    assert j70.speed(24, 150) == 14.35


def test_between_columns_and_rows_it_interpolates(j70):
    # Halfway between 8 and 10 knots at 90°: between 6.25 and 6.68.
    assert 6.25 < j70.speed(9, 90) < 6.68
    # Between the beat angle (39.9° → 5.47) and the first row (52° → 6.03).
    assert 5.47 < j70.speed(10, 46) < 6.03
    # Symmetric in the sign of the angle.
    assert j70.speed(10, -90) == j70.speed(10, 90)


def test_pinching_is_slower_than_the_beat_angle(j70):
    beat, speed = j70.best_upwind(10)
    assert j70.speed(10, beat - 10) < speed
    assert j70.speed(10, 0) == 0


def test_vmg_follows_from_angle_and_speed(j70):
    assert math.isclose(j70.vmg_upwind(10), 5.47 * math.cos(math.radians(39.9)), rel_tol=1e-9)
    assert math.isclose(j70.vmg_downwind(10), 5.9 * -math.cos(math.radians(151.6)), rel_tol=1e-9)


def test_scaling_keeps_angles_and_multiplies_speeds(j70):
    faster = j70.scaled(1.2)
    assert faster.best_upwind(10)[0] == j70.best_upwind(10)[0]
    assert math.isclose(faster.speed(10, 90), 1.2 * j70.speed(10, 90))
