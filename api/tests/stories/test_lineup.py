"""User Story V-2: Four sailors for the matchday — from the season squad.

The rule: A club registers X people for the league. For a matchday, it selects the crew
from those. Anyone not registered cannot be lined up.
"""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Event, Series, Team, TeamMembership
from app.models.auth import Role
from tests.stories.test_login_and_roles import login_as, make_user

MATCHDAY_SLUG = "dsbl-1-2026-act-3"


async def matchday_id() -> int:
    async with SessionLocal() as session:
        return (
            await session.execute(select(Event.id).where(Event.slug == MATCHDAY_SLUG))
        ).scalar_one()


async def first_team() -> tuple[int, int, list[int]]:
    """A team from the first series: (team_id, club_id, squad IDs).

    This is the **registration for the series** — the squad is attached to it. Lineup is
    set at the entry to the individual act; the endpoint finds it via the club itself.

    Deliberately the **last**, not the first: the club and sailor pages check the first,
    and these stories change lineups. Two stories should not interfere with each other.
    """
    async with SessionLocal() as session:
        team = (
            await session.execute(
                select(Team)
                .join(Series, Team.series_id == Series.id)
                .where(Series.slug == "dsbl-1-2026", Team.event_id.is_(None))
                .order_by(Team.id.desc())
                .limit(1)
            )
        ).scalar_one()
        squad = list(
            (
                await session.execute(
                    select(TeamMembership.sailor_id)
                    .where(TeamMembership.team_id == team.id)
                    .order_by(TeamMembership.id)
                )
            ).scalars()
        )
        return team.id, team.club_id, squad


async def other_sailor(except_team: int) -> int:
    """Someone registered in a different team."""
    async with SessionLocal() as session:
        return (
            await session.execute(
                select(TeamMembership.sailor_id)
                .where(TeamMembership.team_id != except_team)
                .limit(1)
            )
        ).scalar_one()


async def club_leadership(client, caplog, email: str, club_id: int) -> dict[str, str]:
    await make_user(email, Role.CLUB_MANAGER, club_id=club_id)
    return {"Authorization": f"Bearer {await login_as(client, email, caplog)}"}


class TestLineup:
    async def test_four_from_squad_can_be_lined_up(self, client, caplog):
        team_id, club_id, squad = await first_team()
        headers = await club_leadership(client, caplog, "au1@example.com", club_id)

        response = await client.put(
            f"/api/admin/events/{await matchday_id()}/crew",
            headers=headers,
            json={
                "team_id": team_id,
                "members": [
                    {"sailor_id": squad[0], "role": "helm"},
                    *({"sailor_id": s, "role": "crew"} for s in squad[1:4]),
                ],
            },
        )
        assert response.status_code == 200, response.text
        lineup = response.json()

        assert lineup["crew_size"] == 4
        assert len(lineup["members"]) == 4
        assert lineup["members"][0]["role"] == "helm"

    async def test_unregistered_sailors_cannot_be_lined_up(self, client, caplog):
        """The core rule — enforced at the endpoint, not just in the UI."""
        team_id, club_id, squad = await first_team()
        external = await other_sailor(team_id)
        headers = await club_leadership(client, caplog, "au2@example.com", club_id)

        response = await client.put(
            f"/api/admin/events/{await matchday_id()}/crew",
            headers=headers,
            json={
                "team_id": team_id,
                "members": [
                    {"sailor_id": squad[0], "role": "helm"},
                    {"sailor_id": squad[1], "role": "crew"},
                    {"sailor_id": squad[2], "role": "crew"},
                    {"sailor_id": external, "role": "crew"},
                ],
            },
        )
        assert response.status_code == 422
        assert "Not in this team's squad" in response.json()["detail"]

    async def test_crew_size_is_flexible(self, client, caplog):
        """Four is the typical size, not a hard limit.

        Illness, late registrations, and non-standard formats would not work otherwise.
        """
        team_id, club_id, squad = await first_team()
        headers = await club_leadership(client, caplog, "au3@example.com", club_id)

        response = await client.put(
            f"/api/admin/events/{await matchday_id()}/crew",
            headers=headers,
            json={
                "team_id": team_id,
                "members": [{"sailor_id": s, "role": "crew"} for s in squad[:3]],
            },
        )
        assert response.status_code == 200, response.text
        assert len(response.json()["members"]) == 3
        # The guide value still appears in the response — for the UI.
        assert response.json()["crew_size"] == 4

    async def test_no_one_appears_twice_in_lineup(self, client, caplog):
        team_id, club_id, squad = await first_team()
        headers = await club_leadership(client, caplog, "au4@example.com", club_id)

        response = await client.put(
            f"/api/admin/events/{await matchday_id()}/crew",
            headers=headers,
            json={
                "team_id": team_id,
                "members": [
                    {"sailor_id": squad[0], "role": "helm"},
                    {"sailor_id": squad[0], "role": "crew"},
                    {"sailor_id": squad[1], "role": "crew"},
                    {"sailor_id": squad[2], "role": "crew"},
                ],
            },
        )
        assert response.status_code == 422
        assert "twice" in response.json()["detail"]

    async def test_cannot_line_up_another_clubs_team(self, client, caplog):
        team_id, club_id, squad = await first_team()
        # Logged in as another club's leadership.
        headers = await club_leadership(client, caplog, "au5@example.com", club_id + 1)

        response = await client.put(
            f"/api/admin/events/{await matchday_id()}/crew",
            headers=headers,
            json={
                "team_id": team_id,
                "members": [{"sailor_id": s, "role": "crew"} for s in squad[:4]],
            },
        )
        assert response.status_code == 403
        assert "own team" in response.json()["detail"]

    async def test_race_officers_can_intervene_on_short_notice(self, client, caplog):
        team_id, _club_id, squad = await first_team()
        await make_user("au6@example.com", Role.RACE_OFFICER)
        headers = {"Authorization": f"Bearer {await login_as(client, 'au6@example.com', caplog)}"}

        response = await client.put(
            f"/api/admin/events/{await matchday_id()}/crew",
            headers=headers,
            json={
                "team_id": team_id,
                "members": [{"sailor_id": s, "role": "crew"} for s in squad[4:8]],
            },
        )
        assert response.status_code == 200

    async def test_empty_list_clears_lineup(self, client, caplog):
        team_id, club_id, squad = await first_team()
        headers = await club_leadership(client, caplog, "au7@example.com", club_id)
        path = f"/api/admin/events/{await matchday_id()}/crew"

        await client.put(
            path,
            headers=headers,
            json={
                "team_id": team_id,
                "members": [{"sailor_id": s, "role": "crew"} for s in squad[:4]],
            },
        )
        empty = await client.put(path, headers=headers, json={"team_id": team_id, "members": []})
        assert empty.status_code == 200
        assert empty.json()["members"] == []

    async def test_nonparticipating_clubs_cannot_be_lined_up(self, client, caplog):
        """Lineup is set at the event entry — not for every event that exists.

        A standalone event without a series takes no participants: initially no one
        participates there, so no one can be lined up either.
        """
        team_id, club_id, _squad = await first_team()
        await make_user("au8@example.com", Role.ADMIN)
        headers = {"Authorization": f"Bearer {await login_as(client, 'au8@example.com', caplog)}"}

        created = (
            await client.post(
                "/api/admin/events",
                headers=headers,
                json={"title": "Free cup without series", "starts_on": "2026-12-19"},
            )
        ).json()

        response = await client.put(
            f"/api/admin/events/{created['id']}/crew",
            headers=headers,
            json={"team_id": team_id, "members": []},
        )
        assert response.status_code == 422
        assert "does not participate in this event" in response.json()["detail"]

    async def test_unauthenticated_users_cannot_do_anything(self, client):
        team_id, _club_id, _squad = await first_team()
        response = await client.put(
            f"/api/admin/events/{await matchday_id()}/crew",
            json={"team_id": team_id, "members": []},
        )
        assert response.status_code == 401
