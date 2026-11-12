"""Story B-12: a lineup is public once its event is — never while it is a draft.

The organizer's lineup screen read it through ``/api/admin/events/{id}/crew/{team}``,
which answered anyone: the names of a draft event's crews, before the event was
announced. Found by the route inventory (`tests/architecture/test_access.py`).
"""

from tests.stories.test_create_event import BOATS, admin, league_clubs


async def _draft_with_clubs(client, headers) -> tuple[int, int]:
    created = await client.post(
        "/api/admin/events",
        headers=headers,
        json={
            "title": "Unannounced Cup",
            "starts_on": "2027-09-01",
            "team_count": 18,
            "flight_count": 16,
            "boats": BOATS,
        },
    )
    assert created.status_code == 201, created.text
    event_id = created.json()["id"]
    teams = await client.put(
        f"/api/admin/events/{event_id}/clubs",
        headers=headers,
        json={"clubs": await league_clubs(client)},
    )
    return event_id, teams.json()[0]["team_id"]


class TestLineupOfADraft:
    async def test_a_guest_does_not_read_a_drafts_lineup(self, client, caplog):
        headers = await admin(client, caplog, "lineup-draft@example.com")
        event_id, team_id = await _draft_with_clubs(client, headers)
        url = f"/api/admin/events/{event_id}/crew/{team_id}"

        assert (await client.get(url)).status_code == 404
        assert (await client.get(url, headers=headers)).status_code == 200

        await client.patch(
            f"/api/admin/events/{event_id}", headers=headers, json={"published": True}
        )
        assert (await client.get(url)).status_code == 200, "published, it is public"
