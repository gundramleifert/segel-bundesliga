"""Defects the concept review found in behaviour, each held by the test it must pass.

Every test here states what the site **should** do and is marked
``xfail(strict=True)`` with its item in ``docs/REVIEW_2026-11.md``: it shows in every run
as a known defect, and the day the fix lands it passes — which ``strict`` turns into a
failure until the marker is deleted. So a fix cannot go unnoticed, and the marker cannot
outlive it. A test that changes shared data puts it back.
"""

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Event, Person, Series
from app.models.auth import Grant, Relation
from tests.accounts import account
from tests.stories.test_create_event import admin
from tests.stories.test_login_and_roles import login_as
from tests.stories.test_registration import auth_headers


async def signed_in(client, caplog, email: str, *grants: Grant) -> dict[str, str]:
    await account(email, *grants)
    return auth_headers(await login_as(client, email, caplog))


# ------------------------------------------------------------------- permissions


@pytest.mark.xfail(strict=True, reason="REVIEW 4.1 — event manager inherits from host club")
async def test_a_clubs_team_manager_does_not_organize_the_league_acts_it_hosts(client, caplog):
    """A club's `manager` decides who sails for it. Hosting a league act makes the club pay
    for it and lend its officials — it does not make the team manager the act's organizer,
    who can change its clubs, cancel it and read the officials' documents."""
    async with SessionLocal() as session:
        act = (
            (
                await session.execute(
                    select(Event).where(
                        Event.host_club_id.is_not(None), Event.series_id.is_not(None)
                    )
                )
            )
            .scalars()
            .first()
        )
    headers = await signed_in(
        client,
        caplog,
        "defect-team-manager@example.com",
        Grant(relation=Relation.MANAGER, club_id=act.host_club_id),
    )

    access = (await client.get(f"/api/events/{act.id}/access", headers=headers)).json()

    assert access["manage"] is False


@pytest.mark.xfail(strict=True, reason="REVIEW 4.3 — the tuple API skips the membership rule")
async def test_a_clubs_admin_cannot_make_a_stranger_its_treasurer(client, caplog, season):
    """The treasurer sees every claimant's IBAN. A club's admin appoints one among the
    club's members (CLAUDE.md) — not any account on the site found by its address."""
    club = next(iter(season.squads))
    headers = await signed_in(
        client,
        caplog,
        "defect-club-admin@example.com",
        Grant(relation=Relation.ADMIN, club_id=club),
    )
    await account("defect-stranger@example.com")

    response = await client.post(
        "/api/auth/tuples",
        json={
            "user": "defect-stranger@example.com",
            "relation": "treasurer",
            "object": f"club:{club}",
        },
        headers=headers,
    )
    try:
        assert response.status_code in (403, 409, 422), response.text
    finally:
        async with SessionLocal() as session:
            for row in (
                await session.execute(
                    select(Grant).where(Grant.club_id == club, Grant.relation == Relation.TREASURER)
                )
            ).scalars():
                await session.delete(row)
            await session.commit()


# ------------------------------------------------------------------- what is decided stays


@pytest.mark.xfail(strict=True, reason="REVIEW 2.2 — scoring editable after an act is scored")
async def test_a_series_scoring_is_frozen_once_an_act_is_scored(client, caplog, season):
    """Changing the discards after act 3 would re-score acts 1–3 without a word. Once an
    act of the series is scored, its rules are the season's."""
    headers = await admin(client, caplog, "defect-admin-scoring@example.com")
    async with SessionLocal() as session:
        before = (await session.get(Series, season.series)).scoring

    response = await client.patch(
        f"/api/admin/series/{season.series}",
        json={"scoring": {"discard_after": [4]}},
        headers=headers,
    )
    try:
        assert response.status_code == 409, response.text
    finally:
        async with SessionLocal() as session:
            (await session.get(Series, season.series)).scoring = before
            await session.commit()


@pytest.mark.xfail(strict=True, reason="REVIEW 2.4 — results_source switchable mid-event")
async def test_where_results_come_from_is_frozen_with_the_configuration(client, caplog, season):
    """Switching a sailed act to SAP would let the next poll overwrite the committee's
    results, protest decisions included. It is part of the configuration the first race
    freezes."""
    headers = await admin(client, caplog, "defect-admin-source@example.com")
    async with SessionLocal() as session:
        before = (await session.get(Event, season.live)).results_source

    response = await client.patch(
        f"/api/admin/events/{season.live}", json={"results_source": "sap"}, headers=headers
    )
    try:
        assert response.status_code == 409, response.text
    finally:
        async with SessionLocal() as session:
            (await session.get(Event, season.live)).results_source = before
            await session.commit()


# ------------------------------------------------------------------- personal data


@pytest.mark.xfail(strict=True, reason="REVIEW 5.5 — deleting an account keeps the person")
async def test_deleting_my_account_erases_who_i_am(client, caplog):
    """GDPR Art. 17: after "Delete my account" nothing names the person any more but the
    results they sailed — no address, no birth date, no row to find them by."""
    email = "defect-erase-me@example.com"
    headers = await signed_in(client, caplog, email)

    assert (await client.delete("/api/auth/me", headers=headers)).status_code == 204

    async with SessionLocal() as session:
        kept = (
            await session.execute(select(Person).where(Person.email == email))
        ).scalar_one_or_none()
    assert kept is None
