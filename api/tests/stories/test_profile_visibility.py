"""User story S-4: a sailor decides whether their own profile page is public.

The **name** stays on every competition record — squad, lineup, results — and only the
**page** (`GET /api/sailors/{id}`) and the link to it go away. The squad and lineup
outputs carry `profile_public`, so the frontend renders a hidden profile's name as plain
text instead of a link.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import NamedTuple

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Club, Sailor, Series, Team, TeamMembership
from app.models.auth import Role
from tests.stories.test_login_and_roles import login_as, make_user
from tests.stories.test_registration import auth_headers
from tests.stories.test_sailor_profile import (
    _ADULT_BIRTH,
    _admin,
    _jpeg_bytes,
    _minor_birth,
    _new_sailor,
)


class SquadSailor(NamedTuple):
    """A seeded sailor on a public squad, linked to an account for this test."""

    sailor_id: int
    club_id: int
    email: str


@asynccontextmanager
async def _squad_sailor(email: str) -> AsyncIterator[SquadSailor]:
    """NRV's first squad member of a published 2026 series, re-addressed to ``email`` so
    the test signs in as them, and given back unchanged afterwards — other stories in the
    same worker count on the seed."""
    async with SessionLocal() as session:
        sailor, club_id = (
            await session.execute(
                select(Sailor, Club.id)
                .join(TeamMembership, TeamMembership.sailor_id == Sailor.id)
                .join(Team, TeamMembership.team_id == Team.id)
                .join(Club, Team.club_id == Club.id)
                .join(Series, Team.series_id == Series.id)
                .where(
                    Club.slug == "nrv",
                    Team.event_id.is_(None),
                    Series.year == 2026,
                    Series.published.is_(True),
                )
                .order_by(Sailor.id)
                .limit(1)
            )
        ).one()
        original = (sailor.email, sailor.birth_date, sailor.profile_public_choice)
        sailor.email, sailor.birth_date, sailor.profile_public_choice = email, None, None
        await session.commit()
        sailor_id = sailor.id
    try:
        yield SquadSailor(sailor_id, club_id, email)
    finally:
        async with SessionLocal() as session:
            sailor = await session.get(Sailor, sailor_id)
            sailor.email, sailor.birth_date, sailor.profile_public_choice = original
            await session.commit()


def _squad_entry(club: dict, sailor_id: int) -> dict:
    for team in club["teams"]:
        for member in team["members"]:
            if member["id"] == sailor_id:
                return member
    raise AssertionError(f"Sailor {sailor_id} not on the club page")


class TestProfileVisibility:
    """S-4: As a sailor, I want to decide whether my profile page is public."""

    async def test_switching_off_hides_the_page_from_guests_but_not_the_name(self, client, caplog):
        """Off: a guest gets 404 for the page, the squad still names the sailor — with
        `profile_public` false, so no link is built. On again: immediate, symmetric."""
        async with _squad_sailor("s4.owner@example.com") as target:
            await make_user(target.email)
            me = auth_headers(await login_as(client, target.email, caplog))

            assert (await client.get("/api/sailors/me", headers=me)).json()[
                "profile_public"
            ] is True
            assert (await client.get(f"/api/sailors/{target.sailor_id}")).status_code == 200

            await client.patch("/api/sailors/me", headers=me, json={"birth_date": _ADULT_BIRTH})
            upload = await client.post(
                "/api/sailors/me/photo",
                headers=me,
                files={"file": ("me.jpg", _jpeg_bytes(), "image/jpeg")},
            )
            assert upload.status_code == 200, upload.text
            photo = f"/api/sailors/{target.sailor_id}/photo"
            assert (await client.get(photo)).status_code == 200

            off = await client.patch("/api/sailors/me", headers=me, json={"profile_public": False})
            assert off.status_code == 200, off.text
            assert off.json()["profile_public"] is False

            assert (await client.get(f"/api/sailors/{target.sailor_id}")).status_code == 404
            club = (await client.get(f"/api/clubs/{target.club_id}")).json()
            entry = _squad_entry(club, target.sailor_id)
            assert entry["first_name"] and entry["last_name"], "The name stays"
            assert entry["profile_public"] is False
            # The photo goes with the page — no photo travels with the name either.
            assert (await client.get(photo)).status_code == 404
            assert (await client.get(photo, headers=me)).status_code == 200

            # The sailor themselves still opens their own page, and sees it is hidden.
            own = await client.get(f"/api/sailors/{target.sailor_id}", headers=me)
            assert own.status_code == 200
            assert own.json()["profile_public"] is False

            on = await client.patch("/api/sailors/me", headers=me, json={"profile_public": True})
            assert on.json()["profile_public"] is True
            assert (await client.get(f"/api/sailors/{target.sailor_id}")).status_code == 200
            club = (await client.get(f"/api/clubs/{target.club_id}")).json()
            assert _squad_entry(club, target.sailor_id)["profile_public"] is True
            await client.delete("/api/sailors/me/photo", headers=me)

    async def test_connected_people_still_open_a_hidden_page(self, client, caplog):
        """admin/editor and a manager of the sailor's club see the page; a stranger with an
        account does not."""
        async with _squad_sailor("s4.circle@example.com") as target:
            await make_user(target.email)
            me = auth_headers(await login_as(client, target.email, caplog))
            await client.patch("/api/sailors/me", headers=me, json={"profile_public": False})

            await make_user("s4.editor@example.com", Role.EDITOR)
            await make_user("s4.manager@example.com", Role.TEAM_MANAGER, club_id=target.club_id)
            await make_user("s4.stranger@example.com")
            path = f"/api/sailors/{target.sailor_id}"
            for email, expected in [
                ("s4.editor@example.com", 200),
                ("s4.manager@example.com", 200),
                ("s4.stranger@example.com", 404),
            ]:
                headers = auth_headers(await login_as(client, email, caplog))
                assert (await client.get(path, headers=headers)).status_code == expected, email

            await client.patch("/api/sailors/me", headers=me, json={"profile_public": True})

    async def test_management_sees_the_setting_but_cannot_flip_it(self, client, caplog):
        """The one field on the sailor record that management does not maintain."""
        admin = await _admin(client, caplog)
        sailor_id = await _new_sailor(
            client, admin, email="s4.adult@example.com", birth_date=_ADULT_BIRTH
        )
        response = await client.patch(
            f"/api/admin/sailors/{sailor_id}", headers=admin, json={"profile_public": False}
        )
        assert response.status_code == 200, response.text
        assert response.json()["profile_public"] is True

    async def test_the_default_follows_age(self, client, caplog):
        """An adult's profile starts public, a minor's starts off; no birth date counts as
        an adult."""
        admin = await _admin(client, caplog)
        adult = await _new_sailor(client, admin, email="s4.a@example.com", birth_date=_ADULT_BIRTH)
        minor = await _new_sailor(
            client, admin, email="s4.m@example.com", birth_date=_minor_birth()
        )
        unknown = await _new_sailor(client, admin, email="s4.u@example.com", birth_date=None)

        assert (await client.get(f"/api/sailors/{adult}")).status_code == 200
        assert (await client.get(f"/api/sailors/{minor}")).status_code == 404
        assert (await client.get(f"/api/sailors/{unknown}")).status_code == 200

        # The minor turns it on themselves.
        await make_user("s4.m@example.com")
        me = auth_headers(await login_as(client, "s4.m@example.com", caplog))
        assert (await client.get("/api/sailors/me", headers=me)).json()["profile_public"] is False
        await client.patch("/api/sailors/me", headers=me, json={"profile_public": True})
        assert (await client.get(f"/api/sailors/{minor}")).status_code == 200
