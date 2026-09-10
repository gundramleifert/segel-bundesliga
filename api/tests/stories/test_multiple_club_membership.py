"""One person, multiple clubs — but once per competition.

A person can sail for multiple clubs: one in the first series, another in juniors. Within
**a single** series or event, they only appear once — otherwise they'd be racing against
themselves.

At the event level, the database enforces the rule. At the series level, the series is one
level above the team and cannot be expressed as a foreign key; the endpoint that registers
the squad enforces it there. These tests document the invariant.
"""

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models import Club, Event, EventCrew, Sailor, Series, Team, TeamMembership
from app.models.org import CrewRole


class TestMultipleClubs:
    """Allowed: the same person registers for two clubs in different series."""

    async def test_person_can_register_in_two_series_for_two_clubs(self, seeded):
        async with SessionLocal() as session:
            # Deliberately the last teams per series: the club and sailor pages check
            # the first, and this test changes squads.
            teams = (
                await session.execute(
                    select(Team, Series)
                    .join(Series, Team.series_id == Series.id)
                    .join(Club, Team.club_id == Club.id)
                    # The squad is attached to the series registration, not the entry to
                    # a single act.
                    .where(Team.event_id.is_(None))
                    .order_by(Series.id, Team.id.desc())
                )
            ).all()

            first = next(t for t, s in teams if s.slug == "dsbl-1-2026")
            juniors = next(t for t, s in teams if s.slug == "junioren-2026")

            person = Sailor(
                first_name="Double",
                last_name="Sailor",
                email="double.sailor@example.com",
            )
            session.add(person)
            await session.flush()

            session.add_all(
                [
                    TeamMembership(
                        team_id=first.id, sailor_id=person.id, role=CrewRole.SUBSTITUTE
                    ),
                    TeamMembership(
                        team_id=juniors.id, sailor_id=person.id, role=CrewRole.SUBSTITUTE
                    ),
                ]
            )
            await session.commit()

            count = (
                await session.execute(
                    select(func.count())
                    .select_from(TeamMembership)
                    .where(TeamMembership.sailor_id == person.id)
                )
            ).scalar_one()
            assert count == 2


class TestOncePerCompetition:
    async def test_no_one_registered_twice_in_same_series(self, seeded):
        """The invariant across the entire dataset.

        If this test fails, an endpoint registered someone twice in the same series — the
        rule only exists on paper then.
        """
        async with SessionLocal() as session:
            duplicates = (
                await session.execute(
                    select(Team.series_id, TeamMembership.sailor_id, func.count())
                    .join(Team, TeamMembership.team_id == Team.id)
                    .where(Team.event_id.is_(None))
                    .group_by(Team.series_id, TeamMembership.sailor_id)
                    .having(func.count() > 1)
                )
            ).all()

        assert not duplicates, (
            "These people are registered multiple times in the same series "
            f"(series, person, count): {duplicates}"
        )

    async def test_database_rejects_second_lineup_in_same_event(
        self, seeded
    ):
        """At the event level, the database enforces the rule."""
        async with SessionLocal() as session:
            crew = (
                await session.execute(select(EventCrew).limit(1))
            ).scalar_one()
            other_team = (
                await session.execute(
                    select(Team.id).where(Team.id != crew.team_id).limit(1)
                )
            ).scalar_one()

            session.add(
                EventCrew(
                    event_id=crew.event_id,
                    team_id=other_team,
                    sailor_id=crew.sailor_id,
                    role=CrewRole.CREW,
                )
            )
            with pytest.raises(IntegrityError):
                await session.commit()

    async def test_no_one_sails_for_two_teams_in_one_act(self, seeded):
        async with SessionLocal() as session:
            duplicates = (
                await session.execute(
                    select(EventCrew.event_id, EventCrew.sailor_id, func.count())
                    .group_by(EventCrew.event_id, EventCrew.sailor_id)
                    .having(func.count() > 1)
                )
            ).all()
        assert not duplicates, f"Duplicate lineups: {duplicates}"

    async def test_endpoint_rejects_foreign_team(self, client, caplog):
        """Via the API — the database is the last barrier, not the only one."""
        from tests.stories.test_lineup import club_leadership, first_team, matchday_id

        team_id, club_id, squad = await first_team()
        headers = await club_leadership(client, caplog, "mv1@example.com", club_id)

        async with SessionLocal() as session:
            foreign_team = (
                await session.execute(
                    select(Team.id)
                    .join(Event, Event.series_id == Team.series_id)
                    .where(Team.id != team_id)
                    .limit(1)
                )
            ).scalar_one()

        response = await client.put(
            f"/api/admin/events/{await matchday_id()}/crew",
            headers=headers,
            json={
                "team_id": foreign_team,
                "members": [{"sailor_id": squad[0], "role": "helm"}],
            },
        )
        assert response.status_code == 403
