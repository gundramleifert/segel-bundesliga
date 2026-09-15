"""User story S-2: confirm a specific version of the liability waiver.

A sailor confirms **one version** of the waiver, either for a whole series (which covers
every event of it) or for a single event. The text is versioned and frozen: a later
change to the wording is a new version that everyone re-confirms, and it never rewrites
an old confirmation.

Minors cannot clear the waiver by their own click — a legal guardian signs on paper and
the reference to that scan is recorded.
"""

import pytest
from sqlalchemy import delete, select

from app.db import SessionLocal
from app.models import Sailor, Series, Team, TeamMembership, WaiverConfirmation, WaiverText
from app.models.auth import Role
from tests.stories.test_login_and_roles import login_as, make_user
from tests.stories.test_registration import auth_headers

V2 = {
    "title_en": "Liability waiver v2",
    "body_en": "Updated: added an engine-failure clause.",
    "title_de": "Haftungsausschluss v2",
    "body_de": "Aktualisiert: Klausel zu Motorschaden ergänzt.",
    "notes": "engine-failure clause",
}


async def _admin(client, caplog):
    await make_user("wv-admin@example.com", Role.ADMIN)
    return auth_headers(await login_as(client, "wv-admin@example.com", caplog))


async def _account_for(client, caplog, email: str):
    await make_user(email)
    return auth_headers(await login_as(client, email, caplog))


async def _new_sailor(client, admin, *, email: str, birth_date: str | None) -> int:
    body: dict[str, object] = {
        "first_name": "Wai",
        "last_name": "Ver",
        "email": email,
    }
    if birth_date is not None:
        body["birth_date"] = birth_date
    response = await client.post("/api/admin/sailors", headers=admin, json=body)
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _squad_sailor(series_slug: str, offset: int) -> tuple[int, str]:
    """A distinct seeded sailor from a series' squad: (id, email).

    Each test picks its own offset — the seeded database is shared across the module, so
    two tests confirming for the same person would collide.
    """
    async with SessionLocal() as session:
        return (
            await session.execute(
                select(Sailor.id, Sailor.email)
                .join(TeamMembership, TeamMembership.sailor_id == Sailor.id)
                .join(Team, TeamMembership.team_id == Team.id)
                .join(Series, Team.series_id == Series.id)
                .where(Series.slug == series_slug, Team.event_id.is_(None))
                .order_by(Sailor.id)
                .offset(offset)
                .limit(1)
            )
        ).one()


_matchday_counter = [50]


async def _junior_event(client, admin, series_id: int) -> int:
    # A high, unique matchday number: other tests query "the event with matchday 1"
    # without filtering by series, and would trip over a junior act numbered 1.
    _matchday_counter[0] += 1
    response = await client.post(
        "/api/admin/events",
        headers=admin,
        json={
            "title": "Juniors Kiel",
            "starts_on": "2026-08-15",
            "series": series_id,
            "matchday": _matchday_counter[0],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _row(response, sailor_id: int) -> dict:
    return next(r for r in response.json()["sailors"] if r["sailor_id"] == sailor_id)


@pytest.fixture
async def version_two(client, caplog):
    """Publish version 2 for the duration of one test, then take it back out.

    The seeded database is shared across the whole run, so a permanently-published v2
    would move every other test's "current version" from under it.
    """
    admin = await _admin(client, caplog)
    created = await client.post("/api/admin/waiver/texts", headers=admin, json=V2)
    assert created.status_code == 201, created.text
    yield created.json()["version"]
    async with SessionLocal() as session:
        stale = select(WaiverText.id).where(WaiverText.version > 1)
        await session.execute(
            delete(WaiverConfirmation).where(WaiverConfirmation.waiver_text_id.in_(stale))
        )
        await session.execute(delete(WaiverText).where(WaiverText.version > 1))
        await session.commit()


class TestVersioning:
    async def test_the_current_version_is_served(self, client):
        body = (await client.get("/api/waiver")).json()
        assert body["version"] == 1
        assert "own risk" in body["body_en"]
        assert body["title_de"].startswith("Haftungs")

    async def test_publishing_a_new_version_puts_it_in_force(self, client, version_two):
        assert version_two == 2
        assert (await client.get("/api/waiver")).json()["version"] == 2

    async def test_a_new_version_supersedes_an_old_confirmation_without_rewriting_it(
        self, client, caplog, ids, version_two
    ):
        admin = await _admin(client, caplog)
        sailor_id, _ = await _squad_sailor("dsbl-1-2026", offset=0)

        # The confirmation was for version 1; version 2 is now in force.
        async with SessionLocal() as session:
            v1 = (
                await session.execute(select(WaiverText).where(WaiverText.version == 1))
            ).scalar_one()
            session.add(
                WaiverConfirmation(
                    sailor_id=sailor_id,
                    waiver_text_id=v1.id,
                    series_id=ids.series("dsbl-1-2026"),
                )
            )
            await session.commit()

        checklist = await client.get(
            f"/api/admin/events/{ids.event('dsbl-1-2026-act-1')}/waivers", headers=admin
        )
        row = _row(checklist, sailor_id)
        assert row["required_version"] == 2
        assert row["confirmed_version"] == 1
        assert row["status"] == "version_outdated"


class TestConfirming:
    async def test_a_series_confirmation_clears_every_event_of_it(
        self, client, caplog, ids
    ):
        admin = await _admin(client, caplog)
        sailor_id, email = await _squad_sailor("dsbl-1-2026", offset=10)
        sailor = await _account_for(client, caplog, email)

        confirmed = await client.post(
            f"/api/series/{ids.series('dsbl-1-2026')}/waiver",
            headers=sailor,
            json={"sailor_id": sailor_id, "locale_shown": "en"},
        )
        assert confirmed.status_code == 201, confirmed.text
        body = confirmed.json()
        assert (body["cleared"], body["version"], body["method"], body["scope"]) == (
            True,
            1,
            "online",
            "series",
        )

        for act in ("dsbl-1-2026-act-1", "dsbl-1-2026-act-2", "dsbl-1-2026-act-3"):
            checklist = await client.get(
                f"/api/admin/events/{ids.event(act)}/waivers", headers=admin
            )
            assert _row(checklist, sailor_id)["status"] == "cleared"

    async def test_an_event_confirmation_leaves_the_other_events_open(
        self, client, caplog, ids
    ):
        admin = await _admin(client, caplog)
        sailor_id, email = await _squad_sailor("dsbl-1-2026", offset=20)
        sailor = await _account_for(client, caplog, email)

        confirmed = await client.post(
            f"/api/events/{ids.event('dsbl-1-2026-act-1')}/waiver",
            headers=sailor,
            json={"sailor_id": sailor_id},
        )
        assert confirmed.status_code == 201, confirmed.text

        first = await client.get(
            f"/api/admin/events/{ids.event('dsbl-1-2026-act-1')}/waivers", headers=admin
        )
        second = await client.get(
            f"/api/admin/events/{ids.event('dsbl-1-2026-act-2')}/waivers", headers=admin
        )
        assert _row(first, sailor_id)["status"] == "cleared"
        assert _row(second, sailor_id)["status"] == "missing"

    async def test_confirming_the_same_version_twice_is_rejected(
        self, client, caplog, ids
    ):
        sailor_id, email = await _squad_sailor("dsbl-1-2026", offset=30)
        sailor = await _account_for(client, caplog, email)
        url = f"/api/series/{ids.series('dsbl-1-2026')}/waiver"

        assert (
            await client.post(url, headers=sailor, json={"sailor_id": sailor_id})
        ).status_code == 201
        again = await client.post(url, headers=sailor, json={"sailor_id": sailor_id})
        assert again.status_code == 409
        problem = again.json()
        assert problem["type"] == "/errors/waiver-already-confirmed"
        assert problem["status"] == 409
        assert problem["required_version"] == 1
        assert again.headers["content-type"].startswith("application/problem+json")

    async def test_you_can_only_confirm_for_yourself(self, client, caplog, ids):
        sailor_id, _ = await _squad_sailor("dsbl-1-2026", offset=40)
        stranger = await _account_for(client, caplog, "wv-stranger@example.com")
        url = f"/api/series/{ids.series('dsbl-1-2026')}/waiver"

        denied = await client.post(url, headers=stranger, json={"sailor_id": sailor_id})
        assert denied.status_code == 403
        assert denied.json()["type"] == "/errors/waiver-confirmation-forbidden"

        admin = await _admin(client, caplog)
        allowed = await client.post(url, headers=admin, json={"sailor_id": sailor_id})
        assert allowed.status_code == 201


class TestMinors:
    async def test_a_minor_cannot_clear_it_online(self, client, caplog, ids):
        sailor_id, email = await _squad_sailor("junioren-2026", offset=0)
        teen = await _account_for(client, caplog, email)

        response = await client.post(
            f"/api/series/{ids.series('junioren-2026')}/waiver",
            headers=teen,
            json={"sailor_id": sailor_id, "method": "online"},
        )
        assert response.status_code == 422
        assert response.json()["type"] == "/errors/guardian-confirmation-needed"

    async def test_a_sailor_without_a_birth_date_cannot_be_confirmed(
        self, client, caplog, ids
    ):
        admin = await _admin(client, caplog)
        sailor_id = await _new_sailor(
            client, admin, email="wv-nodob@example.com", birth_date=None
        )
        response = await client.post(
            f"/api/series/{ids.series('junioren-2026')}/waiver",
            headers=admin,
            json={"sailor_id": sailor_id},
        )
        assert response.status_code == 422
        problem = response.json()
        assert problem["type"] == "/errors/waiver-birth-date-required"
        assert problem["sailor_id"] == sailor_id

    async def test_a_guardian_signature_clears_a_minor(self, client, caplog, ids):
        admin = await _admin(client, caplog)
        sailor_id, _ = await _squad_sailor("junioren-2026", offset=10)
        event_id = await _junior_event(client, admin, ids.series("junioren-2026"))

        confirmed = await client.post(
            f"/api/events/{event_id}/waiver",
            headers=admin,
            json={
                "sailor_id": sailor_id,
                "method": "guardian",
                "guardian_name": "R. Ver (parent)",
                "guardian_signature_ref": "office folder #42",
            },
        )
        assert confirmed.status_code == 201, confirmed.text
        assert confirmed.json()["cleared"] is True

        checklist = await client.get(
            f"/api/admin/events/{event_id}/waivers", headers=admin
        )
        row = _row(checklist, sailor_id)
        assert row["status"] == "cleared"
        assert row["minor"] is True
        assert row["method"] == "guardian"

    async def test_the_signed_form_can_arrive_after_the_name(self, client, caplog, ids):
        admin = await _admin(client, caplog)
        sailor_id, _ = await _squad_sailor("junioren-2026", offset=20)
        event_id = await _junior_event(client, admin, ids.series("junioren-2026"))
        url = f"/api/events/{event_id}/waiver"

        pending = await client.post(
            url,
            headers=admin,
            json={
                "sailor_id": sailor_id,
                "method": "guardian",
                "guardian_name": "R. Ver (parent)",
            },
        )
        assert pending.status_code == 201, pending.text
        assert pending.json()["cleared"] is False
        assert (
            _row(
                await client.get(
                    f"/api/admin/events/{event_id}/waivers", headers=admin
                ),
                sailor_id,
            )["status"]
            == "guardian_signature_missing"
        )

        signed = await client.post(
            url,
            headers=admin,
            json={"sailor_id": sailor_id, "guardian_signature_ref": "folder #7"},
        )
        assert signed.status_code == 201, signed.text
        assert signed.json()["cleared"] is True

    async def test_the_check_in_list_shows_the_organizer_what_is_outstanding(
        self, client, caplog, ids
    ):
        admin = await _admin(client, caplog)
        event_id = await _junior_event(client, admin, ids.series("junioren-2026"))

        summary = (
            await client.get(f"/api/admin/events/{event_id}/waivers", headers=admin)
        ).json()
        assert summary["required_version"] == 1
        assert summary["cleared"] + summary["outstanding"] == len(summary["sailors"])
        # Nobody has confirmed for this fresh event yet.
        assert summary["cleared"] == 0

        # `minor` is deliberately tri-state (`bool | None`) — see `is_minor`. Everyone in
        # the junior series who *has* a birth date on file is a minor; someone with none is
        # reported as unknown and **never** silently as an adult, which is the distinction
        # the whole minors rule rests on. Asserting `all(row["minor"])` instead would be
        # asserting something about the seed rather than about this endpoint: any other test
        # that puts a sailor without a birth date into a junior squad makes it fail, which
        # is exactly what happened.
        assert summary["sailors"], "a junior act should list the series' squad"
        assert all(row["minor"] is not False for row in summary["sailors"])
        assert any(row["minor"] is True for row in summary["sailors"])


class TestProblemFormat:
    """Every error is RFC 9457 application/problem+json (docs/concepts.md → Errors)."""

    async def test_a_typed_error_carries_a_stable_type(self, client, caplog, ids):
        sailor_id, _ = await _squad_sailor("dsbl-1-2026", offset=50)
        stranger = await _account_for(client, caplog, "wv-fmt@example.com")

        response = await client.post(
            f"/api/series/{ids.series('dsbl-1-2026')}/waiver",
            headers=stranger,
            json={"sailor_id": sailor_id},
        )
        assert response.status_code == 403
        assert response.headers["content-type"].startswith("application/problem+json")
        body = response.json()
        assert body["type"] == "/errors/waiver-confirmation-forbidden"
        assert body["status"] == 403
        assert isinstance(body["title"], str) and body["title"]
        assert body["instance"] == f"/api/series/{ids.series('dsbl-1-2026')}/waiver"

    async def test_a_plain_http_error_still_becomes_a_problem(self, client, caplog):
        admin = await _admin(client, caplog)
        response = await client.post(
            "/api/series/999999/waiver", headers=admin, json={"sailor_id": 1}
        )
        assert response.status_code == 404
        body = response.json()
        assert body["type"] == "/errors/http-404"
        # The original message is preserved where clients already read it.
        assert "999999" in body["detail"]

    async def test_a_validation_error_is_typed(self, client, caplog, ids):
        admin = await _admin(client, caplog)
        response = await client.post(
            f"/api/series/{ids.series('dsbl-1-2026')}/waiver",
            headers=admin,
            json={},  # missing sailor_id
        )
        assert response.status_code == 422
        body = response.json()
        assert body["type"] == "/errors/validation"
        assert isinstance(body["detail"], list)


# ------------------------------------------------------------------ Story S-1: self-service


def _png() -> bytes:
    """A real, tiny PNG — the upload is decoded, so the bytes have to be an image."""
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buffer, format="PNG")
    return buffer.getvalue()


async def _club_of(sailor_id: int) -> int:
    async with SessionLocal() as session:
        return (
            await session.execute(
                select(Team.club_id)
                .join(TeamMembership, TeamMembership.team_id == Team.id)
                .where(TeamMembership.sailor_id == sailor_id)
                .limit(1)
            )
        ).scalar_one()


def _mine(response, scope: str, scope_id: int) -> dict:
    assert response.status_code == 200, response.text
    return next(
        r
        for r in response.json()["competitions"]
        if r["scope"] == scope and r["scope_id"] == scope_id
    )


class TestSelfService:
    """Story S-1: a sailor sees, from their own account, what they still have to sign."""

    async def test_my_list_names_every_competition_i_must_sign_for(self, client, caplog, ids):
        sailor_id, email = await _squad_sailor("dsbl-1-2026", offset=60)
        me = await _account_for(client, caplog, email)

        response = await client.get("/api/waiver/me", headers=me)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["sailor_id"] == sailor_id
        assert body["required_version"] == 1
        assert body["birth_date_known"] is True

        row = _mine(response, "series", ids.series("dsbl-1-2026"))
        assert row["status"] == "missing"
        assert row["minor"] is False
        assert row["name"].startswith("1.")
        # Only competitions this sailor is entered in: no juniors series, no other league.
        assert {r["scope_id"] for r in body["competitions"] if r["scope"] == "series"} == {
            ids.series("dsbl-1-2026")
        }

    async def test_an_adult_confirms_online_from_their_own_account(self, client, caplog, ids):
        sailor_id, email = await _squad_sailor("dsbl-1-2026", offset=63)
        me = await _account_for(client, caplog, email)
        series_id = ids.series("dsbl-1-2026")

        confirmed = await client.post(
            f"/api/series/{series_id}/waiver",
            headers=me,
            json={"sailor_id": sailor_id, "locale_shown": "de"},
        )
        assert confirmed.status_code == 201, confirmed.text

        row = _mine(await client.get("/api/waiver/me", headers=me), "series", series_id)
        assert row["status"] == "cleared"
        assert row["method"] == "online"
        assert row["confirmed_version"] == 1
        assert row["scan_available"] is False

    async def test_without_a_sailor_record_there_is_nothing_to_sign(self, client, caplog):
        me = await _account_for(client, caplog, "wv-nobody@example.com")
        response = await client.get("/api/waiver/me", headers=me)
        assert response.status_code == 404
        assert response.json()["type"] == "/errors/no-linked-sailor-record"

    async def test_a_minor_is_told_the_guardian_has_to_sign(self, client, caplog, ids):
        sailor_id, email = await _squad_sailor("junioren-2026", offset=30)
        me = await _account_for(client, caplog, email)
        row = _mine(
            await client.get("/api/waiver/me", headers=me), "series", ids.series("junioren-2026")
        )
        assert row["status"] == "missing"
        assert row["minor"] is True
        assert row["sailor_id"] == sailor_id

    async def test_the_form_is_a_pdf_carrying_the_sailor_and_the_wording(
        self, client, caplog, ids
    ):
        sailor_id, email = await _squad_sailor("junioren-2026", offset=33)
        me = await _account_for(client, caplog, email)
        async with SessionLocal() as session:
            sailor = (
                await session.execute(select(Sailor).where(Sailor.id == sailor_id))
            ).scalar_one()
            first, last = sailor.first_name, sailor.last_name

        response = await client.get(
            "/api/waiver/form",
            headers=me,
            params={
                "scope": "series",
                "scope_id": ids.series("junioren-2026"),
                "sailor_id": sailor_id,
                "locale": "de",
            },
        )
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/pdf"
        assert "attachment" in response.headers["content-disposition"]
        assert response.content.startswith(b"%PDF")
        # The content stream is left uncompressed so the paper can be checked by eye here:
        # the sailor's name and the German title are on it.
        assert first.encode("latin-1") in response.content
        assert last.encode("latin-1") in response.content
        assert b"Haftungsausschluss" in response.content

    async def test_a_stranger_gets_no_form_for_someone_else(self, client, caplog, ids):
        sailor_id, _ = await _squad_sailor("junioren-2026", offset=33)
        stranger = await _account_for(client, caplog, "wv-stranger@example.com")
        response = await client.get(
            "/api/waiver/form",
            headers=stranger,
            params={
                "scope": "series",
                "scope_id": ids.series("junioren-2026"),
                "sailor_id": sailor_id,
            },
        )
        assert response.status_code == 403
        assert response.json()["type"] == "/errors/waiver-confirmation-forbidden"


class TestScans:
    """Story S-1: the guardian's signed form is uploaded, guarded, and every look is logged."""

    async def _upload(self, client, headers, series_id, sailor_id, **fields):
        data = {"sailor_id": str(sailor_id), "guardian_name": "R. Ver (parent)"}
        data.update({k: str(v) for k, v in fields.items()})
        return await client.post(
            f"/api/series/{series_id}/waiver/scan",
            headers=headers,
            data=data,
            files={"file": ("signed.png", _png(), "image/png")},
        )

    async def test_a_guardians_scan_clears_a_minor(self, client, caplog, ids):
        sailor_id, email = await _squad_sailor("junioren-2026", offset=36)
        me = await _account_for(client, caplog, email)
        series_id = ids.series("junioren-2026")

        uploaded = await self._upload(client, me, series_id, sailor_id)
        assert uploaded.status_code == 201, uploaded.text
        body = uploaded.json()
        assert body["cleared"] is True
        assert body["method"] == "guardian"
        assert body["guardian_name"] == "R. Ver (parent)"

        row = _mine(await client.get("/api/waiver/me", headers=me), "series", series_id)
        assert row["status"] == "cleared"
        assert row["scan_available"] is True
        assert row["confirmation_id"] == body["id"]

        scan = await client.get(f"/api/waiver/confirmations/{body['id']}/scan", headers=me)
        assert scan.status_code == 200, scan.text
        assert scan.headers["content-type"] == "image/png"
        assert scan.content == _png()

    async def test_a_scan_completes_a_confirmation_whose_name_came_first(
        self, client, caplog, ids
    ):
        admin = await _admin(client, caplog)
        sailor_id, email = await _squad_sailor("junioren-2026", offset=39)
        series_id = ids.series("junioren-2026")

        named = await client.post(
            f"/api/series/{series_id}/waiver",
            headers=admin,
            json={"sailor_id": sailor_id, "method": "guardian", "guardian_name": "R. Ver"},
        )
        assert named.status_code == 201, named.text
        assert named.json()["cleared"] is False

        me = await _account_for(client, caplog, email)
        uploaded = await self._upload(client, me, series_id, sailor_id)
        assert uploaded.status_code == 201, uploaded.text
        assert uploaded.json()["id"] == named.json()["id"]
        assert uploaded.json()["cleared"] is True

    async def test_only_a_real_document_is_accepted(self, client, caplog, ids):
        sailor_id, email = await _squad_sailor("junioren-2026", offset=42)
        me = await _account_for(client, caplog, email)
        series_id = ids.series("junioren-2026")

        text = await client.post(
            f"/api/series/{series_id}/waiver/scan",
            headers=me,
            data={"sailor_id": str(sailor_id), "guardian_name": "R. Ver"},
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )
        assert text.status_code == 422
        assert text.json()["type"] == "/errors/waiver-scan-invalid-type"

        fake = await client.post(
            f"/api/series/{series_id}/waiver/scan",
            headers=me,
            data={"sailor_id": str(sailor_id), "guardian_name": "R. Ver"},
            files={"file": ("signed.png", b"not really a png", "image/png")},
        )
        assert fake.status_code == 422
        assert fake.json()["type"] == "/errors/waiver-scan-invalid"

        nameless = await client.post(
            f"/api/series/{series_id}/waiver/scan",
            headers=me,
            data={"sailor_id": str(sailor_id)},
            files={"file": ("signed.png", _png(), "image/png")},
        )
        assert nameless.status_code == 422
        assert nameless.json()["type"] == "/errors/guardian-name-required"

        # Nothing was recorded by the refused attempts.
        row = _mine(await client.get("/api/waiver/me", headers=me), "series", series_id)
        assert row["status"] == "missing"

    async def test_an_adult_does_not_upload_a_scan(self, client, caplog, ids):
        sailor_id, email = await _squad_sailor("dsbl-1-2026", offset=66)
        me = await _account_for(client, caplog, email)
        response = await self._upload(client, me, ids.series("dsbl-1-2026"), sailor_id)
        assert response.status_code == 422
        assert response.json()["type"] == "/errors/waiver-scan-not-needed"

    async def test_the_scan_is_shown_only_to_connected_accounts_and_every_look_is_logged(
        self, client, caplog, ids
    ):
        from app.models import AuditLog

        sailor_id, email = await _squad_sailor("junioren-2026", offset=45)
        me = await _account_for(client, caplog, email)
        series_id = ids.series("junioren-2026")
        confirmation_id = (await self._upload(client, me, series_id, sailor_id)).json()["id"]
        url = f"/api/waiver/confirmations/{confirmation_id}/scan"

        async def logged() -> int:
            async with SessionLocal() as session:
                return len(
                    (
                        await session.execute(
                            select(AuditLog).where(
                                AuditLog.entity_type == "waiver_scan",
                                AuditLog.entity_id == confirmation_id,
                                AuditLog.action == "viewed",
                            )
                        )
                    ).scalars().all()
                )

        before = await logged()

        stranger = await _account_for(client, caplog, "wv-peeper@example.com")
        denied = await client.get(url, headers=stranger)
        assert denied.status_code == 403
        assert denied.json()["type"] == "/errors/waiver-scan-forbidden"

        await make_user("wv-otherclub@example.com", Role.CLUB_MANAGER, club_id=ids.club("nrv"))
        other_club = auth_headers(await login_as(client, "wv-otherclub@example.com", caplog))
        assert (await client.get(url, headers=other_club)).status_code == 403

        own_club = await _club_of(sailor_id)
        await make_user("wv-ownclub@example.com", Role.CLUB_MANAGER, club_id=own_club)
        leadership = auth_headers(await login_as(client, "wv-ownclub@example.com", caplog))
        assert (await client.get(url, headers=leadership)).status_code == 200

        admin = await _admin(client, caplog)
        assert (await client.get(url, headers=admin)).status_code == 200

        # Two successful retrievals, two log rows — the refusals are not "views".
        assert await logged() == before + 2

        anonymous = await client.get(url)
        assert anonymous.status_code == 401
