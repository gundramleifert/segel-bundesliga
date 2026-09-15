"""The contract every tracking implementation has to meet (Story L-2).

The emulator knows when each boat rounded and crossed; the analysis pipeline has to find
the same passings within three seconds, rank finished boats in finish order, and rank the
same boats the same way whatever order they are handed in and whatever the polar's absolute
speeds are. A new detector, distance or ranker is admitted when it passes this file.
"""

from datetime import UTC, datetime

import pytest

from app.tracking.analysis import RaceAnalysis, default_pipeline
from app.tracking.course import MarkRole, lay_course
from app.tracking.distance import StraightLineDistance
from app.tracking.emulate import emulated_race
from app.tracking.geo import XY, LocalTangentPlane
from app.tracking.polar import J70, Polar
from app.tracking.ranking import ByLegThenDistance, ByTimeToGo

ORIGIN = (54.42, 10.19)  # Kiel Fjord
BOATS = [1, 2, 3, 4, 5, 6]
START = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def polar() -> Polar:
    return Polar.load(J70)


@pytest.fixture(scope="module")
def race(polar):
    projection = LocalTangentPlane(*ORIGIN)
    # The league's course: start – W – G – W – finish.
    course = lay_course(XY(0, 0), wind_from_deg=20.0, leg_length=300.0, laps=2)
    emulation = emulated_race(course, projection, boats=BOATS, start=START, polar=polar, seed=7)
    tracks = emulation.run()
    return course, emulation, tracks


def test_every_boat_sails_the_whole_course(race):
    course, emulation, tracks = race
    assert emulation.finished()
    for boat in BOATS:
        assert len(emulation.truth()[boat]) == len(course.waypoints())
        # Ten minutes at most for a 300 m leg — not a boat drifting in circles.
        assert len(tracks[boat]) < 900


def test_the_default_pipeline_finds_every_passing_within_three_seconds(race):
    course, emulation, tracks = race
    pipeline = default_pipeline(ORIGIN)
    truth = emulation.truth()
    for boat in BOATS:
        state = pipeline.state_of(boat, tracks[boat], course)
        assert state is not None
        assert [p.waypoint for p in state.passings] == [p.waypoint for p in truth[boat]]
        for found, real in zip(state.passings, truth[boat], strict=True):
            assert abs((found.t - real.t).total_seconds()) <= 3.0, (boat, found, real)


def _same_order_where_it_is_decidable(found: list[int], emulation, tolerance: float = 3.0):
    """The detected order must agree with the truth for every pair of boats whose true
    finish times lie more than ``tolerance`` apart — the detector's contract is ±3 s, so two
    boats finishing half a second apart may legitimately come out swapped."""
    truth = {b: emulation.truth()[b][-1].t for b in BOATS}
    position = {b: i for i, b in enumerate(found)}
    for a in BOATS:
        for b in BOATS:
            if (truth[b] - truth[a]).total_seconds() > tolerance:
                assert position[a] < position[b], (a, b, truth[a], truth[b], found)


def test_the_final_ranking_is_the_finish_order(race):
    course, emulation, tracks = race
    ranked = default_pipeline(ORIGIN).analyse(tracks, course)
    _same_order_where_it_is_decidable([r.state.boat for r in ranked], emulation)
    assert [r.rank for r in ranked] == [1, 2, 3, 4, 5, 6]
    assert all(r.finished_at is not None and r.time_to_go is None for r in ranked)


def _snapshot(tracks, seconds: int):
    cut = START.timestamp() + seconds
    return {boat: [f for f in fixes if f.t.timestamp() <= cut] for boat, fixes in tracks.items()}


@pytest.mark.parametrize("seconds", [60, 150, 240, 330])
def test_mid_race_rank_is_independent_of_boat_order_and_polar_scale(race, polar, seconds):
    course, _emulation, tracks = race
    snapshot = _snapshot(tracks, seconds)
    pipeline = default_pipeline(ORIGIN, polar=polar)
    order = [r.state.boat for r in pipeline.analyse(snapshot, course)]

    shuffled = dict(reversed(list(snapshot.items())))
    assert [r.state.boat for r in pipeline.analyse(shuffled, course)] == order

    scaled = default_pipeline(ORIGIN, polar=polar.scaled(1.2))
    assert [r.state.boat for r in scaled.analyse(snapshot, course)] == order


def test_a_boat_further_up_the_course_ranks_ahead(race):
    course, _emulation, tracks = race
    ranked = default_pipeline(ORIGIN).analyse(_snapshot(tracks, 150), course)
    for ahead, behind in zip(ranked, ranked[1:], strict=False):
        if ahead.finished_at or behind.finished_at:
            continue
        assert ahead.time_to_go <= behind.time_to_go


def test_the_second_implementations_meet_the_same_contract(race, polar):
    course, emulation, tracks = race
    alternative = RaceAnalysis(
        projection=LocalTangentPlane(*ORIGIN),
        distance=StraightLineDistance(),
        detector=default_pipeline(ORIGIN).detector,
        ranker=ByLegThenDistance(),
    )
    ranked = alternative.analyse(tracks, course)
    _same_order_where_it_is_decidable([r.state.boat for r in ranked], emulation)
    # And the time-based ranker with the straight-line distance agrees on the finish too.
    mixed = RaceAnalysis(
        projection=LocalTangentPlane(*ORIGIN),
        distance=StraightLineDistance(),
        detector=default_pipeline(ORIGIN).detector,
        ranker=ByTimeToGo(polar),
    )
    _same_order_where_it_is_decidable(
        [r.state.boat for r in mixed.analyse(tracks, course)], emulation
    )


def test_the_laid_course_has_the_pin_to_port_and_the_finish_where_asked():
    left = lay_course(XY(0, 0), wind_from_deg=0.0, finish_pin_side="left")
    committee = left.marks[MarkRole.COMMITTEE_BOAT]
    pin = left.marks[MarkRole.START_PIN]
    # Wind from the north: looking upwind, port is west — the pin has the smaller x.
    assert pin.x < committee.x
    assert left.marks[MarkRole.FINISH_PIN].x < committee.x
    right = lay_course(XY(0, 0), wind_from_deg=0.0, finish_pin_side="right")
    assert right.marks[MarkRole.FINISH_PIN].x > committee.x
    # Two laps: the gate once, between the windward roundings; never on the way to the
    # finish. One lap: no gate at all.
    assert [w.name for w in left.waypoints()] == [
        "start",
        "windward 1",
        "gate 1",
        "windward 2",
        "finish",
    ]
    assert [w.name for w in lay_course(XY(0, 0), wind_from_deg=0.0, laps=1).waypoints()] == [
        "start",
        "windward 1",
        "finish",
    ]
    upwind = lay_course(XY(0, 0), wind_from_deg=0.0, laps=2, finish_upwind=True).waypoints()
    assert [w.name for w in upwind] == ["start", "windward 1", "gate 1", "windward 2", "finish"]
    assert upwind[-1].direction == +1
