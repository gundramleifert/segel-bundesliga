"""Stories VA-14 and WL-5: an event chooses its scoring — this site or SAP Sailing.

No SAP needed: choosing SAP is a setting on the event, and what it changes here — the
race committee's tools stepping aside — is the site's own answer. The send and the
results that come back are `test_sap_send.py` and `test_journey_sap_scored.py`, against
the local SAP.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.config import settings
from tests.stories.test_create_event import admin
from tests.stories.test_login_and_roles import login_as, make_user
from tests.stories.test_registration import auth_headers

EVENT = "demo-2-2026-act-3"  # planned, drawn, ASVW's


async def _scored_on(client, headers, event_id: int, source: str) -> None:
    response = await client.patch(
        f"/api/admin/events/{event_id}", json={"results_source": source}, headers=headers
    )
    assert response.status_code == 200, response.text


class TestTheEventChoosesItsScoring:
    async def test_on_sap_the_race_control_steps_aside(self, client, caplog, ids):
        """VA-14, WL-5: with SAP chosen, the site offers neither its result entry nor its
        race control, and refuses a race signal; back on this site, both return."""
        headers = await admin(client, caplog, f"scoring-{uuid4().hex[:8]}@example.com")
        event_id = ids.event(EVENT)
        races = (await client.get(f"/api/admin/events/{event_id}/races", headers=headers)).json()
        race_id = races["races"][0]["id"]

        await _scored_on(client, headers, event_id, "sap")
        access = (await client.get(f"/api/events/{event_id}/access", headers=headers)).json()
        assert access["record_results"] is False
        assert access["manage"] is True
        signal = await client.post(
            f"/api/admin/events/{event_id}/races/{race_id}/signal",
            json={"signal": "AP"},
            headers=headers,
        )
        assert signal.status_code == 409
        assert signal.json()["type"].endswith("/event-scored-on-sap")
        start = await client.post(
            f"/api/admin/events/{event_id}/races/{race_id}/start", headers=headers
        )
        assert start.status_code == 409
        sequence = await client.put(
            f"/api/admin/events/{event_id}/races/{race_id}/sequence", headers=headers
        )
        assert sequence.status_code == 409

        await _scored_on(client, headers, event_id, "site")
        access = (await client.get(f"/api/events/{event_id}/access", headers=headers)).json()
        assert access["record_results"] is True

    @pytest.mark.parametrize("user", [None, "admin"])
    async def test_sap_is_offered_only_where_it_is_reachable(
        self, client, caplog, ids, monkeypatch, user
    ):
        """VA-14: the choice is offered when this installation has SAP's credentials — and
        never to someone who cannot change the event."""
        headers = await admin(client, caplog, f"sap-{uuid4().hex[:8]}@example.com") if user else {}
        event_id = ids.event(EVENT)
        monkeypatch.setattr(settings, "sap_user", None)
        access = (await client.get(f"/api/events/{event_id}/access", headers=headers)).json()
        assert access["sap"] is False
        monkeypatch.setattr(settings, "sap_user", "league")
        access = (await client.get(f"/api/events/{event_id}/access", headers=headers)).json()
        assert access["sap"] is (user is not None)

    async def test_a_draft_is_answered_to_its_organizers_only(self, client, caplog, ids):
        """VA-14: the 2027 acts are drafts — their organizer is told SAP is on offer, while
        a guest still learns nothing of the draft (a 404, as everywhere public)."""
        draft = ids.event("dsbl-1-2027-hamburg-alster")
        assert (await client.get(f"/api/events/{draft}")).status_code == 404
        assert (await client.get(f"/api/events/{draft}/access")).status_code == 404
        headers = await admin(client, caplog, f"draft-{uuid4().hex[:8]}@example.com")
        access = await client.get(f"/api/events/{draft}/access", headers=headers)
        assert access.status_code == 200, access.text
        assert access.json()["manage"] is True
        stranger = f"stranger-{uuid4().hex[:8]}@example.com"
        await make_user(stranger)
        headers = auth_headers(await login_as(client, stranger, caplog))
        assert (await client.get(f"/api/events/{draft}/access", headers=headers)).status_code == 404
