"""The 1. and 2. Segel-Bundesliga 2026 from TracTrac — Story A-14.

    uv run python -m app.imports tractrac              # every recorded act, as drafts
    uv run python -m app.imports tractrac --publish

The league sailed 2026 on TracTrac, which has no open data (docs/PLAN_SEEDING.md,
"Results"). What it publishes — each act's event scoreboard, exported as a PDF — and the
pairing list the league's site publishes per act were recorded once by
`scripts/record-dsbl-2026.py` into `app/seed_data/dsbl-2026/`, checked race by race. This
imports those files the way `app.imports.sap` imports SAP's answers: one transaction and
one ``ImportRun`` per act, matched by ``ExternalId``, repeatable, and never overwriting a
result recorded here (the race committee wins over imports).

A record has, per flight of the pairing list, which club sailed which boat in which race,
and per club its place in each flight sailed: a place, a redress worth points, or a
bare `RDG` whose points the recorder derived from the total. Points are derived here
(`recompute_event`) and compared with TracTrac's total; a difference is a warning.
"""

from __future__ import annotations

import json
from datetime import date
from functools import partial
from pathlib import Path
from typing import Any, NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.imports.common import (
    Report,
    enter_team,
    link,
    linked,
    resolve_club,
    run_import,
    unique_slug,
    venue_for_city,
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
)
from app.models.racing import RaceStatus, ResultCode
from app.schemas.admin import ScoringIn
from app.services.standings import recompute_event

SOURCE = Source.TRACTRAC
FOLDER = Path(__file__).parent.parent / "seed_data" / "dsbl-2026"

# The league's codes (the pairing lists') that this site spells differently — reviewed
# 2026-10-27 against the seed's clubs, one line per club, never a name comparison. The
# seed's `KYC (BA)` for Konstanz is what the league calls `KYC (BW)`.
LEAGUE_CODES = {
    "BYC (BA)": "BYC",
    "BYC (BE)": "BYCB",
    "BOH-YC": "BoYC",
    "SVWu": "SVW",
    "KYC (BW)": "KYC (BA)",
    "BuSC": "BUC",
    "SHM": "SCHM",
    "SCR": "SCRh",
    "WSW": "WsW",
}


def our_code(league_code: str) -> str:
    """This site's code for a club the league names ``league_code``."""
    return LEAGUE_CODES.get(league_code, league_code)


class Slot(NamedTuple):
    """Where one club sailed in one flight: the race and the boat number."""

    race: int
    boat: int


async def import_tractrac(
    sessions: async_sessionmaker[AsyncSession],
    folder: Path = FOLDER,
    *,
    publish: bool = False,
    log=print,
) -> Report:
    """Imports every recorded act in ``folder`` — one transaction and one ``ImportRun``
    each, so an act that fails costs only itself."""
    report = Report()
    records = sorted(folder.glob("*-liga-act-*.json"))
    if not records:
        report.warnings.append(f"No recorded act in {folder}.")
    for path in records:
        record = json.loads(path.read_text("utf-8"))
        key = _event_key(record)
        log(f"TracTrac: {key}")
        work = partial(_import_act, record=record, key=key, publish=publish)
        report.merge(await run_import(sessions, SOURCE, key, work))
    return report


def _event_key(record: dict[str, Any]) -> str:
    return f"dsbl-{record['division']}-{record['year']}-act-{record['act']}"


async def _import_act(
    session: AsyncSession, report: Report, *, record: dict[str, Any], key: str, publish: bool
) -> None:
    series = await _series(session, report, record, publish)
    event = await _event(session, report, record, series, key, publish)
    if event is None:
        return

    teams: dict[str, Team] = {}
    for row in record["scoreboard"]:
        club = await resolve_club(
            session,
            report,
            source=SOURCE,
            key=row["code"],
            code=our_code(row["code"]),
            name=row["name"],
        )
        team = await enter_team(session, report, club, series, event, 1)
        teams[row["code"]] = team
        _penalty(report, key, team, row.get("penalty"))

    boats = await _boats(session, report, event, record["boats"])
    races = await _races(session, report, event, len(record["pairing"]))
    results = {row["code"]: row["flights"] for row in record["scoreboard"]}
    entries = {
        (entry.race_id, entry.team_id): entry
        for entry in (
            await session.execute(
                select(RaceEntry).where(RaceEntry.race_id.in_([r.id for r in races.values()]))
            )
        ).scalars()
    }
    for f, flight in enumerate(record["pairing"], start=1):
        for race in flight:
            for boat_number, code in zip(record["boats"], race["boats"], strict=True):
                team = teams.get(code)
                if team is None:
                    report.unassigned.append(f"{key} F{f}: {code} is on the pairing list only")
                    continue
                _result(
                    session,
                    report,
                    f"{key} F{f}/{race['race']} {code}",
                    race=races[(f, race["race"])],
                    boat=boats[boat_number],
                    team=team,
                    value=results[code][f - 1],
                    entries=entries,
                )

    await session.flush()
    await _settle_states(session, event, races)
    await recompute_event(session, event.id)
    await _compare(session, report, key, event, record, teams)


async def _series(
    session: AsyncSession, report: Report, record: dict[str, Any], publish: bool
) -> Series:
    """The division's series of the year — linked before, else the one this site already
    has under its slug (the seed's), else new."""
    level, year = record["division"], record["year"]
    key = f"dsbl-{level}-{year}"
    series = await linked(session, Series, SOURCE, key)
    if series is None:
        series = (
            await session.execute(select(Series).where(Series.slug == key))
        ).scalar_one_or_none()
        if series is not None:
            await link(session, series, SOURCE, key)
            report.tally("updated", "series (linked)")
    if series is None:
        league = (
            await session.execute(select(League).where(League.slug == f"{level}-liga"))
        ).scalar_one_or_none()
        if league is None:
            league = League(
                slug=f"{level}-liga",
                short_name=f"{level}. Liga",
                name=f"{level}. Segel-Bundesliga",
                position=level,
            )
            session.add(league)
            await session.flush()
            report.tally("created", "leagues")
        series = Series(
            slug=await unique_slug(session, Series, key),
            name=f"{level}. Segel-Bundesliga {year}",
            short_name=f"{level}. Liga {year}",
            year=year,
            level=level,
            league_id=league.id,
            scoring=ScoringIn().model_dump(),
            published=publish,
        )
        session.add(series)
        await session.flush()
        await link(session, series, SOURCE, key)
        report.tally("created", "series")
    elif publish and not series.published:
        series.published = True
        report.tally("updated", "series (published)")
    return series


async def _event(
    session: AsyncSession,
    report: Report,
    record: dict[str, Any],
    series: Series,
    key: str,
    publish: bool,
) -> Event | None:
    """The act — linked before; else this series' act of that matchday while nothing is
    drawn or sailed in it yet (one an organizer only created); else new. An act here with
    a pairing list or results is someone else's record of it: a conflict, left alone —
    taking it over would mix their draw with the league's."""
    days = _days(record)
    event = await linked(session, Event, SOURCE, key)
    if event is not None:
        changed = False
        if days and (event.starts_on, event.ends_on) == (None, None):
            event.starts_on, event.ends_on = days
            changed = True
        if publish and not event.published:
            event.published = True
            changed = True
        report.tally("updated" if changed else "unchanged", "events")
        _extend(series, days)
        return event

    act = record["act"]
    existing = (
        await session.execute(
            select(Event).where(Event.series_id == series.id, Event.matchday == act)
        )
    ).scalar_one_or_none()
    if existing is not None:
        drawn = (
            await session.execute(
                select(RaceEntry.id)
                .join(Race, Race.id == RaceEntry.race_id)
                .join(Flight, Flight.id == Race.flight_id)
                .where(Flight.event_id == existing.id)
                .limit(1)
            )
        ).scalar_one_or_none()
        if drawn is not None:
            report.conflicts.append(
                f"{key}: act {act} of {series.name} is event {existing.id} here and has a "
                "pairing list or results already — left alone"
            )
            return None
        await link(session, existing, SOURCE, key)
        report.tally("updated", "events (linked)")
        return existing

    # A host only when the pairing list names one club: Starnberg (1) names two, and the
    # model has one host per event — which of them pays is not ours to guess.
    hosts = [our_code(code) for code in record.get("hosts", [])]
    host = None
    if len(hosts) == 1:
        host = (
            await session.execute(select(Club).where(Club.short_name == hosts[0]))
        ).scalar_one_or_none()
    event = Event(
        slug=await unique_slug(session, Event, f"{series.slug}-act-{act}"),
        title=f"Act {act} {record['city']}",
        matchday=act,
        series_id=series.id,
        venue_id=(await venue_for_city(session, report, record["city"])).id,
        host_club_id=host.id if host else None,
        starts_on=days[0] if days else None,
        ends_on=days[1] if days else None,
        team_count=len(record["scoreboard"]),
        boat_count=len(record["boats"]),
        flight_count=len(record["pairing"]),
        published=publish,
    )
    session.add(event)
    await session.flush()
    await link(session, event, SOURCE, key)
    report.tally("created", "events")
    _extend(series, days)
    return event


def _days(record: dict[str, Any]) -> tuple[date, date] | None:
    """The act's first and last day, as the league's matchday page states them."""
    if not record.get("starts_on") or not record.get("ends_on"):
        return None
    return date.fromisoformat(record["starts_on"]), date.fromisoformat(record["ends_on"])


def _extend(series: Series, days: tuple[date, date] | None) -> None:
    """A series spans its acts: the earliest first day, the latest last one."""
    if days is None:
        return
    if series.starts_on is None or days[0] < series.starts_on:
        series.starts_on = days[0]
    if series.ends_on is None or days[1] > series.ends_on:
        series.ends_on = days[1]


async def _boats(
    session: AsyncSession, report: Report, event: Event, numbers: list[int]
) -> dict[int, Boat]:
    """The act's boats by the pairing list's numbers (the 2. Liga sails 7–12). No colour:
    neither source says which boat had which."""
    existing = {
        boat.number: boat
        for boat in (await session.execute(select(Boat).where(Boat.event_id == event.id))).scalars()
    }
    boats: dict[int, Boat] = {}
    for number in numbers:
        boat = existing.get(number)
        if boat is None:
            boat = Boat(event_id=event.id, number=number)
            session.add(boat)
            report.tally("created", "boats")
        else:
            report.tally("unchanged", "boats")
        boats[number] = boat
    await session.flush()
    return boats


async def _races(
    session: AsyncSession, report: Report, event: Event, flight_count: int
) -> dict[tuple[int, int], Race]:
    """(flight, race in flight) → race, for every flight of the pairing list — the ones
    not sailed stay scheduled, as the draw left them."""
    per_flight = event.races_per_flight
    flights = {
        flight.number: flight
        for flight in (
            await session.execute(select(Flight).where(Flight.event_id == event.id))
        ).scalars()
    }
    races: dict[tuple[int, int], Race] = {}
    for f in range(1, flight_count + 1):
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
        for k in range(1, per_flight + 1):
            race = existing.get(k)
            if race is None:
                race = Race(
                    flight_id=flight.id, number_in_flight=k, sequence=(f - 1) * per_flight + k
                )
                session.add(race)
                report.tally("created", "races")
            races[(f, k)] = race
    await session.flush()
    return races


def result_of(value: dict[str, Any] | None) -> tuple[ResultCode | None, int | None, float | None]:
    """A recorded flight cell as our raw result: code, finish position, redress points."""
    if value is None:
        return None, None, None
    if "place" in value:
        return ResultCode.FINISHED, int(value["place"]), None
    if "redress" in value:
        return ResultCode.RDG, None, float(value["redress"])
    return ResultCode(value["code"]), None, None


def _result(
    session: AsyncSession,
    report: Report,
    where: str,
    *,
    race: Race,
    boat: Boat,
    team: Team,
    value: dict[str, Any] | None,
    entries: dict[tuple[int, int], RaceEntry],
) -> None:
    """One club's place in its race: filled in, left alone, or reported as a conflict —
    a result recorded here is never overwritten. A flight not sailed still gets its
    entry, without a result: that is the pairing list."""
    code, position, redress = result_of(value)
    entry = entries.get((race.id, team.id))
    if entry is None:
        entries[(race.id, team.id)] = RaceEntry(
            race_id=race.id,
            team_id=team.id,
            boat_id=boat.id,
            code=code,
            finish_position=position,
            redress_points=redress,
        )
        session.add(entries[(race.id, team.id)])
        report.tally("created", "results" if code else "pairings")
        return
    if (entry.boat_id, entry.code, entry.finish_position, entry.redress_points) == (
        boat.id,
        code,
        position,
        redress,
    ):
        report.tally("unchanged", "results" if code else "pairings")
        return
    if entry.code is None and entry.boat_id == boat.id and code is not None:
        entry.code, entry.finish_position, entry.redress_points = code, position, redress
        report.tally("updated", "results")
        return
    report.conflicts.append(
        f"{where}: here {entry.code} {entry.finish_position or entry.redress_points or ''} "
        f"on boat {entry.boat_id}, TracTrac {code} {position or redress or ''} on boat "
        f"{boat.id}".replace("  ", " ")
    )


def _penalty(report: Report, key: str, team: Team, points: float | None) -> None:
    """The scoreboard's `P` column as the team's matchday penalty (Story WL-4) — one set
    here wins, like a result does."""
    if points is None or team.penalty_points == points:
        if points is not None:
            report.tally("unchanged", "penalties")
        return
    if team.penalty_points is None:
        team.penalty_points = points
        team.penalty_note = team.penalty_note or "Penalty on TracTrac's scoreboard"
        report.tally("created", "penalties")
        return
    report.conflicts.append(
        f"{key} {team.name}: penalty {team.penalty_points:g} here, {points:g} at TracTrac"
    )


async def _settle_states(
    session: AsyncSession, event: Event, races: dict[tuple[int, int], Race]
) -> None:
    """Races with results are finished, and an act with any is over — the record is of a
    season that ended. Only ever forward from `planned`/`scheduled`: a state the race
    committee set here is theirs."""
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
    if scored and event.status == EventStatus.PLANNED:
        event.status = EventStatus.FINAL


async def _compare(
    session: AsyncSession,
    report: Report,
    key: str,
    event: Event,
    record: dict[str, Any],
    teams: dict[str, Team],
) -> None:
    """Our derived points against TracTrac's total — within 0.05, as it rounds."""
    ours = {
        standing.team_id: standing.net_points
        for standing in (
            await session.execute(select(EventStanding).where(EventStanding.event_id == event.id))
        ).scalars()
    }
    for row in record["scoreboard"]:
        team = teams.get(row["code"])
        if team is None:
            continue
        here = float(ours.get(team.id, 0.0))
        if abs(here - float(row["points"])) > 0.05:
            report.warnings.append(
                f"{key} {row['code']}: {here:g} points here, {row['points']:g} at TracTrac"
            )
