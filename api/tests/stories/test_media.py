"""Story R-2: the picture library, and the import API that feeds it.

Every picture arrives through one service, from editorial or from a source holding an
import key: re-encoded, the same bytes twice one entry, a source's own id twice one entry,
and a picture a post shows cannot be deleted.
"""

import io
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

from PIL import Image
from sqlalchemy import update

from app.db import SessionLocal
from app.models import ImportKey
from app.models.auth import Role
from tests.stories.test_login_and_roles import login_as, make_user
from tests.stories.test_posts import editor
from tests.stories.test_registration import auth_headers


def picture(
    fmt: str = "JPEG", size: tuple[int, int] = (64, 48), exif: Image.Exif | None = None
) -> bytes:
    """A picture no other test has uploaded — the library would answer that one's entry."""
    colour = tuple(secrets.randbelow(256) for _ in range(3))
    buffer = io.BytesIO()
    image = Image.new("RGB", size, colour)
    image.putpixel((secrets.randbelow(size[0]), secrets.randbelow(size[1])), (255, 255, 255))
    image.save(buffer, format=fmt, **({"exif": exif} if exif is not None else {}))
    return buffer.getvalue()


async def make_key(client, headers, **fields) -> dict:
    made = await client.post(
        "/api/admin/import-keys", headers=headers, json={"label": "Photos Kiel, act 3", **fields}
    )
    assert made.status_code == 201, made.text
    return made.json()


def deliver(client, key: str, data: bytes, name: str = "start.jpg", **form):
    return client.post(
        "/api/import/media",
        headers={"X-Import-Key": key},
        files={"file": (name, data, "image/jpeg")},
        data=form,
    )


class TestLibrary:
    """As editorial I keep every picture in one library — Story R-2."""

    async def test_an_upload_is_an_entry_with_a_preview_and_the_same_bytes_are_one(
        self, client, caplog
    ):
        """R-2: an upload is re-encoded with a small preview; the same file twice is one entry."""
        headers = await editor(client, caplog, "media-editor@example.com")
        data = picture(size=(3000, 1500))
        first = await client.post(
            "/api/admin/media",
            headers=headers,
            files={"file": ("kiel_start-race-3.jpg", data, "image/jpeg")},
        )
        assert first.status_code == 201, first.text
        item = first.json()
        assert (item["width"], item["height"]) == (2400, 1200)
        assert item["alt"] == "kiel start race 3"
        assert item["source"] == "upload"

        thumb = await client.get(item["thumb_url"])
        assert thumb.status_code == 200
        assert max(Image.open(io.BytesIO(thumb.content)).size) == 480
        assert "immutable" in thumb.headers["cache-control"]

        again = await client.post(
            "/api/admin/media", headers=headers, files={"file": ("copy.jpg", data, "image/jpeg")}
        )
        assert again.status_code == 200
        assert again.json()["id"] == item["id"] and again.json()["created"] is False

    async def test_a_picture_with_the_wrong_extension_is_taken_by_its_content(self, client, caplog):
        """R-2: the type is told by the content, never by the name or the declared type."""
        headers = await editor(client, caplog, "media-editor@example.com")
        misnamed = await client.post(
            "/api/admin/media",
            headers=headers,
            files={"file": ("Organizational_chart.png", picture("JPEG"), "image/png")},
        )
        assert misnamed.status_code == 201, misnamed.text
        nameless = await client.post(
            "/api/admin/media",
            headers=headers,
            files={"file": ("upload", picture("PNG"), "application/octet-stream")},
        )
        assert nameless.status_code == 201, nameless.text

        not_a_picture = await client.post(
            "/api/admin/media",
            headers=headers,
            files={"file": ("chart.png", b"%PDF-1.4 a document", "image/png")},
        )
        assert not_a_picture.status_code == 422
        assert not_a_picture.json()["type"].endswith("/media-invalid-type")
        assert "application/pdf" in not_a_picture.json()["detail"]

        # The first bytes of a PNG and nothing behind them: sniffed as PNG, refused by Pillow.
        truncated = await client.post(
            "/api/admin/media",
            headers=headers,
            files={"file": ("cut.png", picture("PNG")[:40], "image/png")},
        )
        assert truncated.status_code == 422
        assert truncated.json()["type"].endswith("/media-invalid")

    async def test_the_camera_date_is_kept_and_the_rest_of_exif_is_not(self, client, caplog):
        """R-2: the day the photo was taken survives the re-encoding; the location does not."""
        headers = await editor(client, caplog, "media-editor@example.com")
        exif = Image.Exif()
        exif.get_ifd(0x8769)[36867] = "2026:06:14 10:02:11"  # DateTimeOriginal
        exif.get_ifd(0x8825)[2] = (54.0, 19.0, 0.0)  # GPSLatitude
        raw = picture(exif=exif)
        assert Image.open(io.BytesIO(raw)).getexif().get_ifd(0x8825), "the upload has a location"
        uploaded = (
            await client.post(
                "/api/admin/media",
                headers=headers,
                files={"file": ("gps.jpg", raw, "image/jpeg")},
            )
        ).json()
        assert uploaded["taken_on"] == "2026-06-14"

        served = Image.open(io.BytesIO((await client.get(uploaded["url"])).content))
        assert not served.getexif().get_ifd(0x8825)
        assert 36867 not in served.getexif().get_ifd(0x8769)

    async def test_alt_text_and_credit_are_corrected_and_the_list_finds_them(self, client, caplog):
        """R-2: the Media tab corrects alt text and credit, and searches them."""
        headers = await editor(client, caplog, "media-editor@example.com")
        item = (
            await client.post(
                "/api/admin/media",
                headers=headers,
                files={"file": ("x.jpg", picture(), "image/jpeg")},
            )
        ).json()
        changed = await client.patch(
            f"/api/admin/media/{item['id']}",
            headers=headers,
            json={"alt": "Six boats at the start", "credit": "A. Photographer"},
        )
        assert changed.status_code == 200
        assert changed.json()["credit"] == "A. Photographer"

        found = (
            await client.get("/api/admin/media", headers=headers, params={"q": "six boats"})
        ).json()
        assert [entry["id"] for entry in found["items"]] == [item["id"]]

    async def test_a_picture_a_post_shows_cannot_be_deleted(self, client, caplog):
        """R-2: deleting is refused while a post shows the picture, naming the post."""
        headers = await editor(client, caplog, "media-editor@example.com")
        item = (
            await client.post(
                "/api/admin/media",
                headers=headers,
                files={"file": ("y.jpg", picture(), "image/jpeg")},
            )
        ).json()
        post = (
            await client.post(
                "/api/admin/posts",
                headers=headers,
                json={
                    "title": "With a picture",
                    "body": f'<p>Start</p><img src="{item["url"]}" alt="x">',
                },
            )
        ).json()

        detail = (await client.get(f"/api/admin/media/{item['id']}", headers=headers)).json()
        assert detail["used_in"] == [{"id": post["id"], "title": "With a picture"}]
        refused = await client.delete(f"/api/admin/media/{item['id']}", headers=headers)
        assert refused.status_code == 409
        assert refused.json()["type"].endswith("/media-in-use")
        assert refused.json()["posts"][0]["id"] == post["id"]

        await client.delete(f"/api/admin/posts/{post['id']}", headers=headers)
        assert (
            await client.delete(f"/api/admin/media/{item['id']}", headers=headers)
        ).status_code == 204
        assert (await client.get(item["url"])).status_code == 404

    async def test_only_editorial_reaches_the_library(self, client, caplog):
        """R-2: editorial alone, like posts — a club's manager neither lists nor makes keys."""
        email = "media-manager@example.com"
        await make_user(email, Role.TEAM_MANAGER)
        manager = auth_headers(await login_as(client, email, caplog))
        assert (await client.get("/api/admin/media", headers=manager)).status_code == 403
        made = await client.post("/api/admin/import-keys", headers=manager, json={"label": "Mine"})
        assert made.status_code == 403
        assert (await client.get("/api/media/..%2Fsbl.db")).status_code == 404
        assert (await client.get("/api/media/0123.jpg")).status_code == 404

    async def test_the_same_bytes_arriving_at_once_are_one_entry(self, client, caplog):
        """R-2: two deliveries of one file at the same moment — a link and editorial, or a
        retry — are one entry, the second answered as known, and no file is left over."""
        import asyncio

        from app.config import settings
        from app.services import media

        data = picture()
        directory = Path(settings.uploads_dir) / "media"
        before = set(directory.glob("*")) if directory.exists() else set()

        async def once():
            async with SessionLocal() as session:
                stored = await media.store(
                    session, data, original_name="same.jpg", arrival=media.Arrival()
                )
                return stored.item.id, stored.created

        first, second = await asyncio.gather(once(), once())
        assert first[0] == second[0]
        assert sorted([first[1], second[1]]) == [False, True]
        assert len(set(directory.glob("*")) - before) == 2  # one picture, one preview


class TestImport:
    """As a photographer I deliver pictures with a link, without an account — Story R-2."""

    async def test_a_source_delivers_with_its_key_and_its_credit(self, client, caplog):
        """R-2: a key is shown once; a source greets with it and delivers into the library."""
        headers = await editor(client, caplog, "media-editor@example.com")
        made = await make_key(client, headers, credit="Regatta photographers")
        key = made["key"]
        assert key.startswith("sbl_imp_") and made["active"] is True
        listed = (await client.get("/api/admin/import-keys", headers=headers)).json()
        assert all("key" not in row for row in listed)

        info = await client.get("/api/import/key", headers={"X-Import-Key": key})
        assert info.json()["label"] == "Photos Kiel, act 3"

        delivered = await deliver(client, key, picture())
        assert delivered.status_code == 201, delivered.text
        assert delivered.json()["credit"] == "Regatta photographers"
        assert delivered.json()["source"] == "import"
        own = await deliver(client, key, picture(), credit="B. Sample", alt="Rounding the mark")
        assert own.json()["credit"] == "B. Sample" and own.json()["alt"] == "Rounding the mark"

        row = next(
            r
            for r in (await client.get("/api/admin/import-keys", headers=headers)).json()
            if r["id"] == made["id"]
        )
        assert row["pictures"] == 2 and row["last_used_at"]

    async def test_a_source_that_retries_does_not_duplicate(self, client, caplog):
        """R-2: the source's own id sent twice with one key is one entry, even as new bytes."""
        headers = await editor(client, caplog, "media-editor@example.com")
        key = (await make_key(client, headers))["key"]
        first = await deliver(client, key, picture(), external_id="nextcloud:/Kiel/IMG_1.jpg")
        again = await deliver(client, key, picture(), external_id="nextcloud:/Kiel/IMG_1.jpg")
        assert first.status_code == 201
        assert again.status_code == 200
        assert again.json()["id"] == first.json()["id"]

    async def test_a_revoked_expired_or_missing_key_is_refused_alike(self, client, caplog):
        """R-2: a revoked or expired key is refused, and what it delivered stays."""
        headers = await editor(client, caplog, "media-editor@example.com")
        revoked = await make_key(client, headers)
        kept = (await deliver(client, revoked["key"], picture())).json()
        assert (
            await client.delete(f"/api/admin/import-keys/{revoked['id']}", headers=headers)
        ).status_code == 204

        expired = await make_key(client, headers, valid_days=1)
        async with SessionLocal() as session:
            await session.execute(
                update(ImportKey)
                .where(ImportKey.id == expired["id"])
                .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
            )
            await session.commit()

        for key in (revoked["key"], expired["key"], "sbl_imp_invented", None):
            answer = await client.post(
                "/api/import/media",
                headers={"X-Import-Key": key} if key else {},
                files={"file": ("z.jpg", picture(), "image/jpeg")},
            )
            assert answer.status_code == 401
            assert answer.json()["type"].endswith("/import-key-invalid")
        assert (await client.get(kept["url"])).status_code == 200
        rows = {
            r["id"]: r for r in (await client.get("/api/admin/import-keys", headers=headers)).json()
        }
        assert rows[revoked["id"]]["active"] is False and rows[expired["id"]]["active"] is False


class TestContext:
    """As editorial I find a regatta's pictures by its event or series — Story R-2."""

    async def test_a_link_for_an_event_puts_its_pictures_there(self, client, caplog, ids):
        """R-2: pictures sent with an event's link are that event's, and its series' too."""
        headers = await editor(client, caplog, "media-editor@example.com")
        event_id = ids.event("dsbl-1-2026-act-3")
        series_id = ids.series("dsbl-1-2026")
        key = await make_key(client, headers, event_id=event_id)
        assert key["context"]

        info = (await client.get("/api/import/key", headers={"X-Import-Key": key["key"]})).json()
        assert info["context"] == key["context"]
        delivered = (await deliver(client, key["key"], picture())).json()
        assert delivered["event_id"] == event_id and delivered["context"] == key["context"]

        for params in ({"event_id": event_id}, {"series_id": series_id}):
            found = (await client.get("/api/admin/media", headers=headers, params=params)).json()
            assert delivered["id"] in [item["id"] for item in found["items"]]
        other = (
            await client.get(
                "/api/admin/media",
                headers=headers,
                params={"series_id": ids.series("junioren-2026")},
            )
        ).json()
        assert delivered["id"] not in [item["id"] for item in other["items"]]

    async def test_the_context_is_changed_one_at_a_time(self, client, caplog, ids):
        """R-2: an event or a series, never both; it can be changed and taken off."""
        headers = await editor(client, caplog, "media-editor@example.com")
        item = (
            await client.post(
                "/api/admin/media",
                headers=headers,
                files={"file": ("c.jpg", picture(), "image/jpeg")},
            )
        ).json()
        url = f"/api/admin/media/{item['id']}"
        to_series = await client.patch(
            url, headers=headers, json={"series_id": ids.series("dsbl-1-2026")}
        )
        assert to_series.json()["series_id"] and to_series.json()["event_id"] is None
        to_event = await client.patch(
            url, headers=headers, json={"event_id": ids.event("dsbl-1-2026-act-3")}
        )
        assert to_event.json()["event_id"] and to_event.json()["series_id"] is None
        both = await client.patch(
            url,
            headers=headers,
            json={
                "event_id": ids.event("dsbl-1-2026-act-3"),
                "series_id": ids.series("dsbl-1-2026"),
            },
        )
        assert both.status_code == 422 and both.json()["type"].endswith("/media-context-both")
        off = await client.patch(url, headers=headers, json={"event_id": None})
        assert off.json()["event_id"] is None and off.json()["context"] is None


class TestFromAddress:
    """As editorial I take a picture from a web address into the library — Story R-2."""

    async def test_a_picture_is_fetched_and_copied(self, client, caplog, monkeypatch):
        """R-2: fetched, copied into the library, following a redirect; never a live server."""
        import httpx

        from app.services import media

        data = picture()

        def answer(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/old.jpg":
                return httpx.Response(301, headers={"location": "/photos/start.jpg"})
            if request.url.path == "/photos/start.jpg":
                return httpx.Response(200, content=data)
            return httpx.Response(404)

        async def public(host: str) -> bool:
            return host == "press.example.com"

        monkeypatch.setattr(media, "_transport", httpx.MockTransport(answer))
        monkeypatch.setattr(media, "_public", public)
        headers = await editor(client, caplog, "media-editor@example.com")

        fetched = await client.post(
            "/api/admin/media/from-url",
            headers=headers,
            json={"url": "https://press.example.com/old.jpg"},
        )
        assert fetched.status_code == 201, fetched.text
        assert fetched.json()["original_name"] == "start.jpg"

        missing = await client.post(
            "/api/admin/media/from-url",
            headers=headers,
            json={"url": "https://press.example.com/gone.jpg"},
        )
        assert missing.status_code == 422 and missing.json()["type"].endswith(
            "/media-url-unreachable"
        )

    async def test_an_address_inside_the_network_is_refused(self, client, caplog):
        """R-2: only public addresses — the server never fetches from itself or its network."""
        headers = await editor(client, caplog, "media-editor@example.com")
        for url in (
            "http://localhost:8000/api/health",
            "http://10.0.0.7/x.jpg",
            "http://169.254.169.254/latest",
            "file:///etc/passwd",
        ):
            refused = await client.post(
                "/api/admin/media/from-url", headers=headers, json={"url": url}
            )
            assert refused.status_code == 422, url
            assert refused.json()["type"].endswith("/media-url-invalid"), url


class TestUploadWithoutLink:
    """As editorial I upload a batch myself, without a link — Story R-2."""

    async def test_editorial_uploads_with_credit_and_event(self, client, caplog, ids):
        """R-2: editorial's own upload takes a credit and an event for the batch."""
        headers = await editor(client, caplog, "media-editor@example.com")
        event_id = ids.event("dsbl-1-2026-act-3")
        uploaded = await client.post(
            "/api/admin/media",
            headers=headers,
            data={"credit": "D. Editor", "event_id": str(event_id)},
            files={"file": ("batch.jpg", picture(), "image/jpeg")},
        )
        assert uploaded.status_code == 201, uploaded.text
        assert uploaded.json()["credit"] == "D. Editor"
        assert uploaded.json()["event_id"] == event_id and uploaded.json()["source"] == "upload"

        both = await client.post(
            "/api/admin/media",
            headers=headers,
            data={"event_id": str(event_id), "series_id": str(ids.series("dsbl-1-2026"))},
            files={"file": ("both.jpg", picture(), "image/jpeg")},
        )
        assert both.status_code == 422 and both.json()["type"].endswith("/media-context-both")
