"""The leagues' past matchdays from SAP Sailing Analytics (Story A-14).

The 1. and 2. Liga are on ``www.sapsailing.com`` (up to 2023), the Junioren-Liga on its
own host, ``hnv.sapsailing.com`` (``--base-url``) — the same API, other names.

Reads the **public** API of ``www.sapsailing.com`` — no secret, verified 2026-10-12
(``docs/findings.md`` §3a): the regatta list, and per regatta the v2 leaderboard, which
carries everything a matchday needs in one document — the clubs (``shortName`` is the
club code), the 16 flight columns, per cell the fleet (``Race 1``–``Race 3``), the boat
(sail number, ``#rrggbb``) and the scored result.

The points SAP shows are **not** copied: the raw result (finish position, code) is, and
``recompute_event`` derives the points here, like after any result entry. SAP's net
points are then compared with ours, and a difference is reported — it is the check that
the import understood the source.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from functools import partial
from typing import Any, NamedTuple
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.imports.common import (
    Report,
    link,
    link_key,
    linked,
    resolve_club,
    run_import,
    unique_slug,
)
from app.models import (
    Boat,
    Club,
    Event,
    EventStanding,
    EventStatus,
    Flight,
    League,
    Race,
    RaceEntry,
    Series,
    Source,
    Team,
    Venue,
)
from app.models.racing import RaceStatus, ResultCode
from app.schemas.admin import ScoringIn
from app.services.participation import event_entry, team_name
from app.services.standings import recompute_event
from app.text import slugify

SOURCE = Source.SAP_SAILING
BASE_URL = "https://www.sapsailing.com/sailingserver/api"
# A series' slug keeps the DSBL prefix (`dsbl-1-2026`) — series slugs are stable, and the
# seed's series are found by it. The league is the division's own (Story B-14).
SERIES_PREFIX = "dsbl"
# The matchdays are sailed on German water; a start at 23:30 UTC is the next day here.
LOCAL_TIME = ZoneInfo("Europe/Berlin")

# The juniors' league, whose acts sit on their own SAP host (`hnv.sapsailing.com`).
JUNIOR_LEAGUE = "junioren-liga"

# `1. Segel-Bundesliga 2023 - Berlin (1)`, `2. Segel-Bundesliga 2020 - Hamburg (Finale)`,
# `1. Segel-Bundesliga2018 - Travemünde (3)`. Not `… 2015-2016 - Relegation`: a
# relegation regatta is no matchday of either division.
_NAME = re.compile(
    r"^(?P<level>[12])\.\s*Segel-Bundesliga\s*(?P<year>\d{4})(?!\s*-\s*\d)\s*-\s*(?P<rest>.+?)\s*$"
)
_SUFFIX = re.compile(r"\s*\((?P<label>[^)]*)\)\s*$")
# `Deutsche Junioren Segel-Liga 2026 - Act 4 (Finale)`, `… 2024 - Nord Act 1`,
# `… 2017, NORD, ACT 2`. Not the cup (`Deutscher Junioren- & Segel-Liga Pokal 2026`), and
# not an act without a year: neither belongs to a series.
_JUNIOR_NAME = re.compile(
    r"^Deutsche Junioren Segel-Liga,?\s*(?P<year>\d{4})\s*[-,]\s*(?P<rest>.+?)\s*$"
)
_ACT = re.compile(r"\bAct\s*(?P<number>\d+)\b", re.IGNORECASE)
# `KiYC 2`: the club's code, then the team's number when a club sails more than one.
_TEAM_NUMBER = re.compile(r"^(?P<code>.*?\S)\s+(?P<team>\d+)$")
# `Kieler Yacht-Club e.V. 2`: the team's number after a club's name — one or two digits,
# so a founding year (`Segel-Club von 1903`) stays part of the name.
_NAME_TEAM_NUMBER = re.compile(r"(?<=\S)\s+\d{1,2}$")

# The juniors' host spells some clubs' codes differently from ours (and from the
# league's host). One reviewed line per club — never a comparison of names (Domain
# decisions: external systems are matched via `ExternalId`).
_JUNIOR_CODES = {
    "bayc": "BYC",  # Bayerischer Yacht-Club
    "beyc": "BYCB",  # Berliner Yacht-Club
    "bohyc": "BoYC",  # Bocholter Yacht-Club
    "kiyc": "KYC (SH)",  # Kieler Yacht-Club
    "koyc": "KYC (BA)",  # Konstanzer Yacht Club
    "shm": "SCHM",  # Segel-Club Hansa Münster
}
# A filler the juniors' host enters to make a pairing list come out even.
_PLACEHOLDERS = {"no show"}

# SAP's `maxPointsReason` → our code. Anything not here is reported, and stored as RDG
# with SAP's points so the table still adds up — that is what a redress is.
_CODES = {
    "NONE": ResultCode.FINISHED,
    "DNS": ResultCode.DNS,
    "DNC": ResultCode.DNS,
    "DNF": ResultCode.DNF,
    "RET": ResultCode.RET,
    "RAF": ResultCode.RET,
    "OCS": ResultCode.OCS,
    "DSQ": ResultCode.DSQ,
    "DNE": ResultCode.DNE,
    "DGM": ResultCode.DNE,
    "RDG": ResultCode.RDG,
    "ZFP": ResultCode.ZFP,
    "SCP": ResultCode.SCP,
    "UFD": ResultCode.UFD,
    "BFD": ResultCode.BFD,
}


@dataclass(frozen=True)
class RegattaName:
    """What a league regatta's name on SAP says about it."""

    name: str
    # The 1. or 2. Liga's division; none for the juniors.
    level: int | None
    year: int
    # The juniors' names carry none.
    city: str | None
    # The `(n)` at the end, or the juniors' `Act n`.
    number: int | None
    # The `(…)` at the end when it is not a number — `Finale`; the juniors' `Nord`.
    label: str | None
    league: str = ""

    def __post_init__(self) -> None:
        if not self.league:
            object.__setattr__(self, "league", f"{self.level}-liga")

    @property
    def junior(self) -> bool:
        return self.league == JUNIOR_LEAGUE

    @property
    def series_name(self) -> str:
        if self.junior:
            return f"Junioren-Segelliga {self.year}"
        return f"{self.level}. Segel-Bundesliga {self.year}"

    @property
    def series_slug(self) -> str:
        # The seed's slugs (`dsbl-1-2026`, `junioren-2026`): stable, and how the seed's
        # series of the year is found.
        if self.junior:
            return f"junioren-{self.year}"
        return f"{SERIES_PREFIX}-{self.level}-{self.year}"

    @property
    def series_short_name(self) -> str:
        return f"Junioren {self.year}" if self.junior else f"{self.level}. Liga {self.year}"


class CompetitorCode(NamedTuple):
    """A competitor's short name on SAP, read as our club code and the club's team."""

    code: str
    team: int


def parse_years(spec: str) -> set[int]:
    """`2025-2026`, `2023`, `2019,2021-2023` → the years they name. Empty → none."""
    years: set[int] = set()
    for part in filter(None, (p.strip() for p in spec.split(","))):
        first, sep, last = part.partition("-")
        if not first.strip().isdigit() or (sep and not last.strip().isdigit()):
            raise ValueError(f"{part!r} is not a year or a range of years (2025-2026)")
        start, end = int(first), int(last) if sep else int(first)
        if end < start:
            raise ValueError(f"{part!r}: the range runs backwards")
        years.update(range(start, end + 1))
    return years


def parse_regatta_name(name: str) -> RegattaName | None:
    match = _NAME.match(name)
    if match is None:
        return _parse_junior_name(name)
    rest = match["rest"]
    number = label = None
    suffix = _SUFFIX.search(rest)
    if suffix:
        rest = rest[: suffix.start()]
        if suffix["label"].strip().isdigit():
            number = int(suffix["label"])
        else:
            label = suffix["label"].strip()
    # `Finale Berlin`, `Finale - Berlin`: the final is a label, the rest the city.
    if re.match(r"^Finale\b", rest):
        label = label or "Finale"
        rest = re.sub(r"^Finale\s*-?\s*", "", rest)
    return RegattaName(
        name=name,
        level=int(match["level"]),
        year=int(match["year"]),
        city=rest.strip(" -"),
        number=number,
        label=label,
    )


def _parse_junior_name(name: str) -> RegattaName | None:
    match = _JUNIOR_NAME.match(name)
    act = _ACT.search(match["rest"]) if match else None
    if match is None or act is None:
        return None
    rest = match["rest"][: act.start()] + match["rest"][act.end() :]
    label = rest.strip(" -,()") or None
    if label and label.isupper():
        label = label.capitalize()
    return RegattaName(
        name=name,
        level=None,
        year=int(match["year"]),
        city=None,
        number=int(act["number"]),
        label=label,
        league=JUNIOR_LEAGUE,
    )


def junior_competitor(short_name: str) -> CompetitorCode:
    """`KiYC 2` → our `KYC (SH)`, team 2; `NRV` → `NRV`, team 1."""
    short = short_name.strip()
    match = _TEAM_NUMBER.match(short)
    code, team = (match["code"], int(match["team"])) if match else (short, 1)
    return CompetitorCode(_JUNIOR_CODES.get(code.casefold(), code), team)


class SapClient:
    """The few public endpoints the import reads. One request at a time, on purpose."""

    def __init__(self, http: httpx.AsyncClient, base_url: str = BASE_URL):
        self._http = http
        self._base = base_url.rstrip("/")
        self._leaderboards: dict[str, dict[str, Any]] = {}

    async def _get(self, path: str) -> Any:
        response = await self._http.get(f"{self._base}/{path}")
        response.raise_for_status()
        return response.json()

    async def regattas(self) -> list[dict[str, Any]]:
        return await self._get("v1/regattas")

    async def competitors(self, name: str) -> list[dict[str, Any]]:
        """The regatta's clubs, with ``flagImageUri`` — the crest — from 2022 on."""
        return await self._get(f"v1/regattas/{quote(name, safe='')}/competitors")

    async def leaderboard(self, name: str) -> dict[str, Any]:
        if name not in self._leaderboards:
            self._leaderboards[name] = await self._get(f"v2/leaderboards/{quote(name, safe='')}")
        return self._leaderboards[name]


# ---------------------------------------------------------------------------- the run


async def import_sap(
    sessions: async_sessionmaker[AsyncSession],
    client: SapClient,
    *,
    years: Iterable[int] = (),
    names: Iterable[str] = (),
    everything: bool = False,
    publish: bool = False,
    log=print,
) -> Report:
    """Imports the selected DSBL regattas — one transaction and one ``ImportRun`` each,
    so a regatta that fails costs only itself."""
    report = Report()
    years, names = set(years), set(names)

    listed = await client.regattas()
    regattas = [
        parsed for regatta in listed if (parsed := parse_regatta_name(regatta["name"])) is not None
    ]
    unknown = names - {r.name for r in regattas}
    for name in sorted(unknown):
        report.errors.append(f"{name}: not a DSBL matchday on SAP (or not there at all)")
    selected = [r for r in regattas if everything or r.year in years or r.name in names]
    if not selected and not unknown:
        report.warnings.append("No regatta matched the selection.")

    matchdays = await _number_matchdays(client, regattas, selected, report)

    for regatta in sorted(selected, key=lambda r: (r.year, r.level, matchdays.get(r.name) or 99)):
        log(f"SAP: {regatta.name}")
        try:
            leaderboard = await client.leaderboard(regatta.name)
        except httpx.HTTPError as error:
            report.errors.append(f"{regatta.name}: {error}")
            continue
        try:
            crests = {
                c["id"]: c["flagImageUri"]
                for c in await client.competitors(regatta.name)
                if c.get("flagImageUri")
            }
        except httpx.HTTPError as error:
            report.warnings.append(f"{regatta.name}: no crests ({error})")
            crests = {}

        work = partial(
            _import_regatta,
            regatta=regatta,
            leaderboard=leaderboard,
            crests=crests,
            matchday=matchdays.get(regatta.name),
            listed_days=_listed_days(next((r for r in listed if r["name"] == regatta.name), {})),
            publish=publish,
        )
        report.merge(await run_import(sessions, SOURCE, regatta.name, work))
    return report


async def _number_matchdays(
    client: SapClient,
    regattas: list[RegattaName],
    selected: list[RegattaName],
    report: Report,
) -> dict[str, int]:
    """Matchday per regatta name: the `(n)` in the names where every regatta of that
    series has a distinct one, else the order of their first start."""
    by_series: dict[tuple[str, int], list[RegattaName]] = defaultdict(list)
    for regatta in regattas:
        by_series[(regatta.league, regatta.year)].append(regatta)

    numbers: dict[str, int] = {}
    for key in {(r.league, r.year) for r in selected}:
        siblings = by_series[key]
        named = [r.number for r in siblings]
        if None not in named and len(set(named)) == len(named):
            numbers.update({r.name: r.number for r in siblings if r.number is not None})
            continue
        starts: dict[str, datetime] = {}
        for regatta in siblings:
            try:
                first = _start_times(await client.leaderboard(regatta.name))
            except httpx.HTTPError as error:
                report.warnings.append(f"{regatta.name}: no dates to number it by ({error})")
                continue
            if first:
                starts[regatta.name] = min(first)
        for n, name in enumerate(sorted(starts, key=starts.__getitem__), start=1):
            numbers[name] = n
    return numbers


def _start_times(leaderboard: dict[str, Any]) -> list[datetime]:
    return [
        datetime.fromtimestamp(tracked["startTimeMillis"] / 1000, UTC)
        for column in leaderboard.get("trackedRacesInfo", [])
        for fleet in column.get("fleets", [])
        if (tracked := fleet.get("trackedRace")) and tracked.get("startTimeMillis")
    ]


def _local_day(moment: datetime) -> date:
    return moment.astimezone(LOCAL_TIME).date()


class Days(NamedTuple):
    """An act's first and last day, local."""

    first: date
    last: date


def _listed_days(regatta: dict[str, Any]) -> Days | None:
    """The days the regatta list gives — for an act without tracked starts (the juniors'
    acts track none, Story A-14), the dates it was planned for."""
    start, end = regatta.get("startDate"), regatta.get("endDate")
    if not start:
        return None
    first = _local_day(datetime.fromtimestamp(start / 1000, UTC))
    return Days(first, _local_day(datetime.fromtimestamp((end or start) / 1000, UTC)))


# ---------------------------------------------------------------------- one regatta


async def _import_regatta(
    session: AsyncSession,
    report: Report,
    regatta: RegattaName,
    leaderboard: dict[str, Any],
    crests: dict[str, str],
    matchday: int | None,
    publish: bool,
    listed_days: Days | None = None,
) -> None:
    competitors = leaderboard.get("competitors", [])
    columns: list[str] = leaderboard.get("columnNames", [])
    fleets_by_column = {
        info["raceColumnName"]: info.get("fleets", [])
        for info in leaderboard.get("trackedRacesInfo", [])
    }
    fleet_names = sorted(
        {fleet["name"] for fleets in fleets_by_column.values() for fleet in fleets}
        | {
            cell["fleet"]
            for competitor in competitors
            for cell in _cells(competitor).values()
            if cell.get("fleet")
        }
    )
    # Keyed by SAP's boat id: before 2022 the sail number is empty (`Boot 5`).
    boats_seen = {
        cell["boat"]["id"]: cell["boat"]
        for competitor in competitors
        for cell in _cells(competitor).values()
        if cell.get("boat") and cell["boat"].get("id")
    }
    starts = _start_times(leaderboard)
    placeholders = [
        c for c in competitors if (c.get("shortName") or "").strip().casefold() in _PLACEHOLDERS
    ]
    for competitor in placeholders:
        report.unassigned.append(f"{regatta.name}: {competitor['shortName']} is no club")

    series = await _series(session, report, regatta, publish)
    event = await _event(
        session,
        report,
        regatta,
        series,
        matchday,
        publish,
        team_count=len(competitors) - len(placeholders),
        boat_count=len(boats_seen),
        flight_count=len(columns),
        days=Days(min(map(_local_day, starts)), max(map(_local_day, starts)))
        if starts
        else listed_days,
    )
    if fleet_names and len(fleet_names) != event.races_per_flight:
        report.warnings.append(
            f"{regatta.name}: {len(fleet_names)} races per flight at SAP, "
            f"{event.races_per_flight} by this event's configuration"
        )

    # Clubs and their entry — in the series and in this act.
    teams: dict[str, Team] = {}
    for competitor in competitors:
        if competitor in placeholders:
            continue
        short = (competitor.get("shortName") or competitor.get("name") or "").strip()
        if not short:
            report.unassigned.append(f"{regatta.name}: a competitor without a club code")
            continue
        code, number = junior_competitor(short) if regatta.junior else CompetitorCode(short, 1)
        name = (competitor.get("name") or code).strip()
        if regatta.junior:
            name = _NAME_TEAM_NUMBER.sub("", name)
        club = await resolve_club(
            session,
            report,
            source=SOURCE,
            key=code.upper(),
            code=code,
            name=name,
        )
        # The crest only where the club has none: one set here is the club's own choice.
        crest = crests.get(competitor["id"])
        if crest and not club.logo_url:
            club.logo_url = crest[:300]
            report.tally("updated", "clubs (crest)")
        teams[competitor["id"]] = await _entry(session, report, club, series, event, number)

    boats = await _boats(session, report, event, boats_seen)
    races = await _races(session, report, event, columns, fleet_names, fleets_by_column)
    entries = {
        EntryKey(entry.race_id, entry.team_id): entry
        for entry in (
            await session.execute(
                select(RaceEntry).where(RaceEntry.race_id.in_([r.id for r in races.values()]))
            )
        ).scalars()
    }

    for competitor in competitors:
        team = teams.get(competitor["id"])
        if team is None:
            continue
        for column, cell in _cells(competitor).items():
            _result(session, report, regatta, races, boats, entries, team, column, cell)
        _penalty(report, regatta, team, competitor.get("carriedPoints"))

    await session.flush()
    last_scored = leaderboard.get("lastScoringUpdate")
    await _settle_states(
        session,
        event,
        races,
        _local_day(datetime.fromtimestamp(last_scored / 1000, UTC)) if last_scored else None,
    )
    await recompute_event(session, event.id)
    await _compare_net_points(session, report, regatta, event, competitors, teams)


def _cells(competitor: dict[str, Any]) -> dict[str, dict[str, Any]]:
    # An empty leaderboard calls the same object `raceScores` (docs/findings.md §3).
    return competitor.get("columns") or competitor.get("raceScores") or {}


async def _series(
    session: AsyncSession, report: Report, regatta: RegattaName, publish: bool
) -> Series:
    series = await linked(session, Series, SOURCE, regatta.series_name)
    slug = regatta.series_slug
    if series is None:
        # The seed's and the admin's own series of that year, if there is one.
        series = (
            await session.execute(select(Series).where(Series.slug == slug))
        ).scalar_one_or_none()
        if series is not None:
            await link(session, series, SOURCE, regatta.series_name)
            report.tally("updated", "series (linked)")
    if series is None:
        series = Series(
            slug=await unique_slug(session, Series, slug),
            name=regatta.series_name,
            short_name=regatta.series_short_name,
            year=regatta.year,
            level=regatta.level,
            league_id=(await _league(session, report, regatta)).id,
            scoring=ScoringIn().model_dump(),
            published=publish,
        )
        session.add(series)
        await session.flush()
        await link(session, series, SOURCE, regatta.series_name)
        report.tally("created", "series")
    elif publish and not series.published:
        series.published = True
        report.tally("updated", "series (published)")
    return series


async def _league(session: AsyncSession, report: Report, regatta: RegattaName) -> League:
    """The regatta's league — the 1. and 2. Liga are two leagues (Story B-14), the
    juniors a third."""
    slug = regatta.league
    league = (await session.execute(select(League).where(League.slug == slug))).scalar_one_or_none()
    if league is None:
        league = (
            League(
                slug=slug, short_name="Junioren", name="Deutsche Junioren Segel-Liga", position=3
            )
            if regatta.junior
            else League(
                slug=slug,
                short_name=f"{regatta.level}. Liga",
                name=f"{regatta.level}. Segel-Bundesliga",
                position=regatta.level,
            )
        )
        session.add(league)
        await session.flush()
        report.tally("created", "leagues")
    return league


async def _event(
    session: AsyncSession,
    report: Report,
    regatta: RegattaName,
    series: Series,
    matchday: int | None,
    publish: bool,
    *,
    team_count: int,
    boat_count: int,
    flight_count: int,
    days: Days | None,
) -> Event:
    event = await linked(session, Event, SOURCE, regatta.name)
    if event is not None:
        changed = False
        if days and (event.starts_on, event.ends_on) == (None, None):
            event.starts_on, event.ends_on = days
            changed = True
        if publish and not event.published:
            event.published = True
            changed = True
        report.tally("updated" if changed else "unchanged", "events")
        return event

    if matchday is not None:
        taken = (
            await session.execute(
                select(Event.id).where(Event.series_id == series.id, Event.matchday == matchday)
            )
        ).scalar_one_or_none()
        if taken is not None:
            report.warnings.append(
                f"{regatta.name}: matchday {matchday} of {series.name} is already event "
                f"{taken} here — imported without a matchday number"
            )
            matchday = None

    place = regatta.city or regatta.name
    title = " ".join(filter(None, (f"Act {matchday}", regatta.city))) if matchday else place
    if regatta.label:
        title = f"{title} ({regatta.label})"
    event = Event(
        slug=await unique_slug(
            session,
            Event,
            f"{series.slug}-act-{matchday}" if matchday else f"{series.slug}-{slugify(place)}",
        ),
        title=title,
        matchday=matchday,
        series_id=series.id,
        venue_id=(await _venue(session, report, regatta.city)).id if regatta.city else None,
        team_count=team_count or 18,
        boat_count=boat_count or 6,
        flight_count=flight_count or 16,
        starts_on=days[0] if days else None,
        ends_on=days[1] if days else None,
        sap_leaderboard=regatta.name,
        published=publish,
    )
    session.add(event)
    await session.flush()
    await link(session, event, SOURCE, regatta.name)
    report.tally("created", "events")

    if days:
        if series.starts_on is None or days[0] < series.starts_on:
            series.starts_on = days[0]
        if series.ends_on is None or days[1] > series.ends_on:
            series.ends_on = days[1]
    return event


async def _venue(session: AsyncSession, report: Report, city: str) -> Venue:
    """The venue named after the matchday's city — the seed's `Kiel`, or a new one."""
    slug = slugify(city)
    venue = (await session.execute(select(Venue).where(Venue.slug == slug))).scalar_one_or_none()
    if venue is None:
        # In Python, not SQL: SQLite's lower() would miss the Ü of Überlingen.
        venue = next(
            (
                v
                for v in (await session.execute(select(Venue))).scalars()
                if v.city.casefold() == city.casefold()
            ),
            None,
        )
    if venue is None:
        venue = Venue(slug=slug, name=city, city=city)
        session.add(venue)
        await session.flush()
        report.tally("created", "venues")
    return venue


async def _entry(
    session: AsyncSession, report: Report, club: Club, series: Series, event: Event, number: int
) -> Team:
    """The club's registration for the series and its team ``number`` in this act — both
    rows the model asks for (Domain decisions: `Team` is the enrollment). A club's second
    team (`KYC (SH) 2`) is an entry of its own, lined up from the club's one squad (Story
    VA-13), so the club stays registered once."""
    registration = (
        await session.execute(
            select(Team).where(
                Team.club_id == club.id, Team.series_id == series.id, Team.event_id.is_(None)
            )
        )
    ).scalar_one_or_none()
    if registration is None:
        session.add(Team(name=club.short_name, club_id=club.id, series_id=series.id))
        report.tally("created", "series registrations")
    entry = await event_entry(session, event.id, club.id, number)
    if entry is None:
        if number > event.teams_per_club:
            event.teams_per_club = number
            report.tally("updated", "events (teams per club)")
        entry = Team(
            name=team_name(club, number),
            number=number,
            club_id=club.id,
            series_id=series.id,
            event_id=event.id,
        )
        session.add(entry)
        report.tally("created", "event entries")
    else:
        report.tally("unchanged", "event entries")
    await session.flush()
    return entry


def boat_numbers(boats: dict[str, dict[str, Any]]) -> dict[str, int]:
    """SAP boat id → our boat number: the sail number, else the number in the name
    (`Boot 5`), else the next free one — the same answer on every run."""
    wanted: dict[str, int | None] = {}
    for boat_id, data in boats.items():
        sail_id = (data.get("sailId") or "").strip()
        digits = re.search(r"\d+", data.get("name") or "")
        wanted[boat_id] = (
            int(sail_id) if sail_id.isdigit() else int(digits.group()) if digits else None
        )
    numbers: dict[str, int] = {}
    taken: set[int] = set()
    for boat_id in sorted(boats, key=lambda b: (wanted[b] is None, wanted[b] or 0, b)):
        number = wanted[boat_id]
        if number is None or number in taken:
            number = max(taken, default=0) + 1
        taken.add(number)
        numbers[boat_id] = number
    return numbers


async def _boats(
    session: AsyncSession, report: Report, event: Event, seen: dict[str, dict[str, Any]]
) -> dict[str, Boat]:
    existing = {
        boat.number: boat
        for boat in (await session.execute(select(Boat).where(Boat.event_id == event.id))).scalars()
    }
    boats: dict[str, Boat] = {}
    for boat_id, number in boat_numbers(seen).items():
        data = seen[boat_id]
        boat = existing.get(number)
        if boat is None:
            boat = Boat(
                event_id=event.id,
                number=number,
                sail_number=(data.get("sailId") or "").strip() or None,
                name=(data.get("name") or "").strip()[:80] or None,
                # SAP's own colour, `#rrggbb` — the pairing tool reads that form too.
                color=(data.get("color") or "").upper() or None,
            )
            session.add(boat)
            report.tally("created", "boats")
        else:
            report.tally("unchanged", "boats")
        boats[boat_id] = boat
    await session.flush()
    return boats


async def _races(
    session: AsyncSession,
    report: Report,
    event: Event,
    columns: list[str],
    fleet_names: list[str],
    fleets_by_column: dict[str, list[dict[str, Any]]],
) -> dict[tuple[str, str], Race]:
    """(column, fleet) → race. Flight *n* is the *n*-th column, race *k* the *k*-th
    fleet — `F3` / `Race 2` is flight 3, race 2."""
    flights = {
        flight.number: flight
        for flight in (
            await session.execute(select(Flight).where(Flight.event_id == event.id))
        ).scalars()
    }
    races: dict[tuple[str, str], Race] = {}
    per_flight = max(len(fleet_names), 1)
    for f, column in enumerate(columns, start=1):
        flight = flights.get(f)
        if flight is None:
            flight = Flight(event_id=event.id, number=f)
            session.add(flight)
            await session.flush()
            report.tally("created", "flights")
        existing = {
            race.number_in_flight: race
            for race in (
                await session.execute(select(Race).where(Race.flight_id == flight.id))
            ).scalars()
        }
        tracked = {
            fleet["name"]: fleet.get("trackedRace") or {}
            for fleet in fleets_by_column.get(column, [])
        }
        for k, fleet in enumerate(fleet_names, start=1):
            race = existing.get(k)
            info = tracked.get(fleet, {})
            if race is None:
                race = Race(
                    flight_id=flight.id,
                    number_in_flight=k,
                    sequence=(f - 1) * per_flight + k,
                    started_at=(
                        datetime.fromtimestamp(info["startTimeMillis"] / 1000, UTC)
                        if info.get("startTimeMillis")
                        else None
                    ),
                )
                session.add(race)
                await session.flush()
                report.tally("created", "races")
            if info.get("id") and await link_key(session, Race, SOURCE, race.id) is None:
                if await linked(session, Race, SOURCE, info["id"]) is None:
                    await link(session, race, SOURCE, info["id"])
            races[(column, fleet)] = race
    return races


class EntryKey(NamedTuple):
    """A result's place: one team in one race."""

    race_id: int
    team_id: int


def _result(
    session: AsyncSession,
    report: Report,
    regatta: RegattaName,
    races: dict[tuple[str, str], Race],
    boats: dict[str, Boat],
    entries: dict[EntryKey, RaceEntry],
    team: Team,
    column: str,
    cell: dict[str, Any],
) -> None:
    """One team's result in one race — filled in, left alone, or reported as a conflict.
    A result recorded here is never overwritten (the race committee wins over imports)."""
    if cell.get("totalPoints") is None:
        return  # not sailed (yet)
    where = f"{regatta.name} {column}/{cell.get('fleet')} {team.name}"
    race = races.get((column, cell.get("fleet") or ""))
    boat = boats.get((cell.get("boat") or {}).get("id") or "")
    if race is None or boat is None:
        report.unassigned.append(f"{where}: no race or boat for this result")
        return

    code, position, redress, warning = result_of(cell)
    if warning:
        report.warnings.append(f"{where}: {warning}")

    key = EntryKey(race.id, team.id)
    entry = entries.get(key)
    if entry is None:
        entries[key] = RaceEntry(
            race_id=race.id,
            team_id=team.id,
            boat_id=boat.id,
            code=code,
            finish_position=position,
            redress_points=redress,
        )
        session.add(entries[key])
        report.tally("created", "results")
        return
    if entry.code is None and entry.boat_id == boat.id:
        entry.code, entry.finish_position, entry.redress_points = code, position, redress
        report.tally("updated", "results")
        return
    if (entry.boat_id, entry.code, entry.finish_position, entry.redress_points) == (
        boat.id,
        code,
        position,
        redress,
    ):
        report.tally("unchanged", "results")
        return
    report.conflicts.append(
        f"{where}: here {entry.code} {entry.finish_position or ''} on boat {entry.boat_id}, "
        f"SAP {code} {position or ''} on boat {boat.id}".replace("  ", " ")
    )


def _penalty(report: Report, regatta: RegattaName, team: Team, carried: Any) -> None:
    """SAP's ``carriedPoints`` — points a team carries into the matchday — as the team's
    matchday penalty (Story WL-4). One set here wins, like a result does."""
    points = float(carried) if carried else None
    if points is None or team.penalty_points == points:
        if points is not None:
            report.tally("unchanged", "penalties")
        return
    if team.penalty_points is None:
        team.penalty_points = points
        team.penalty_note = team.penalty_note or "Carried points (SAP Sailing)"
        report.tally("created", "penalties")
        return
    report.conflicts.append(
        f"{regatta.name} {team.name}: penalty {team.penalty_points:g} here, "
        f"{points:g} carried at SAP"
    )


def result_of(cell: dict[str, Any]) -> tuple[str, int | None, float | None, str | None]:
    """A leaderboard cell as our raw result: code, finish position, redress points — and
    a warning when SAP's code has no equivalent here.

    The finish position is SAP's ``totalPoints``, not its ``rank``: after a redress,
    ``rank`` still counts the boat that got RDG, while the points are the official place
    (Hamburg 2023, F12: DYC rank 4, scored 3). Only under a percentage penalty do the
    points include more than the place, and then ``rank`` is the place.
    """
    reason = cell.get("maxPointsReason") or "NONE"
    points = float(cell["totalPoints"])
    code = _CODES.get(reason)
    if code is None:
        return (
            ResultCode.RDG,
            None,
            points,
            f"SAP code {reason} has no equivalent here — stored as RDG with SAP's {points:g} "
            "points",
        )
    if code == ResultCode.RDG:
        return code, None, points, None
    if code in (ResultCode.ZFP, ResultCode.SCP):
        return code, cell.get("rank") or int(points), None, None
    if code == ResultCode.FINISHED:
        if points.is_integer():
            return code, int(points), None, None
        # A finish worth a fraction of a place is not a finish we can record as one.
        return (
            ResultCode.RDG,
            None,
            points,
            f"a finish scored {points:g} at SAP — stored as RDG with those points",
        )
    return code, None, None, None


async def _settle_states(
    session: AsyncSession,
    event: Event,
    races: dict[tuple[str, str], Race],
    last_scored: date | None,
) -> None:
    """Races with results are finished; an event whose last start lies a day back is
    final — or, with no dates (the juniors' acts track no starts), whose last scoring at
    SAP does. Only ever forward from `planned`/`scheduled` — a state the race committee
    set here is theirs."""
    scored = set(
        (
            await session.execute(
                select(RaceEntry.race_id)
                .where(RaceEntry.race_id.in_([race.id for race in races.values()]))
                .where(RaceEntry.code.is_not(None))
            )
        ).scalars()
    )
    for race in races.values():
        if race.id in scored and race.status == RaceStatus.SCHEDULED:
            race.status = RaceStatus.FINISHED
            race.finished_at = race.started_at
    if scored and event.status == EventStatus.PLANNED:
        today = datetime.now(LOCAL_TIME).date()
        last_day = event.ends_on or last_scored
        over = last_day is not None and last_day < today
        event.status = EventStatus.FINAL if over else EventStatus.LIVE


async def _compare_net_points(
    session: AsyncSession,
    report: Report,
    regatta: RegattaName,
    event: Event,
    competitors: list[dict[str, Any]],
    teams: dict[str, Team],
) -> None:
    ours = {
        standing.team_id: standing.net_points
        for standing in (
            await session.execute(select(EventStanding).where(EventStanding.event_id == event.id))
        ).scalars()
    }
    for competitor in competitors:
        team = teams.get(competitor["id"])
        theirs = competitor.get("netPoints")
        if team is None or theirs is None:
            continue
        # The matchday penalty is inside our net already (Story WL-4).
        if abs(float(ours.get(team.id, 0.0)) - float(theirs)) > 0.01:
            report.warnings.append(
                f"{regatta.name} {team.name}: {ours.get(team.id)} net points here, {theirs} at SAP"
            )
