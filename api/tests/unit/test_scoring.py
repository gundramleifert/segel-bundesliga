import pytest

from app.models.racing import ResultCode
from app.scoring import RaceResult, ScoringConfig, race_points, score_event

STARTERS = 6


def finished(race_id: int, position: int, sequence: int | None = None) -> RaceResult:
    return RaceResult(
        race_id=race_id,
        sequence=sequence if sequence is not None else race_id,
        starters=STARTERS,
        code=ResultCode.FINISHED,
        finish_position=position,
    )


def test_finish_position_is_the_score():
    assert race_points(finished(1, 3), ScoringConfig()) == 3.0


@pytest.mark.parametrize(
    "code",
    [
        ResultCode.DNS,
        ResultCode.DNF,
        ResultCode.OCS,
        ResultCode.DSQ,
        # Story WL-3: a U-flag or black-flag start penalty scores like OCS (RRS A5.2).
        ResultCode.UFD,
        ResultCode.BFD,
    ],
)
def test_non_finishers_score_starters_plus_one(code):
    result = RaceResult(race_id=1, sequence=1, starters=STARTERS, code=code)
    assert race_points(result, ScoringConfig()) == STARTERS + 1


def test_redress_uses_the_juries_points():
    result = RaceResult(
        race_id=1, sequence=1, starters=STARTERS, code=ResultCode.RDG, redress_points=2.5
    )
    assert race_points(result, ScoringConfig()) == 2.5


def test_percentage_penalty_adds_20_percent_of_starters():
    # 20% of 6 starters = 1.2 -> rounded 1 point penalty on place 2.
    result = RaceResult(
        race_id=1,
        sequence=1,
        starters=STARTERS,
        code=ResultCode.ZFP,
        finish_position=2,
    )
    assert race_points(result, ScoringConfig()) == 3.0


def test_percentage_penalty_never_worse_than_dnf():
    result = RaceResult(
        race_id=1,
        sequence=1,
        starters=STARTERS,
        code=ResultCode.ZFP,
        finish_position=6,
    )
    assert race_points(result, ScoringConfig()) == STARTERS + 1


def test_event_ranking_orders_by_net_points():
    scores = score_event(
        {
            10: [finished(1, 1), finished(2, 2)],  # 3 Punkte
            11: [finished(1, 2), finished(2, 1)],  # 3 Punkte
            12: [finished(1, 3), finished(2, 3)],  # 6 Punkte
        }
    )
    assert [s.team_id for s in scores][-1] == 12
    assert scores[-1].net == 6.0


def test_tie_is_broken_by_the_better_series_then_the_last_race():
    ""  # Both teams have 3 points and each a first place — the last race decides.""
    scores = score_event(
        {
            10: [finished(1, 1, sequence=1), finished(2, 2, sequence=2)],
            11: [finished(1, 2, sequence=1), finished(2, 1, sequence=2)],
        }
    )
    assert scores[0].team_id == 11
    assert scores[0].net == scores[1].net == 3.0


def test_discards_remove_the_worst_result_once_configured():
    config = ScoringConfig(discard_after=(4,))
    results = [finished(i, 1) for i in range(1, 4)] + [finished(4, 6)]
    scores = score_event({10: results}, config)
    assert scores[0].total == 9.0
    assert scores[0].net == 3.0
    assert scores[0].discarded_races == {4}


def test_dne_survives_a_discard():
    """A non-discardable disqualification remains.

    The next-worst result is dropped in its place.
    """
    config = ScoringConfig(discard_after=(2,))
    dne = RaceResult(race_id=1, sequence=1, starters=STARTERS, code=ResultCode.DNE)
    scores = score_event({10: [dne, finished(2, 5), finished(3, 1)]}, config)
    assert scores[0].discarded_races == {2}


def test_races_without_a_result_are_ignored():
    pending = RaceResult(race_id=2, sequence=2, starters=STARTERS)
    scores = score_event({10: [finished(1, 4), pending]})
    assert scores[0].net == 4.0
    assert 2 not in scores[0].points_by_race


def test_a_matchday_penalty_counts_once_and_is_never_discarded():
    """Story WL-4: carried points sit on top of the races, outside the discards."""
    config = ScoringConfig(discard_after=(4,))
    results = [finished(i, 1) for i in range(1, 4)] + [finished(4, 6)]
    scores = score_event(
        {10: results, 20: [finished(i, 2) for i in range(1, 5)]}, config, {10: 3.0}
    )
    penalised = next(s for s in scores if s.team_id == 10)
    # Races 9, the worst (6) discarded: net 3 — plus the penalty, once, on both.
    assert (penalised.total, penalised.net, penalised.penalty) == (12.0, 6.0, 3.0)
    assert penalised.discarded_races == {4}
    # Without the penalty team 10 would lead (3 against 6); with it they tie on 6 and the
    # better series decides — the penalty counts in the ranking, not only in the total.
    assert [s.team_id for s in scores] == [10, 20]
    assert next(s for s in scores if s.team_id == 20).penalty == 0.0


def test_a_penalty_alone_is_a_score():
    """Story WL-4: a team penalised before its first race already has a row."""
    scores = score_event({10: []}, None, {10: 2.0})
    assert (scores[0].total, scores[0].net) == (2.0, 2.0)
