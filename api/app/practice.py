"""A practice season — invented squads, crews and three acts — for the test suites.

The seed holds nothing invented (the demo went on 2026-11-06), and the real 2026 season
is sailed and over with nobody named on it: no squad, no crew, no live act. The tests
need exactly those, so they build them here — the backend's through the ``season``
fixtures (`tests/conftest.py`), the browser's through ``POST /api/dev/season``
(`app/routers/dev.py`, on only with ``SBL_DEV_LOGIN``) — never the seed, never a real
site.

One season: a published series of a real division's 18 clubs, in the league
``practice``, a squad of ten new people
per club, and three acts — one **final**, one **live** (two thirds sailed) and one
**planned** — each with the catalog's pairing list, six boats and four of each squad
lined up. Results are raw finishes, scored by `compute_event` as the race
committee's would be. Built once per label: a second call answers what is there.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Boat,
    Club,
    CrewRole,
    Event,
    EventCrew,
    EventStatus,
    Flight,
    League,
    Person,
    Race,
    RaceEntry,
    ResultCode,
    Series,
    Team,
    TeamMembership,
)
from app.models.racing import BOAT_COLORS
from app.pairing.catalog import load_entry, shuffle_pairing
from app.services import people, race_state
from app.services.pairing_service import PairingDraft, publish_pairing
from app.services.participation import activate
from app.text import slugify

YEAR = 2026
#: The league both practice seasons are in — on a test stack, never a real site.
LEAGUE = "practice"
BOATS = 6
FLIGHTS = 16
SQUAD_SIZE = 10
CREW = 4
#: The three acts: (state, first day, the host club's slug). The planned one is the test
#: club's in the 2. Liga, as the demo's act 3 was.
ACTS = [
    (EventStatus.FINAL, date(YEAR, 5, 8), "dtyc"),
    (EventStatus.LIVE, date(YEAR, 6, 12), "kyc-sh"),
    (EventStatus.PLANNED, date(YEAR, 7, 17), "asvw"),
]


@dataclass
class Season:
    """What a test addresses: ids, never slugs to look up."""

    label: str
    series: int
    final: int
    live: int
    planned: int
    #: Club id → its squad's person ids, in squad order (helm first, substitutes last).
    squads: dict[int, list[int]] = field(default_factory=dict)
    #: Club id → its registration for the series (the squad's team).
    registrations: dict[int, int] = field(default_factory=dict)
    #: (event id, club id) → its team in that act.
    entries: dict[tuple[int, int], int] = field(default_factory=dict)

    @property
    def events(self) -> list[int]:
        return [self.final, self.live, self.planned]


async def season(session: AsyncSession, level: int = 1) -> Season:
    """The practice season of the 1. or 2. Liga's clubs — built on the first call, read
    on every later one. Commits."""
    label = f"practice-{level}-{YEAR}"
    existing = (
        await session.execute(select(Series).where(Series.slug == label))
    ).scalar_one_or_none()
    if existing is None:
        await _build(session, level, label)
        await session.commit()
    return await _read(session, label)


async def _build(session: AsyncSession, level: int, label: str) -> None:
    rng = random.Random(f"{label}")
    real = (
        await session.execute(select(Series).where(Series.slug == f"dsbl-{level}-{YEAR}"))
    ).scalar_one()
    # The clubs that sailed the real first act — sailed and over, so no test changes
    # them, as one may the series' registrations (a 19th club has no draw in the catalog).
    # IN, not a join with DISTINCT: Postgres cannot compare a club's JSON column.
    first_act = select(Event.id).where(Event.series_id == real.id, Event.matchday == 1)
    entered = select(Team.club_id).where(Team.event_id == first_act.scalar_subquery())
    clubs = list(
        (
            await session.execute(
                select(Club).where(Club.id.in_(entered)).order_by(Club.short_name)
            )
        ).scalars()
    )
    league = (
        await session.execute(select(League).where(League.slug == LEAGUE))
    ).scalar_one_or_none()
    if league is None:
        # Its own league, as the demo's was: the act pages, the live chapter and the
        # switch between divisions are a league's (`/practice/2026/act-2`).
        league = League(
            slug=LEAGUE,
            short_name="Practice",
            name="Practice league",
            tagline="Invented squads, weekends and results — for the test suites.",
            position=9,
        )
        session.add(league)
        await session.flush()
    series = Series(
        slug=label,
        league_id=league.id,
        name=f"Practice {level}. Liga {YEAR}",
        short_name=f"Practice {level}",
        year=YEAR,
        level=level,
        published=True,
        scoring=real.scoring,
        squad_min=real.squad_min,
        squad_max=real.squad_max,
    )
    session.add(series)
    await session.flush()

    registrations = [
        Team(name=club.short_name, club_id=club.id, series_id=series.id) for club in clubs
    ]
    session.add_all(registrations)
    await session.flush()

    squads: dict[int, list[Person]] = {}
    for club, team in zip(clubs, registrations, strict=True):
        squads[team.id] = []
        for position in range(SQUAD_SIZE):
            person = await people.new_person(
                session,
                first_name=f"{'Alice' if position % 2 else 'Bob'}{position + 1}",
                last_name=f"{club.short_name} P{level}",
                email=f"p{level}.{position + 1}@{slugify(club.slug)}.practice.example.com",
                birth_date=date(rng.randint(1985, 2004), rng.randint(1, 12), rng.randint(1, 28)),
            )
            await activate(session, person, club.id)
            squads[team.id].append(person)
            session.add(TeamMembership(team_id=team.id, person_id=person.id, role=_role(position)))

    hosts = {
        c.slug: c
        for c in (
            await session.execute(select(Club).where(Club.slug.in_([h for _, _, h in ACTS])))
        ).scalars()
    }
    for matchday, (status, day, host) in enumerate(ACTS, start=1):
        event = Event(
            slug=f"{label}-act-{matchday}",
            title=f"Practice act {matchday}",
            matchday=matchday,
            starts_on=day,
            ends_on=day + timedelta(days=2),
            status=status,
            published=True,
            team_count=len(clubs),
            boat_count=BOATS,
            flight_count=FLIGHTS,
            series_id=series.id,
            host_club_id=hosts[host].id,
        )
        session.add(event)
        await session.flush()
        entries = [
            Team(name=r.name, number=1, club_id=r.club_id, series_id=series.id, event_id=event.id)
            for r in registrations
        ]
        session.add_all(entries)
        session.add_all(
            Boat(
                event_id=event.id, number=b, color=BOAT_COLORS[b - 1], sail_number=f"GER {700 + b}"
            )
            for b in range(1, BOATS + 1)
        )
        await session.flush()
        pairing = shuffle_pairing(load_entry(len(entries), BOATS, FLIGHTS), seed=matchday)
        await publish_pairing(
            session, event, PairingDraft.from_import(pairing, [t.id for t in entries])
        )
        for registration, entry in zip(registrations, entries, strict=True):
            session.add_all(
                EventCrew(
                    event_id=event.id,
                    team_id=entry.id,
                    person_id=person.id,
                    role=CrewRole.HELM if position == 0 else CrewRole.CREW,
                )
                for position, person in enumerate(squads[registration.id][:CREW])
            )
        await _results(session, event, status, rng)


def _role(position: int) -> CrewRole:
    if position == 0:
        return CrewRole.HELM
    return CrewRole.CREW if position < CREW else CrewRole.SUBSTITUTE


async def _results(session: AsyncSession, event: Event, status: str, rng: random.Random) -> None:
    """A final act fully sailed, a live one two thirds, a planned one not at all — with
    the odd DNF and ZFP, so the scoring has something to show."""
    sailed = {EventStatus.FINAL: FLIGHTS * 3, EventStatus.LIVE: FLIGHTS * 3 * 2 // 3}.get(status, 0)
    races = (
        await session.execute(
            select(Race)
            .join(Flight, Flight.id == Race.flight_id)
            .where(Flight.event_id == event.id, Race.sequence <= sailed)
            .order_by(Race.sequence)
        )
    ).scalars()
    for race in races:
        race_state.record_imported_finish(race)
        entries = list(
            (
                await session.execute(
                    select(RaceEntry).where(RaceEntry.race_id == race.id).order_by(RaceEntry.id)
                )
            ).scalars()
        )
        order = list(range(1, len(entries) + 1))
        rng.shuffle(order)
        for position, entry in zip(order, entries, strict=True):
            if rng.random() < 0.02:
                entry.code = ResultCode.DNF
            else:
                entry.code = ResultCode.ZFP if rng.random() < 0.03 else ResultCode.FINISHED
                entry.finish_position = position
    await session.flush()


async def _read(session: AsyncSession, label: str) -> Season:
    series = (await session.execute(select(Series).where(Series.slug == label))).scalar_one()
    events = {
        e.matchday: e.id
        for e in (
            await session.execute(select(Event).where(Event.series_id == series.id))
        ).scalars()
    }
    found = Season(label, series.id, events[1], events[2], events[3])
    teams = (await session.execute(select(Team).where(Team.series_id == series.id))).scalars()
    for team in teams:
        if team.event_id is None:
            found.registrations[team.club_id] = team.id
        else:
            found.entries[(team.event_id, team.club_id)] = team.id
    rows = await session.execute(
        select(Team.club_id, TeamMembership.person_id)
        .join(TeamMembership, TeamMembership.team_id == Team.id)
        .where(Team.series_id == series.id, Team.event_id.is_(None))
        .order_by(TeamMembership.id)
    )
    for club_id, person_id in rows:
        found.squads.setdefault(club_id, []).append(person_id)
    return found
