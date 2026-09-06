"""Der Katalog fertiger Pairing-Listen.

The claim everything rests on: Shuffling does not change quality.  If that is true,
a once-computed list may be reassigned any number of times — and the expensive
Optimierungslauf entfällt bei jeder weiteren Veranstaltung.
"""

import pytest

from app.pairing import logistics_report, pairing_report
from app.pairing.catalog import KatalogFehler, als_yaml, katalog, lade, mische


def guete(pairing) -> dict:
    return {
        **pairing_report(pairing.slots, len(pairing.teams), len(pairing.boats)),
        **logistics_report(pairing.slots, len(pairing.boats)).as_dict(),
    }


class TestKatalog:
    def test_der_katalog_kennt_den_ligazuschnitt(self):
        """""18 teams, 6 boats, 16 flights — the Bundesliga matchday."""""
        zuschnitte = {(e.teams, e.boats, e.flights) for e in katalog()}
        assert (18, 6, 16) in zuschnitte

    def test_der_zuschnitt_wird_aus_der_datei_gelesen_nicht_aus_dem_namen(self):
        """""A file from the Java tool can be placed in unchanged."""""
        for eintrag in katalog():
            geladen = lade(eintrag.teams, eintrag.boats, eintrag.flights)
            assert geladen.flights == eintrag.flights
            assert len(geladen.boats) == eintrag.boats
            assert len(geladen.teams) == eintrag.teams

    def test_die_abgelegte_liste_ist_eine_gueltige_auslosung(self):
        """Each team once per flight, each boat once per race — otherwise
        it would be worthless."""
        pairing = lade(18, 6, 16)
        assert len(pairing.slots) == 18 * 16

        je_flight: dict[int, list[int]] = {}
        je_wettfahrt: dict[int, list[int]] = {}
        for slot in pairing.slots:
            je_flight.setdefault(slot.flight, []).append(slot.team_index)
            je_wettfahrt.setdefault(slot.sequence, []).append(slot.boat_number)

        assert len(je_flight) == 16
        for teams in je_flight.values():
            assert sorted(teams) == list(range(18))
        for boote in je_wettfahrt.values():
            assert sorted(boote) == [1, 2, 3, 4, 5, 6]

    def test_die_abgelegte_liste_kommt_ohne_bootswechsel_aus(self):
        """""This is why it is stored rather than recomputed.

        The Python generator produces about 27 boat changes here; the stored run of the
        Java-Werkzeugs kommt mit null aus. Genau diese Güte soll erhalten bleiben.
        """
        bericht = guete(lade(18, 6, 16))
        assert bericht["boat_changes"] == 0
        assert bericht["repeated_groups"] == 0

    def test_ein_unbekannter_zuschnitt_sagt_was_es_gibt(self):
        with pytest.raises(KatalogFehler) as fehler:
            lade(20, 5, 12)
        assert "20 teams" in str(fehler.value)
        assert "Available" in str(fehler.value)


class TestMischen:
    def test_mischen_laesst_jede_guetekennzahl_unveraendert(self):
        """""The metrics depend on the structure, not who sits where."""""
        pairing = lade(18, 6, 16)
        vorher = guete(pairing)
        for seed in (1, 42, 4711):
            assert guete(mische(pairing, seed)) == vorher

    def test_mischen_bleibt_eine_gueltige_auslosung(self):
        gemischt = mische(lade(18, 6, 16), 42)
        je_flight: dict[int, list[int]] = {}
        for slot in gemischt.slots:
            je_flight.setdefault(slot.flight, []).append(slot.team_index)
        for teams in je_flight.values():
            assert sorted(teams) == list(range(18))

    def test_derselbe_startwert_ergibt_dieselbe_auslosung(self):
        """""A draw must be provable in case of dispute."""""
        pairing = lade(18, 6, 16)
        assert mische(pairing, 42).slots == mische(pairing, 42).slots

    def test_ein_anderer_startwert_ergibt_eine_andere_auslosung(self):
        pairing = lade(18, 6, 16)
        assert mische(pairing, 1).slots != mische(pairing, 2).slots

    def test_mischen_dauert_nicht_lange(self):
        """""The whole point: seconds instead of minutes."""""
        import time

        pairing = lade(18, 6, 16)
        start = time.perf_counter()
        for seed in range(50):
            mische(pairing, seed)
        assert time.perf_counter() - start < 1.0


class TestAblegen:
    def test_was_geschrieben_wird_laesst_sich_wieder_lesen(self, tmp_path):
        """""Without this round, the catalog would only be as good as the file it contains."""""
        pairing = lade(12, 6, 8)
        datei = tmp_path / "t12-b6-f8.yml"
        datei.write_text(als_yaml(pairing.slots, pairing.flights), encoding="utf-8")

        wieder = lade(12, 6, 8, basis=tmp_path)
        assert wieder.slots == pairing.slots
