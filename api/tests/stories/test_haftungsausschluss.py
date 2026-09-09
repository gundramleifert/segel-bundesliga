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
from tests.stories.test_registrierung import auth_headers

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
        assert all(r["minor"] for r in summary["sailors"])


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
