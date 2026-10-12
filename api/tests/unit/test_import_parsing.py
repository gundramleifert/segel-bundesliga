"""Story A-14: what the importers read out of names — SAP's regatta names, and the kind of
a Manage2Sail document from its file name."""

import pytest

from app.imports.m2s import document_kind
from app.imports.sap import parse_regatta_name, result_of
from app.models import EventDocumentKind


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("1. Segel-Bundesliga 2023 - Berlin (1)", (1, 2023, "Berlin", 1, None)),
        ("2. Segel-Bundesliga 2022 - Friedrichshafen (5)", (2, 2022, "Friedrichshafen", 5, None)),
        ("1. Segel-Bundesliga2018 - Travemünde (3)", (1, 2018, "Travemünde", 3, None)),
        ("1. Segel-Bundesliga 2020 - Hamburg (Finale)", (1, 2020, "Hamburg", None, "Finale")),
        ("1. Segel-Bundesliga 2021 - Finale Berlin", (1, 2021, "Berlin", None, "Finale")),
        ("2. Segel-Bundesliga 2021 - Finale - Berlin", (2, 2021, "Berlin", None, "Finale")),
        ("1. Segel-Bundesliga 2021 - Überlingen", (1, 2021, "Überlingen", None, None)),
    ],
)
def test_a_dsbl_regatta_name_says_division_year_city_and_matchday(name, expected):
    """Story A-14: the matchday is the `(n)`; a final is a label, not a city."""
    parsed = parse_regatta_name(name)
    assert parsed is not None
    assert (parsed.level, parsed.year, parsed.city, parsed.number, parsed.label) == expected


@pytest.mark.parametrize(
    "name",
    [
        "1. Segel-Bundesliga 2015-2016 - Relegation (0)",  # a relegation, no matchday
        "1. Segel-Bundesliga - Kiel (3)",  # no year
        "Relegation zur Segel-Bundesliga 2017 - Hamburg (7)",
        "Deutsche Junioren Segel-Liga 2016 - Sorpesee (1)",
    ],
)
def test_anything_else_is_no_dsbl_matchday(name):
    """Story A-14: only the two divisions' matchdays are imported from SAP."""
    assert parse_regatta_name(name) is None


@pytest.mark.parametrize(
    ("title", "kind"),
    [
        ("20260401_Ausschreibung_DJSL-2026.pdf", EventDocumentKind.NOTICE_OF_RACE),
        ("Notice of Race DSBL 2026.pdf", EventDocumentKind.NOTICE_OF_RACE),
        ("20260506_SI_DJSL 2026_final.pdf", EventDocumentKind.SAILING_INSTRUCTIONS),
        ("20260507__Event SI_DJSL 2026_ACT1_KYC.pdf", EventDocumentKind.SAILING_INSTRUCTIONS),
        ("20260507_NO 1_KYC_ACT 1_Team Umpire.pdf", EventDocumentKind.NOTICE),
        # A numbered notice that amends the SI is a notice.
        ("20260822_NO 1_ACT 2_Change SI_Course Diagram.pdf", EventDocumentKind.NOTICE),
        ("20250505_DJSL 2026 Pairingliste ACT 1.pdf", EventDocumentKind.OTHER),
        # `si` inside a word is not the SI.
        ("Kautionsbürgschaft_Strandesitz.pdf", EventDocumentKind.OTHER),
    ],
)
def test_a_document_s_kind_comes_from_its_title(title, kind):
    """Story A-14: notice of race, sailing instructions, notice — or other."""
    assert document_kind(title) == kind


@pytest.mark.parametrize(
    ("cell", "expected"),
    [
        # Hamburg 2023, F12/Race 1: a boat ahead got redress, so SAP's rank says 4 while
        # the official place — the points — is 3.
        ({"maxPointsReason": "NONE", "totalPoints": 3.0, "rank": 4}, ("FINISHED", 3, None)),
        (
            {"maxPointsReason": "RDG", "totalPoints": 2.7857142857142856, "rank": 3},
            ("RDG", None, 2.7857142857142856),
        ),
        ({"maxPointsReason": "DNF", "totalPoints": 7.0, "rank": 3}, ("DNF", None, None)),
        ({"maxPointsReason": "RAF", "totalPoints": 7.0, "rank": 6}, ("RET", None, None)),
        # Under a percentage penalty the points carry the penalty; the rank is the place.
        ({"maxPointsReason": "ZFP", "totalPoints": 5.0, "rank": 4}, ("ZFP", 4, None)),
        # A code with no equivalent keeps SAP's points, as a redress.
        ({"maxPointsReason": "DPI", "totalPoints": 4.5, "rank": 4}, ("RDG", None, 4.5)),
    ],
)
def test_a_sap_cell_becomes_a_raw_result(cell, expected):
    """Story A-14: the finish position is SAP's points, not its rank."""
    code, position, redress, _ = result_of(cell)
    assert (code, position, redress) == expected


def test_a_boat_s_number_comes_from_its_sail_number_or_its_name():
    """Story A-14: before 2022 SAP's boats have no sail number, only `Boot 5`."""
    from app.imports.sap import boat_numbers

    assert boat_numbers(
        {
            "a": {"sailId": "", "name": "Boot 5"},
            "b": {"sailId": "2", "name": "Boat 2 (1)"},
            "c": {"sailId": "", "name": "Committee"},
            "d": {"sailId": "", "name": "Boot 2"},  # 2 is taken by b: the next number up
        }
    ) == {"b": 2, "d": 3, "a": 5, "c": 6}
