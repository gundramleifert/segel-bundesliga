"""Send an event and its pairing list to SAP Sailing Analytics (Story VA-15).

    uv run python -m app.imports sap-send demo-2-2026-act-3 \\
        --base-url http://127.0.0.1:8888/sailingserver/api --boats ../deploy/sap-local/boats.json

The other direction of `app/imports/sap.py`: **configuration flows to SAP, results flow
back** (CLAUDE.md). What is sent is ours — the event, its teams, and the draw: which team
sails which boat in which race. SAP then scores the day, and the import reads the results
back from the leaderboard this creates, by the name stored on the event.

How SAP's REST API takes a league matchday (tried against `deploy/sap-local/`):

- ``events/createEvent`` makes the event, its regatta and leaderboard, with boats that
  change per race (``canBoatsOfCompetitorsChangePerRace``).
- A flight is a race column (``F1``…), its races are fleets (``Race 1``…). Fleets are set
  only when a series is *created* — ``updateOrCreateSeries`` ignores them on an existing
  one — so the flights go into a series of their own, ``Flights``.
- A team is ``competitors/createandadd``; SAP makes a boat with every team, named after
  it, which the league does not sail. The six boats it does sail are SAP's already
  (``--boats``: our colour → SAP's boat id), made once per server in SAP's admin console —
  locally by ``deploy/sap-local/boats.sh``.
- The draw is ``mark/addCompetitorToRace`` per race, after
  ``enableRaceLogForCompetitorRegistration`` for that race.
- Sending again replaces SAP's draw: the race columns are removed and made anew, which
  drops their registrations; teams already there are kept.

Refused once the event's first race froze it (VA-8): the draw SAP has must be the one
sailed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.imports.common import link, link_key
from app.imports.sap import SOURCE, boat_key
from app.models import Boat, Event, Flight, Race, Team
from app.services.event_readiness import configuration_frozen

SERIES = "Flights"
BOAT_CLASS = "J/70"

#: Our boat colour → SAP's boat id, from ``--boats``.
type BoatIds = dict[str, str]


@dataclass
class SendReport:
    leaderboard: str = ""
    teams_created: int = 0
    teams_kept: int = 0
    races: int = 0
    errors: list[str] = field(default_factory=list)

    def render(self) -> str:
        lines = [
            f"leaderboard: {self.leaderboard}",
            f"teams: {self.teams_created} created, {self.teams_kept} already there",
            f"races with their draw: {self.races}",
        ]
        lines += [f"error: {e}" for e in self.errors]
        return "\n".join(lines)


def load_boats(path: Path) -> BoatIds:
    """``boats.json`` as `deploy/sap-local/boats.sh` writes it: colour → {"id": …}."""
    return {colour: boat["id"] for colour, boat in json.loads(path.read_text()).items()}


def leaderboard_name(event: Event) -> str:
    """The name the import recognises a league matchday by (`app/imports/sap.py`, ``_NAME``):
    ``2. Segel-Bundesliga 2027 - Warnemünde (5)``."""
    place = event.venue.city if event.venue else event.title
    base = f"{event.series.name} - {place}" if event.series else event.title
    return f"{base} ({event.matchday})" if event.matchday else base


class SapWriter:
    """SAP's write endpoints, as the admin of the target server. One request at a time."""

    def __init__(self, http: httpx.AsyncClient, base_url: str):
        self._http = http
        self._base = base_url.rstrip("/")

    async def _call(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        response = await self._http.request(method, f"{self._base}/{path}", **kwargs)
        if response.is_error:
            raise SapRefused(f"{method} {path}: {response.status_code} {response.text[:200]}")
        return response

    async def regatta(self, name: str) -> dict[str, Any] | None:
        response = await self._http.get(f"{self._base}/v1/regattas/{quote(name, safe='')}")
        return None if response.status_code == 404 else response.raise_for_status().json()

    async def create_event(self, event: Event, name: str) -> None:
        form: dict[str, Any] = {
            "eventName": name,
            "venuename": event.venue.city if event.venue else name,
            "createregatta": "true",
            "createleaderboardgroup": "true",
            "boatclassname": BOAT_CLASS,
            "numberofraces": "0",
            "canBoatsOfCompetitorsChangePerRace": "true",
            "scoringScheme": "LOW_POINT",
            # Shown on SAP's site only once it is public here — a draft stays a draft.
            "ispublic": "true" if event.published else "false",
        }
        if event.starts_on:
            form["startdate"] = f"{event.starts_on.isoformat()}T08:00:00Z"
        if event.ends_on:
            form["enddate"] = f"{event.ends_on.isoformat()}T18:00:00Z"
        await self._call("POST", "v1/events/createEvent", data=form)

    async def flights(self, name: str, flights: int, races_per_flight: int) -> None:
        regatta = await self.regatta(name) or {}
        series = {s["name"]: s for s in regatta.get("series", [])}
        if SERIES in series:
            for column in series[SERIES]["races"]:
                await self._call(
                    "POST",
                    f"v1/regattas/{quote(name, safe='')}/removeracecolumn",
                    params={"racecolumn": column},
                )
        else:
            fleets = [
                {"fleetName": f"Race {k}", "orderNo": 0, "htmlColor": "#000000"}
                for k in range(1, races_per_flight + 1)
            ]
            await self._call(
                "POST",
                "v1/regattas/updateOrCreateSeries",
                json={
                    "regattaName": name,
                    "seriesName": SERIES,
                    "seriesNameNew": SERIES,
                    "isMedal": False,
                    "isFleetsCanRunInParallel": False,
                    "startsWithZeroScore": False,
                    "firstColumnIsNonDiscardableCarryForward": False,
                    "hasSplitFleetContiguousScoring": False,
                    "hasCrossFleetMergedRanking": True,
                    "oneAlwaysStaysOne": False,
                    "fleets": fleets,
                },
            )
        await self._call(
            "POST",
            f"v1/regattas/{quote(name, safe='')}/addracecolumns",
            params={"numberofraces": flights, "prefix": "F", "toseries": SERIES},
        )

    async def competitors(self, name: str) -> list[dict[str, Any]]:
        response = await self._call("GET", f"v1/regattas/{quote(name, safe='')}/competitors")
        return response.json()

    async def create_competitor(self, name: str, team: Team, short_name: str) -> str:
        response = await self._call(
            "POST",
            f"v1/regattas/{quote(name, safe='')}/competitors/createandadd",
            params={
                "boatclass": BOAT_CLASS,
                "competitorName": team.name,
                "competitorShortName": short_name,
                "sailid": short_name,
                "nationalityIOC": "GER",
            },
        )
        return response.json()["id"]

    async def draw(self, name: str, column: str, fleet: str, pairs: dict[str, str]) -> None:
        """Registers the race's teams, each on its boat: competitor id → boat id."""
        await self._call(
            "POST",
            f"v1/leaderboards/{quote(name, safe='')}/enableRaceLogForCompetitorRegistration",
            params={"raceColumnName": column, "fleetName": fleet},
        )
        await self._call(
            "POST",
            "v1/mark/addCompetitorToRace",
            json={
                "leaderboardName": name,
                "raceColumnName": column,
                "fleetName": fleet,
                "competitors": [{"competitorId": c, "boatId": b} for c, b in pairs.items()],
            },
        )


class SapRefused(Exception):
    """SAP answered a write with an error — named, with the step it failed at."""


async def _event(session: AsyncSession, slug: str) -> Event:
    event = (
        await session.execute(
            select(Event)
            .where(Event.slug == slug)
            .options(
                selectinload(Event.series),
                selectinload(Event.venue),
                selectinload(Event.boats),
                selectinload(Event.teams).selectinload(Team.club),
                selectinload(Event.flights).selectinload(Flight.races).selectinload(Race.entries),
            )
        )
    ).scalar_one_or_none()
    if event is None:
        raise SystemExit(f"No event {slug!r} here.")
    return event


def _short_name(team: Team, numbered: bool) -> str:
    """The club's code — the bridge back (A-14) — and the team's number where a club
    enters more than one (VA-13): ``KYC 2``."""
    return f"{team.club.short_name} {team.number}" if numbered else team.club.short_name


async def send_event(
    sessions: async_sessionmaker[AsyncSession],
    writer: SapWriter,
    slug: str,
    boats: BoatIds,
) -> SendReport:
    report = SendReport()
    async with sessions() as session:
        event = await _event(session, slug)
        if await configuration_frozen(session, event.id):
            raise SystemExit(f"{slug}: its first race froze it — SAP's draw stays as sailed.")
        missing = [b.color or str(b.number) for b in event.boats if b.color not in boats]
        if missing:
            raise SystemExit(f"{slug}: no SAP boat for {', '.join(missing)} (--boats)")
        name = report.leaderboard = leaderboard_name(event)
        try:
            if await writer.regatta(name) is None:
                await writer.create_event(event, name)
            races_per_flight = max((len(f.races) for f in event.flights), default=0)
            await writer.flights(name, len(event.flights), races_per_flight)

            present = {c["id"] for c in await writer.competitors(name)}
            clubs = [t.club_id for t in event.teams]
            competitor: dict[int, str] = {}
            for team in event.teams:
                key = await link_key(session, Team, SOURCE, team.id)
                if key in present:
                    report.teams_kept += 1
                else:
                    key = await writer.create_competitor(
                        name, team, _short_name(team, clubs.count(team.club_id) > 1)
                    )
                    await link(session, team, SOURCE, key)
                    report.teams_created += 1
                competitor[team.id] = key

            boat_of = {b.id: boats[b.color] for b in event.boats if b.color}
            # SAP's six boats sail every event, so a boat's key is the leaderboard's and
            # SAP's id together — what the import reads the results back by.
            for boat in event.boats:
                if boat.color and await link_key(session, Boat, SOURCE, boat.id) is None:
                    await link(session, boat, SOURCE, boat_key(name, boats[boat.color]))
            for flight in sorted(event.flights, key=lambda f: f.number):
                for race in sorted(flight.races, key=lambda r: r.number_in_flight):
                    pairs = {competitor[e.team_id]: boat_of[e.boat_id] for e in race.entries}
                    if pairs:
                        await writer.draw(
                            name, f"F{flight.number}", f"Race {race.number_in_flight}", pairs
                        )
                        report.races += 1
        except SapRefused as refused:
            report.errors.append(str(refused))
            await session.rollback()
            return report

        event.sap_leaderboard = name
        if await link_key(session, Event, SOURCE, event.id) is None:
            await link(session, event, SOURCE, name)
        await session.commit()
    return report
