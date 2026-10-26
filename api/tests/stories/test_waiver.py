"""User story S-2: confirm a specific version of the liability waiver.

A sailor confirms **one version** of the waiver, either for a whole series (which covers
every event of it) or for a single event. The text is versioned and frozen: a later
change to the wording is a new version that everyone re-confirms, and it never rewrites
an old confirmation.

Minors cannot clear the waiver by their own click — a legal guardian signs on paper and
the reference to that scan is recorded.
"""

from datetime import date

import pytest
from sqlalchemy import delete, select

from app.db import SessionLocal
from app.models import (
    Club,
    Person,
    Series,
    Team,
    TeamMembership,
    TeamStatus,
    WaiverConfirmation,
    WaiverText,
)
from app.models.auth import Grant, Relation, Role
from tests.stories.test_login_and_roles import login_as, make_user
from tests.stories.test_my_space import SOON, _club, _event, _person, _series, _tag, _team
from tests.stories.test_registration import auth_headers
from tests.stories.test_reimbursements import login

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


async def _new_person(client, admin, *, email: str, birth_date: str | None) -> int:
    body: dict[str, object] = {
        "first_name": "Wai",
        "last_name": "Ver",
        "email": email,
    }
    if birth_date is not None:
        body["birth_date"] = birth_date
    response = await client.post("/api/admin/people", headers=admin, json=body)
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _squad_person(series_slug: str, offset: int) -> tuple[int, str]:
    """A distinct seeded sailor from a series' squad: (id, email).

    Each test picks its own offset — the seeded database is shared across the module, so
    two tests confirming for the same person would collide.
    """
    async with SessionLocal() as session:
        return (
            await session.execute(
                select(Person.id, Person.email)
                .join(TeamMembership, TeamMembership.person_id == Person.id)
                .join(Team, TeamMembership.team_id == Team.id)
                .join(Series, Team.series_id == Series.id)
                .where(Series.slug == series_slug, Team.event_id.is_(None))
                .order_by(Person.id)
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


def _row(response, person_id: int) -> dict:
    return next(r for r in response.json()["people"] if r["person_id"] == person_id)


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
    async def test_a_new_version_supersedes_an_old_confirmation_without_rewriting_it(
        self, client, caplog, ids, version_two
    ):
        admin = await _admin(client, caplog)
        person_id, _ = await _squad_person("dsbl-1-2026", offset=0)

        # The confirmation was for version 1; version 2 is now in force.
        async with SessionLocal() as session:
            v1 = (
                await session.execute(select(WaiverText).where(WaiverText.version == 1))
            ).scalar_one()
            session.add(
                WaiverConfirmation(
                    person_id=person_id,
                    waiver_text_id=v1.id,
                    series_id=ids.series("dsbl-1-2026"),
                )
            )
            await session.commit()

        checklist = await client.get(
            f"/api/admin/events/{ids.event('dsbl-1-2026-act-1')}/waivers", headers=admin
        )
        row = _row(checklist, person_id)
        assert row["required_version"] == 2
        assert row["confirmed_version"] == 1
        assert row["status"] == "version_outdated"


class TestConfirming:
    async def test_a_series_confirmation_clears_every_event_of_it(self, client, caplog, ids):
        admin = await _admin(client, caplog)
        person_id, email = await _squad_person("dsbl-1-2026", offset=10)
        person = await _account_for(client, caplog, email)

        confirmed = await client.post(
            f"/api/series/{ids.series('dsbl-1-2026')}/waiver",
            headers=person,
            json={"person_id": person_id, "locale_shown": "en"},
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
            assert _row(checklist, person_id)["status"] == "cleared"

    async def test_an_event_confirmation_leaves_the_other_events_open(self, client, caplog, ids):
        admin = await _admin(client, caplog)
        person_id, email = await _squad_person("dsbl-1-2026", offset=20)
        person = await _account_for(client, caplog, email)

        confirmed = await client.post(
            f"/api/events/{ids.event('dsbl-1-2026-act-1')}/waiver",
            headers=person,
            json={"person_id": person_id},
        )
        assert confirmed.status_code == 201, confirmed.text

        first = await client.get(
            f"/api/admin/events/{ids.event('dsbl-1-2026-act-1')}/waivers", headers=admin
        )
        second = await client.get(
            f"/api/admin/events/{ids.event('dsbl-1-2026-act-2')}/waivers", headers=admin
        )
        assert _row(first, person_id)["status"] == "cleared"
        assert _row(second, person_id)["status"] == "missing"

    async def test_confirming_the_same_version_twice_is_rejected(self, client, caplog, ids):
        person_id, email = await _squad_person("dsbl-1-2026", offset=30)
        person = await _account_for(client, caplog, email)
        url = f"/api/series/{ids.series('dsbl-1-2026')}/waiver"

        assert (
            await client.post(url, headers=person, json={"person_id": person_id})
        ).status_code == 201
        again = await client.post(url, headers=person, json={"person_id": person_id})
        assert again.status_code == 409
        problem = again.json()
        assert problem["type"] == "/errors/waiver-already-confirmed"
        assert problem["status"] == 409
        assert problem["required_version"] == 1
        assert again.headers["content-type"].startswith("application/problem+json")

    async def test_you_can_only_confirm_for_yourself(self, client, caplog, ids):
        """The refusal is also the worked example of a typed RFC 9457 error
        (docs/concepts.md → Errors): a stable type, status, title and instance."""
        person_id, _ = await _squad_person("dsbl-1-2026", offset=40)
        stranger = await _account_for(client, caplog, "wv-stranger@example.com")
        url = f"/api/series/{ids.series('dsbl-1-2026')}/waiver"

        denied = await client.post(url, headers=stranger, json={"person_id": person_id})
        assert denied.status_code == 403
        assert denied.headers["content-type"].startswith("application/problem+json")
        body = denied.json()
        assert body["type"] == "/errors/waiver-confirmation-forbidden"
        assert body["status"] == 403
        assert isinstance(body["title"], str) and body["title"]
        assert body["instance"] == url

        admin = await _admin(client, caplog)
        allowed = await client.post(url, headers=admin, json={"person_id": person_id})
        assert allowed.status_code == 201

    async def test_a_team_manager_signs_only_for_their_own_clubs_sailors(self, client, caplog, ids):
        """Stories S-1, S-3: a club's manager hands in the forms *their* club collected —
        confirming, uploading a scan or printing a form for a sailor of another club is
        refused, as it is for any stranger. (Until 2026-10-17 any team manager on the site
        could sign for anybody; found by Journey J-5.)"""
        person_id, _ = await _squad_person("dsbl-1-2026", offset=45)
        own_club = await _club_of(person_id)
        async with SessionLocal() as session:
            person_clubs = set(
                (
                    await session.execute(
                        select(Team.club_id)
                        .join(TeamMembership, TeamMembership.team_id == Team.id)
                        .where(TeamMembership.person_id == person_id)
                    )
                ).scalars()
            )
            other_club = (
                await session.execute(
                    select(Club.id).where(Club.id.not_in(person_clubs)).order_by(Club.id).limit(1)
                )
            ).scalar_one()
        series_id = ids.series("dsbl-1-2026")
        url = f"/api/series/{series_id}/waiver"
        form = f"/api/waiver/form?scope=series&scope_id={series_id}&person_id={person_id}"

        await make_user("wv-foreign-mgr@example.com", Role.TEAM_MANAGER, club_id=other_club)
        foreign = auth_headers(await login_as(client, "wv-foreign-mgr@example.com", caplog))
        denied = await client.post(url, headers=foreign, json={"person_id": person_id})
        assert denied.status_code == 403, denied.text
        assert denied.json()["type"] == "/errors/waiver-confirmation-forbidden"
        assert (await client.get(form, headers=foreign)).status_code == 403

        await make_user("wv-own-mgr@example.com", Role.TEAM_MANAGER, club_id=own_club)
        own = auth_headers(await login_as(client, "wv-own-mgr@example.com", caplog))
        assert (await client.get(form, headers=own)).status_code == 200
        allowed = await client.post(url, headers=own, json={"person_id": person_id})
        assert allowed.status_code == 201, allowed.text

    async def test_a_rejected_registration_signs_for_nobody(self, client, caplog, ids):
        """Stories S-1, S-3: a squad on a registration the league office rejected never
        became a participation, so it makes nobody that club's sailor to sign for."""
        person_id, _ = await _squad_person("dsbl-1-2026", offset=46)
        async with SessionLocal() as session:
            club = Club(slug="wv-rejected", name="Rejected Waiver Club", short_name="RWC")
            series = Series(slug="wv-rejected-series", name="Rejected Waiver Cup", short_name="RWC")
            session.add_all([club, series])
            await session.flush()
            team = Team(
                name="RWC", club_id=club.id, series_id=series.id, status=TeamStatus.REJECTED
            )
            session.add(team)
            await session.flush()
            session.add(TeamMembership(team_id=team.id, person_id=person_id))
            await session.commit()
            club_id = club.id
        await make_user("wv-rejected-mgr@example.com", Role.TEAM_MANAGER, club_id=club_id)
        manager = auth_headers(await login_as(client, "wv-rejected-mgr@example.com", caplog))
        series_id = ids.series("dsbl-1-2026")
        denied = await client.post(
            f"/api/series/{series_id}/waiver", headers=manager, json={"person_id": person_id}
        )
        assert denied.status_code == 403, denied.text


class TestMinors:
    async def test_a_minor_cannot_clear_it_online(self, client, caplog, ids):
        person_id, email = await _squad_person("junioren-2026", offset=0)
        teen = await _account_for(client, caplog, email)

        response = await client.post(
            f"/api/series/{ids.series('junioren-2026')}/waiver",
            headers=teen,
            json={"person_id": person_id, "method": "online"},
        )
        assert response.status_code == 422
        assert response.json()["type"] == "/errors/guardian-confirmation-needed"

    async def test_a_sailor_without_a_birth_date_cannot_be_confirmed(self, client, caplog, ids):
        admin = await _admin(client, caplog)
        person_id = await _new_person(client, admin, email="wv-nodob@example.com", birth_date=None)
        response = await client.post(
            f"/api/series/{ids.series('junioren-2026')}/waiver",
            headers=admin,
            json={"person_id": person_id},
        )
        assert response.status_code == 422
        problem = response.json()
        assert problem["type"] == "/errors/waiver-birth-date-required"
        assert problem["person_id"] == person_id

    async def test_a_guardian_signature_clears_a_minor(self, client, caplog, ids):
        admin = await _admin(client, caplog)
        person_id, _ = await _squad_person("junioren-2026", offset=10)
        event_id = await _junior_event(client, admin, ids.series("junioren-2026"))

        confirmed = await client.post(
            f"/api/events/{event_id}/waiver",
            headers=admin,
            json={
                "person_id": person_id,
                "method": "guardian",
                "guardian_name": "R. Ver (parent)",
                "guardian_signature_ref": "office folder #42",
            },
        )
        assert confirmed.status_code == 201, confirmed.text
        assert confirmed.json()["cleared"] is True

        checklist = await client.get(f"/api/admin/events/{event_id}/waivers", headers=admin)
        row = _row(checklist, person_id)
        assert row["status"] == "cleared"
        assert row["minor"] is True
        assert row["method"] == "guardian"

    async def test_the_signed_form_can_arrive_after_the_name(self, client, caplog, ids):
        admin = await _admin(client, caplog)
        person_id, _ = await _squad_person("junioren-2026", offset=20)
        event_id = await _junior_event(client, admin, ids.series("junioren-2026"))
        url = f"/api/events/{event_id}/waiver"

        pending = await client.post(
            url,
            headers=admin,
            json={
                "person_id": person_id,
                "method": "guardian",
                "guardian_name": "R. Ver (parent)",
            },
        )
        assert pending.status_code == 201, pending.text
        assert pending.json()["cleared"] is False
        assert (
            _row(
                await client.get(f"/api/admin/events/{event_id}/waivers", headers=admin),
                person_id,
            )["status"]
            == "guardian_signature_missing"
        )

        signed = await client.post(
            url,
            headers=admin,
            json={"person_id": person_id, "guardian_signature_ref": "folder #7"},
        )
        assert signed.status_code == 201, signed.text
        assert signed.json()["cleared"] is True

    async def test_the_check_in_list_shows_the_organizer_what_is_outstanding(
        self, client, caplog, ids
    ):
        admin = await _admin(client, caplog)
        event_id = await _junior_event(client, admin, ids.series("junioren-2026"))

        summary = (await client.get(f"/api/admin/events/{event_id}/waivers", headers=admin)).json()
        assert summary["required_version"] == 1
        assert summary["cleared"] + summary["outstanding"] == len(summary["people"])
        # Nobody has confirmed for this fresh event yet.
        assert summary["cleared"] == 0

        # `minor` is deliberately tri-state (`bool | None`) — see `is_minor`. Everyone in
        # the junior series who *has* a birth date on file is a minor; someone with none is
        # reported as unknown and **never** silently as an adult, which is the distinction
        # the whole minors rule rests on. Asserting `all(row["minor"])` instead would be
        # asserting something about the seed rather than about this endpoint: any other test
        # that puts a sailor without a birth date into a junior squad makes it fail, which
        # is exactly what happened.
        assert summary["people"], "a junior act should list the series' squad"
        assert all(row["minor"] is not False for row in summary["people"])
        assert any(row["minor"] is True for row in summary["people"])


class TestProblemFormat:
    """Every error is RFC 9457 application/problem+json (docs/concepts.md → Errors)."""

    async def test_an_unknown_thing_is_a_typed_not_found(self, client, caplog):
        admin = await _admin(client, caplog)
        response = await client.post(
            "/api/series/999999/waiver", headers=admin, json={"person_id": 1}
        )
        assert response.status_code == 404
        assert response.headers["content-type"].startswith("application/problem+json")
        body = response.json()
        assert body["type"] == "/errors/series-not-found"
        assert body["id"] == 999999

    async def test_a_plain_http_error_still_becomes_a_problem(self, client):
        """No router raises a plain HTTPException any more, but the framework does — an
        unknown route is still answered as a problem, with the generic type."""
        response = await client.get("/api/no-such-route")
        assert response.status_code == 404
        assert response.headers["content-type"].startswith("application/problem+json")
        assert response.json()["type"] == "/errors/http-404"

    async def test_a_validation_error_is_typed(self, client, caplog, ids):
        admin = await _admin(client, caplog)
        response = await client.post(
            f"/api/series/{ids.series('dsbl-1-2026')}/waiver",
            headers=admin,
            json={},  # missing person_id
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


async def _club_of(person_id: int) -> int:
    async with SessionLocal() as session:
        return (
            await session.execute(
                select(Team.club_id)
                .join(TeamMembership, TeamMembership.team_id == Team.id)
                .where(TeamMembership.person_id == person_id)
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
        person_id, email = await _squad_person("dsbl-1-2026", offset=60)
        me = await _account_for(client, caplog, email)

        response = await client.get("/api/waiver/me", headers=me)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["person_id"] == person_id
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
        person_id, email = await _squad_person("dsbl-1-2026", offset=63)
        me = await _account_for(client, caplog, email)
        series_id = ids.series("dsbl-1-2026")

        confirmed = await client.post(
            f"/api/series/{series_id}/waiver",
            headers=me,
            json={"person_id": person_id, "locale_shown": "de"},
        )
        assert confirmed.status_code == 201, confirmed.text

        row = _mine(await client.get("/api/waiver/me", headers=me), "series", series_id)
        assert row["status"] == "cleared"
        assert row["method"] == "online"
        assert row["confirmed_version"] == 1
        assert row["scan_available"] is False

    async def test_without_a_squad_there_is_nothing_to_sign(self, client, caplog):
        """Every account has its person (#40), so there is always a record to show — and
        someone in no squad has no competition to confirm for."""
        me = await _account_for(client, caplog, "wv-nobody@example.com")
        response = await client.get("/api/waiver/me", headers=me)
        assert response.status_code == 200, response.text
        assert response.json()["competitions"] == []

    async def test_a_minor_is_told_the_guardian_has_to_sign(self, client, caplog, ids):
        person_id, email = await _squad_person("junioren-2026", offset=30)
        me = await _account_for(client, caplog, email)
        row = _mine(
            await client.get("/api/waiver/me", headers=me), "series", ids.series("junioren-2026")
        )
        assert row["status"] == "missing"
        assert row["minor"] is True
        assert row["person_id"] == person_id

    async def test_the_form_is_a_pdf_carrying_the_sailor_and_the_wording(self, client, caplog, ids):
        person_id, email = await _squad_person("junioren-2026", offset=33)
        me = await _account_for(client, caplog, email)
        async with SessionLocal() as session:
            person = (
                await session.execute(select(Person).where(Person.id == person_id))
            ).scalar_one()
            first, last = person.first_name, person.last_name

        response = await client.get(
            "/api/waiver/form",
            headers=me,
            params={
                "scope": "series",
                "scope_id": ids.series("junioren-2026"),
                "person_id": person_id,
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
        person_id, _ = await _squad_person("junioren-2026", offset=33)
        stranger = await _account_for(client, caplog, "wv-stranger@example.com")
        response = await client.get(
            "/api/waiver/form",
            headers=stranger,
            params={
                "scope": "series",
                "scope_id": ids.series("junioren-2026"),
                "person_id": person_id,
            },
        )
        assert response.status_code == 403
        assert response.json()["type"] == "/errors/waiver-confirmation-forbidden"


class TestScans:
    """Story S-1: the guardian's signed form is uploaded, guarded, and every look is logged."""

    async def _upload(self, client, headers, series_id, person_id, **fields):
        data = {"person_id": str(person_id), "guardian_name": "R. Ver (parent)"}
        data.update({k: str(v) for k, v in fields.items()})
        return await client.post(
            f"/api/series/{series_id}/waiver/scan",
            headers=headers,
            data=data,
            files={"file": ("signed.png", _png(), "image/png")},
        )

    async def test_a_guardians_scan_clears_a_minor(self, client, caplog, ids):
        person_id, email = await _squad_person("junioren-2026", offset=36)
        me = await _account_for(client, caplog, email)
        series_id = ids.series("junioren-2026")

        uploaded = await self._upload(client, me, series_id, person_id)
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

    async def test_a_scan_completes_a_confirmation_whose_name_came_first(self, client, caplog, ids):
        admin = await _admin(client, caplog)
        person_id, email = await _squad_person("junioren-2026", offset=39)
        series_id = ids.series("junioren-2026")

        named = await client.post(
            f"/api/series/{series_id}/waiver",
            headers=admin,
            json={"person_id": person_id, "method": "guardian", "guardian_name": "R. Ver"},
        )
        assert named.status_code == 201, named.text
        assert named.json()["cleared"] is False

        me = await _account_for(client, caplog, email)
        uploaded = await self._upload(client, me, series_id, person_id)
        assert uploaded.status_code == 201, uploaded.text
        assert uploaded.json()["id"] == named.json()["id"]
        assert uploaded.json()["cleared"] is True

    async def test_only_a_real_document_is_accepted(self, client, caplog, ids):
        person_id, email = await _squad_person("junioren-2026", offset=42)
        me = await _account_for(client, caplog, email)
        series_id = ids.series("junioren-2026")

        text = await client.post(
            f"/api/series/{series_id}/waiver/scan",
            headers=me,
            data={"person_id": str(person_id), "guardian_name": "R. Ver"},
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )
        assert text.status_code == 422
        assert text.json()["type"] == "/errors/waiver-scan-invalid-type"

        fake = await client.post(
            f"/api/series/{series_id}/waiver/scan",
            headers=me,
            data={"person_id": str(person_id), "guardian_name": "R. Ver"},
            files={"file": ("signed.png", b"not really a png", "image/png")},
        )
        # Named and declared a PNG, but the content is text: the content decides.
        assert fake.status_code == 422
        assert fake.json()["type"] == "/errors/waiver-scan-invalid-type"

        nameless = await client.post(
            f"/api/series/{series_id}/waiver/scan",
            headers=me,
            data={"person_id": str(person_id)},
            files={"file": ("signed.png", _png(), "image/png")},
        )
        assert nameless.status_code == 422
        assert nameless.json()["type"] == "/errors/guardian-name-required"

        # Nothing was recorded by the refused attempts.
        row = _mine(await client.get("/api/waiver/me", headers=me), "series", series_id)
        assert row["status"] == "missing"

    async def test_an_adult_does_not_upload_a_scan(self, client, caplog, ids):
        person_id, email = await _squad_person("dsbl-1-2026", offset=66)
        me = await _account_for(client, caplog, email)
        response = await self._upload(client, me, ids.series("dsbl-1-2026"), person_id)
        assert response.status_code == 422
        assert response.json()["type"] == "/errors/waiver-scan-not-needed"

    async def test_the_scan_is_shown_only_to_connected_accounts_and_every_look_is_logged(
        self, client, caplog, ids
    ):
        from app.models import AuditLog

        person_id, email = await _squad_person("junioren-2026", offset=45)
        me = await _account_for(client, caplog, email)
        series_id = ids.series("junioren-2026")
        confirmation_id = (await self._upload(client, me, series_id, person_id)).json()["id"]
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
                    )
                    .scalars()
                    .all()
                )

        before = await logged()

        stranger = await _account_for(client, caplog, "wv-peeper@example.com")
        denied = await client.get(url, headers=stranger)
        assert denied.status_code == 403
        assert denied.json()["type"] == "/errors/waiver-scan-forbidden"

        await make_user("wv-otherclub@example.com", Role.TEAM_MANAGER, club_id=ids.club("asvw"))
        other_club = auth_headers(await login_as(client, "wv-otherclub@example.com", caplog))
        assert (await client.get(url, headers=other_club)).status_code == 403

        own_club = await _club_of(person_id)
        await make_user("wv-ownclub@example.com", Role.TEAM_MANAGER, club_id=own_club)
        leadership = auth_headers(await login_as(client, "wv-ownclub@example.com", caplog))
        assert (await client.get(url, headers=leadership)).status_code == 200

        admin = await _admin(client, caplog)
        assert (await client.get(url, headers=admin)).status_code == 200

        # Two successful retrievals, two log rows — the refusals are not "views".
        assert await logged() == before + 2

        anonymous = await client.get(url)
        assert anonymous.status_code == 401


class TestClubOverview:
    """V-14: the team manager sees which of the club's sailors have signed."""

    async def test_the_team_manager_sees_who_signed_in_each_competition(self, client, caplog):
        """One block per series squad and per entry in a stand-alone event; the missing
        first; a series confirmation clears the series' block."""
        club = await _club()
        series = await _series()
        cup = await _event(starts_on=SOON)  # in no series
        squad = await _team(club, series_id=series)
        entry = await _team(club, event_id=cup)
        signed, unsigned = f"v14-a-{_tag()}@example.com", f"v14-b-{_tag()}@example.com"
        signed_id = await _person(signed, squad, entry, birth_date=date(1990, 1, 1))
        unsigned_id = await _person(unsigned, squad, birth_date=date(1991, 1, 1))
        person = await login(client, caplog, signed)
        confirmed = await client.post(
            f"/api/series/{series}/waiver", headers=person, json={"person_id": signed_id}
        )
        assert confirmed.status_code == 201, confirmed.text

        manager = await login(
            client,
            caplog,
            f"v14-tm-{_tag()}@example.com",
            Grant(relation=Relation.MANAGER, club_id=club),
        )
        response = await client.get(f"/api/clubs/{club}/waivers", headers=manager)
        assert response.status_code == 200, response.text
        blocks = {(b["scope"], b["scope_id"]): b for b in response.json()["competitions"]}
        assert set(blocks) == {("series", series), ("event", cup)}

        in_series = blocks[("series", series)]
        assert (in_series["cleared"], in_series["outstanding"]) == (1, 1)
        assert [(s["person_id"], s["status"]) for s in in_series["people"]] == [
            (unsigned_id, "missing"),
            (signed_id, "cleared"),
        ]
        # A series confirmation does not cover an event that belongs to no series.
        at_cup = blocks[("event", cup)]
        assert [(s["person_id"], s["status"]) for s in at_cup["people"]] == [(signed_id, "missing")]

    async def test_a_member_or_another_club_is_refused(self, client, caplog):
        club, other = await _club(), await _club()
        for grant in (
            Grant(relation=Relation.MEMBER, club_id=club),
            Grant(relation=Relation.MANAGER, club_id=other),
        ):
            headers = await login(client, caplog, f"v14-no-{_tag()}@example.com", grant)
            response = await client.get(f"/api/clubs/{club}/waivers", headers=headers)
            assert response.status_code == 403, response.text
            assert response.json()["type"].endswith("/club-waivers-forbidden")
