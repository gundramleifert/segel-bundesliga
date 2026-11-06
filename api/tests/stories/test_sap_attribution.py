"""Story B-21: SAP Sailing is credited wherever its results show.

The seed's Junioren-Liga 2026 was imported from SAP Sailing (`app/seed_junioren.py`), the
1. Liga 2026 from TracTrac — so the one is credited and the other is not, with no SAP
running.
"""

from __future__ import annotations

from base64 import b64encode
from urllib.parse import quote

# SAP's event of the juniors' act 1 on hnv.sapsailing.com (its event list, 2026-11-03).
ACT_1 = "4639e483-8ce0-41d2-b974-fce7fc7481a7"


class TestSapIsCredited:
    async def test_an_act_from_sap_says_so_and_one_from_elsewhere_does_not(self, client, ids):
        """B-21: an event whose results came from SAP carries ``results_from_sap``, on its
        own page and in its series' table; an event scored elsewhere does not."""
        juniors = (await client.get(f"/api/series/{ids.series('junioren-2026')}/table")).json()
        assert juniors["events"], "the Junioren-Liga 2026 is seeded"
        assert all(e["results_from_sap"] for e in juniors["events"])

        act = (await client.get(f"/api/events/{juniors['events'][0]['id']}")).json()
        assert act["event"]["results_from_sap"] is True

        first = (await client.get(f"/api/series/{ids.series('dsbl-1-2026')}/table")).json()
        assert first["events"]
        assert not any(e["results_from_sap"] for e in first["events"])

    async def test_an_act_links_its_own_leaderboard_at_sap(self, client, ids):
        """B-21: the credit under an act from SAP leads to that act's leaderboard, on the
        server it was imported from — the juniors' own host, not a landing page."""
        juniors = (await client.get(f"/api/series/{ids.series('junioren-2026')}/table")).json()
        act = (await client.get(f"/api/events/{juniors['events'][0]['id']}")).json()["event"]
        regatta = quote(b64encode(act["sap_leaderboard"].encode()).decode())
        assert act["sap_leaderboard_url"] == (
            "https://hnv.sapsailing.com/gwt/Home.html#/regatta/leaderboard/"
            f":eventId={ACT_1}&regattaId={regatta}"
        )
        first = (await client.get(f"/api/series/{ids.series('dsbl-1-2026')}/table")).json()
        assert all(e["sap_leaderboard_url"] is None for e in first["events"])
