"""Gegen echte Ausgaben des Java-Werkzeugs, nicht gegen erfundene Beispiele.

Die Fixtures unter ``tests/fixtures/pairing/`` stammen aus
``gundramleifert/PairingList``, Event ``2026_DSBL-1``.
"""

from pathlib import Path

import pytest

from app.pairing import (
    PairingImportError,
    load_pairing_csv,
    load_pairing_yaml,
    pairing_report,
    parse_schedule_config,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "pairing"
SCHEDULE_CFG = (FIXTURES / "schedule_cfg.yml").read_text(encoding="utf-8")
PAIRING_YML = (FIXTURES / "pairing_list.yml").read_text(encoding="utf-8")
PAIRING_CSV = (FIXTURES / "pairing_list.csv").read_text(encoding="utf-8")


def test_schedule_config_reads_teams_and_boat_colours():
    config = parse_schedule_config(SCHEDULE_CFG)
    assert len(config.teams) == 18
    assert config.flights == 16
    # Umlaute und Klammern in Kürzeln müssen unversehrt durchkommen.
    assert "BYCÜ" in config.teams
    assert "BYC (BA)" in config.teams
    assert [b.color for b in config.boats] == [
        "BLACK", "GREEN", "DARKBLUE", "RED", "GRAY", "ORANGE"
    ]
    assert [b.number for b in config.boats] == [1, 2, 3, 4, 5, 6]


def test_yaml_import_yields_a_complete_matchday():
    pairing = load_pairing_yaml(SCHEDULE_CFG, PAIRING_YML)
    assert pairing.flights == 16
    assert pairing.races_per_flight == 3
    assert len({s.sequence for s in pairing.slots}) == 48
    assert len(pairing.slots) == 48 * 6


def test_the_first_race_matches_the_printed_list():
    ""# First line of the YAML file: "2,0,15,12,1,13" — position = boat number."""
    pairing = load_pairing_yaml(SCHEDULE_CFG, PAIRING_YML)
    first = sorted(
        (s for s in pairing.slots if s.sequence == 1), key=lambda s: s.boat_number
    )
    assert [s.team_index for s in first] == [2, 0, 15, 12, 1, 13]
    assert pairing.team_name(first[0]) == pairing.teams[2]


def test_csv_and_yaml_describe_the_same_draw():
    ""# CSV is 1-based, YAML is 0-based — both must produce the same result.""
    from_yaml = load_pairing_yaml(SCHEDULE_CFG, PAIRING_YML)
    from_csv = load_pairing_csv(SCHEDULE_CFG, PAIRING_CSV)
    assert sorted(from_csv.slots, key=_slot_key) == sorted(from_yaml.slots, key=_slot_key)


def test_every_team_sails_exactly_once_per_flight():
    pairing = load_pairing_yaml(SCHEDULE_CFG, PAIRING_YML)
    for flight in range(1, pairing.flights + 1):
        teams = [s.team_index for s in pairing.slots if s.flight == flight]
        assert sorted(teams) == list(range(18)), f"Flight {flight} ist keine volle Runde"


def test_the_official_draw_sets_the_quality_benchmark():
    """""The actual draw sailed — the benchmark for our fallback.

    With 16 flights and 6 boats, a team sails each boat on average 2.67 times; the Java
    tool allows a spread of 2 and thus gains a tighter
    Gegnerverteilung (4 bis 6 Begegnungen je Paar).
    """
    pairing = load_pairing_yaml(SCHEDULE_CFG, PAIRING_YML)
    report = pairing_report(pairing.slots, team_count=18)
    assert report == {
        "races": 48,
        "boat_spread_max": 2,
        "opponent_min": 4,
        "opponent_max": 6,
        "repeated_groups": 0,
    }


class TestUnvollstaendigeFlotte:
    """17 Teams auf 6 Booten: das Java-Werkzeug füllt mit Leerplätzen auf.

    Fixture: Event ``2024-04-06_JSCL-Vilamoura``, Youth Sailing Champions League.
    """

    CFG = (FIXTURES.parent / "pairing-17teams" / "schedule_cfg.yml").read_text(
        encoding="utf-8"
    )
    YML = (FIXTURES.parent / "pairing-17teams" / "pairing_list.yml").read_text(
        encoding="utf-8"
    )

    def test_the_roster_is_not_a_multiple_of_the_fleet(self):
        config = parse_schedule_config(self.CFG)
        assert len(config.teams) == 17
        assert len(config.boats) == 6

    def test_placeholder_seats_produce_no_entry(self):
        pairing = load_pairing_yaml(self.CFG, self.YML)
        # 16 Flights à 3 Wettfahrten, aber nur 17 statt 18 Teams je Flight.
        assert len({s.sequence for s in pairing.slots}) == 48
        assert len(pairing.slots) == 16 * 17
        assert max(s.team_index for s in pairing.slots) == 16

    def test_one_race_per_flight_runs_a_boat_short(self):
        pairing = load_pairing_yaml(self.CFG, self.YML)
        for flight in range(1, 17):
            besetzt = [
                len([s for s in pairing.slots if s.flight == flight and s.race_in_flight == r])
                for r in (1, 2, 3)
            ]
            assert sorted(besetzt) == [5, 6, 6], f"Flight {flight}: {besetzt}"

    def test_every_team_still_sails_once_per_flight(self):
        pairing = load_pairing_yaml(self.CFG, self.YML)
        for flight in range(1, 17):
            teams = [s.team_index for s in pairing.slots if s.flight == flight]
            assert sorted(teams) == list(range(17))


def test_a_flight_missing_a_team_is_rejected():
    broken = PAIRING_YML.replace('"2,0,15,12,1,13"', '"2,0,15,12,1,2"', 1)
    with pytest.raises(PairingImportError, match="is not a complete round"):
        load_pairing_yaml(SCHEDULE_CFG, broken)


def test_a_team_index_beyond_the_roster_is_rejected():
    broken = PAIRING_YML.replace('"2,0,15,12,1,13"', '"2,0,15,12,1,99"', 1)
    with pytest.raises(PairingImportError, match="is outside"):
        load_pairing_yaml(SCHEDULE_CFG, broken)


def test_a_flight_count_mismatch_is_rejected():
    with pytest.raises(PairingImportError, match="lists 15 flights"):
        load_pairing_yaml(SCHEDULE_CFG.replace("flights: 16", "flights: 15"), PAIRING_YML)


def test_a_comma_separated_csv_is_rejected_with_a_helpful_message():
    with pytest.raises(PairingImportError, match="delimiter"):
        load_pairing_csv(SCHEDULE_CFG, PAIRING_CSV.replace(";", ","))


def _slot_key(slot):
    return (slot.sequence, slot.boat_number)
