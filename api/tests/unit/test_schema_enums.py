"""Closed sets are typed as enums in the request schemas, so an unknown value is refused
at validation (422) before a router or service sees it."""

import pytest
from pydantic import ValidationError

from app.models.racing import PreparatoryFlag, RaceSignal, ResultCode
from app.schemas.admin import RaceResultIn, RaceSignalIn, RaceStartIn


def test_a_result_code_is_parsed_into_the_enum() -> None:
    assert RaceResultIn(boat_number=1, code="DNF").code is ResultCode.DNF
    assert RaceResultIn(boat_number=1, code=None).code is None


def test_an_unknown_result_code_is_refused() -> None:
    with pytest.raises(ValidationError):
        RaceResultIn(boat_number=1, code="XYZ")


def test_flags_are_parsed_into_their_enums() -> None:
    assert RaceStartIn(preparatory="BLACK").preparatory is PreparatoryFlag.BLACK
    assert RaceSignalIn(signal="X").signal is RaceSignal.X
    with pytest.raises(ValidationError):
        RaceSignalIn(signal="N")
