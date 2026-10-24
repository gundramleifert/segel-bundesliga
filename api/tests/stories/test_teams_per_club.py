"""Story VA-13: a club enters more than one team — an option of the event.

The seed's ASVW is registered for the 2. Liga 2026 with a squad; each test makes its own
acts in that series, so the seeded acts stay as they are.
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Team, TeamMembership
from tests.stories.test_create_event import admin
from tests.stories.test_login_and_roles import login_as, make_user
from tests.stories.test_registration import auth_headers

SERIES = "dsbl-2-2026"


async def _act(client, headers, ids, *, teams_per_club: int, team_count: int = 18) -> int:
    response = await client.post(
        "/api/admin/events",
        headers=headers,
        json={
            "title": f"Act {uuid4().hex[:6]}",
            "series": ids.series(SERIES),
            "team_count": team_count,
            "teams_per_club": teams_per_club,
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["teams_per_club"] == teams_per_club
    return response.json()["id"]


async def _enter(client, headers, event_id: int, clubs: list[int]):
    return await client.put(
        f"/api/admin/events/{event_id}/clubs", headers=headers, json={"clubs": clubs}
    )


async def _asvw_squad(ids) -> list[int]:
    async with SessionLocal() as session:
        registration = (
            await session.execute(
                select(Team.id).where(
                    Team.club_id == ids.club("asvw"),
                    Team.series_id == ids.series(SERIES),
                    Team.event_id.is_(None),
                )
            )
        ).scalar_one()
        return list(
            (
                await session.execute(
                    select(TeamMembership.sailor_id)
                    .where(TeamMembership.team_id == registration)
                    .order_by(TeamMembership.sailor_id)
                )
            ).scalars()
        )


class TestTeamsPerClub:
    """VA-13: as an organizer I let a club enter several teams in one event."""

    async def test_a_club_listed_twice_enters_two_teams(self, client, caplog, ids):
        """Story VA-13: `ASVW` and `ASVW 2`, each its own entry, numbered."""
        headers = await admin(client, caplog, "va13-two@example.com")
        event_id = await _act(client, headers, ids, teams_per_club=2)
        asvw = ids.club("asvw")

        response = await _enter(client, headers, event_id, [asvw, asvw])
        assert response.status_code == 200, response.text
        teams = sorted((p["number"], p["name"]) for p in response.json() if p["club"]["id"] == asvw)
        assert teams == [(1, "ASVW"), (2, "ASVW 2")]

    async def test_more_teams_than_the_event_allows_are_refused(self, client, caplog, ids):
        """Story VA-13: one team per club is the normal case; a second needs the option."""
        headers = await admin(client, caplog, "va13-one@example.com")
        event_id = await _act(client, headers, ids, teams_per_club=1)
        asvw = ids.club("asvw")

        response = await _enter(client, headers, event_id, [asvw, asvw])
        assert response.status_code == 422, response.text
        assert response.json()["type"].endswith("/too-many-teams-per-club")

    async def test_any_number_of_teams_up_to_the_event_s_size(self, client, caplog, ids):
        """Story VA-13: three teams of one club, and fewer again takes the highest away."""
        headers = await admin(client, caplog, "va13-three@example.com")
        event_id = await _act(client, headers, ids, teams_per_club=3)
        asvw = ids.club("asvw")

        three = await _enter(client, headers, event_id, [asvw, asvw, asvw])
        assert three.status_code == 200, three.text
        assert sorted(p["name"] for p in three.json() if p["club"]["id"] == asvw) == [
            "ASVW",
            "ASVW 2",
            "ASVW 3",
        ]
        two = await _enter(client, headers, event_id, [asvw, asvw])
        assert sorted(p["number"] for p in two.json() if p["club"]["id"] == asvw) == [1, 2]

    async def test_a_club_cannot_enter_more_teams_than_the_event_has(self, client, caplog, ids):
        """Story VA-13: the option runs from 1 up to the number of teams."""
        headers = await admin(client, caplog, "va13-size@example.com")
        response = await client.post(
            "/api/admin/events",
            headers=headers,
            json={"title": "Too many", "team_count": 6, "teams_per_club": 7},
        )
        assert response.status_code == 422, response.text

        event_id = await _act(client, headers, ids, teams_per_club=2, team_count=6)
        patched = await client.patch(
            f"/api/admin/events/{event_id}", headers=headers, json={"teams_per_club": 7}
        )
        assert patched.status_code == 422, patched.text

    async def test_every_team_is_lined_up_from_the_club_s_one_squad(self, client, caplog, ids):
        """Story VA-13: a sailor sails for ASVW 1 at one act and ASVW 2 at the next —
        always for ASVW, and never for two teams in the same act."""
        headers = await admin(client, caplog, "va13-squad@example.com")
        asvw = ids.club("asvw")
        first_act = await _act(client, headers, ids, teams_per_club=2)
        second_act = await _act(client, headers, ids, teams_per_club=2)
        teams: dict[tuple[int, int], int] = {}
        for event_id in (first_act, second_act):
            entered = await _enter(client, headers, event_id, [asvw, asvw])
            assert entered.status_code == 200, entered.text
            for p in entered.json():
                if p["club"]["id"] == asvw:
                    teams[(event_id, p["number"])] = p["team_id"]
        squad = await _asvw_squad(ids)
        sailor = squad[0]

        async def line_up(event_id: int, number: int, sailor_ids: list[int]):
            return await client.put(
                f"/api/admin/events/{event_id}/crew",
                headers=headers,
                json={
                    "team_id": teams[(event_id, number)],
                    "members": [{"sailor_id": s} for s in sailor_ids],
                },
            )

        first = await line_up(first_act, 1, [sailor])
        assert first.status_code == 200, first.text
        second = await line_up(second_act, 2, [sailor])
        assert second.status_code == 200, second.text
        assert second.json()["team_id"] == teams[(second_act, 2)]

        # The same act, the club's other team: one boat at a time.
        twice = await line_up(first_act, 2, [sailor])
        assert twice.status_code == 409, twice.text
        # Team 2 draws from the same squad — another sailor of it is fine.
        other = await line_up(first_act, 2, [squad[1]])
        assert other.status_code == 200, other.text

    async def test_the_event_s_organizer_sets_and_changes_the_number(self, client, caplog, ids):
        """Story VA-13: the organizer's parameter, changeable — but never below the teams a
        club has already entered."""
        headers = await admin(client, caplog, "va13-org-admin@example.com")
        event_id = await _act(client, headers, ids, teams_per_club=1)
        email = "va13-organizer@example.com"
        await make_user(email)
        granted = await client.post(
            "/api/auth/tuples",
            headers=headers,
            json={"user": email, "relation": "manager", "object": f"event:{event_id}"},
        )
        assert granted.status_code == 201, granted.text
        organizer = auth_headers(await login_as(client, email, caplog))
        asvw = ids.club("asvw")

        raised = await client.patch(
            f"/api/admin/events/{event_id}", headers=organizer, json={"teams_per_club": 3}
        )
        assert raised.status_code == 200, raised.text
        assert raised.json()["teams_per_club"] == 3
        entered = await _enter(client, organizer, event_id, [asvw, asvw, asvw])
        assert entered.status_code == 200, entered.text

        # Two would leave `ASVW 3` beyond the limit: take the team away first.
        lowered = await client.patch(
            f"/api/admin/events/{event_id}", headers=organizer, json={"teams_per_club": 2}
        )
        assert lowered.status_code == 422, lowered.text
        assert lowered.json()["type"].endswith("/teams-per-club-below-entered")
        assert (await _enter(client, organizer, event_id, [asvw, asvw])).status_code == 200
        lowered = await client.patch(
            f"/api/admin/events/{event_id}", headers=organizer, json={"teams_per_club": 2}
        )
        assert lowered.status_code == 200, lowered.text

    async def test_the_club_page_names_each_team_s_crew(self, client, caplog, ids):
        """Story VA-13: `ASVW` and `ASVW 2` in one act are two crews on the club page, each
        under its own name — never one list of eight."""
        headers = await admin(client, caplog, "va13-club-page@example.com")
        asvw = ids.club("asvw")
        event_id = await _act(client, headers, ids, teams_per_club=2)
        published = await client.post(f"/api/admin/events/{event_id}/publish", headers=headers)
        assert published.status_code == 200, published.text
        entered = await _enter(client, headers, event_id, [asvw, asvw])
        team_ids = {p["number"]: p["team_id"] for p in entered.json() if p["club"]["id"] == asvw}
        squad = await _asvw_squad(ids)
        for number, sailors in ((1, squad[:2]), (2, squad[2:4])):
            lined_up = await client.put(
                f"/api/admin/events/{event_id}/crew",
                headers=headers,
                json={"team_id": team_ids[number], "members": [{"sailor_id": s} for s in sailors]},
            )
            assert lined_up.status_code == 200, lined_up.text

        page = (await client.get(f"/api/clubs/{asvw}", params={"year": 2026})).json()
        entry = next(
            e for team in page["teams"] for e in team["events"] if e["event"]["id"] == event_id
        )
        crews = {c["team_name"]: sorted(m["id"] for m in c["members"]) for c in entry["crews"]}
        assert crews == {"ASVW": squad[:2], "ASVW 2": squad[2:4]}
