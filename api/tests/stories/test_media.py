"""Story R-2: the picture library, and the import API that feeds it.

Every picture arrives through one service, from editorial or from a source holding an
import key: re-encoded, the same bytes twice one entry, a source's own id twice one entry,
and a picture a post shows cannot be deleted.
"""

import io
import secrets
from datetime import UTC, datetime, timedelta

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
