"""User story V-17: a club accepts the data processing agreement before working with its
people here — the club's admin, once per version, confirming they may sign for it.

Every test works on a fresh club whose admin is made with ``dpa_accepted=False``: the
helpers accept it for every other story's club.
"""

from uuid import uuid4

from app.db import SessionLocal
from app.models import Club
from app.models.auth import Role
from app.services.dpa import DPA_VERSION
from tests.stories.test_login_and_roles import (
    _admin_headers,
    _headers,
    _problem_code,
    make_user,
)


async def _club() -> int:
    async with SessionLocal() as session:
        club = Club(slug=f"dpa-{uuid4().hex[:8]}", name="Segelclub Vertrag", short_name="SCV")
        session.add(club)
        await session.commit()
        return club.id


async def _admin(client, caplog, club: int) -> dict[str, str]:
    email = f"board-{uuid4().hex[:6]}@example.com"
    await make_user(email, Role.CLUB_ADMIN, club_id=club, dpa_accepted=False)
    return await _headers(client, caplog, email)


async def _add_member(client, headers, club: int):
    email = f"m-{uuid4().hex[:6]}@example.com"
    await make_user(email)
    return await client.post(f"/api/clubs/{club}/members", headers=headers, json={"email": email})


class TestDpa:
    async def test_the_club_side_waits_for_the_agreement(self, client, caplog):
        """V-17: adding a member is `dpa-required` until the club's admin accepted; then
        it works, and the club's status says who accepted which version."""
        club = await _club()
        board = await _admin(client, caplog, club)

        refused = await _add_member(client, board, club)
        assert refused.status_code == 409, refused.text
        assert _problem_code(refused) == "dpa-required"
        assert refused.json()["club_id"] == club

        status = (await client.get(f"/api/clubs/{club}/dpa", headers=board)).json()
        assert status == {
            "version": DPA_VERSION,
            "accepted": False,
            "accepted_at": None,
            "accepted_by_name": None,
        }

        accepted = await client.post(
            f"/api/clubs/{club}/dpa",
            headers=board,
            json={"version": DPA_VERSION, "authorized": True},
        )
        assert accepted.status_code == 201, accepted.text
        assert accepted.json()["accepted"] is True
        assert accepted.json()["accepted_by_name"]

        assert (await _add_member(client, board, club)).status_code == 201

    async def test_accepting_needs_the_authority_and_the_current_version(self, client, caplog):
        """V-17: without confirming the authority to sign, or for an older version, the
        agreement is not accepted."""
        club = await _club()
        board = await _admin(client, caplog, club)
        url = f"/api/clubs/{club}/dpa"

        unconfirmed = await client.post(
            url, headers=board, json={"version": DPA_VERSION, "authorized": False}
        )
        assert unconfirmed.status_code == 422
        assert _problem_code(unconfirmed) == "dpa-authority-unconfirmed"

        outdated = await client.post(
            url, headers=board, json={"version": "1999-01-01", "authorized": True}
        )
        assert outdated.status_code == 409
        assert _problem_code(outdated) == "dpa-version-outdated"

        assert (await client.get(url, headers=board)).json()["accepted"] is False

    async def test_only_the_clubs_admin_accepts(self, client, caplog):
        """V-17: the club's team manager reads the status but cannot sign."""
        club = await _club()
        email = f"tm-{uuid4().hex[:6]}@example.com"
        await make_user(email, Role.TEAM_MANAGER, club_id=club, dpa_accepted=False)
        manager = await _headers(client, caplog, email)

        assert (await client.get(f"/api/clubs/{club}/dpa", headers=manager)).status_code == 200
        refused = await client.post(
            f"/api/clubs/{club}/dpa",
            headers=manager,
            json={"version": DPA_VERSION, "authorized": True},
        )
        assert refused.status_code == 403
        assert _problem_code(refused) == "dpa-forbidden"

    async def test_the_league_office_is_not_held_up(self, client, caplog):
        """V-17: the site's admin acts for the association, not the club — no agreement
        needed to add someone to a club that has none."""
        club = await _club()
        office = await _admin_headers(client, caplog)
        assert (await _add_member(client, office, club)).status_code == 201
