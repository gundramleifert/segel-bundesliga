"""Story R-3: a league's media page shows the library's photos.

What photographers delivered for a league's regattas appears there without editorial
placing each picture in a post — only what is public, newest regatta first.
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
