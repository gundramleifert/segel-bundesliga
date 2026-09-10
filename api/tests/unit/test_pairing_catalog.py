"""The catalog of ready-made pairing lists.

The claim everything rests on: shuffling does not change quality. If that holds, a
once-computed list may be reassigned any number of times — and the expensive optimization
run is skipped for every further event.
"""

import pytest

from app.pairing import logistics_report, pairing_report
from app.pairing.catalog import CatalogError, catalog_entries, load_entry, shuffle_pairing, to_yaml


def quality(pairing) -> dict:
    return {
        **pairing_report(pairing.slots, len(pairing.teams), len(pairing.boats)),
        **logistics_report(pairing.slots, len(pairing.boats)).as_dict(),
    }


class TestTheCatalog:
    def test_the_catalog_knows_the_league_configuration(self):
        """""18 teams, 6 boats, 16 flights — the Bundesliga matchday."""""
        zuschnitte = {(e.teams, e.boats, e.flights) for e in catalog_entries()}
        assert (18, 6, 16) in zuschnitte

    def test_the_configuration_is_read_from_the_file_not_from_its_name(self):
        """""A file from the Java tool can be placed in unchanged."""""
        for entry in catalog_entries():
            geladen = load_entry(entry.teams, entry.boats, entry.flights)
            assert geladen.flights == entry.flights
            assert len(geladen.boats) == entry.boats
            assert len(geladen.teams) == entry.teams

    def test_the_stored_list_is_a_valid_draw(self):
        """Each team once per flight, each boat once per race — otherwise
        it would be worthless."""
        pairing = load_entry(18, 6, 16)
        assert len(pairing.slots) == 18 * 16

        per_flight: dict[int, list[int]] = {}
        per_race: dict[int, list[int]] = {}
        for slot in pairing.slots:
            per_flight.setdefault(slot.flight, []).append(slot.team_index)
            per_race.setdefault(slot.sequence, []).append(slot.boat_number)

        assert len(per_flight) == 16
        for teams in per_flight.values():
            assert sorted(teams) == list(range(18))
        for boats in per_race.values():
            assert sorted(boats) == [1, 2, 3, 4, 5, 6]

    def test_the_stored_list_needs_no_boat_changes(self):
        """This is why it is stored rather than recomputed.

        The Python generator produces about 27 boat changes here; the stored run of the
        Java tool needs none. That quality is exactly what must survive being reused.
        """
        report = quality(load_entry(18, 6, 16))
        assert report["boat_changes"] == 0
        assert report["repeated_groups"] == 0

    def test_an_unknown_configuration_says_which_ones_exist(self):
        with pytest.raises(CatalogError) as error:
            load_entry(20, 5, 12)
        assert "20 teams" in str(error.value)
        assert "Available" in str(error.value)


class TestShuffling:
    def test_shuffling_leaves_every_quality_metric_unchanged(self):
        """""The metrics depend on the structure, not who sits where."""""
        pairing = load_entry(18, 6, 16)
        vorher = quality(pairing)
        for seed in (1, 42, 4711):
            assert quality(shuffle_pairing(pairing, seed)) == vorher

    def test_shuffling_stays_a_valid_draw(self):
        gemischt = shuffle_pairing(load_entry(18, 6, 16), 42)
        per_flight: dict[int, list[int]] = {}
        for slot in gemischt.slots:
            per_flight.setdefault(slot.flight, []).append(slot.team_index)
        for teams in per_flight.values():
            assert sorted(teams) == list(range(18))

    def test_derselbe_startwert_ergibt_dieselbe_auslosung(self):
        """""A draw must be provable in case of dispute."""""
        pairing = load_entry(18, 6, 16)
        assert shuffle_pairing(pairing, 42).slots == shuffle_pairing(pairing, 42).slots

    def test_a_different_seed_yields_a_different_draw(self):
        pairing = load_entry(18, 6, 16)
        assert shuffle_pairing(pairing, 1).slots != shuffle_pairing(pairing, 2).slots

    def test_shuffling_takes_milliseconds(self):
        """""The whole point: seconds instead of minutes."""""
        import time

        pairing = load_entry(18, 6, 16)
        start = time.perf_counter()
        for seed in range(50):
            shuffle_pairing(pairing, seed)
        assert time.perf_counter() - start < 1.0


class TestStoringACatalogEntry:
    def test_what_is_written_can_be_read_back(self, tmp_path):
        """""Without this round, the catalog would only be as good as the file it contains."""""
        pairing = load_entry(12, 6, 8)
        datei = tmp_path / "t12-b6-f8.yml"
        datei.write_text(to_yaml(pairing.slots, pairing.flights), encoding="utf-8")

        wieder = load_entry(12, 6, 8, base=tmp_path)
        assert wieder.slots == pairing.slots
