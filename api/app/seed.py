"""Seed data: one season, two leagues, one completely sailed matchday.

Without real data volumes, scoring, pairing, and live view cannot be assessed —
that's why this seed generates a complete matchday with 16 flights of 3 races each.

The clubs are real, the sailor names are made up: personal data do not belong in
a test fixture.

    uv run python -m app.seed
"""

from __future__ import annotations

import asyncio
import random
from datetime import date, timedelta

from sqlalchemy import delete, select

from app.db import SessionLocal
from app.models import (
    Boat,
    Club,
    CrewRole,
    Event,
    EventCrew,
    EventStanding,
    EventStatus,
    Flight,
    Race,
    RaceEntry,
    RaceStatus,
    ResultCode,
    Sailor,
    Series,
    SeriesStanding,
    Team,
    TeamMembership,
    Venue,
)
from app.models.racing import BOAT_COLORS
from app.pairing import build_pairing
from app.services.standings import recompute_series
from app.text import slugify

JAHRGANG = 2026
BOATS = 6
FLIGHTS = 16
# A club registers ten members for the season (Story V-1); four of them sail
# at one matchday (Story V-2).
KADER = 10
CREW = 4

CLUBS: list[tuple[str, str, str]] = [
    ("Norddeutscher Regatta Verein", "NRV", "Hamburg"),
    ("Deutscher Touring Yacht-Club", "DTYC", "Tutzing"),
    ("Bayerischer Yacht-Club", "BYC", "Starnberg"),
    ("Württembergischer Yacht-Club", "WYC", "Friedrichshafen"),
    ("Verein Seglerhaus am Wannsee", "VSaW", "Berlin"),
    ("Flensburger Segel-Club", "FSC", "Flensburg"),
    ("Kieler Yacht-Club", "KYC", "Kiel"),
    ("Lindauer Segler-Club", "LSC", "Lindau"),
    ("Chiemsee Yacht Club", "CYC", "Prien"),
    ("Segel-Club Rhe", "SCRhe", "Hamburg"),
    ("Berliner Yacht-Club", "BYCB", "Berlin"),
    ("Hamburger Segel-Club", "HSC", "Hamburg"),
    ("Segler-Vereinigung Kiel", "SVK", "Kiel"),
    ("Münchner Yacht-Club", "MYC", "München"),
    ("Bodensee-Yachtclub Überlingen", "BYCÜ", "Überlingen"),
    ("Joersfelder Segel-Club", "JSC", "Joersfeld"),
    ("Duisburger Yacht-Club", "DYC", "Duisburg"),
    ("Potsdamer Yacht Club", "PYC", "Potsdam"),
]

VENUES: list[tuple[str, str, str]] = [
    ("Tutzing", "Tutzing", "Starnberger See"),
    ("Kiel", "Kiel", "Kieler Förde"),
    ("Friedrichshafen", "Friedrichshafen", "Bodensee"),
    ("Berlin-Wannsee", "Berlin", "Wannsee"),
]

FIRST_NAMES = ["Alex", "Chris", "Jona", "Kim", "Luca", "Mika", "Noa", "Robin", "Sam", "Toni"]
LAST_NAMES = ["Ahrens", "Bergmann", "Clausen", "Dahl", "Ehlers", "Frank", "Groth", "Hansen"]


async def seed() -> None:
    rng = random.Random(20260829)

    async with SessionLocal() as session:
        if (await session.execute(select(Club).limit(1))).scalar_one_or_none() is not None:
            await _wipe(session)

        # A series carries its year in the name — there is no separate season anymore.
        wertung = {"discard_after": [], "penalty_percent": 20}
        erste = Series(
            slug="dsbl-1-2026",
            name="1. Segel-Bundesliga 2026",
            short_name="1. Liga 2026",
            year=JAHRGANG,
            level=1,
            scoring=wertung,
        )
        zweite = Series(
            slug="dsbl-2-2026",
            name="2. Segel-Bundesliga 2026",
            short_name="2. Liga 2026",
            year=JAHRGANG,
            level=2,
            scoring=wertung,
        )
        junioren = Series(
            slug="junioren-2026",
            name="Junioren-Segelliga 2026",
            short_name="Junioren 2026",
            year=JAHRGANG,
            scoring=wertung,
        )
        champions = Series(
            slug="scl-2026",
            name="Sailing Champions League 2026",
            short_name="SCL 2026",
            year=JAHRGANG,
            scoring=wertung,
        )
        serien = [erste, zweite, junioren, champions]
        session.add_all(serien)

        venues = [
            Venue(slug=slugify(name), name=name, city=city, water=water)
            for name, city, water in VENUES
        ]
        session.add_all(venues)

        clubs = [
            Club(
                slug=slugify(short),
                name=name,
                short_name=short,
                city=city,
                description=(
                    f"{name} segelt seit Jahren in der Segel-Bundesliga. "
                    f"Heimatrevier ist {city}."
                ),
            )
            for name, short, city in CLUBS
        ]
        session.add_all(clubs)
        await session.flush()

        # The teams of all leagues. A club can compete in several; each
        # team has its own roster — juniors are different people than the first.
        zuordnungen: list[tuple[Series, Club]] = [
            *((erste, club) for club in clubs),
            *(
                (serie, club)
                for serie, anzahl in ((junioren, 12), (champions, 6))
                for club in clubs[:anzahl]
            ),
        ]

        mannschaften = [
            (
                serie,
                club,
                Team(name=club.short_name, club_id=club.id, series_id=serie.id),
            )
            for serie, club in zuordnungen
        ]
        session.add_all(team for _, _, team in mannschaften)
        await session.flush()

        # The acts are sailed for the first series. These are the registrations for
        # the series; the participation in each act is created below per event.
        meldungen = [team for serie, _, team in mannschaften if serie is erste]

        kader: dict[int, list[Sailor]] = {}
        laufend = 0
        for _serie, club, team in mannschaften:
            kader[team.id] = []
            for position in range(KADER):
                vorname = rng.choice(FIRST_NAMES)
                nachname = rng.choice(LAST_NAMES)
                laufend += 1
                sailor = Sailor(
                    first_name=vorname,
                    last_name=nachname,
                    # Unique via a sequential counter — names repeat
                    # and a club fields multiple teams.
                    email=f"{slugify(vorname)}.{slugify(nachname)}{laufend}"
                    f"@{club.slug}.example.com",
                    birth_date=date(
                        rng.randint(1985, 2005), rng.randint(1, 12), rng.randint(1, 28)
                    ),
                )
                session.add(sailor)
                await session.flush()
                kader[team.id].append(sailor)
                session.add(
                    TeamMembership(
                        team_id=team.id,
                        sailor_id=sailor.id,
                        role=(
                            CrewRole.HELM
                            if position == 0
                            else CrewRole.CREW
                            if position < CREW
                            else CrewRole.SUBSTITUTE
                        ),
                    )
                )

        # Three matchdays: one finished, one live, one planned.
        for matchday, (venue, status, day) in enumerate(
            [
                (venues[0], EventStatus.FINAL, date(2026, 5, 8)),
                (venues[1], EventStatus.LIVE, date(2026, 6, 12)),
                (venues[2], EventStatus.PLANNED, date(2026, 7, 17)),
            ],
            start=1,
        ):
            event = Event(
                slug=f"dsbl-1-2026-act-{matchday}",
                title=f"{matchday}. Spieltag {venue.city}",
                matchday=matchday,
                starts_on=day,
                ends_on=day + timedelta(days=2),
                status=status,
                team_count=len(meldungen),
                boat_count=BOATS,
                flight_count=FLIGHTS,
                series_id=erste.id,
                venue_id=venue.id,
            )
            session.add(event)
            await session.flush()

            # The participation in this act. This is where pairing list, results, and
            # lineup hang from — the series registration alongside carries the roster.
            antritte = [
                Team(
                    name=meldung.name,
                    club_id=meldung.club_id,
                    series_id=erste.id,
                    event_id=event.id,
                )
                for meldung in meldungen
            ]
            session.add_all(antritte)
            await session.flush()

            await _seed_matchday(session, event, antritte, rng, status)

            # Lineup for the matchday: the first four from the roster sail.
            for meldung, antritt in zip(meldungen, antritte, strict=True):
                for position, sailor in enumerate(kader[meldung.id][:CREW]):
                    session.add(
                        EventCrew(
                            event_id=event.id,
                            team_id=antritt.id,
                            sailor_id=sailor.id,
                            role=CrewRole.HELM if position == 0 else CrewRole.CREW,
                        )
                    )

        await session.commit()

        # Points and standings are derived — build them once after creation.
        for serie in serien:
            await recompute_series(session, serie.id)
        await session.commit()

    print(
        f"Seed complete: {len(CLUBS)} clubs with {KADER} members each, 4 series, 3 acts, "
        f"{FLIGHTS * 3} races per act"
    )


async def _seed_matchday(session, event, teams, rng, status) -> None:
    boats = [
        Boat(
            event_id=event.id,
            number=n,
            color=BOAT_COLORS[n - 1],
            sail_number=f"GER {700 + n}",
        )
        for n in range(1, BOATS + 1)
    ]
    session.add_all(boats)

    flights = [Flight(event_id=event.id, number=n) for n in range(1, FLIGHTS + 1)]
    session.add_all(flights)
    await session.flush()

    boat_by_number = {b.number: b for b in boats}
    flight_by_number = {f.number: f for f in flights}

    slots = build_pairing(team_count=len(teams), flights=FLIGHTS, boats=BOATS)
    races: dict[int, Race] = {}
    for slot in slots:
        if slot.sequence not in races:
            race = Race(
                flight_id=flight_by_number[slot.flight].id,
                number_in_flight=slot.race_in_flight,
                sequence=slot.sequence,
                status=RaceStatus.SCHEDULED,
            )
            session.add(race)
            races[slot.sequence] = race
    await session.flush()

    # A planned matchday has a pairing list but no results.
    # A live one is two-thirds sailed.
    if status == EventStatus.PLANNED:
        sailed_until = 0
    elif status == EventStatus.LIVE:
        sailed_until = FLIGHTS * 3 * 2 // 3
    else:
        sailed_until = FLIGHTS * 3

    by_race: dict[int, list] = {}
    for slot in slots:
        by_race.setdefault(slot.sequence, []).append(slot)

    for sequence, race_slots in by_race.items():
        race = races[sequence]
        finished = sequence <= sailed_until
        if finished:
            race.status = RaceStatus.FINISHED

        order = list(range(1, len(race_slots) + 1))
        rng.shuffle(order)
        for position, slot in zip(order, race_slots, strict=True):
            entry = RaceEntry(
                race_id=race.id,
                team_id=teams[slot.team_index].id,
                boat_id=boat_by_number[slot.boat_number].id,
            )
            if finished:
                # Occasionally a penalty so the scoring logic is visible.
                if rng.random() < 0.02:
                    entry.code = ResultCode.DNF
                elif rng.random() < 0.03:
                    entry.code = ResultCode.ZFP
                    entry.finish_position = position
                else:
                    entry.code = ResultCode.FINISHED
                    entry.finish_position = position
            session.add(entry)


async def _wipe(session) -> None:
    # Order by foreign keys: Team points to Event and Series, so it must
    # be deleted before both.
    for model in (
        RaceEntry, Race, Flight, Boat, EventCrew, EventStanding, SeriesStanding,
        TeamMembership, Team, Event, Sailor, Club, Venue, Series,
    ):
        await session.execute(delete(model))
    await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
