"""Story VA-15: the event and its pairing list sent to SAP Sailing.

Never against a live SAP: a fake one answers here, keeping what it was sent, so the test
can ask what SAP would now hold. What the real API wants was tried against
`deploy/sap-local/` (2026-11-01) — fleets only on a new series, a boat with every team,
the draw per race after enabling its registration — and the fake answers the same way.

Like the import tests, **each test sends from its own database**: a small matchday — four
teams of three clubs (one club with two teams), two boats, two flights of two races —
arranged directly, since no endpoint builds a drawn event in one call.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import parse_qs, unquote

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.imports.common import link_key
from app.imports.sap import SOURCE, SapClient, import_sap
from app.imports.sap_send import SapWriter, send_event
from app.models import (
    Base,
    Boat,
    Club,
    Event,
    EventStatus,
    Flight,
    Race,
    RaceEntry,
    RaceStatus,
    Series,
    Team,
    Venue,
)

BOATS = {"BLACK": "sap-boat-black", "GREEN": "sap-boat-green"}
NAME = "2. Segel-Bundesliga 2027 - Warnemünde (4)"
#: (club code, team number, boat colour in F1 R1, F1 R2, F2 R1, F2 R2) — four teams on two
#: boats: two race in each race.
DRAW = [
    ("ASVW", 1, "BLACK", None, "GREEN", None),
    ("NRV", 1, "GREEN", None, None, "BLACK"),
    ("KYC", 1, None, "BLACK", "BLACK", None),
    ("KYC", 2, None, "GREEN", None, "GREEN"),
]


class FakeSap:
    """The endpoints the send uses, answering like SAP and keeping the state."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.events = 0
        self.fleets: list[str] = []
        self.columns: list[str] = []
        self.competitors: dict[str, dict[str, Any]] = {}
        self.enabled: set[tuple[str, str]] = set()
        #: (column, fleet) → competitor id → boat id
        self.draw: dict[tuple[str, str], dict[str, str]] = {}
        #: (column, fleet) → competitor id → place — what the race committee enters at SAP
        self.places: dict[tuple[str, str], dict[str, int]] = {}

    def finish(self, column: str, fleet: str, order: list[str]) -> None:
        """The race committee enters a race's finish at SAP: competitor ids, first first."""
        self.places[(column, fleet)] = {cid: place for place, cid in enumerate(order, 1)}

    def leaderboard(self) -> dict[str, Any]:
        """The v2 leaderboard, shaped like the recorded one (`tests/fixtures/sap/`)."""
        competitors = []
        for cid, data in self.competitors.items():
            columns = {}
            for (column, fleet), places in self.places.items():
                if cid in places:
                    boat = self.draw[(column, fleet)][cid]
                    columns[column] = {
                        "boat": {"id": boat, "name": boat, "sailId": None, "color": None},
                        "fleet": fleet,
                        "totalPoints": float(places[cid]),
                        "netPoints": float(places[cid]),
                        "maxPointsReason": "NONE",
                        "isDiscarded": False,
                        "rank": places[cid],
                        "trackedRank": places[cid],
                        "finished": True,
                    }
            net = sum(c["netPoints"] for c in columns.values())
            competitors.append(
                {
                    **data,
                    "name": data["shortName"],
                    "carriedPoints": None,
                    "netPoints": net,
                    "columns": columns,
                }
            )
        return {
            "name": NAME,
            "columnNames": self.columns,
            "trackedRacesInfo": [
                {
                    "raceColumnName": c,
                    "fleets": [{"name": f, "trackedRace": None} for f in self.fleets],
                }
                for c in self.columns
            ],
            "competitors": competitors,
            "lastScoringUpdate": None,
        }

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        path = unquote(request.url.path).removeprefix("/api/")
        query = {k: v[0] for k, v in parse_qs(request.url.query.decode()).items()}
        self.calls.append(f"{request.method} {path.split('/')[-1]}")
        regatta = f"v1/regattas/{NAME}"
        if request.method == "GET" and path == "v1/regattas":
            return httpx.Response(200, json=[{"name": NAME}] if self.events else [])
        if request.method == "GET" and path == f"v2/leaderboards/{NAME}":
            return httpx.Response(200, json=self.leaderboard())
        if request.method == "GET" and path == regatta:
            if not self.events:
                return httpx.Response(404)
            series = [{"name": "Flights", "fleets": self.fleets, "races": self.columns}]
            return httpx.Response(200, json={"name": NAME, "series": series if self.fleets else []})
        if path == "v1/events/createEvent":
            form = parse_qs(request.content.decode())
            assert form["eventName"] == [NAME]
            assert form["canBoatsOfCompetitorsChangePerRace"] == ["true"]
            self.events += 1
            return httpx.Response(200, json={"leaderboard": NAME})
        if path == "v1/regattas/updateOrCreateSeries":
            body = json.loads(request.content)
            if not self.fleets:  # SAP sets fleets only when it creates the series
                self.fleets = [f["fleetName"] for f in body["fleets"]]
            return httpx.Response(200)
        if path == f"{regatta}/removeracecolumn":
            column = query["racecolumn"]
            self.columns.remove(column)
            for key in [k for k in self.draw if k[0] == column]:
                del self.draw[key]
                self.enabled.discard(key)
            return httpx.Response(200)
        if path == f"{regatta}/addracecolumns":
            new = [f"F{len(self.columns) + i}" for i in range(1, int(query["numberofraces"]) + 1)]
            self.columns += new
            return httpx.Response(200, json=[{"racename": c} for c in new])
        if request.method == "GET" and path == f"{regatta}/competitors":
            return httpx.Response(200, json=list(self.competitors.values()))
        if path == f"{regatta}/competitors/createandadd":
            cid = f"sap-team-{len(self.competitors) + 1}"
            self.competitors[cid] = {"id": cid, "shortName": query["competitorShortName"]}
            return httpx.Response(200, json=self.competitors[cid])
        if path == f"v1/leaderboards/{NAME}/enableRaceLogForCompetitorRegistration":
            self.enabled.add((query["raceColumnName"], query["fleetName"]))
            return httpx.Response(200)
        if path == "v1/mark/addCompetitorToRace":
            body = json.loads(request.content)
            race = (body["raceColumnName"], body["fleetName"])
            if race not in self.enabled or race[0] not in self.columns:
                return httpx.Response(400, text=f"Competitor registration not allowed for {race}")
            self.draw.setdefault(race, {}).update(
                {c["competitorId"]: c["boatId"] for c in body["competitors"]}
            )
            return httpx.Response(200)
        return httpx.Response(404, text=f"fake SAP: no {request.method} {path}")


@pytest.fixture
async def db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'send.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with sessions() as session:
        clubs = {
            code: Club(slug=code.lower(), name=code, short_name=code)
            for code in ("ASVW", "NRV", "KYC")
        }
        series = Series(
            slug="dsbl-2-2027",
            name="2. Segel-Bundesliga 2027",
            short_name="2. Liga 2027",
            year=2027,
            level=2,
        )
        venue = Venue(slug="warnemuende", name="Warnemünde", city="Warnemünde")
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


async def _send(db, sap: FakeSap):
    async with httpx.AsyncClient(transport=sap.transport()) as http:
        return await send_event(
            db, SapWriter(http, "https://sap.example.com/api"), "dsbl-2-2027-warnemuende", BOATS
        )


class TestSendTheEventToSap:
    async def test_sap_holds_the_event_its_teams_and_our_draw(self, db):
        """Story VA-15, Journey step J-10.16: one send makes the event, a flight per race
        column with its races as fleets, the teams under their club codes, and every race's
        team-on-boat pairs."""
        sap = FakeSap()
        report = await _send(db, sap)

        assert report.errors == []
        assert (report.teams_created, report.races) == (4, 4)
        assert sap.events == 1
        assert sap.columns == ["F1", "F2"]
        assert sap.fleets == ["Race 1", "Race 2"]
        # A club entering two teams is told apart by number (VA-13).
        assert sorted(c["shortName"] for c in sap.competitors.values()) == [
            "ASVW",
            "KYC 1",
            "KYC 2",
            "NRV",
        ]
        team_of = {}
        async with db() as session:
            for team in (await session.execute(select(Team))).scalars():
                team_of[await link_key(session, Team, SOURCE, team.id)] = team.name
            event = (await session.execute(select(Event))).scalar_one()
            assert event.sap_leaderboard == NAME
            assert await link_key(session, Event, SOURCE, event.id) == NAME
        assert {team_of[c]: b for c, b in sap.draw[("F1", "Race 1")].items()} == {
            "ASVW 1": "sap-boat-black",
            "NRV 1": "sap-boat-green",
        }
        assert {team_of[c]: b for c, b in sap.draw[("F2", "Race 2")].items()} == {
            "NRV 1": "sap-boat-black",
            "KYC 2": "sap-boat-green",
        }

    async def test_sending_again_replaces_the_draw_and_keeps_the_teams(self, db):
        """Story VA-15: a second send — after a new draw — makes no second event and no
        second team; SAP's draw is ours as it now stands."""
        sap = FakeSap()
        await _send(db, sap)
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

        report = await _send(db, sap)

        assert (report.teams_created, report.teams_kept, report.races) == (0, 4, 4)
        assert sap.events == 1 and len(sap.competitors) == 4
        assert sap.columns == ["F1", "F2"]
        assert sorted(sap.draw[("F1", "Race 1")].values()) == ["sap-boat-black", "sap-boat-green"]
        assert list(sap.draw[("F1", "Race 1")].values()) == ["sap-boat-green", "sap-boat-black"]
        assert sum(len(pairs) for pairs in sap.draw.values()) == 8

    async def test_a_started_event_is_not_sent(self, db):
        """Story VA-15: once the first race froze the event (VA-8), SAP's draw stays the one
        sailed — the send is refused before anything reaches SAP."""
        async with db() as session:
            race = (await session.execute(select(Race).where(Race.sequence == 1))).scalar_one()
            race.status = RaceStatus.FINISHED
            race.started_at = datetime(2027, 8, 20, 10, tzinfo=UTC)
            await session.commit()
        sap = FakeSap()

        with pytest.raises(SystemExit, match="froze"):
            await _send(db, sap)
        assert sap.calls == []

    async def test_a_boat_without_its_sap_boat_is_named(self, db):
        """Story VA-15: a boat colour SAP has no boat for is named, and nothing is sent."""
        sap = FakeSap()
        async with httpx.AsyncClient(transport=sap.transport()) as http:
            with pytest.raises(SystemExit, match="GREEN"):
                await send_event(
                    db,
                    SapWriter(http, "https://sap.example.com/api"),
                    "dsbl-2-2027-warnemuende",
                    {"BLACK": "sap-boat-black"},
                )
        assert sap.calls == []


class TestBothDirections:
    async def test_the_draw_goes_to_sap_and_the_results_come_back(self, db):
        """Stories VA-15, WL-5, Journey step J-10.7: configuration flows to SAP, results
        flow back. The event and its draw are sent; the race committee scores a flight at
        SAP; the import takes the places onto the very teams, boats and races of our draw —
        no second event, team or boat — and the points are derived here."""
        sap = FakeSap()
        await _send(db, sap)
        code = {cid: c["shortName"] for cid, c in sap.competitors.items()}
        by_code = {v: k for k, v in code.items()}
        # F1: ASVW beats NRV in race 1, KYC 2 beats KYC 1 in race 2.
        sap.finish("F1", "Race 1", [by_code["ASVW"], by_code["NRV"]])
        sap.finish("F1", "Race 2", [by_code["KYC 2"], by_code["KYC 1"]])

        async with httpx.AsyncClient(transport=sap.transport()) as http:
            report = await import_sap(
                db, SapClient(http, "https://sap.example.com/api"), names=[NAME], log=lambda _: None
            )

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
                        RaceEntry.points,
                    )
                    .join(RaceEntry, RaceEntry.team_id == Team.id)
                    .join(Race, Race.id == RaceEntry.race_id)
                    .join(Boat, Boat.id == RaceEntry.boat_id)
                    .where(RaceEntry.finish_position.is_not(None))
                    .order_by(Race.sequence, RaceEntry.finish_position)
                )
            ).all()
        # On the boat our draw gave each team, with the points derived here.
        assert [tuple(r) for r in rows] == [
            ("ASVW 1", 1, 1, "BLACK", 1.0),
            ("NRV 1", 1, 2, "GREEN", 2.0),
            ("KYC 2", 2, 1, "GREEN", 1.0),
            ("KYC 1", 2, 2, "BLACK", 2.0),
        ]
