"""User story S-4: a sailor decides whether their own profile page is public.

The **name** stays on every competition record — squad, lineup, results — and only the
**page** (`GET /api/people/{id}`) and the link to it go away. The squad and lineup
outputs carry `profile_public`, so the frontend renders a hidden profile's name as plain
text instead of a link.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import NamedTuple

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Club, Person, Series, Team, TeamMembership
from app.models.auth import Role
from tests.stories.test_login_and_roles import login_as, make_user
from tests.stories.test_registration import auth_headers
from tests.stories.test_sailor_profile import (
    _ADULT_BIRTH,
    _admin,
    _jpeg_bytes,
    _minor_birth,
    _new_person,
)


class SquadPerson(NamedTuple):
    """A seeded sailor on a public squad, linked to an account for this test."""

    person_id: int
    club_id: int
    email: str


@asynccontextmanager
async def _squad_person(email: str) -> AsyncIterator[SquadPerson]:
    """ASVW's first squad member of a published 2026 series, re-addressed to ``email`` so
    the test signs in as them, and given back unchanged afterwards — other stories in the
    same worker count on the seed."""
    async with SessionLocal() as session:
        person, club_id = (
            await session.execute(
                select(Person, Club.id)
                .join(TeamMembership, TeamMembership.person_id == Person.id)
                .join(Team, TeamMembership.team_id == Team.id)
                .join(Club, Team.club_id == Club.id)
                .join(Series, Team.series_id == Series.id)
                .where(
                    Club.slug == "asvw",
                    Team.event_id.is_(None),
                    Series.year == 2026,
                    Series.published.is_(True),
                )
                .order_by(Person.id)
                .limit(1)
            )
        ).one()
        original = (person.email, person.birth_date, person.profile_public_choice)
        person.email, person.birth_date, person.profile_public_choice = email, None, None
        await session.commit()
        person_id = person.id
    try:
        yield SquadPerson(person_id, club_id, email)
    finally:
        async with SessionLocal() as session:
            person = await session.get(Person, person_id)
            person.email, person.birth_date, person.profile_public_choice = original
            await session.commit()


def _squad_entry(club: dict, person_id: int) -> dict:
    for team in club["teams"]:
        for member in team["members"]:
            if member["id"] == person_id:
                return member
    raise AssertionError(f"Sailor {person_id} not on the club page")


class TestProfileVisibility:
    """S-4: As a sailor, I want to decide whether my profile page is public."""

    async def test_switching_off_hides_the_page_from_guests_but_not_the_name(self, client, caplog):
        """Off: a guest gets 404 for the page, the squad still names the sailor — with
        `profile_public` false, so no link is built. On again: immediate, symmetric."""
        async with _squad_person("s4.owner@example.com") as target:
            await make_user(target.email)
            me = auth_headers(await login_as(client, target.email, caplog))

            assert (await client.get("/api/people/me", headers=me)).json()[
                "profile_public"
            ] is True
            assert (await client.get(f"/api/people/{target.person_id}")).status_code == 200

            await client.patch("/api/people/me", headers=me, json={"birth_date": _ADULT_BIRTH})
            upload = await client.post(
                "/api/people/me/photo",
                headers=me,
                files={"file": ("me.jpg", _jpeg_bytes(), "image/jpeg")},
            )
            assert upload.status_code == 200, upload.text
            photo = f"/api/people/{target.person_id}/photo"
            assert (await client.get(photo)).status_code == 200

            off = await client.patch("/api/people/me", headers=me, json={"profile_public": False})
            assert off.status_code == 200, off.text
            assert off.json()["profile_public"] is False

            assert (await client.get(f"/api/people/{target.person_id}")).status_code == 404
            club = (await client.get(f"/api/clubs/{target.club_id}")).json()
            entry = _squad_entry(club, target.person_id)
            assert entry["first_name"] and entry["last_name"], "The name stays"
            assert entry["profile_public"] is False
            # The photo goes with the page — no photo travels with the name either.
            assert (await client.get(photo)).status_code == 404
            assert (await client.get(photo, headers=me)).status_code == 200

            # The sailor themselves still opens their own page, and sees it is hidden.
            own = await client.get(f"/api/people/{target.person_id}", headers=me)
            assert own.status_code == 200
            assert own.json()["profile_public"] is False

            on = await client.patch("/api/people/me", headers=me, json={"profile_public": True})
            assert on.json()["profile_public"] is True
            assert (await client.get(f"/api/people/{target.person_id}")).status_code == 200
            club = (await client.get(f"/api/clubs/{target.club_id}")).json()
            assert _squad_entry(club, target.person_id)["profile_public"] is True
            await client.delete("/api/people/me/photo", headers=me)

    async def test_connected_people_still_open_a_hidden_page(self, client, caplog):
        """The admin and a manager of the sailor's club see the page; a stranger with an
        account does not, and neither does editorial (decided 2026-10-24)."""
        async with _squad_person("s4.circle@example.com") as target:
            await make_user(target.email)
            me = auth_headers(await login_as(client, target.email, caplog))
            await client.patch("/api/people/me", headers=me, json={"profile_public": False})

            await make_user("s4.editor@example.com", Role.EDITOR)
            await make_user("s4.manager@example.com", Role.TEAM_MANAGER, club_id=target.club_id)
            await make_user("s4.stranger@example.com")
            path = f"/api/people/{target.person_id}"
            for email, expected in [
                ("s4.editor@example.com", 404),
                ("s4.manager@example.com", 200),
                ("s4.stranger@example.com", 404),
            ]:
                headers = auth_headers(await login_as(client, email, caplog))
                assert (await client.get(path, headers=headers)).status_code == expected, email

            await client.patch("/api/people/me", headers=me, json={"profile_public": True})

    async def test_management_sees_the_setting_but_cannot_flip_it(self, client, caplog):
        """The one field on the person record that management does not maintain."""
        admin = await _admin(client, caplog)
        person_id = await _new_person(
            client, admin, email="s4.adult@example.com", birth_date=_ADULT_BIRTH
        )
        response = await client.patch(
            f"/api/admin/people/{person_id}", headers=admin, json={"profile_public": False}
        )
        assert response.status_code == 200, response.text
        assert response.json()["profile_public"] is True

    async def test_the_default_follows_age(self, client, caplog):
        """An adult's profile starts public, a minor's starts off; no birth date counts as
        an adult."""
        admin = await _admin(client, caplog)
        adult = await _new_person(client, admin, email="s4.a@example.com", birth_date=_ADULT_BIRTH)
        minor = await _new_person(
            client, admin, email="s4.m@example.com", birth_date=_minor_birth()
        )
        unknown = await _new_person(client, admin, email="s4.u@example.com", birth_date=None)

        assert (await client.get(f"/api/people/{adult}")).status_code == 200
        assert (await client.get(f"/api/people/{minor}")).status_code == 404
        assert (await client.get(f"/api/people/{unknown}")).status_code == 200

        # The minor turns it on themselves.
        await make_user("s4.m@example.com")
        me = auth_headers(await login_as(client, "s4.m@example.com", caplog))
        assert (await client.get("/api/people/me", headers=me)).json()["profile_public"] is False
        await client.patch("/api/people/me", headers=me, json={"profile_public": True})
        assert (await client.get(f"/api/people/{minor}")).status_code == 200
