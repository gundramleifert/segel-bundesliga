"""User Story V-2: Four sailors for the matchday — from the season squad.

The rule: A club registers X people for the league. For a matchday, it selects the crew
from those. Anyone not registered cannot be lined up.
"""

import pytest
from sqlalchemy import delete

from app.db import SessionLocal
from app.models import CrewRole, EventCrew
from app.models.auth import Role
from tests.stories.test_login_and_roles import login_as, make_user


def first_team(season) -> tuple[int, int, list[int]]:
    """A team of the practice season: (team_id, club_id, squad IDs).

    This is the **registration for the series** — the squad is attached to it. Lineup is
    set at the entry to the individual act; the endpoint finds it via the club itself.

    Deliberately the **last** club, not the first: the club and sailor pages check the
    first, and these stories change lineups. Two stories should not interfere.
    """
    club_id = max(season.registrations, key=season.registrations.__getitem__)
    return season.registrations[club_id], club_id, season.squads[club_id]


def other_person(season, club_id: int) -> int:
    """Someone registered in a different club's squad."""
    return next(squad[0] for club, squad in season.squads.items() if club != club_id)


@pytest.fixture(autouse=True)
async def _restore_lineup(season):
    """These stories rewrite the planned act's lineup; put the season's back after each."""
    yield
    _team_id, club_id, squad = first_team(season)
    entry = season.entries[(season.planned, club_id)]
    async with SessionLocal() as session:
        await session.execute(
            delete(EventCrew).where(
                EventCrew.event_id == season.planned, EventCrew.team_id == entry
            )
        )
        session.add_all(
            EventCrew(
                event_id=season.planned,
                team_id=entry,
                person_id=person,
                role=CrewRole.HELM if position == 0 else CrewRole.CREW,
            )
            for position, person in enumerate(squad[:4])
        )
        await session.commit()


async def club_leadership(client, caplog, email: str, club_id: int) -> dict[str, str]:
    await make_user(email, Role.TEAM_MANAGER, club_id=club_id)
    return {"Authorization": f"Bearer {await login_as(client, email, caplog)}"}


class TestLineup:
    async def test_four_from_squad_can_be_lined_up(self, client, caplog, season):
        """Four is the typical size, not a hard limit — and an empty list clears the lineup.

        Illness, late registrations, and non-standard formats would not work otherwise.
        """
        team_id, club_id, squad = first_team(season)
        headers = await club_leadership(client, caplog, "au1@example.com", club_id)
        path = f"/api/admin/events/{season.planned}/crew"

        response = await client.put(
            path,
            headers=headers,
            json={
                "team_id": team_id,
                "members": [
                    {"person_id": squad[0], "role": "helm"},
                    *({"person_id": s, "role": "crew"} for s in squad[1:4]),
                ],
            },
        )
        assert response.status_code == 200, response.text
        lineup = response.json()

        assert lineup["crew_size"] == 4
        assert len(lineup["members"]) == 4
        assert lineup["members"][0]["role"] == "helm"

        three = await client.put(
            path,
            headers=headers,
            json={
                "team_id": team_id,
                "members": [{"person_id": s, "role": "crew"} for s in squad[:3]],
            },
        )
        assert three.status_code == 200, three.text
        assert len(three.json()["members"]) == 3
        # The guide value still appears in the response — for the UI.
        assert three.json()["crew_size"] == 4

        empty = await client.put(path, headers=headers, json={"team_id": team_id, "members": []})
        assert empty.status_code == 200
        assert empty.json()["members"] == []

    async def test_unregistered_sailors_cannot_be_lined_up(self, client, caplog, season):
        """The core rule — enforced at the endpoint, not just in the UI."""
        team_id, club_id, squad = first_team(season)
        external = other_person(season, club_id)
        headers = await club_leadership(client, caplog, "au2@example.com", club_id)

        response = await client.put(
            f"/api/admin/events/{season.planned}/crew",
            headers=headers,
            json={
                "team_id": team_id,
                "members": [
                    {"person_id": squad[0], "role": "helm"},
                    {"person_id": squad[1], "role": "crew"},
                    {"person_id": squad[2], "role": "crew"},
                    {"person_id": external, "role": "crew"},
                ],
            },
        )
        assert response.status_code == 422
        assert response.json()["type"] == "/errors/lineup-not-in-squad"

    async def test_no_one_appears_twice_in_lineup(self, client, caplog, season):
        team_id, club_id, squad = first_team(season)
        headers = await club_leadership(client, caplog, "au4@example.com", club_id)

        response = await client.put(
            f"/api/admin/events/{season.planned}/crew",
            headers=headers,
            json={
                "team_id": team_id,
                "members": [
                    {"person_id": squad[0], "role": "helm"},
                    {"person_id": squad[0], "role": "crew"},
                    {"person_id": squad[1], "role": "crew"},
                    {"person_id": squad[2], "role": "crew"},
                ],
            },
        )
        assert response.status_code == 422
        assert response.json()["type"] == "/errors/lineup-duplicate-person"

    async def test_cannot_line_up_another_clubs_team(self, client, caplog, season):
        team_id, club_id, squad = first_team(season)
        # Logged in as another club's leadership.
        headers = await club_leadership(client, caplog, "au5@example.com", club_id + 1)

        response = await client.put(
            f"/api/admin/events/{season.planned}/crew",
            headers=headers,
            json={
                "team_id": team_id,
                "members": [{"person_id": s, "role": "crew"} for s in squad[:4]],
            },
        )
        assert response.status_code == 403
        assert response.json()["type"] == "/errors/lineup-not-own-team"

    async def test_race_officers_can_intervene_on_short_notice(self, client, caplog, season):
        team_id, _club_id, squad = first_team(season)
        await make_user("au6@example.com", Role.RACE_OFFICER)
        headers = {"Authorization": f"Bearer {await login_as(client, 'au6@example.com', caplog)}"}

        response = await client.put(
            f"/api/admin/events/{season.planned}/crew",
            headers=headers,
            json={
                "team_id": team_id,
                "members": [{"person_id": s, "role": "crew"} for s in squad[4:8]],
            },
        )
        assert response.status_code == 200

    async def test_nonparticipating_clubs_cannot_be_lined_up(self, client, caplog, season):
        """Lineup is set at the event entry — not for every event that exists.

        A standalone event without a series takes no participants: initially no one
        participates there, so no one can be lined up either.
        """
        team_id, club_id, _squad = first_team(season)
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
        assert response.json()["type"] == "/errors/club-not-in-event"

    async def test_unauthenticated_users_cannot_do_anything(self, client, season):
        team_id, _club_id, _squad = first_team(season)
        response = await client.put(
            f"/api/admin/events/{season.planned}/crew",
            json={"team_id": team_id, "members": []},
        )
        assert response.status_code == 401
