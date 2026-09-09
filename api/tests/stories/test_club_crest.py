"""User story V-3: a club's crest ("Stander") as an uploaded file.

Storage mirrors the sailor photo (Story S-2): a deterministic path under
`SBL_UPLOADS_DIR`, so the file's existence *is* the state — no column to keep in sync.

Two things are specific to a crest and therefore asserted here explicitly:

* **Transparency survives.** A crest is a logo drawn over colored surfaces, so unlike a
  sailor photo it is never flattened onto a background (see
  `app/crests.py::save_crest`).
* **An upload wins over `Club.logo_url`, without overwriting it.** The column keeps
  meaning "externally hosted emblem"; resolution happens on read
  (`ClubOut._prefer_uploaded_crest`), so removing an upload falls back to the pasted URL
  and every existing consumer — club list, club page, event-logo fallback — needs no
  change.
"""

import io

from PIL import Image

from app.models.auth import Role
from tests.stories.test_login_and_roles import login_as, make_user
from tests.stories.test_registrierung import auth_headers


async def _headers(client, caplog, email: str, *roles: str, club_id: int | None = None):
    await make_user(email, *roles, club_id=club_id)
    return auth_headers(await login_as(client, email, caplog))


async def _new_club(client, admin, *, short_name: str, logo_url: str | None = None) -> dict:
    body: dict[str, object] = {
        "name": f"Segelclub {short_name}",
        "short_name": short_name,
        "city": "Musterhafen",
    }
    if logo_url is not None:
        body["logo_url"] = logo_url
    response = await client.post("/api/admin/clubs", headers=admin, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _png(size: tuple[int, int] = (400, 240), *, transparent_half: bool = True) -> bytes:
    """A real PNG whose left half is fully transparent — so flattening it onto any
    background would be visible immediately."""
    image = Image.new("RGBA", size, (12, 84, 160, 255))
    if transparent_half:
        image.paste((0, 0, 0, 0), (0, 0, size[0] // 2, size[1]))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _jpeg(size: tuple[int, int] = (300, 200)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (200, 50, 10)).save(buf, format="JPEG")
    return buf.getvalue()


class TestUploadCrest:
    """As a club manager, I want to upload our crest so that we are recognizable."""

    async def test_an_admin_can_upload_a_crest_and_it_is_served(self, client, caplog):
        admin = await _headers(client, caplog, "crest-admin@example.com", Role.ADMIN)
        club = await _new_club(client, admin, short_name="WPN")

        uploaded = await client.post(
            f"/api/admin/clubs/{club['id']}/logo",
            headers=admin,
            files={"file": ("stander.png", _png(), "image/png")},
        )
        assert uploaded.status_code == 200, uploaded.text
        # The response already carries the URL of the crest just uploaded — the caller
        # never has to construct it.
        logo_url = uploaded.json()["logo_url"]
        assert logo_url.startswith(f"/api/clubs/{club['id']}/logo?v=")

        served = await client.get(logo_url)
        assert served.status_code == 200
        assert served.headers["content-type"] == "image/png"

        # And the public club page shows it, with no frontend change involved.
        page = await client.get(f"/api/clubs/{club['id']}")
        assert page.json()["logo_url"] == logo_url

    async def test_the_clubs_own_manager_can_upload_it(self, client, caplog):
        """The same restriction as club assignment (Z-3): own club only."""
        admin = await _headers(client, caplog, "crest-admin2@example.com", Role.ADMIN)
        club = await _new_club(client, admin, short_name="WPE")
        manager = await _headers(
            client,
            caplog,
            "crest-manager@example.com",
            Role.CLUB_MANAGER,
            club_id=club["id"],
        )

        uploaded = await client.post(
            f"/api/admin/clubs/{club['id']}/logo",
            headers=manager,
            files={"file": ("stander.png", _png(), "image/png")},
        )
        assert uploaded.status_code == 200, uploaded.text

    async def test_a_manager_of_another_club_is_rejected(self, client, caplog):
        admin = await _headers(client, caplog, "crest-admin3@example.com", Role.ADMIN)
        mine = await _new_club(client, admin, short_name="WPM")
        other = await _new_club(client, admin, short_name="WPO")
        manager = await _headers(
            client,
            caplog,
            "crest-fremd@example.com",
            Role.CLUB_MANAGER,
            club_id=mine["id"],
        )

        response = await client.post(
            f"/api/admin/clubs/{other['id']}/logo",
            headers=manager,
            files={"file": ("stander.png", _png(), "image/png")},
        )
        assert response.status_code == 403
        assert response.json()["type"] == "/errors/club-crest-not-yours"

        # Nothing was written for the club they tried to reach.
        assert (await client.get(f"/api/clubs/{other['id']}/logo")).status_code == 404

    async def test_a_replacement_upload_simply_wins(self, client, caplog):
        admin = await _headers(client, caplog, "crest-admin4@example.com", Role.ADMIN)
        club = await _new_club(client, admin, short_name="WPR")

        first = await client.post(
            f"/api/admin/clubs/{club['id']}/logo",
            headers=admin,
            files={"file": ("alt.png", _png(size=(400, 240)), "image/png")},
        )
        assert first.status_code == 200, first.text

        second = await client.post(
            f"/api/admin/clubs/{club['id']}/logo",
            headers=admin,
            files={"file": ("neu.png", _png(size=(200, 200)), "image/png")},
        )
        assert second.status_code == 200, second.text

        served = await client.get(second.json()["logo_url"])
        assert Image.open(io.BytesIO(served.content)).size == (200, 200)

    async def test_a_non_image_upload_is_rejected_with_a_clear_error(self, client, caplog):
        admin = await _headers(client, caplog, "crest-admin5@example.com", Role.ADMIN)
        club = await _new_club(client, admin, short_name="WPT")

        response = await client.post(
            f"/api/admin/clubs/{club['id']}/logo",
            headers=admin,
            files={"file": ("evil.txt", b"not an image", "text/plain")},
        )
        assert response.status_code == 422
        assert response.json()["type"] == "/errors/club-crest-invalid-type"

    async def test_an_oversized_upload_is_rejected_before_processing(self, client, caplog):
        admin = await _headers(client, caplog, "crest-admin6@example.com", Role.ADMIN)
        club = await _new_club(client, admin, short_name="WPG")

        oversized = b"\xff" * (2 * 1024 * 1024 + 1)
        response = await client.post(
            f"/api/admin/clubs/{club['id']}/logo",
            headers=admin,
            files={"file": ("huge.png", oversized, "image/png")},
        )
        assert response.status_code == 413
        assert response.json()["type"] == "/errors/club-crest-too-large"


class TestCrestTransparency:
    """The deliberate difference from the sailor photo: a crest keeps its alpha channel."""

    async def test_a_transparent_png_stays_transparent(self, client, caplog):
        admin = await _headers(client, caplog, "crest-alpha@example.com", Role.ADMIN)
        club = await _new_club(client, admin, short_name="WPA")

        uploaded = await client.post(
            f"/api/admin/clubs/{club['id']}/logo",
            headers=admin,
            files={"file": ("stander.png", _png(size=(400, 240)), "image/png")},
        )
        assert uploaded.status_code == 200, uploaded.text

        served = await client.get(uploaded.json()["logo_url"])
        stored = Image.open(io.BytesIO(served.content))
        assert stored.mode == "RGBA"
        # The transparent half is still transparent — not flattened onto white, which
        # would show as a box wherever the crest sits on the brand-blue surfaces.
        assert stored.getpixel((10, 10))[3] == 0
        assert stored.getpixel((stored.width - 10, 10))[3] == 255

    async def test_an_oversized_crest_is_downscaled_without_being_cropped(
        self, client, caplog
    ):
        """No square crop, unlike a sailor photo: a pennant is not square, and the aspect
        ratio has to survive. Only the longest edge is bounded."""
        admin = await _headers(client, caplog, "crest-gross@example.com", Role.ADMIN)
        club = await _new_club(client, admin, short_name="WPB")

        uploaded = await client.post(
            f"/api/admin/clubs/{club['id']}/logo",
            headers=admin,
            files={"file": ("breit.png", _png(size=(1200, 600)), "image/png")},
        )
        assert uploaded.status_code == 200, uploaded.text

        served = await client.get(uploaded.json()["logo_url"])
        assert Image.open(io.BytesIO(served.content)).size == (512, 256)

    async def test_an_opaque_jpeg_is_accepted_too(self, client, caplog):
        """Other formats are accepted as input; the store is PNG either way."""
        admin = await _headers(client, caplog, "crest-jpeg@example.com", Role.ADMIN)
        club = await _new_club(client, admin, short_name="WPJ")

        uploaded = await client.post(
            f"/api/admin/clubs/{club['id']}/logo",
            headers=admin,
            files={"file": ("stander.jpg", _jpeg(), "image/jpeg")},
        )
        assert uploaded.status_code == 200, uploaded.text

        served = await client.get(uploaded.json()["logo_url"])
        assert served.headers["content-type"] == "image/png"
        stored = Image.open(io.BytesIO(served.content))
        assert stored.format == "PNG"
        assert stored.size == (300, 200)


class TestRemoveCrest:
    """Replacing and removing are possible — and removing restores what was there before."""

    async def test_removing_the_crest_falls_back_to_the_pasted_url(self, client, caplog):
        admin = await _headers(client, caplog, "crest-loeschen@example.com", Role.ADMIN)
        club = await _new_club(client, admin, short_name="WPL", logo_url="/brand/wpl.png")
        assert club["logo_url"] == "/brand/wpl.png"

        uploaded = await client.post(
            f"/api/admin/clubs/{club['id']}/logo",
            headers=admin,
            files={"file": ("stander.png", _png(), "image/png")},
        )
        assert uploaded.json()["logo_url"].startswith(f"/api/clubs/{club['id']}/logo")

        deleted = await client.delete(f"/api/admin/clubs/{club['id']}/logo", headers=admin)
        assert deleted.status_code == 204

        # Removing again is a no-op, not an error.
        assert (
            await client.delete(f"/api/admin/clubs/{club['id']}/logo", headers=admin)
        ).status_code == 204

        gone = await client.get(f"/api/clubs/{club['id']}/logo")
        assert gone.status_code == 404
        assert gone.json()["type"] == "/errors/club-crest-not-found"

        # The externally hosted emblem was never overwritten by the upload.
        page = await client.get(f"/api/clubs/{club['id']}")
        assert page.json()["logo_url"] == "/brand/wpl.png"

    async def test_a_club_without_a_crest_has_nothing_to_serve(self, client, caplog):
        admin = await _headers(client, caplog, "crest-leer@example.com", Role.ADMIN)
        club = await _new_club(client, admin, short_name="WPX")

        response = await client.get(f"/api/clubs/{club['id']}/logo")
        assert response.status_code == 404
        assert response.json()["type"] == "/errors/club-crest-not-found"


class TestCrestAsEventLogo:
    """Appears in the matchday view too: an event without its own logo uses the host's
    crest (`public.py::_event_out`), and the upload feeds that chain unchanged."""

    async def test_an_event_without_its_own_logo_uses_the_uploaded_crest(
        self, client, caplog
    ):
        admin = await _headers(client, caplog, "crest-ausrichter@example.com", Role.ADMIN)
        club = await _new_club(client, admin, short_name="WPV")
        uploaded = await client.post(
            f"/api/admin/clubs/{club['id']}/logo",
            headers=admin,
            files={"file": ("stander.png", _png(), "image/png")},
        )
        logo_url = uploaded.json()["logo_url"]

        event = await client.post(
            "/api/admin/events",
            headers=admin,
            json={
                "title": "Matchday with the club crest",
                "starts_on": "2026-11-14",
                "host_club_id": club["id"],
            },
        )
        assert event.status_code == 201, event.text
        assert event.json()["logo_url"] == logo_url
