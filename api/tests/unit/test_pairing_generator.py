"""The own generator is only the fallback — it must still deliver a fair list.

The benchmark is the actual draw of the Java tool
(see ``test_pairing_import.test_the_official_draw_sets_the_quality_benchmark``):
boat spread ≤ 2, opponent meetings 4–6, no duplicate groups.
"""

import pytest

from app.pairing import build_pairing, pairing_report


def test_a_matchday_has_every_team_once_per_flight():
    slots = build_pairing(team_count=18, flights=16)
    for flight in range(1, 17):
        teams = [s.team_index for s in slots if s.flight == flight]
        assert sorted(teams) == list(range(18)), f"Flight {flight} is not a complete round"


def test_every_race_fills_each_boat_exactly_once():
    slots = build_pairing(team_count=18, flights=16)
    by_race: dict[int, list[int]] = {}
    for slot in slots:
        by_race.setdefault(slot.sequence, []).append(slot.boat_number)
    assert len(by_race) == 48
    for sequence, boats in by_race.items():
        assert sorted(boats) == [1, 2, 3, 4, 5, 6], f"Race {sequence} is incorrectly assigned"


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4])
def test_the_result_is_as_balanced_as_the_official_draw(seed):
    report = pairing_report(build_pairing(18, 16, seed=seed), team_count=18)
    assert report["repeated_groups"] == 0
    assert report["boat_spread_max"] <= 2
    # Slightly wider than the Java tool (4–6 there), but no outliers downward.
    assert report["opponent_min"] >= 3
    assert report["opponent_max"] <= 7


def test_the_draw_is_reproducible():
    """A draw must be provable — same input, same result."""
    assert build_pairing(18, 16, seed=42) == build_pairing(18, 16, seed=42)


def test_different_seeds_give_different_draws():
    assert build_pairing(18, 16, seed=1) != build_pairing(18, 16, seed=2)


def test_a_roster_that_does_not_fill_the_boats_is_rejected():
    with pytest.raises(ValueError, match="evenly distributed"):
        build_pairing(team_count=17, flights=16)


def test_smaller_fleets_work_too():
    """Not every league sails with 18 teams — youth and women leagues vary."""
    slots = build_pairing(team_count=12, flights=8, boats=4)
    assert len({s.sequence for s in slots}) == 8 * 3
    assert pairing_report(slots, team_count=12, boats=4)["repeated_groups"] == 0
