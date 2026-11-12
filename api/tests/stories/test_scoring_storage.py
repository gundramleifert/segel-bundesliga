"""Points are computed from the raw results, on every read — never stored (review 2.1).

The test that matters: when race officials enter a protest decision, points and standings
move without anyone touching them by hand, and without anyone remembering to recompute —
there is nothing stored that could stay behind.
"""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Flight, Race, RaceEntry, ResultCode
from app.models.auth import Role
from app.scoring.low_point import shared_ranks
from app.services.standings import compute_event


class TestComputedPoints:
    async def test_the_event_table_covers_every_team(self, season):
        async with SessionLocal() as session:
            scores = await compute_event(session, season.final)

        assert len(scores) == 18
        # Low-point: lower is better.
        assert [score.net for score in scores] == sorted(score.net for score in scores)

    async def test_an_unraced_entry_has_no_points(self, season):
        async with SessionLocal() as session:
            scores = await compute_event(session, season.planned)

        assert all(not score.points_by_race for score in scores)

    async def test_protest_decision_pulls_points_along(self, season):
        """The actual reason for separating raw data and points: one row changes, and
        the next read says so — with no recompute call to forget."""
        event_id = season.final

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
            entry_id, team_id, race_id = entry.id, entry.team_id, entry.race_id

            def points(scores) -> float:
                return next(s for s in scores if s.team_id == team_id).points_by_race[race_id]

            assert points(await compute_event(session, event_id)) == 1.0

            # The jury disqualifies the winner of this race.
            entry.code = ResultCode.DSQ
            entry.finish_position = None
            await session.commit()

        async with SessionLocal() as session:
            # Six boats in the race: DSQ counts participant count + 1.
            assert points(await compute_event(session, event_id)) == 7.0

            # The season is shared by the run: the protest is withdrawn again.
            after = await session.get(RaceEntry, entry_id)
            after.code = ResultCode.FINISHED
            after.finish_position = 1
            await session.commit()


class TestTies:
    """Review 2.5: a tie nothing breaks is shared; the series breaks ties by the acts in
    their sailing order."""

    def test_equal_keys_share_a_rank_and_the_next_one_skips(self):
        assert shared_ranks([1, 2, 2, 3]) == [1, 2, 2, 4]
        assert shared_ranks([(5.0, (1,)), (5.0, (1,))]) == [1, 1]
        assert shared_ranks([]) == []

    def test_the_series_tie_break_reads_the_latest_act_by_its_order_not_its_id(self):
        """Act 2 was created first, so its id (10) is lower than act 1's (20). Two clubs
        tie on points; the better in act 2 — the one sailed last — is ahead. Read by the
        highest id, act 1 would have decided."""
        from app.services.standings import SeriesRow, rank_series

        a = SeriesRow(team_id=1, points=3.0, event_ranks={20: 1, 10: 2})
        b = SeriesRow(team_id=2, points=3.0, event_ranks={20: 2, 10: 1})
        c = SeriesRow(team_id=3, points=3.0, event_ranks={20: 2, 10: 1})

        ranked = rank_series([a, b, c], sailed=[20, 10])

        assert [(row.team_id, row.rank) for row in ranked] == [(2, 1), (3, 1), (1, 3)]


class TestSeriesStanding:
    """Whoever misses an event gets participant count + 1 for that event.

    A club can participate in event 1 and not event 2 — the series still stands.
    Failing to compete must never be better than competing and placing last.
    """

    async def test_who_was_everywhere_stands_with_their_placements(self, client, season):
        table = (await client.get(f"/api/series/{season.series}/table")).json()

        assert len(table["rows"]) == 18
        for row in table["rows"]:
            assert row["missed_matchdays"] == []
            assert row["events_sailed"] == 2, "Two events sailed, one planned"
            assert row["points"] == sum(row["ranks_by_matchday"].values())
        # Sorted by points, ranked in that order.
        points = [z["points"] for z in table["rows"]]
        assert points == sorted(points)
        assert [z["rank"] for z in table["rows"]] == list(range(1, len(points) + 1))

    async def test_latecomer_gets_substitute_scoring(self, client, caplog, season):
        """A club assigned to the series later has not sailed anywhere — and the substitute
        scoring is worse than last place, the actual reason for the rule."""
        from tests.stories.test_series_assignment import as_role, new_club

        header = await as_role(client, caplog, "sw-latecomer@example.com", Role.ADMIN)
        club = await new_club(client, header, "Latecomer Sailing Club", "ZSC")
        series_path = f"/api/admin/clubs/{club['id']}/series"
        await client.put(series_path, headers=header, json={"series": [season.series]})
        try:
            table = (await client.get(f"/api/series/{season.series}/table")).json()
        finally:
            # The season is shared by the run: the latecomer leaves it again.
            await client.put(series_path, headers=header, json={"series": []})
        new_team = next(z for z in table["rows"] if z["team"]["club"]["slug"] == club["slug"])

        # 18 teams participated each time, so 19 per event.
        assert new_team["missed_matchdays"] == [1, 2]
        assert new_team["events_sailed"] == 0
        assert new_team["ranks_by_matchday"] == {"1": 19, "2": 19}
        assert new_team["points"] == 38.0

        sailed = [z for z in table["rows"] if not z["missed_matchdays"]]
        missed = [z for z in table["rows"] if z["missed_matchdays"]]
        assert min(z["points"] for z in missed) > max(z["points"] for z in sailed)
