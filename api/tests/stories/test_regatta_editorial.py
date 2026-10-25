"""Stories R-1, R-2: editorial on a series or an event writes that regatta's news and
keeps its pictures — and organizes nothing (decided 2026-10-24)."""

from __future__ import annotations

from uuid import uuid4

from tests.stories.test_create_event import admin
from tests.stories.test_login_and_roles import login_as, make_user
from tests.stories.test_media import picture
from tests.stories.test_registration import auth_headers

SERIES = "dsbl-1-2026"
ACT = "dsbl-1-2026-act-1"
ELSEWHERE = "junioren-2026"


async def _editor_of(client, caplog, office, obj: str) -> dict[str, str]:
    """A fresh account holding ``editor`` on one series or event, signed in."""
    email = f"regatta-editor-{uuid4().hex[:6]}@example.com"
    await make_user(email)
    granted = await client.post(
        "/api/auth/tuples",
        headers=office,
        json={"user": email, "relation": "editor", "object": obj},
    )
    assert granted.status_code == 201, granted.text
    return auth_headers(await login_as(client, email, caplog))


async def _post(client, headers, **about):
    return await client.post(
        "/api/admin/posts",
        headers=headers,
        json={"title": f"Report {uuid4().hex[:6]}", "body": "<p>Text.</p>", **about},
    )


async def _upload(client, headers, **about):
    return await client.post(
        "/api/admin/media",
        headers=headers,
        files={"file": ("start.jpg", picture(), "image/jpeg")},
        data={key: str(value) for key, value in about.items()},
    )


class TestEditorialOfOneRegatta:
    """R-1, R-2: as a series' or an event's editor I write about that regatta."""

    async def test_a_series_editor_writes_about_its_events_in_its_league(self, client, caplog, ids):
        """Story R-1: a series' editor writes about the series and its events; the post
        appears in the series' league, whatever league it names. Another regatta, or
        none, is the site's editor's."""
        office = await admin(client, caplog, "regatta-office@example.com")
        editor = await _editor_of(client, caplog, office, f"series:{ids.series(SERIES)}")

        written = await _post(client, editor, event_id=ids.event(ACT), league_id=None)
        assert written.status_code == 201, written.text
        one_liga = (await client.get("/api/leagues/1-liga")).json()["league"]["id"]
        assert written.json()["league_id"] == one_liga

        assert (await _post(client, editor, series_id=ids.series(SERIES))).status_code == 201
        other = await _post(client, editor, series_id=ids.series(ELSEWHERE))
        assert other.status_code == 403, other.text
        assert (await _post(client, editor)).status_code == 403

        # Their list is their regatta's; another regatta's post is not theirs to know of.
        foreign = await _post(client, office, series_id=ids.series(ELSEWHERE))
        listed = (await client.get("/api/admin/posts", headers=editor)).json()["items"]
        assert written.json()["id"] in [p["id"] for p in listed]
        assert foreign.json()["id"] not in [p["id"] for p in listed]
        url = f"/api/admin/posts/{foreign.json()['id']}"
        assert (await client.get(url, headers=editor)).status_code == 404
        assert (
            await client.patch(url, headers=editor, json={"title": "Mine now"})
        ).status_code == 404
        assert (await client.delete(url, headers=editor)).status_code == 404

    async def test_an_event_editor_keeps_that_event_s_pictures(self, client, caplog, ids):
        """Story R-2: an event's editor uploads to the event and sees its pictures, not
        another regatta's."""
        office = await admin(client, caplog, "regatta-office2@example.com")
        editor = await _editor_of(client, caplog, office, f"event:{ids.event(ACT)}")

        mine = await _upload(client, editor, event_id=ids.event(ACT))
        assert mine.status_code == 201, mine.text
        assert (await _upload(client, editor, series_id=ids.series(SERIES))).status_code == 403
        assert (await _upload(client, editor)).status_code == 403

        foreign = await _upload(client, office, series_id=ids.series(ELSEWHERE))
        listed = (await client.get("/api/admin/media", headers=editor)).json()["items"]
        # Their regatta's pictures — other tests may have added some — and no other's.
        assert mine.json()["id"] in [p["id"] for p in listed]
        assert foreign.json()["id"] not in [p["id"] for p in listed]
        url = f"/api/admin/media/{foreign.json()['id']}"
        assert (await client.get(url, headers=editor)).status_code == 404
        moved = await client.patch(
            f"/api/admin/media/{mine.json()['id']}",
            headers=editor,
            json={"series_id": ids.series(ELSEWHERE)},
        )
        assert moved.status_code == 403, moved.text

    async def test_a_regatta_s_editor_organizes_nothing(self, client, caplog, ids):
        """Story Z-2: editorial writes; it neither edits the series nor runs its events."""
        office = await admin(client, caplog, "regatta-office3@example.com")
        series_id = ids.series(SERIES)
        editor = await _editor_of(client, caplog, office, f"series:{series_id}")
        changed = await client.patch(
            f"/api/admin/series/{series_id}", headers=editor, json={"description": "Mine"}
        )
        assert changed.status_code == 403, changed.text
        access = (await client.get(f"/api/events/{ids.event(ACT)}/access", headers=editor)).json()
        assert access["manage"] is False
        assert (await client.get("/api/admin/import-keys", headers=editor)).status_code == 403
