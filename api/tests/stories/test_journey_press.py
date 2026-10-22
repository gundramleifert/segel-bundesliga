"""Journey J-6 (``docs/journeys/press.md``) — from a sailed race to the report and the press
release; Stories WL-2, R-2, R-1, R-3.

The act is the 2. Liga's live one (``dsbl-2-2026-act-2``): published, half sailed, so a
race still waits for its result. The WL-2 story tests take the 1. Liga's live act, so the
two never claim the same race. Everything the walk creates carries its own tag; nothing is
counted against the seed (docs/gotchas).
"""

from uuid import uuid4

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Boat, Event, Flight, Race, RaceEntry, RaceStatus
from tests.journeys import step
from tests.stories.test_posts import editor, league_id, photo
from tests.stories.test_result_entry import _race_officer

ACT = "dsbl-2-2026-act-2"
LEAGUE = "2-liga"


async def _a_race_still_to_score() -> tuple[int, int, list[int]]:
    """(event, race, boats) of the act's last race without a result. Read from the
    database: no endpoint lists the races still to be sailed by number, and picking one is
    arranging the walk, not walking it."""
    async with SessionLocal() as session:
        event_id = (await session.execute(select(Event.id).where(Event.slug == ACT))).scalar_one()
        race_id = (
            await session.execute(
                select(Race.id)
                .join(Flight, Race.flight_id == Flight.id)
                .where(Flight.event_id == event_id, Race.status == RaceStatus.SCHEDULED)
                .order_by(Race.sequence.desc())
                .limit(1)
            )
        ).scalar_one()
        boats = list(
            (
                await session.execute(
                    select(Boat.number)
                    .join(RaceEntry, RaceEntry.boat_id == Boat.id)
                    .where(RaceEntry.race_id == race_id)
                    .order_by(Boat.number)
                )
            ).scalars()
        )
        return event_id, race_id, boats


class TestFromARaceToThePress:
    async def test_the_photographer_sends_the_pictures(self, client, caplog):
        tag = uuid4().hex[:8]
        event_id, race_id, boats = await _a_race_still_to_score()
        before = (await client.get(f"/api/events/{event_id}")).json()["races_scored"]

        step("J-6.1", "race officer enters a race's results")
        officer = await _race_officer(client, caplog, f"press-ro-{tag}@example.com")
        entered = await client.put(
            f"/api/admin/events/{event_id}/races/{race_id}/result",
            headers=officer,
            json={
                "results": [
                    {"boat_number": boat, "code": "FINISHED", "finish_position": place}
                    for place, boat in enumerate(boats, start=1)
                ]
            },
        )
        assert entered.status_code == 200, entered.text
        assert (await client.get(f"/api/events/{event_id}")).json()["races_scored"] == before + 1

        step("J-6.2", "editor makes an upload link for the act")
        desk = await editor(client, caplog, f"press-editor-{tag}@example.com")
        made = await client.post(
            "/api/admin/import-keys",
            headers=desk,
            json={
                "label": f"Photos act 2 {tag}",
                "credit": f"Photographer {tag}",
                "event_id": event_id,
            },
        )
        assert made.status_code == 201, made.text
        key = made.json()["key"]

        step("J-6.3", "photographer uploads the pictures from the link")
        link = {"X-Import-Key": key}
        said = await client.get("/api/import/key", headers=link)
        assert said.status_code == 200, said.text
        delivered = await client.post(
            "/api/import/media",
            headers=link,
            files={"file": (f"act2-{tag}.jpg", photo((1200, 800)), "image/jpeg")},
        )
        assert delivered.status_code == 201, delivered.text
        picture = delivered.json()
        assert picture["event_id"] == event_id and picture["credit"] == f"Photographer {tag}"

        step("J-6.4", "editor writes the report about the act")
        report = {
            "kind": "news",
            "title": f"A close Sunday in Kiel {tag}",
            "league_id": await league_id(client, LEAGUE),
            "teaser": "The 2. Liga's second act, race by race.",
            "body": "<p>Light wind, and a leader who held on.</p>",
            "photo_url": picture["url"],
            "event_id": event_id,
        }
        draft = await client.post("/api/admin/posts", headers=desk, json=report)
        assert draft.status_code == 201, draft.text
        post = draft.json()
        assert post["published"] is False
        assert (await client.get(f"/api/posts/{post['slug']}")).status_code == 404

        step("J-6.5", "editor previews the report")
        preview = await client.post("/api/admin/posts/preview", headers=desk, json=report)
        assert preview.status_code == 200, preview.text
        assert picture["url"] in {shown["url"] for shown in preview.json()["gallery"]}
        assert (await client.get(f"/api/posts/{post['slug']}")).status_code == 404

        step("J-6.6", "editor publishes the report")
        published = await client.patch(
            f"/api/admin/posts/{post['id']}", headers=desk, json={"published": True}
        )
        assert published.status_code == 200, published.text

        step("J-6.7", "editor publishes the press release")
        release = await client.post(
            "/api/admin/posts",
            headers=desk,
            json={
                "kind": "press",
                "title": f"Results of act 2 {tag}",
                "league_id": await league_id(client, LEAGUE),
                "body": "<p>The standings after the second act.</p>",
                "published": True,
            },
        )
        assert release.status_code == 201, release.text

        step("J-6.8", "visitor reads the report on the league's news")
        news = await client.get("/api/posts", params={"league": LEAGUE, "kind": "news"})
        assert post["slug"] in {item["slug"] for item in news.json()["items"]}
        page = (await client.get(f"/api/posts/{post['slug']}")).json()
        assert page["regatta"] and picture["url"] in {shown["url"] for shown in page["gallery"]}

        step("J-6.9", "visitor opens the release in the press centre")
        press = await client.get("/api/posts", params={"league": LEAGUE, "kind": "press"})
        assert release.json()["slug"] in {item["slug"] for item in press.json()["items"]}
        text = await client.get(f"/api/posts/{release.json()['slug']}")
        assert text.status_code == 200 and "second act" in text.json()["body"]

        step("J-6.10", "visitor looks at the act's photos on the media page")
        media = await client.get("/api/media", params={"league": LEAGUE, "limit": 100})
        shown = {item["id"]: item for item in media.json()["items"]}
        assert picture["id"] in shown and shown[picture["id"]]["credit"] == f"Photographer {tag}"
