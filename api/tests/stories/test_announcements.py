"""Story VA-11: the race committee, the jury and the organizer publish announcements on
the event's notice board."""

from __future__ import annotations

from uuid import uuid4

from tests.stories.test_create_event import admin
from tests.stories.test_login_and_roles import login_as, make_user
from tests.stories.test_registration import auth_headers

EVENT = "dsbl-1-2026-act-1"


async def _holder(client, caplog, headers, relation: str, obj: str) -> dict[str, str]:
    """A fresh account holding one relation on one object, signed in."""
    email = f"va11-{relation}-{uuid4().hex[:6]}@example.com"
    await make_user(email)
    granted = await client.post(
        "/api/auth/tuples",
        headers=headers,
        json={"user": email, "relation": relation, "object": obj},
    )
    assert granted.status_code == 201, granted.text
    return auth_headers(await login_as(client, email, caplog))


async def _publish(client, headers, event_id: int, issuer: str, title: str = "AP ashore"):
    return await client.post(
        f"/api/admin/events/{event_id}/announcements",
        headers=headers,
        json={"issuer": issuer, "title": title, "body": "Next signal not before 10:30."},
    )


class TestAnnouncements:
    """VA-11: as the organizer, race committee or jury of an event I publish an
    announcement on the website."""

    async def test_the_race_committee_publishes_and_everyone_reads_it(self, client, caplog, ids):
        """Story VA-11: a race officer of the event publishes; a visitor reads it on the
        event's notice board, with its number, issuer, time and publisher."""
        headers = await admin(client, caplog, "va11-admin@example.com")
        event_id = ids.event(EVENT)
        officer = await _holder(client, caplog, headers, "race_officer", f"event:{event_id}")

        published = await _publish(client, officer, event_id, "race_committee")
        assert published.status_code == 201, published.text
        assert published.json()["author"]

        board = (await client.get(f"/api/events/{event_id}/announcements")).json()
        assert board[0]["id"] == published.json()["id"]
        assert board[0]["issuer"] == "race_committee"
        assert board[0]["title"] == "AP ashore"
        assert board[0]["number"] == published.json()["number"]
        # Read back from the table, the time still says it is UTC — a browser reads a
        # zoneless one as local time.
        assert board[0]["created_at"].endswith("Z"), board[0]["created_at"]

    async def test_announcements_are_numbered_per_event(self, client, caplog, ids):
        """Story VA-11: each event counts its own notices, 1, 2, 3 … — whoever publishes
        them — so a sailor can name the one they mean."""
        headers = await admin(client, caplog, "va11-admin8@example.com")
        here, there = ids.event(EVENT), ids.event("dsbl-1-2026-act-2")
        first = (await _publish(client, headers, here, "race_committee")).json()
        second = (await _publish(client, headers, here, "organizer", "Dinner at 20:00")).json()
        elsewhere = (await _publish(client, headers, there, "jury")).json()
        assert second["number"] == first["number"] + 1
        # The other event's count is its own: it continues from its own board, not this one.
        board = (await client.get(f"/api/events/{there}/announcements")).json()
        assert board[0]["id"] == elsewhere["id"]
        assert elsewhere["number"] == len(board)

    async def test_the_organizer_and_the_jury_speak_for_themselves(self, client, caplog, ids):
        """Story VA-11: each issuer is the relation it names — the organizer publishes as
        the organizer, the jury as the jury, and neither as the race committee."""
        headers = await admin(client, caplog, "va11-admin2@example.com")
        event_id = ids.event(EVENT)
        organizer = await _holder(client, caplog, headers, "manager", f"event:{event_id}")
        jury = await _holder(client, caplog, headers, "jury", f"event:{event_id}")

        assert (await _publish(client, organizer, event_id, "organizer")).status_code == 201
        assert (await _publish(client, jury, event_id, "jury", "Hearing 17:00")).status_code == 201
        refused = await _publish(client, jury, event_id, "race_committee")
        assert refused.status_code == 403, refused.text
        assert refused.json()["required"] == ["race_officer"]

        access = (await client.get(f"/api/events/{event_id}/access", headers=jury)).json()
        assert access["announce_as"] == ["jury"]

    async def test_a_race_officer_through_the_series_may_announce(self, client, caplog, ids):
        """Story VA-11: the model's rewrite rules count — a race officer of the series is
        one of each of its events."""
        headers = await admin(client, caplog, "va11-admin3@example.com")
        event_id = ids.event(EVENT)
        officer = await _holder(
            client, caplog, headers, "race_officer", f"series:{ids.series('dsbl-1-2026')}"
        )
        assert (await _publish(client, officer, event_id, "race_committee")).status_code == 201

    async def test_nobody_else_may_announce(self, client, caplog, ids):
        """Story VA-11: a helper, an officer of another event and a guest cannot."""
        headers = await admin(client, caplog, "va11-admin4@example.com")
        event_id = ids.event(EVENT)
        helper = await _holder(client, caplog, headers, "helper", f"event:{event_id}")
        elsewhere = await _holder(
            client, caplog, headers, "race_officer", f"event:{ids.event('dsbl-1-2026-act-2')}"
        )
        for who in (helper, elsewhere):
            assert (await _publish(client, who, event_id, "race_committee")).status_code == 403
        assert (await _publish(client, {}, event_id, "race_committee")).status_code == 401
        access = (await client.get(f"/api/events/{event_id}/access", headers=helper)).json()
        assert access["announce_as"] == []

    async def test_an_announcement_can_be_retracted(self, client, caplog, ids):
        """Story VA-11: a wrong time is retracted by whoever may speak for its issuer —
        the jury cannot take back the committee's notice."""
        headers = await admin(client, caplog, "va11-admin5@example.com")
        event_id = ids.event(EVENT)
        officer = await _holder(client, caplog, headers, "race_officer", f"event:{event_id}")
        jury = await _holder(client, caplog, headers, "jury", f"event:{event_id}")
        announcement = (await _publish(client, officer, event_id, "race_committee")).json()
        url = f"/api/admin/events/{event_id}/announcements/{announcement['id']}"

        assert (await client.delete(url, headers=jury)).status_code == 403
        assert (await client.delete(url, headers=officer)).status_code == 204
        again = await client.delete(url, headers=officer)
        assert again.status_code == 404
        assert again.json()["type"].endswith("/announcement-not-found")
        board = (await client.get(f"/api/events/{event_id}/announcements")).json()
        assert announcement["id"] not in [a["id"] for a in board]

    async def test_a_title_is_needed(self, client, caplog, ids):
        """Story VA-11: an announcement without a title is refused."""
        headers = await admin(client, caplog, "va11-admin6@example.com")
        for title in ("", "   "):
            response = await _publish(client, headers, ids.event(EVENT), "organizer", title=title)
            assert response.status_code == 422, response.text
            assert response.json()["type"].endswith("/announcement-title-empty")

    async def test_publishing_tells_open_pages(self, client, caplog, ids):
        """Story VA-11 / B-5: a published announcement is a change on the event's topic,
        after the commit — the stream carries no copy of it."""
        from app.live import hub

        headers = await admin(client, caplog, "va11-admin7@example.com")
        event_id = ids.event(EVENT)
        before = hub.version(f"event:{event_id}")
        assert (await _publish(client, headers, event_id, "organizer")).status_code == 201
        assert hub.version(f"event:{event_id}") > before
