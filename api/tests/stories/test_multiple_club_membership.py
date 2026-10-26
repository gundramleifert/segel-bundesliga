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
from app.models import EventCrew, Team, TeamMembership
from app.models.org import CrewRole


class TestOncePerCompetition:
    async def test_no_one_registered_twice_in_same_series(self, seeded):
        """The invariant across the entire dataset.

        If this test fails, an endpoint registered someone twice in the same series — the
        rule only exists on paper then.
        """
        async with SessionLocal() as session:
            duplicates = (
                await session.execute(
                    select(Team.series_id, TeamMembership.person_id, func.count())
                    .join(Team, TeamMembership.team_id == Team.id)
                    .where(Team.event_id.is_(None))
                    .group_by(Team.series_id, TeamMembership.person_id)
                    .having(func.count() > 1)
                )
            ).all()

        assert not duplicates, (
            "These people are registered multiple times in the same series "
            f"(series, person, count): {duplicates}"
        )

    async def test_database_rejects_second_lineup_in_same_event(self, seeded):
        """At the event level, the database enforces the rule."""
        async with SessionLocal() as session:
            crew = (await session.execute(select(EventCrew).limit(1))).scalar_one()
            other_team = (
                await session.execute(select(Team.id).where(Team.id != crew.team_id).limit(1))
            ).scalar_one()

            session.add(
                EventCrew(
                    event_id=crew.event_id,
                    team_id=other_team,
                    person_id=crew.person_id,
                    role=CrewRole.CREW,
                )
            )
            with pytest.raises(IntegrityError):
                await session.commit()
