"""The 1. and 2. Liga 2026 from TracTrac's scoreboards and the league's pairing lists.

What `scripts/record-dsbl-2026.py` recorded into `app/seed_data/dsbl-2026/` (Story A-14):
imported into a database of its own — this site's clubs and leagues, nothing else — so
the seed's own 2026 acts do not stand in the way and every number can be held against
TracTrac's.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.imports.tractrac import FOLDER, import_tractrac
from app.models import Base, Club, Event, EventStanding, League, RaceEntry, Series, Team
from app.models.racing import ResultCode
from app.seed import CLUBS
from app.services.standings import recompute_series

RECORDS = sorted(FOLDER.glob("*-liga-act-*.json"))


@pytest.fixture
async def db(tmp_path):
    from app.text import slugify

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'tractrac.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with sessions() as session:
        for level in (1, 2):
            session.add(
                League(
                    slug=f"{level}-liga",
                    short_name=f"{level}. Liga",
                    name=f"{level}. Segel-Bundesliga",
                    position=level,
                )
            )
        session.add_all(
            Club(slug=slugify(short), name=name, short_name=short) for name, short, *_ in CLUBS
        )
        await session.commit()
    yield sessions
    await engine.dispose()


async def _import(db, **kwargs):
    return await import_tractrac(db, log=lambda _: None, **kwargs)


async def _event(session, division: int, act: int) -> Event:
    return (
        await session.execute(
            select(Event)
            .join(Series, Series.id == Event.series_id)
            .where(Series.slug == f"dsbl-{division}-2026", Event.matchday == act)
        )
    ).scalar_one()


async def _team(session, event: Event, code: str) -> Team:
    return (
        await session.execute(
            select(Team)
            .join(Club, Club.id == Team.club_id)
            .where(Team.event_id == event.id, Club.short_name == code)
        )
    ).scalar_one()


class TestTracTracImport:
    """Story A-14: the 1. and 2. Liga 2026, as TracTrac scored them."""

    async def test_every_act_arrives_scored_as_tractrac_scored_it(self, db):
        """Story A-14: eleven acts, and every club's rank and points here are TracTrac's."""
        report = await _import(db)
        assert report.errors == [], report.render()
        assert report.conflicts == [] and report.unassigned == [], report.render()
        # The points derived here agree with the scoreboard's — no difference reported.
        assert report.warnings == [], report.render()

        async with db() as session:
            for path in RECORDS:
                record = json.loads(path.read_text("utf-8"))
                event = await _event(session, record["division"], record["act"])
                assert event.team_count == 18 and event.boat_count == 6
                assert event.flight_count == 16
                standings = {
                    club: (rank, net)
                    for club, rank, net in (
                        await session.execute(
                            select(Club.short_name, EventStanding.rank, EventStanding.net_points)
                            .join(Team, Team.id == EventStanding.team_id)
                            .join(Club, Club.id == Team.club_id)
                            .where(EventStanding.event_id == event.id)
                        )
                    ).all()
                }
                assert len(standings) == 18, path.name
                for row in record["scoreboard"]:
                    ours = next(v for k, v in standings.items() if _same(k, row["code"]))
                    assert ours[1] == pytest.approx(row["points"], abs=0.05), (path.name, row)
                    # Ties too: more firsts, then seconds … of places sailed (a redress is
                    # none) — 2. Liga act 1's RSN and Konstanz on 24 included.
                    assert ours[0] == row["rank"], (path.name, row)

    async def test_the_series_tables_are_the_season_scoreboards(self, db):
        """Story A-14: the 2026 tables come out as TracTrac's season scoreboards — the
        1. Liga's NRV on 12 points, the 2. Liga's Konstanzer YC on 22."""
        await _import(db)
        async with db() as session:
            tops = {}
            for division in (1, 2):
                series = (
                    await session.execute(
                        select(Series).where(Series.slug == f"dsbl-{division}-2026")
                    )
                ).scalar_one()
                rows = await recompute_series(session, series.id)
                names = {
                    team_id: code
                    for team_id, code in (
                        await session.execute(
                            select(Team.id, Club.short_name).join(Club, Club.id == Team.club_id)
                        )
                    ).all()
                }
                tops[division] = [(names[r.team_id], r.points) for r in rows[:3]]
        assert tops[1] == [("NRV", 12), ("JSC", 35), ("MYC", 40)]
        assert tops[2][0] == ("KYC (BA)", 22)
        assert sorted(tops[2][1:]) == [("LYC", 28), ("RSN", 28)]

    async def test_a_league_code_is_mapped_to_this_site_s_club(self, db):
        """Story A-14: the league's `BOH-YC` is this site's Bocholter Yachtclub `BoYC` —
        no club is created for a code spelled differently."""
        await _import(db)
        async with db() as session:
            assert (await session.execute(select(func.count(Club.id)))).scalar_one() == len(CLUBS)
            event = await _event(session, 1, 6)
            bocholt = await _team(session, event, "BoYC")
            assert bocholt is not None

    async def test_a_redress_and_a_matchday_penalty_are_kept(self, db):
        """Stories A-14, WL-4: Flensburg's redress in act 2 (its points shown only in the
        total) and Warnemünde's 3-point penalty there."""
        await _import(db)
        async with db() as session:
            event = await _event(session, 2, 2)
            flensburg = await _team(session, event, "FSC")
            redress = (
                await session.execute(
                    select(RaceEntry).where(
                        RaceEntry.team_id == flensburg.id, RaceEntry.code == ResultCode.RDG
                    )
                )
            ).scalar_one()
            assert redress.redress_points == pytest.approx(1.33)
            warnemuende = await _team(session, event, "ASVW")
            assert warnemuende.penalty_points == 3

    async def test_a_second_run_changes_nothing(self, db):
        """Story A-14: repeatable — the second run creates and updates nothing."""
        await _import(db)
        report = await _import(db)
        assert report.errors == [] and report.conflicts == [], report.render()
        assert not report.created and not report.updated, report.render()

    async def test_a_result_corrected_here_is_kept(self, db):
        """Story A-14: the race committee wins — a result changed here after the import is
        reported as a conflict on the next run, never overwritten."""
        await _import(db)
        async with db() as session:
            event = await _event(session, 1, 3)
            entry = (
                await session.execute(
                    select(RaceEntry)
                    .join(Team, Team.id == RaceEntry.team_id)
                    .where(Team.event_id == event.id, RaceEntry.finish_position == 1)
                    .limit(1)
                )
            ).scalar_one()
            entry.code, entry.finish_position = ResultCode.DSQ, None
            await session.commit()
            entry_id = entry.id
        report = await _import(db)
        assert len(report.conflicts) == 1, report.render()
        async with db() as session:
            assert (await session.get(RaceEntry, entry_id)).code == ResultCode.DSQ


def _same(ours: str, league: str) -> bool:
    from app.imports.tractrac import our_code

    return ours == our_code(league)


class TestTracTracImportOnTheSeed:
    """Story A-14: on a database that already has its own 2026 acts — the seed's."""

    async def test_an_act_drawn_here_is_left_alone(self, db):
        """Story A-14: an act of the same matchday that already has a pairing list here —
        drawn, nothing sailed — is a conflict, not taken over: its draw and the league's
        would mix."""
        from app.models import Boat, Flight, Race

        async with db() as session:
            series = Series(
                slug="dsbl-1-2026",
                name="1. Segel-Bundesliga 2026",
                short_name="1. Liga 2026",
                year=2026,
                level=1,
                league_id=(
                    await session.execute(select(League.id).where(League.slug == "1-liga"))
                ).scalar_one(),
            )
            session.add(series)
            await session.flush()
            event = Event(slug="dsbl-1-2026-act-3", title="Act 3", matchday=3, series_id=series.id)
            session.add(event)
            await session.flush()
            club = (await session.execute(select(Club).limit(1))).scalar_one()
            team = Team(
                name=club.short_name, club_id=club.id, series_id=series.id, event_id=event.id
            )
            boat = Boat(event_id=event.id, number=1)
            flight = Flight(event_id=event.id, number=1)
            session.add_all([team, boat, flight])
            await session.flush()
            race = Race(flight_id=flight.id, number_in_flight=1, sequence=1)
            session.add(race)
            await session.flush()
            session.add(RaceEntry(race_id=race.id, team_id=team.id, boat_id=boat.id))
            await session.commit()

        report = await _import(db)
        assert report.errors == [], report.render()
        assert [c for c in report.conflicts if "act-3" in c.split(":")[0]] == [
            f"dsbl-1-2026-act-3: act 3 of 1. Segel-Bundesliga 2026 is event {event.id} here "
            "and has a pairing list or results already — left alone"
        ]
