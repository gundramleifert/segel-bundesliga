"""Story VA-15: the event and its pairing list sent to SAP Sailing.

Against **the local SAP Sailing** (`deploy/sap-local/`, `tests/sap_double.py`), the
double of SAP's hosted server — no simulation: what SAP now holds is asked of SAP, the
draw of a race from its race log. Skipped when no local SAP answers. Each test sends to a
leaderboard of its own (a venue named with a tag), so runs never meet at SAP.

Like the import tests, **each test sends from its own database**: a small matchday — four
teams of three clubs (one club with two teams), two boats, two flights of two races —
arranged directly, since no endpoint builds a drawn event in one call.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.imports.common import link_key
from app.imports.sap import SOURCE, SapClient, import_sap
from app.imports.sap_send import SapWriter, SendRefused, send_event
from app.models import (
    Base,
    Boat,
    Club,
    Event,
    EventStatus,
    ExternalId,
    Flight,
    Race,
    RaceEntry,
    RaceStatus,
    ResultsSource,
    Series,
    Team,
    Venue,
)
from tests import sap_double
from tests.sap_double import LocalSap
from tests.standings import points

pytestmark = pytest.mark.skipif(
    not sap_double.available(), reason="no local SAP Sailing (deploy/sap-local/README.md)"
)

BOATS = {colour: sap_double.boats()[colour] for colour in ("BLACK", "GREEN")}
CLUB_NAMES = {
    "ASVW": "Akademischer Segelverein Warnemünde",
    "NRV": "Norddeutscher Regatta Verein",
    "KYC": "Kieler Yacht-Club",
}
#: (club code, team number, boat colour in F1 R1, F1 R2, F2 R1, F2 R2) — four teams on two
#: boats: two race in each race.
DRAW = [
    ("ASVW", 1, "BLACK", None, "GREEN", None),
    ("NRV", 1, "GREEN", None, None, "BLACK"),
    ("KYC", 1, None, "BLACK", "BLACK", None),
    ("KYC", 2, None, "GREEN", None, "GREEN"),
]


#: The series every test's act belongs to — SAP's season group of that name is shared by
#: all of them, and stays: only each test's own event, regatta and leaderboard go.
SEASON = "2. Segel-Bundesliga 2027"


@pytest.fixture
def city() -> str:
    return f"Warnemünde {uuid4().hex[:6]}"


@pytest.fixture
def name(city) -> str:
    """The leaderboard the send names at SAP (`sap_send.leaderboard_name`)."""
    return f"{SEASON} - {city} (4)"


@pytest.fixture(autouse=True)
def sap(name):
    """The test's event at the local SAP — deleted afterwards, so SAP holds only what
    someone sent on purpose."""
    local = LocalSap(name)
    yield local
    local.delete()
    local.close()


@pytest.fixture
async def db(empty_database, city):
    engine = create_async_engine(empty_database)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with sessions() as session:
        clubs = {
            code: Club(slug=code.lower(), name=name, short_name=code)
            for code, name in CLUB_NAMES.items()
        }
        series = Series(
            slug="dsbl-2-2027",
            name=SEASON,
            short_name="2. Liga 2027",
            year=2027,
            level=2,
        )
        venue = Venue(slug="warnemuende", name="Warnemünde", city=city)
        event = Event(
            slug="dsbl-2-2027-warnemuende",
            title="Act 4 Warnemünde",
            matchday=4,
            starts_on=date(2027, 8, 20),
            ends_on=date(2027, 8, 22),
            status=EventStatus.PLANNED,
            team_count=4,
            boat_count=2,
            flight_count=2,
            series=series,
            venue=venue,
        )
        session.add_all([*clubs.values(), series, venue, event])
        await session.flush()
        boats = {c: Boat(event_id=event.id, number=i, color=c) for i, c in enumerate(BOATS, 1)}
        teams = [
            Team(name=f"{code} {n}", club_id=clubs[code].id, number=n, event_id=event.id)
            for code, n, *_ in DRAW
        ]
        flights = [Flight(event_id=event.id, number=n) for n in (1, 2)]
        session.add_all([*boats.values(), *teams, *flights])
        await session.flush()
        races = [
            Race(flight_id=flight.id, number_in_flight=k, sequence=2 * (flight.number - 1) + k)
            for flight in flights
            for k in (1, 2)
        ]
        session.add_all(races)
        await session.flush()
        for team, row in zip(teams, DRAW, strict=True):
            for race, colour in zip(races, row[2:], strict=True):
                if colour:
                    session.add(
                        RaceEntry(race_id=race.id, team_id=team.id, boat_id=boats[colour].id)
                    )
        await session.commit()
    yield sessions
    await engine.dispose()


async def _send(db, boats: dict[str, str] = BOATS):
    async with httpx.AsyncClient(auth=sap_double.AUTH, timeout=60) as http, db() as session:
        event = (await session.execute(select(Event))).scalar_one()
        return await send_event(session, SapWriter(http, sap_double.API), event.id, boats)


async def _import(db, name: str):
    async with httpx.AsyncClient(auth=sap_double.AUTH, timeout=60) as http:
        return await import_sap(
            db, SapClient(http, sap_double.API), names=[name], log=lambda _: None
        )


async def _team_names(db) -> dict[str, str]:
    """SAP's competitor id → our team's name, through the links the send stored."""
    async with db() as session:
        return {
            await link_key(session, Team, SOURCE, team.id): team.name
            for team in (await session.execute(select(Team))).scalars()
        }


class TestSendTheEventToSap:
    async def test_sap_holds_the_event_its_teams_and_our_draw(self, db, sap, name):
        """Story VA-15, Journey step J-10.16: one send makes the event, a flight per race
        column with its races as fleets, the teams under their club codes, and every race's
        team-on-boat pairs."""
        report = await _send(db)

        assert report.errors == []
        assert (report.teams_created, report.races) == (4, 4)
        assert name in sap_double.leaderboards()
        flights = next(s for s in sap.regatta()["series"] if s["name"] == "Flights")
        assert flights["races"] == ["F1", "F2"]
        assert [f["name"] for f in flights["fleets"]] == ["Race 1", "Race 2"]
        # In SAP's colours for the races: blue, yellow (and green for a third).
        assert [f["color"] for f in flights["fleets"]] == [
            {"r": 39, "g": 140, "b": 194},
            {"r": 251, "g": 186, "b": 0},
        ]
        # A club entering two teams is told apart by number (VA-13).
        assert sorted(sap.competitors()) == ["ASVW", "KYC 1", "KYC 2", "NRV"]
        # Named as SAP names the league's teams: the club in full, the code as short name.
        assert sorted(sap.names().items()) == [
            ("ASVW", "Akademischer Segelverein Warnemünde"),
            ("KYC 1", "Kieler Yacht-Club"),
            ("KYC 2", "Kieler Yacht-Club 2"),
            ("NRV", "Norddeutscher Regatta Verein"),
        ]
        team_of = await _team_names(db)
        async with db() as session:
            event = (await session.execute(select(Event))).scalar_one()
            assert event.sap_leaderboard == name
            # Sent, it is scored there (VA-14): results come from SAP from now on.
            assert event.results_source == ResultsSource.SAP
            assert await link_key(session, Event, SOURCE, event.id) == name
        assert {team_of[c]: b for c, b in sap.draw("F1", "Race 1").items()} == {
            "ASVW 1": BOATS["BLACK"],
            "NRV 1": BOATS["GREEN"],
        }
        assert {team_of[c]: b for c, b in sap.draw("F2", "Race 2").items()} == {
            "NRV 1": BOATS["BLACK"],
            "KYC 2": BOATS["GREEN"],
        }

    async def test_the_act_is_in_the_seasons_leaderboard_group(self, db, sap, name):
        """Story VA-15: an act of a series goes into the season's leaderboard group, as SAP
        keeps the league — the group named as the series, with an overall leaderboard,
        and the act's event referring to it. Sending again adds nothing twice."""
        await _send(db)
        report = await _send(db)

        assert report.errors == [] and report.group == SEASON
        group = sap.group(SEASON)
        assert group["hasOverallLeaderboard"] is True
        held = [b["name"] if isinstance(b, dict) else b for b in group["leaderboards"]]
        assert held.count(name) == 1
        assert [g["name"] for g in sap.event()["leaderboardGroups"]] == [SEASON]

    async def test_sending_again_replaces_the_draw_and_keeps_the_teams(self, db, sap, name):
        """Story VA-15: a second send — after a new draw — makes no second event and no
        second team; SAP's draw is ours as it now stands."""
        await _send(db)
        async with db() as session:  # a new draw: ASVW and NRV swap boats in F1 R1
            entries = (
                (
                    await session.execute(
                        select(RaceEntry)
                        .join(Race)
                        .where(Race.sequence == 1)
                        .order_by(RaceEntry.id)
                    )
                )
                .scalars()
                .all()
            )
            # Swapped by delete and add: (race, boat) is unique, so a swap in place collides.
            swapped = [
                (e.race_id, e.team_id, b.boat_id)
                for e, b in zip(entries, entries[::-1], strict=True)
            ]
            for entry in entries:
                await session.delete(entry)
            await session.flush()
            session.add_all(RaceEntry(race_id=r, team_id=t, boat_id=b) for r, t, b in swapped)
            await session.commit()

        report = await _send(db)

        assert (report.teams_created, report.teams_kept, report.races) == (0, 4, 4)
        assert sap_double.leaderboards().count(name) == 1 and len(sap.competitors()) == 4
        flights = next(s for s in sap.regatta()["series"] if s["name"] == "Flights")
        assert flights["races"] == ["F1", "F2"]
        team_of = await _team_names(db)
        assert {team_of[c]: b for c, b in sap.draw("F1", "Race 1").items()} == {
            "ASVW 1": BOATS["GREEN"],
            "NRV 1": BOATS["BLACK"],
        }
        assert sum(len(sap.draw(f"F{f}", f"Race {r}")) for f in (1, 2) for r in (1, 2)) == 8

    async def test_a_team_gone_at_sap_is_made_again(self, db, sap):
        """Story VA-15: a team the site linked to SAP is no longer there (SAP's data was
        cleaned up) — the next send makes it again and the link follows the new one."""
        await _send(db)
        async with db() as session:  # the link now names a competitor SAP does not have
            asvw = (await session.execute(select(Team).where(Team.name == "ASVW 1"))).scalar_one()
            row = (
                await session.execute(
                    select(ExternalId).where(
                        ExternalId.source == SOURCE,
                        ExternalId.entity_type == Team.__tablename__,
                        ExternalId.entity_id == asvw.id,
                    )
                )
            ).scalar_one()
            row.external_key = str(uuid4())
            await session.commit()

        report = await _send(db)

        assert report.errors == []
        assert (report.teams_created, report.teams_kept) == (1, 3)
        team_of = await _team_names(db)
        # The team SAP lost a link to is a new competitor; the other three are the ones sent.
        assert set(team_of) <= sap.competitor_ids()
        assert {team_of[c]: b for c, b in sap.draw("F1", "Race 1").items()}["ASVW 1"] == BOATS[
            "BLACK"
        ]

    async def test_a_started_event_is_not_sent(self, db, name):
        """Story VA-15: once the first race froze the event (VA-8), SAP's draw stays the one
        sailed — the send is refused before anything reaches SAP."""
        async with db() as session:
            race = (await session.execute(select(Race).where(Race.sequence == 1))).scalar_one()
            race.status = RaceStatus.FINISHED
            race.started_at = datetime(2027, 8, 20, 10, tzinfo=UTC)
            await session.commit()

        with pytest.raises(SendRefused, match="froze"):
            await _send(db)
        assert name not in sap_double.leaderboards()

    async def test_a_boat_without_its_sap_boat_is_named(self, db, name):
        """Story VA-15: a boat colour SAP has no boat for is named, and nothing is sent."""
        with pytest.raises(SendRefused, match="GREEN"):
            await _send(db, {"BLACK": BOATS["BLACK"]})
        assert name not in sap_double.leaderboards()


class TestBothDirections:
    async def test_the_draw_goes_to_sap_and_the_results_come_back(self, db, sap, name):
        """Stories VA-15, WL-5, Journey step J-10.7: configuration flows to SAP, results
        flow back. The event and its draw are sent; the race committee scores a flight at
        SAP; the import takes the places onto the very teams, boats and races of our draw —
        no second event, team or boat — and the points are derived here."""
        await _send(db)
        by_code = sap.competitors()
        # F1: ASVW beats NRV in race 1, KYC 2 beats KYC 1 in race 2.
        sap.enter("F1", "Race 1", [(by_code["ASVW"], 1, "NONE"), (by_code["NRV"], 2, "NONE")])
        sap.enter("F1", "Race 2", [(by_code["KYC 2"], 1, "NONE"), (by_code["KYC 1"], 2, "NONE")])

        report = await _import(db, name)

        assert report.errors == [] and report.conflicts == []
        async with db() as session:
            assert len((await session.execute(select(Event))).scalars().all()) == 1
            assert len((await session.execute(select(Team))).scalars().all()) == 4
            assert len((await session.execute(select(Boat))).scalars().all()) == 2
            rows = (
                await session.execute(
                    select(
                        Team.name,
                        Race.sequence,
                        RaceEntry.finish_position,
                        Boat.color,
                        RaceEntry.team_id,
                        RaceEntry.race_id,
                    )
                    .join(RaceEntry, RaceEntry.team_id == Team.id)
                    .join(Race, Race.id == RaceEntry.race_id)
                    .join(Boat, Boat.id == RaceEntry.boat_id)
                    .where(RaceEntry.finish_position.is_not(None))
                    .order_by(Race.sequence, RaceEntry.finish_position)
                )
            ).all()
            event_id = (await session.execute(select(Event.id))).scalar_one()
            derived = await points(session, event_id)
        rows = [(*r[:4], derived[(r[4], r[5])]) for r in rows]
        # On the boat our draw gave each team, with the points derived here.
        assert [tuple(r) for r in rows] == [
            ("ASVW 1", 1, 1, "BLACK", 1.0),
            ("NRV 1", 1, 2, "GREEN", 2.0),
            ("KYC 2", 2, 1, "GREEN", 1.0),
            ("KYC 1", 2, 2, "BLACK", 2.0),
        ]

    async def test_points_that_differ_at_sap_are_reported_and_ours_stand(self, db, sap, name):
        """Story WL-5, Journey step J-10.9: SAP's net points not ours — SAP's series
        discards a race, ours does not — the import says so for the teams it touches, and
        the points here stay the ones derived here."""
        await _send(db)
        by_code = sap.competitors()
        sap.enter("F1", "Race 1", [(by_code["ASVW"], 1, "NONE"), (by_code["NRV"], 2, "NONE")])
        sap.discard([1])

        report = await _import(db, name)

        assert sum("net points here" in w for w in report.warnings) == 2
        async with db() as session:
            event_id = (await session.execute(select(Event.id))).scalar_one()
            derived = sorted((await points(session, event_id)).values())
        assert derived == [1.0, 2.0]
