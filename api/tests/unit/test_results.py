"""The result rules without a database — Story WL-2, ``app/services/results.py``."""

import pytest

from app.models import Event, Series
from app.models.racing import ResultCode
from app.problems import Problem
from app.services.lookup import not_found_code
from app.services.results import NO_RESULT, RawResult, SubmittedResult, resolve_results

RACE = 7


def first(position: int) -> RawResult:
    return RawResult(ResultCode.FINISHED, position, None)


def refusal(current, submitted) -> str:
    with pytest.raises(Problem) as caught:
        resolve_results(current, submitted, RACE)
    return caught.value.code


def test_a_boat_not_in_the_race_is_refused():
    """Story WL-2: a result for a boat with no entry is refused, naming the boat."""
    assert refusal({1: NO_RESULT}, [SubmittedResult(9, "FINISHED", 1)]) == (
        "race-result-unknown-boat"
    )


def test_an_unknown_code_is_refused():
    """Story WL-2: only the codes of RRS Appendix A are results."""
    assert refusal({1: NO_RESULT}, [SubmittedResult(1, "LATE", 1)]) == "race-result-invalid-code"


def test_a_finish_needs_a_position_and_redress_needs_points():
    """Story WL-2: FINISHED/ZFP/SCP carry a place, RDG carries its points."""
    assert refusal({1: NO_RESULT}, [SubmittedResult(1, "ZFP")]) == "race-result-position-required"
    assert refusal({1: NO_RESULT}, [SubmittedResult(1, "RDG")]) == "race-result-redress-required"


def test_a_place_another_boat_keeps_is_refused():
    """Story WL-2: the duplicate check runs over the race's resulting state — a boat not
    submitted still holds its place."""
    current = {1: first(1), 2: NO_RESULT}
    assert refusal(current, [SubmittedResult(2, "FINISHED", 1)]) == (
        "race-result-duplicate-position"
    )


def test_moving_a_boat_off_a_place_frees_it():
    """Story WL-2: two boats swapping places in one submission is no conflict."""
    current = {1: first(1), 2: first(2)}
    updates = resolve_results(
        current, [SubmittedResult(1, "FINISHED", 2), SubmittedResult(2, "FINISHED", 1)], RACE
    )
    assert updates == {1: first(2), 2: first(1)}


def test_fields_a_code_does_not_carry_are_dropped():
    """Story WL-2: a DNF keeps no place and an RDG no position; no code clears all three."""
    updates = resolve_results(
        {1: first(1), 2: NO_RESULT, 3: first(3)},
        [
            SubmittedResult(1, "DNF", 1),
            SubmittedResult(2, "RDG", 4, 2.5),
            SubmittedResult(3, None, 3, 1.0),
        ],
        RACE,
    )
    assert updates == {
        1: RawResult(ResultCode.DNF, None, None),
        2: RawResult(ResultCode.RDG, None, 2.5),
        3: NO_RESULT,
    }


def test_a_missing_row_has_a_code_named_after_its_model():
    """The 404 codes ``get_or_404`` derives are the ones clients already map."""
    assert not_found_code(Event) == "event-not-found"
    assert not_found_code(Series) == "series-not-found"
