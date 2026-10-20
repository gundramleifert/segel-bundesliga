"""Story R-3: a league's media page shows the library's photos and videos.

What photographers delivered for a league's regattas appears there without editorial
placing each picture in a post — only what is public, newest regatta first. Videos are
YouTube links, never files.
"""

from sqlalchemy import update

from app.db import SessionLocal
from app.models import Event
from tests.stories.test_media import picture
from tests.stories.test_posts import editor


async def upload(client, headers, **context) -> dict:
    made = await client.post(
        "/api/admin/media",
        headers=headers,
        files={"file": ("regatta.jpg", picture(size=(1200, 800)), "image/jpeg")},
        data={"credit": "P. Photographer", **{k: str(v) for k, v in context.items()}},
    )
    assert made.status_code == 201, made.text
    return made.json()


async def league_media(client, league: str = "1-liga") -> list[dict]:
    page = (await client.get("/api/media", params={"league": league, "limit": 100})).json()
    return page["items"]


class TestPhotos:
    """As a visitor I see the photos of a league's regattas — Story R-3."""

    async def test_a_leagues_page_shows_its_events_and_series_pictures(self, client, caplog, ids):
        """R-3: an event's and a series' pictures are the league's; nothing else is."""
        headers = await editor(client, caplog, "media-editor@example.com")
        of_event = await upload(client, headers, event_id=ids.event("dsbl-1-2026-act-3"))
        of_series = await upload(client, headers, series_id=ids.series("dsbl-1-2026"))
        of_nothing = await upload(client, headers)

        shown = {p["id"]: p for p in await league_media(client)}
        assert of_event["id"] in shown and of_series["id"] in shown
        assert of_nothing["id"] not in shown
        picture = shown[of_event["id"]]
        assert picture["credit"] == "P. Photographer"
        assert picture["context"] and picture["srcset"].endswith("1200w")
        assert of_event["id"] not in {p["id"] for p in await league_media(client, "2-liga")}

    async def test_a_draft_events_pictures_are_not_shown(self, client, caplog, ids):
        """R-3: only what is public — a picture of an unpublished event stays in the library."""
        headers = await editor(client, caplog, "media-editor@example.com")
        event_id = ids.event("dsbl-1-2026-act-2")
        item = await upload(client, headers, event_id=event_id)
        async with SessionLocal() as session:
            await session.execute(update(Event).where(Event.id == event_id).values(published=False))
            await session.commit()
        try:
            assert item["id"] not in {p["id"] for p in await league_media(client)}
        finally:
            async with SessionLocal() as session:
                await session.execute(
                    update(Event).where(Event.id == event_id).values(published=True)
                )
                await session.commit()

    async def test_the_page_is_paged(self, client, caplog, ids):
        """R-3: a season brings hundreds — a page at a time."""
        headers = await editor(client, caplog, "media-editor@example.com")
        for _ in range(3):
            await upload(client, headers, event_id=ids.event("dsbl-1-2026-act-1"))
        first = (await client.get("/api/media", params={"league": "1-liga", "limit": 2})).json()
        assert len(first["items"]) == 2 and first["total"] >= 3


class TestVideos:
    """As editorial I put a league's videos on its media page — Story R-3."""

    async def test_a_youtube_address_becomes_a_video_of_the_league(self, client, caplog, ids):
        """R-3: any YouTube address is read for its video and start; others are refused."""
        headers = await editor(client, caplog, "media-editor@example.com")
        for address, start in [
            ("https://www.youtube.com/watch?v=gMxZptdnbxo&t=1m30s", 90),
            ("youtu.be/gMxZptdnbxo?t=45", 45),
            ("https://www.youtube.com/live/gMxZptdnbxo", 0),
        ]:
            made = await client.post(
                "/api/admin/videos",
                headers=headers,
                json={"url": address, "title": "Act 3", "event_id": ids.event("dsbl-1-2026-act-3")},
            )
            assert made.status_code == 201, made.text
            assert (made.json()["youtube_id"], made.json()["start"]) == ("gMxZptdnbxo", start)

        for address in ("https://vimeo.com/123456", "https://www.youtube.com/watch?v=short"):
            refused = await client.post(
                "/api/admin/videos", headers=headers, json={"url": address, "title": "No"}
            )
            assert refused.status_code == 422, address
            assert refused.json()["type"].endswith("/video-url-invalid")

        shown = (await client.get("/api/videos", params={"league": "1-liga"})).json()
        assert made.json()["id"] in {v["id"] for v in shown}
        other = (await client.get("/api/videos", params={"league": "2-liga"})).json()
        assert made.json()["id"] not in {v["id"] for v in other}

    async def test_a_video_is_corrected_and_removed(self, client, caplog, ids):
        """R-3: title and event change; a removed video leaves the page."""
        headers = await editor(client, caplog, "media-editor@example.com")
        video = (
            await client.post(
                "/api/admin/videos",
                headers=headers,
                json={"url": "https://youtu.be/Vv0Fjvd1Q-0", "title": "Draft title"},
            )
        ).json()
        assert video["id"] not in {
            v["id"] for v in (await client.get("/api/videos", params={"league": "1-liga"})).json()
        }
        changed = await client.patch(
            f"/api/admin/videos/{video['id']}",
            headers=headers,
            json={"title": "Final day", "series_id": ids.series("dsbl-1-2026")},
        )
        assert changed.json()["title"] == "Final day" and changed.json()["context"]
        listed = (await client.get("/api/videos", params={"league": "1-liga"})).json()
        assert video["id"] in {v["id"] for v in listed}

        await client.delete(f"/api/admin/videos/{video['id']}", headers=headers)
        listed = (await client.get("/api/videos", params={"league": "1-liga"})).json()
        assert video["id"] not in {v["id"] for v in listed}

    async def test_only_editorial_adds_videos(self, client):
        """R-3: like the library, editorial alone."""
        refused = await client.post(
            "/api/admin/videos", json={"url": "https://youtu.be/Vv0Fjvd1Q-0", "title": "x"}
        )
        assert refused.status_code == 401
