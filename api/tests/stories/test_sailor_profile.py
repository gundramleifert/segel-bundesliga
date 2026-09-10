"""User story S-2: a sailor manages their own profile — name, birthdate, and photo.

The linking rule is the same one waivers already rely on (`app/routers/waivers.py`,
`Sailor.email`): a sailor's own account is whichever `User` shares their **verified**
email address. `GET/PATCH /api/sailors/me` resolve through that link, never through an
id supplied by the caller — so there is no way to point them at someone else's record.

Photo visibility resolves S-2's own open question: an adult's (or unknown-birthdate's)
photo is public, a minor's is shown only to a signed-in account connected to them (the
sailor themselves, admin/editor, or a manager of a club they're registered with) — see
`app/routers/sailors.py::_may_view_minor_photo`.
"""

import io
from datetime import date, timedelta

from PIL import Image

from app.db import SessionLocal
from app.models import Sailor
from app.models.auth import Role
from tests.stories.test_login_and_roles import login_as, make_user
from tests.stories.test_registration import auth_headers


async def _admin(client, caplog):
    await make_user("profil-admin@example.com", Role.ADMIN)
    return auth_headers(await login_as(client, "profil-admin@example.com", caplog))


async def _new_sailor(
    client, admin, *, email: str, birth_date: str | None, first="Pro", last="Fil"
) -> int:
    body: dict[str, object] = {"first_name": first, "last_name": last, "email": email}
    if birth_date is not None:
        body["birth_date"] = birth_date
    response = await client.post("/api/admin/sailors", headers=admin, json=body)
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _account_for(client, caplog, email: str):
    """A verified account for this address — the same flow a real sign-in goes through,
    so `User.email_verified` ends up true exactly as it would for a real sailor."""
    await make_user(email)
    return auth_headers(await login_as(client, email, caplog))


def _jpeg_bytes(size: tuple[int, int] = (300, 500), color=(200, 50, 10)) -> bytes:
    """A tiny real JPEG — not square, so cropping is actually exercised."""
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG")
    return buf.getvalue()


_ADULT_BIRTH = "1990-05-01"


def _minor_birth() -> str:
    return (date.today() - timedelta(days=365 * 10)).isoformat()


class TestOwnProfile:
    """As a sailor, I want to view and edit my own name and birthdate."""

    async def test_a_sailor_can_view_and_edit_their_own_profile(self, client, caplog):
        admin = await _admin(client, caplog)
        sailor_id = await _new_sailor(
            client, admin, email="profil.anna@example.com", birth_date=_ADULT_BIRTH
        )
        anna = await _account_for(client, caplog, "profil.anna@example.com")

        seen = await client.get("/api/sailors/me", headers=anna)
        assert seen.status_code == 200, seen.text
        body = seen.json()
        assert body == {
            "id": sailor_id,
            "first_name": "Pro",
            "last_name": "Fil",
            "birth_date": _ADULT_BIRTH,
            "has_photo": False,
        }

        edited = await client.patch(
            "/api/sailors/me",
            headers=anna,
            json={"first_name": "Anna", "last_name": "Neu", "birth_date": "1991-06-02"},
        )
        assert edited.status_code == 200, edited.text
        assert edited.json()["first_name"] == "Anna"
        assert edited.json()["last_name"] == "Neu"
        assert edited.json()["birth_date"] == "1991-06-02"

    async def test_editing_my_profile_cannot_change_my_email(self, client, caplog):
        """Email is identity, not something this endpoint touches — even if a caller
        includes it in the request body, it is silently ignored, not applied."""
        admin = await _admin(client, caplog)
        sailor_id = await _new_sailor(
            client, admin, email="profil.email@example.com", birth_date=_ADULT_BIRTH
        )
        account = await _account_for(client, caplog, "profil.email@example.com")

        response = await client.patch(
            "/api/sailors/me",
            headers=account,
            json={"first_name": "Changed", "email": "someone.else@example.com"},
        )
        assert response.status_code == 200, response.text

        async with SessionLocal() as session:
            sailor = await session.get(Sailor, sailor_id)
            assert sailor.email == "profil.email@example.com"
            assert sailor.first_name == "Changed"

    async def test_an_account_with_no_linked_sailor_gets_a_clear_response_not_a_crash(
        self, client, caplog
    ):
        await make_user("profil-verwaist@example.com", Role.ADMIN)
        orphan = auth_headers(await login_as(client, "profil-verwaist@example.com", caplog))

        response = await client.get("/api/sailors/me", headers=orphan)
        assert response.status_code == 404
        assert response.json()["type"] == "/errors/no-linked-sailor-record"

        edit_attempt = await client.patch(
            "/api/sailors/me", headers=orphan, json={"first_name": "X"}
        )
        assert edit_attempt.status_code == 404
        assert edit_attempt.json()["type"] == "/errors/no-linked-sailor-record"

    async def test_a_sailor_cannot_reach_another_sailors_record_through_this_endpoint(
        self, client, caplog
    ):
        """There is no id parameter on `/api/sailors/me` — it can only ever resolve to the
        caller's own row. Editing my profile must leave a namesake untouched."""
        admin = await _admin(client, caplog)
        anna_id = await _new_sailor(
            client, admin, email="profil.anna2@example.com", birth_date=_ADULT_BIRTH,
            first="Anna", last="Eins",
        )
        bea_id = await _new_sailor(
            client, admin, email="profil.bea@example.com", birth_date=_ADULT_BIRTH,
            first="Bea", last="Zwei",
        )
        anna = await _account_for(client, caplog, "profil.anna2@example.com")

        response = await client.patch(
            "/api/sailors/me", headers=anna, json={"first_name": "Angepasst"}
        )
        assert response.status_code == 200, response.text
        assert response.json()["id"] == anna_id

        async with SessionLocal() as session:
            bea = await session.get(Sailor, bea_id)
            assert bea.first_name == "Bea"
            assert bea.last_name == "Zwei"


class TestOwnPhoto:
    """As a sailor, I want to upload, replace, and remove my own photo."""

    async def test_upload_replace_and_delete_round_trip(self, client, caplog):
        admin = await _admin(client, caplog)
        await _new_sailor(
            client, admin, email="profil.foto@example.com", birth_date=_ADULT_BIRTH
        )
        account = await _account_for(client, caplog, "profil.foto@example.com")

        no_photo = await client.get("/api/sailors/me", headers=account)
        assert no_photo.json()["has_photo"] is False

        uploaded = await client.post(
            "/api/sailors/me/photo",
            headers=account,
            files={"file": ("me.jpg", _jpeg_bytes(), "image/jpeg")},
        )
        assert uploaded.status_code == 200, uploaded.text
        assert uploaded.json()["has_photo"] is True
        sailor_id = uploaded.json()["id"]

        fetched = await client.get(f"/api/sailors/{sailor_id}/photo")
        assert fetched.status_code == 200
        assert fetched.headers["content-type"] == "image/jpeg"
        # Cropped to a square and downsized, regardless of the uploaded aspect ratio.
        stored = Image.open(io.BytesIO(fetched.content))
        assert stored.size == (512, 512)

        replaced = await client.post(
            "/api/sailors/me/photo",
            headers=account,
            files={"file": ("me2.jpg", _jpeg_bytes(color=(10, 200, 30)), "image/jpeg")},
        )
        assert replaced.status_code == 200
        assert replaced.json()["has_photo"] is True

        deleted = await client.delete("/api/sailors/me/photo", headers=account)
        assert deleted.status_code == 204

        # Deleting again is a no-op, not an error — there's simply nothing left to remove.
        deleted_again = await client.delete("/api/sailors/me/photo", headers=account)
        assert deleted_again.status_code == 204

        gone = await client.get(f"/api/sailors/{sailor_id}/photo")
        assert gone.status_code == 404
        assert gone.json()["type"] == "/errors/sailor-photo-not-found"

    async def test_a_non_image_upload_is_rejected_with_a_clear_error(self, client, caplog):
        admin = await _admin(client, caplog)
        await _new_sailor(
            client, admin, email="profil.textdatei@example.com", birth_date=_ADULT_BIRTH
        )
        account = await _account_for(client, caplog, "profil.textdatei@example.com")

        response = await client.post(
            "/api/sailors/me/photo",
            headers=account,
            files={"file": ("evil.txt", b"not an image", "text/plain")},
        )
        assert response.status_code == 422
        assert response.json()["type"] == "/errors/sailor-photo-invalid-type"

    async def test_an_absurdly_large_upload_is_rejected_before_processing(self, client, caplog):
        admin = await _admin(client, caplog)
        await _new_sailor(
            client, admin, email="profil.riesig@example.com", birth_date=_ADULT_BIRTH
        )
        account = await _account_for(client, caplog, "profil.riesig@example.com")

        oversized = b"\xff" * (5 * 1024 * 1024 + 1)
        response = await client.post(
            "/api/sailors/me/photo",
            headers=account,
            files={"file": ("huge.jpg", oversized, "image/jpeg")},
        )
        assert response.status_code == 413
        assert response.json()["type"] == "/errors/sailor-photo-too-large"


class TestMinorPhotoVisibility:
    """S-2's own open question, resolved: an adult's photo is public, a minor's is not."""

    async def test_an_adults_photo_is_public(self, client, caplog):
        admin = await _admin(client, caplog)
        await _new_sailor(
            client, admin, email="profil.erwachsen@example.com", birth_date=_ADULT_BIRTH
        )
        account = await _account_for(client, caplog, "profil.erwachsen@example.com")
        uploaded = await client.post(
            "/api/sailors/me/photo",
            headers=account,
            files={"file": ("me.jpg", _jpeg_bytes(), "image/jpeg")},
        )
        sailor_id = uploaded.json()["id"]

        # No Authorization header at all — a plain guest.
        response = await client.get(f"/api/sailors/{sailor_id}/photo")
        assert response.status_code == 200

    async def test_a_minors_photo_is_hidden_from_guests_and_unrelated_accounts(
        self, client, caplog
    ):
        admin = await _admin(client, caplog)
        await _new_sailor(
            client, admin, email="profil.minderjaehrig@example.com", birth_date=_minor_birth()
        )
        minor_account = await _account_for(client, caplog, "profil.minderjaehrig@example.com")
        uploaded = await client.post(
            "/api/sailors/me/photo",
            headers=minor_account,
            files={"file": ("me.jpg", _jpeg_bytes(), "image/jpeg")},
        )
        assert uploaded.status_code == 200, uploaded.text
        sailor_id = uploaded.json()["id"]

        guest = await client.get(f"/api/sailors/{sailor_id}/photo")
        assert guest.status_code == 403
        assert guest.json()["type"] == "/errors/sailor-photo-protected"

        await make_user("profil-unbeteiligt@example.com")
        unrelated = auth_headers(await login_as(client, "profil-unbeteiligt@example.com", caplog))
        stranger = await client.get(f"/api/sailors/{sailor_id}/photo", headers=unrelated)
        assert stranger.status_code == 403

        own = await client.get(f"/api/sailors/{sailor_id}/photo", headers=minor_account)
        assert own.status_code == 200

        admin_view = await client.get(f"/api/sailors/{sailor_id}/photo", headers=admin)
        assert admin_view.status_code == 200

    async def test_a_photo_without_a_birth_date_on_file_is_restricted_not_published(
        self, client, caplog
    ):
        """The gate must not fail open. `birth_date` is optional and self-reported, so if an
        unknown age counted as an adult, a minor could publish their photo to the world just
        by leaving the field blank — the restriction is lifted by supplying the date."""
        admin = await _admin(client, caplog)
        await _new_sailor(client, admin, email="profil.ohnedatum@example.com", birth_date=None)
        account = await _account_for(client, caplog, "profil.ohnedatum@example.com")
        uploaded = await client.post(
            "/api/sailors/me/photo",
            headers=account,
            files={"file": ("me.jpg", _jpeg_bytes(), "image/jpeg")},
        )
        assert uploaded.status_code == 200, uploaded.text
        sailor_id = uploaded.json()["id"]
        assert uploaded.json()["birth_date"] is None

        guest = await client.get(f"/api/sailors/{sailor_id}/photo")
        assert guest.status_code == 403
        assert guest.json()["type"] == "/errors/sailor-photo-protected"

        # The sailor themselves still sees it, as do administration and editorial staff.
        own = await client.get(f"/api/sailors/{sailor_id}/photo", headers=account)
        assert own.status_code == 200
        admin_view = await client.get(f"/api/sailors/{sailor_id}/photo", headers=admin)
        assert admin_view.status_code == 200

        # Supplying the birth date is what makes an adult's photo public.
        patched = await client.patch(
            "/api/sailors/me", headers=account, json={"birth_date": _ADULT_BIRTH}
        )
        assert patched.status_code == 200, patched.text
        assert (await client.get(f"/api/sailors/{sailor_id}/photo")).status_code == 200
