"""What a club's offices give on the events it hosts and who may hold them (Stories Z-2,
A-8, VA-6; review 4.1, 4.3).

Both were found by the concept review and held as ``xfail`` until fixed: a club's team
manager organized every league act the club hosted, and a club's admin could make any
account on the site its treasurer — who reads every claimant's IBAN.
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Event
from app.models.auth import Grant, Relation
from tests.accounts import account
from tests.stories.test_login_and_roles import _problem_code, login_as
from tests.stories.test_registration import auth_headers


async def signed_in(client, caplog, email: str, *grants: Grant) -> dict[str, str]:
    await account(email, *grants)
    return auth_headers(await login_as(client, email, caplog))


async def test_a_clubs_team_manager_does_not_organize_the_league_acts_it_hosts(client, caplog):
    """Story Z-2: a club's `manager` decides who sails for it. Hosting a league act makes
    the club pay for it and lend its officials — it does not make the team manager the
    act's organizer, who can change its clubs, cancel it and read the officials'
    documents. The club's admin, its leadership, still is."""
    async with SessionLocal() as session:
        act = (
            (
                await session.execute(
                    select(Event).where(
                        Event.host_club_id.is_not(None),
                        Event.series_id.is_not(None),
                        Event.published.is_(True),
                    )
                )
            )
            .scalars()
            .first()
        )
    tag = uuid4().hex[:6]
    team_manager = await signed_in(
        client,
        caplog,
        f"tm-{tag}@example.com",
        Grant(relation=Relation.MANAGER, club_id=act.host_club_id),
    )
    club_admin = await signed_in(
        client,
        caplog,
        f"ca-{tag}@example.com",
        Grant(relation=Relation.ADMIN, club_id=act.host_club_id),
    )

    url = f"/api/events/{act.id}/access"
    assert (await client.get(url, headers=team_manager)).json()["manage"] is False
    assert (await client.get(url, headers=club_admin)).json()["manage"] is True


async def test_a_clubs_team_manager_hosts_no_event_of_their_own(client, caplog, season):
    """Story VA-6: an event outside a series is its host club's leadership's to create —
    its admin, not the team manager."""
    club = next(iter(season.squads))
    headers = await signed_in(
        client,
        caplog,
        f"tm-host-{uuid4().hex[:6]}@example.com",
        Grant(relation=Relation.MANAGER, club_id=club),
    )
    response = await client.post(
        "/api/admin/events", headers=headers, json={"title": "Club Cup", "host_club_id": club}
    )
    assert response.status_code == 403, response.text


async def test_a_clubs_admin_cannot_make_a_stranger_its_treasurer(client, caplog, season):
    """Story A-8: the treasurer sees every claimant's IBAN. A club's admin appoints one
    among the club's members — not any account on the site found by its address."""
    club = next(iter(season.squads))
    tag = uuid4().hex[:6]
    headers = await signed_in(
        client, caplog, f"ca-{tag}@example.com", Grant(relation=Relation.ADMIN, club_id=club)
    )
    await account(f"stranger-{tag}@example.com")
    await account(f"member-{tag}@example.com", Grant(relation=Relation.MEMBER, club_id=club))

    def appoint(email: str):
        return client.post(
            "/api/auth/tuples",
            json={"user": email, "relation": "treasurer", "object": f"club:{club}"},
            headers=headers,
        )

    refused = await appoint(f"stranger-{tag}@example.com")
    assert refused.status_code == 409, refused.text
    assert _problem_code(refused) == "tuple-not-a-member"

    appointed = await appoint(f"member-{tag}@example.com")
    assert appointed.status_code == 201, appointed.text
    deleted = await client.delete(f"/api/auth/tuples/{appointed.json()['id']}", headers=headers)
    assert deleted.status_code == 204
