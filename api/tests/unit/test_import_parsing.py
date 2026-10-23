"""Story A-14: what the importers read out of names — SAP's regatta names, and the kind of
a Manage2Sail document from its file name."""

import pytest

from app.imports.m2s import document_kind
from app.imports.sap import junior_competitor, parse_regatta_name, result_of
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
        # The juniors' cup is no act; an act without a year belongs to no series.
        "Deutscher Junioren- & Segel-Liga Pokal 2026",
        "Deutsche Junioren Segel-Liga - Act 3",
        "DJSL Coaching Trainingsregatten",
    ],
)
def test_anything_else_is_no_dsbl_matchday(name):
    """Story A-14: only the leagues' matchdays are imported from SAP."""
    assert parse_regatta_name(name) is None


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Deutsche Junioren Segel-Liga 2026 - Act 1", (2026, 1, None)),
        ("Deutsche Junioren Segel-Liga 2026 - Act 4 (Finale)", (2026, 4, "Finale")),
        ("Deutsche Junioren Segel-Liga 2024 - Nord Act 1", (2024, 1, "Nord")),
        ("Deutsche Junioren Segel-Liga 2024 - Act 4 Finale", (2024, 4, "Finale")),
        ("Deutsche Junioren Segel-Liga 2023 - Act 1 Mitte", (2023, 1, "Mitte")),
        ("Deutsche Junioren Segel-Liga 2021 - Finale Act 4", (2021, 4, "Finale")),
        ("Deutsche Junioren Segel-Liga 2018, Act1", (2018, 1, None)),
        ("Deutsche Junioren Segel-Liga 2017, NORD, ACT 2", (2017, 2, "Nord")),
    ],
)
def test_a_junioren_act_s_name_says_year_act_and_label(name, expected):
    """Story A-14: the juniors' acts on their own SAP host — no city, the act's number."""
    parsed = parse_regatta_name(name)
    assert parsed is not None
    assert parsed.league == "junioren-liga" and parsed.city is None
    assert (parsed.year, parsed.number, parsed.label) == expected
    assert parsed.series_name == f"Junioren-Segelliga {parsed.year}"


@pytest.mark.parametrize(
    ("short_name", "expected"),
    [
        ("NRV", ("NRV", 1)),
        ("KiYC 1", ("KYC (SH)", 1)),
        ("KiYC 2 ", ("KYC (SH)", 2)),
        ("BaYC", ("BYC", 1)),
        ("SHM", ("SCHM", 1)),
        ("VSaW", ("VSaW", 1)),
    ],
)
def test_a_junioren_competitor_is_a_club_code_and_a_team_number(short_name, expected):
    """Story A-14: the number after the code is the team; the host's codes map to ours."""
    assert junior_competitor(short_name) == expected


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


@pytest.mark.parametrize(
    ("spec", "years"),
    [
        ("2025-2026", {2025, 2026}),
        ("2023", {2023}),
        ("2019, 2021-2023", {2019, 2021, 2022, 2023}),
        ("", set()),
    ],
)
def test_a_year_range_names_its_years(spec, years):
    """Story A-14: `--years 2025-2026`, the range the staging build imports."""
    from app.imports.sap import parse_years

    assert parse_years(spec) == years


@pytest.mark.parametrize("spec", ["2026-2025", "twenty", "2025-"])
def test_a_range_that_is_none_is_refused(spec):
    """Story A-14: a mistyped range fails loudly rather than importing nothing."""
    from app.imports.sap import parse_years

    with pytest.raises(ValueError):
        parse_years(spec)
