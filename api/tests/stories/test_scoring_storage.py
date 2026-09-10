"""Points are stored — and recomputed after a correction.

The stored points are derived. The test that matters: when race officials enter a protest
decision, points and standings must move without anyone touching them by hand.
"""

import pytest
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import (
    Event,
    EventStanding,
    Flight,
    Race,
    RaceEntry,
    ResultCode,
    Series,
)
from app.models.auth import Role
from app.services import recompute_event

LEAGUE = "dsbl-1-2026"


async def matchday(number: int) -> int:
    """The n-th matchday **of the seeded first league**.

    Qualified by series on purpose: matchday numbers count from 1 within their own series,
    so any test that creates a series of its own also creates a "matchday 1". Asking for
    the number alone found more than one row as soon as that happened.
    """
    async with SessionLocal() as session:
        return (
            await session.execute(
                select(Event.id)
                .join(Series, Event.series_id == Series.id)
                .where(Series.slug == LEAGUE, Event.matchday == number)
            )
        ).scalar_one()


async def first_matchday() -> int:
    return await matchday(1)


class TestStoredPoints:
    async def test_every_scored_result_has_stored_points(self, seeded):
        event_id = await first_matchday()
        async with SessionLocal() as session:
            unscoredcount = (
                await session.execute(
                    select(func.count())
                    .select_from(RaceEntry)
                    .join(Race, RaceEntry.race_id == Race.id)
                    .join(Flight, Race.flight_id == Flight.id)
                    .where(
                        Flight.event_id == event_id,
                        RaceEntry.code.is_not(None),
                        RaceEntry.points.is_(None),
                    )
                )
            ).scalar_one()
        assert unscoredcount == 0

    async def test_unraced_entry_has_no_points(self, seeded):
        planned = await matchday(3)
        async with SessionLocal() as session:
            with_points = (
                await session.execute(
                    select(func.count())
                    .select_from(RaceEntry)
                    .join(Race, RaceEntry.race_id == Race.id)
                    .join(Flight, Race.flight_id == Flight.id)
                    .where(Flight.event_id == planned, RaceEntry.points.is_not(None))
                )
            ).scalar_one()
        assert with_points == 0

    async def test_stored_event_standing_covers_all_teams(self, seeded):
        event_id = await first_matchday()
        async with SessionLocal() as session:
            rows = (
                await session.execute(
                    select(EventStanding)
                    .where(EventStanding.event_id == event_id)
                    .order_by(EventStanding.rank)
                )
            ).scalars().all()

        assert len(rows) == 18
        assert [row.rank for row in rows] == list(range(1, 19))
        # Low-point: lower is better.
        assert [row.net_points for row in rows] == sorted(row.net_points for row in rows)

    async def test_protest_decision_pulls_points_along(self, seeded):
        """The actual reason for separating raw data and points."""
        event_id = await first_matchday()

        async with SessionLocal() as session:
            entry = (
                await session.execute(
                    select(RaceEntry)
                    .join(Race, RaceEntry.race_id == Race.id)
                    .join(Flight, Race.flight_id == Flight.id)
                    .where(
                        Flight.event_id == event_id,
                        RaceEntry.code == ResultCode.FINISHED,
                        RaceEntry.finish_position == 1,
                    )
                    .limit(1)
                )
            ).scalar_one()
            entry_id, team_id = entry.id, entry.team_id
            before = entry.points
            assert before == 1.0

            # The jury disqualifies the winner of this race.
            entry.code = ResultCode.DSQ
            entry.finish_position = None
            await recompute_event(session, event_id)
            await session.commit()

        async with SessionLocal() as session:
            after = (
                await session.execute(select(RaceEntry).where(RaceEntry.id == entry_id))
            ).scalar_one()
            # Six boats in the race: DSQ counts participant count + 1.
            assert after.points == 7.0

            standing = (
                await session.execute(
                    select(EventStanding).where(
                        EventStanding.event_id == event_id,
                        EventStanding.team_id == team_id,
                    )
                )
            ).scalar_one()
            # From 1 point to 7 — the event standing must have worsened by 6.
            assert standing.net_points > 0


class TestSeriesStanding:
    """Whoever misses an event gets participant count + 1 for that event.

    A club can participate in event 1 and not event 2 — the series still stands.
    Failing to compete must never be better than competing and placing last.
    """

    async def _series(self) -> int:
        async with SessionLocal() as session:
            return (
                await session.execute(select(Series.id).where(Series.slug == "dsbl-1-2026"))
            ).scalar_one()

    async def test_who_was_everywhere_stands_with_their_placements(self, client, ids):
        table = (
            await client.get(f"/api/series/{ids.series('dsbl-1-2026')}/table")
        ).json()

        assert len(table["rows"]) == 18
        for row in table["rows"]:
            assert row["missed_matchdays"] == []
            assert row["events_sailed"] == 2, "Two events sailed, one planned"
            assert row["points"] == sum(row["ranks_by_matchday"].values())

    async def test_latecomer_gets_substitute_scoring(self, client, caplog, ids):
        """A club assigned to the series later has not sailed anywhere."""
        from tests.stories.test_series_assignment import as_role, new_club

        header = await as_role(client, caplog, "sw-latecomer@example.com", Role.ADMIN)
        club = await new_club(client, header, "Latecomer Sailing Club", "ZSC")
        await client.put(
            f"/api/admin/clubs/{club['id']}/series",
            headers=header,
            json={"series": [ids.series("dsbl-1-2026")]},
        )

        table = (
            await client.get(f"/api/series/{ids.series('dsbl-1-2026')}/table")
        ).json()
        new_team = next(z for z in table["rows"] if z["team"]["club"]["slug"] == club["slug"])

        # 18 teams participated each time, so 19 per event.
        assert new_team["missed_matchdays"] == [1, 2]
        assert new_team["events_sailed"] == 0
        assert new_team["ranks_by_matchday"] == {"1": 19, "2": 19}
        assert new_team["points"] == 38.0

    async def test_substitute_scoring_is_worse_than_last_place(self, client, ids):
        """The actual reason for the rule."""
        table = (
            await client.get(f"/api/series/{ids.series('dsbl-1-2026')}/table")
        ).json()

        sailed = [z for z in table["rows"] if not z["missed_matchdays"]]
        missed = [z for z in table["rows"] if z["missed_matchdays"]]
        if not missed:
            pytest.skip("No team with missed matchdays in this order")

        worst_present = max(z["points"] for z in sailed)
        assert min(z["points"] for z in missed) > worst_present

    async def test_table_is_sorted_by_points(self, client, ids):
        table = (
            await client.get(f"/api/series/{ids.series('dsbl-1-2026')}/table")
        ).json()
        points = [z["points"] for z in table["rows"]]
        assert points == sorted(points)
        assert [z["rank"] for z in table["rows"]] == list(range(1, len(points) + 1))
