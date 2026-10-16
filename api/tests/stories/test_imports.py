"""Story A-14: clubs, past seasons and event documents from SAP Sailing and Manage2Sail.

Never against the live systems: every response comes from `tests/fixtures/sap/` and
`tests/fixtures/m2s/`, recorded on 2026-10-12 — the leaderboard of
`1. Segel-Bundesliga 2023 - Berlin (1)`, and the event page, entry list (names replaced)
and document list of `Deutsche Junioren Segel-Liga 2026, ACT 1`.

**Each test imports into its own database**, not the shared seeded one: an import creates
clubs (`TSC`, `SSVL`, …), and a club appearing in the shared database broke other story
tests that create a club with the same slug. The small database here holds the league and
the clubs the linking is about.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import unquote

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import get_session
from app.imports.m2s import Manage2SailClient, import_m2s
from app.imports.sap import SapClient, import_sap
from app.models import (
    Base,
    Boat,
    Club,
    Event,
    EventDocumentKind,
    EventStanding,
    EventStatus,
    ExternalId,
    Flight,
    League,
    Race,
    RaceEntry,
    Series,
    Source,
    Team,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"
BERLIN = "1. Segel-Bundesliga 2023 - Berlin (1)"
CREST = (
    "https://german-sailing-league-media.s3.eu-west-1.amazonaws.com/german-clubflags/small/msc.png"
)
M2S_EVENT = "ee214292-a957-44af-81fc-3e6923a97161"
M2S_CLASS = "6e37e41d-6466-4aeb-b194-68705d5ccb23"


def _sap_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        path = unquote(request.url.path)
        if path == "/sailingserver/api/v1/regattas":
            return httpx.Response(200, content=(FIXTURES / "sap/regattas.json").read_bytes())
        if path == f"/sailingserver/api/v1/regattas/{BERLIN}/competitors":
            # SAP names crests from 2022 on; this 2023 recording has none, so one is added.
            competitors = json.loads((FIXTURES / "sap/competitors.json").read_text("utf-8"))
            for competitor in competitors:
                if competitor["shortName"] == "MSC":
                    competitor["flagImageUri"] = CREST
            return httpx.Response(200, json=competitors)
        if path == f"/sailingserver/api/v2/leaderboards/{BERLIN}":
            return httpx.Response(200, content=(FIXTURES / "sap/leaderboard.json").read_bytes())
        return httpx.Response(404, json={"message": "not recorded"})

    return httpx.MockTransport(handler)


def _m2s_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == f"/en-US/event/{M2S_EVENT}":
            return httpx.Response(200, text=(FIXTURES / "m2s/event.html").read_text("utf-8"))
        if path == f"/api/event/{M2S_EVENT}/regattaentry":
            assert request.url.params["regattaId"] == M2S_CLASS
            return httpx.Response(200, content=(FIXTURES / "m2s/entries.json").read_bytes())
        if path == f"/api/event/{M2S_EVENT}/document/{M2S_EVENT}":
            return httpx.Response(200, content=(FIXTURES / "m2s/documents.json").read_bytes())
        if path == f"/api/event/{M2S_EVENT}/document/{M2S_CLASS}":
            return httpx.Response(200, json=[])
        return httpx.Response(404)

    return httpx.MockTransport(handler)


# The clubs this site "already has": linked by code where the code is unambiguous.
_CLUBS = [
    ("Norddeutscher Regatta Verein", "NRV"),
    ("Verein Seglerhaus am Wannsee", "VSaW"),
    ("Bodensee-Yachtclub Überlingen", "BYCÜ"),
    ("Kieler Yacht-Club", "KYC"),
    ("Bayerischer Yacht-Club", "BYC"),
]


@pytest.fixture
async def db(tmp_path):
    from app.text import slugify

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'imports.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with sessions() as session:
        session.add(League(slug="1-liga", short_name="1. Liga", name="1. Segel-Bundesliga"))
        session.add_all(
            Club(slug=slugify(short), name=name, short_name=short) for name, short in _CLUBS
        )
        await session.commit()
    yield sessions
    await engine.dispose()


@pytest.fixture
async def client(db):
    """The public API, reading the import's database."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async def session_override():
        async with db() as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_session, None)


async def _import_berlin(db, **kwargs):
    async with httpx.AsyncClient(transport=_sap_transport()) as http:
        return await import_sap(db, SapClient(http), names=[BERLIN], log=lambda _: None, **kwargs)


async def _import_m2s(db, **kwargs):
    async with httpx.AsyncClient(transport=_m2s_transport()) as http:
        return await import_m2s(
            db, Manage2SailClient(http), M2S_EVENT, log=lambda _: None, **kwargs
        )


async def _sap_event(session) -> Event:
    event_id = (
        await session.execute(
            select(ExternalId.entity_id).where(
                ExternalId.source == Source.SAP_SAILING,
                ExternalId.entity_type == "event",
                ExternalId.external_key == BERLIN,
            )
        )
    ).scalar_one()
    return await session.get(Event, event_id)


class TestSapImport:
    """Story A-14: a DSBL matchday from SAP — series, event, clubs, boats, races, results."""

    async def test_a_matchday_arrives_with_its_clubs_races_and_results(self, db):
        """Story A-14: one regatta becomes act 1 of the 1. Liga 2023, scored here."""
        report = await _import_berlin(db)
        assert report.errors == [], report.render()
        # SAP's net points agree with the ones derived here — the import understood it,
        # including the 3 points four teams carry into the matchday (Story WL-4).
        assert report.warnings == [], report.render()
        assert report.created["penalties"] == 4

        async with db() as session:
            event = await _sap_event(session)
            series = await session.get(Series, event.series_id)
            assert (series.name, series.level, series.year) == ("1. Segel-Bundesliga 2023", 1, 2023)
            assert event.matchday == 1
            assert (event.team_count, event.boat_count, event.flight_count) == (18, 6, 16)
            assert event.status == EventStatus.FINAL
            assert str(event.starts_on).startswith("2023-05")
            assert event.sap_leaderboard == BERLIN

            boats = (
                (await session.execute(select(Boat).where(Boat.event_id == event.id)))
                .scalars()
                .all()
            )
            assert {b.sail_number: b.color for b in boats} == {
                "1": "#00B0F0",
                "2": "#808080",
                "3": "#E20202",
                "4": "#04C41D",
                "5": "#FFFFFF",
                "6": "#7030A0",
            }
            races = (
                await session.execute(
                    select(func.count())
                    .select_from(Race)
                    .join(Flight)
                    .where(Flight.event_id == event.id)
                )
            ).scalar_one()
            assert races == 48
            results = (
                await session.execute(
                    select(func.count())
                    .select_from(RaceEntry)
                    .join(Race)
                    .join(Flight)
                    .where(Flight.event_id == event.id, RaceEntry.code.is_not(None))
                )
            ).scalar_one()
            # 14 of the 16 flights were sailed; the last two were not.
            assert results == 18 * 14

            winner = (
                await session.execute(
                    select(Club.short_name, EventStanding.net_points)
                    .join(Team, Team.id == EventStanding.team_id)
                    .join(Club, Club.id == Team.club_id)
                    .where(EventStanding.event_id == event.id, EventStanding.rank == 1)
                )
            ).one()
            assert tuple(winner) == ("MSC", 32.0)

            # A club with no crest takes SAP's.
            msc = (await session.execute(select(Club).where(Club.short_name == "MSC"))).scalar_one()
            assert msc.logo_url == CREST

    async def test_a_club_this_site_has_is_linked_not_duplicated(self, db):
        """Story A-14: NRV, VSaW and BYCÜ here are found by their code, case-insensitively."""
        await _import_berlin(db)
        async with db() as session:
            for code in ("NRV", "VSaW", "BYCÜ"):
                # In Python: SQLite's lower() leaves the Ü of BYCÜ alone.
                clubs = [
                    club
                    for club in (await session.execute(select(Club))).scalars()
                    if club.short_name.casefold() == code.casefold()
                ]
                assert len(clubs) == 1, code
                keys = (
                    (
                        await session.execute(
                            select(ExternalId.external_key).where(
                                ExternalId.source == Source.SAP_SAILING,
                                ExternalId.entity_type == "club",
                                ExternalId.entity_id == clubs[0].id,
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                assert keys == [code.upper()]

    async def test_a_second_run_changes_nothing(self, db):
        """Story A-14: repeatable — the same data a second time creates and updates nothing."""
        await _import_berlin(db)
        report = await _import_berlin(db)
        assert not report.created and not report.updated, report.render()
        assert report.unchanged["results"] == 18 * 14

    async def test_a_result_recorded_here_wins_over_the_import(self, db):
        """Story A-14: the race committee wins — a differing result is kept and reported."""
        await _import_berlin(db)
        async with db() as session:
            event = await _sap_event(session)
            entry = (
                await session.execute(
                    select(RaceEntry)
                    .join(Race)
                    .join(Flight)
                    .where(
                        Flight.event_id == event.id, Flight.number == 1, Race.number_in_flight == 1
                    )
                    .where(RaceEntry.code == "FINISHED")
                    .limit(1)
                )
            ).scalar_one()
            original = entry.finish_position
            entry.finish_position = 6 if original != 6 else 5
            await session.commit()
        try:
            report = await _import_berlin(db)
            assert len(report.conflicts) == 1, report.render()
            async with db() as session:
                assert (await session.get(RaceEntry, entry.id)).finish_position != original
        finally:
            async with db() as session:
                (await session.get(RaceEntry, entry.id)).finish_position = original
                await session.commit()

    async def test_an_imported_season_is_a_draft_until_published(self, db, client):
        """Story A-14: a past season on the public site is a decision, not a side effect."""
        await _import_berlin(db)
        async with db() as session:
            event_id = (await _sap_event(session)).id
        assert (await client.get(f"/api/events/{event_id}")).status_code == 404

        await _import_berlin(db, publish=True)
        assert (await client.get(f"/api/events/{event_id}")).status_code == 200
        documents = await client.get(f"/api/events/{event_id}/documents")
        assert documents.status_code == 200 and documents.json() == []

    async def test_a_name_that_is_no_matchday_is_an_error(self, db):
        """Story A-14: asking for a regatta SAP does not list as a matchday says so."""
        async with httpx.AsyncClient(transport=_sap_transport()) as http:
            report = await import_sap(
                db,
                SapClient(http),
                names=["1. Segel-Bundesliga 2031 - Mars"],
                log=lambda _: None,
            )
        assert len(report.errors) == 1


class TestManage2SailImport:
    """Story A-14: an event's entries and its notice-board documents from Manage2Sail."""

    async def test_the_documents_arrive_as_links_with_their_kind(self, db, client):
        """Story A-14: notice of race, sailing instructions and notices, linked."""
        report = await _import_m2s(db, publish=True)
        assert report.errors == [], report.render()
        async with db() as session:
            event = (
                await session.execute(
                    select(Event)
                    .join(ExternalId, ExternalId.entity_id == Event.id)
                    .where(
                        ExternalId.source == Source.MANAGE2SAIL,
                        ExternalId.entity_type == "event",
                        ExternalId.external_key == M2S_EVENT,
                    )
                )
            ).scalar_one()
            assert event.title == "Deutsche Junioren Segel-Liga 2026, ACT 1"
            assert (str(event.starts_on), str(event.ends_on)) == ("2026-05-08", "2026-05-10")

        response = await client.get(f"/api/events/{event.id}/documents")
        assert response.status_code == 200
        documents = {d["title"]: d for d in response.json()}
        assert len(documents) == len(json.loads((FIXTURES / "m2s/documents.json").read_text()))
        assert (
            documents["20260401_Ausschreibung_DJSL-2026.pdf"]["kind"]
            == EventDocumentKind.NOTICE_OF_RACE
        )
        assert (
            documents["20260506_SI_DJSL 2026_final.pdf"]["kind"]
            == EventDocumentKind.SAILING_INSTRUCTIONS
        )
        assert (
            documents["20260507_NO 1_KYC_ACT 1_Team Umpire.pdf"]["kind"] == EventDocumentKind.NOTICE
        )
        assert all(
            d["url"].startswith("https://www.manage2sail.com/en-US/Home/DownloadDocument/")
            for d in documents.values()
        )

    async def test_a_shared_club_code_is_never_guessed(self, db):
        """Story A-14: `KYC` is the Kieler and the Konstanzer Yacht-Club at Manage2Sail —
        neither is matched to the KYC here by code; both wait for --link."""
        report = await _import_m2s(db)
        unassigned = "\n".join(report.unassigned)
        assert "KYC|Kieler Yacht-Club e. V." in unassigned
        assert "KYC|Konstanzer Yachtclub e. V." in unassigned
        assert "BYC|Bayerischer Yacht-Club e. V." in unassigned

        async with db() as session:
            assert (
                await session.execute(
                    select(func.count()).select_from(Club).where(Club.short_name == "KYC")
                )
            ).scalar_one() == 1

        # Tied by hand, the Kieler entry arrives — once, since a club enters an event once.
        report = await _import_m2s(db, links={"KYC|Kieler Yacht-Club e. V.": "kyc"})
        assert "KYC|Kieler Yacht-Club e. V." not in "\n".join(
            line for line in report.unassigned if "several clubs" in line
        )
        assert any("second entry of KYC" in line for line in report.unassigned)

    async def test_a_second_run_changes_nothing(self, db):
        """Story A-14: repeatable for Manage2Sail too."""
        await _import_m2s(db)
        report = await _import_m2s(db)
        assert not report.created and not report.updated, report.render()

    @pytest.mark.parametrize("missing", [999999])
    async def test_attaching_to_an_event_that_does_not_exist_fails_cleanly(self, db, missing):
        """Story A-14: --to an unknown event is an error, and nothing is written."""
        report = await _import_m2s(db, to_event=missing)
        assert report.errors and "No event" in report.errors[0]
