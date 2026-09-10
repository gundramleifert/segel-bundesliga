"""Seed data: one season, two leagues, one completely sailed matchday.

Without real data volumes, scoring, pairing, and live view cannot be assessed —
that's why this seed generates a complete matchday with 16 flights of 3 races each.

The clubs are real; every sailor name is synthetic — drawn from a generated 30 x 30
pool of made-up names (see ``_name_pool``), so no real person appears in the fixture.

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
    WaiverText,
)
from app.models.racing import BOAT_COLORS
from app.pairing import build_pairing
from app.services.standings import recompute_series
from app.text import slugify

YEAR = 2026
BOATS = 6
FLIGHTS = 16
# A club registers ten members for the season (Story V-1); four of them sail
# at one matchday (Story V-2).
SQUAD_SIZE = 10
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

# Sailor names are synthetic — a 30 x 30 pool of made-up names built from syllables, so
# 900 combinations cover the ~360 seeded sailors without a real person's name appearing.
# Its own RNG with a fixed seed: reproducible, and independent of the main seed sequence.
def _name_pool(count: int, *, seed: int, suffixes: tuple[str, ...] = ()) -> list[str]:
    rng = random.Random(seed)
    heads = (
        "ba be bo da de ei fa fi ha he ju ka ke la le li ma me mi na ne ni "
        "ro ru sa se si ta te to va ve vi"
    ).split()
    tails = "lin ric son den mar vik nor tal ber ken del ras nis wen".split()
    names: set[str] = set()
    while len(names) < count:
        name = rng.choice(heads) + rng.choice(tails)
        if suffixes:
            name += rng.choice(suffixes)
        names.add(name.capitalize())
    return sorted(names)


FIRST_NAMES = _name_pool(30, seed=4241)
LAST_NAMES = _name_pool(30, seed=4242, suffixes=("sen", "berg", "gaard", "dahl", "qvist"))


async def seed() -> None:
    rng = random.Random(20260829)

    async with SessionLocal() as session:
        if (await session.execute(select(Club).limit(1))).scalar_one_or_none() is not None:
            await _wipe(session)

        # A series carries its year in the name — there is no separate season anymore.
        # Everything the seed creates is a **running competition**, so it is published
        # (Story VA-8): a draft is invisible on the public site, and a seed of drafts would
        # leave the whole dev setup blank.
        scoring = {"discard_after": [], "penalty_percent": 20}
        first_league = Series(
            slug="dsbl-1-2026",
            name="1. Segel-Bundesliga 2026",
            short_name="1. Liga 2026",
            year=YEAR,
            level=1,
            published=True,
            scoring=scoring,
            description=(
                "## Willkommen zur 1. Segel-Bundesliga 2026\n\n"
                "Gesegelt wird nach **Low-Point-Wertung**: Wer die wenigsten Punkte "
                "sammelt, gewinnt. Die Serientabelle addiert die Platzierungen aller "
                "Acts; wer bei einem Act fehlt, bekommt dort *Teilnehmerzahl + 1* "
                "Punkte angerechnet.\n\n"
                "Wir freuen uns auf eine spannende Saison mit allen 18 Vereinen!"
            ),
        )
        second_league = Series(
            slug="dsbl-2-2026",
            name="2. Segel-Bundesliga 2026",
            short_name="2. Liga 2026",
            year=YEAR,
            level=2,
            published=True,
            scoring=scoring,
        )
        juniors = Series(
            slug="junioren-2026",
            name="Junioren-Segelliga 2026",
            short_name="Junioren 2026",
            year=YEAR,
            published=True,
            scoring=scoring,
        )
        champions = Series(
            slug="scl-2026",
            name="Sailing Champions League 2026",
            short_name="SCL 2026",
            year=YEAR,
            published=True,
            scoring=scoring,
        )
        series_list = [first_league, second_league, juniors, champions]
        session.add_all(series_list)

        # The liability waiver in force. One version is enough for the seed; a wording
        # change would be version 2 (Story S-2).
        session.add(
            WaiverText(
                version=1,
                title_en="Liability waiver and assumption of risk",
                body_en=(
                    "I take part in the Sailing Bundesliga at my own risk. I confirm that "
                    "I am medically fit to sail, can swim, and will wear a personal "
                    "flotation device on the water. I am responsible for deciding whether "
                    "to start or continue in the prevailing conditions (RRS 3). Neither "
                    "the organizing authority, the host club, the league, nor their "
                    "officials are liable for damage to property or injury to persons "
                    "caused by slight negligence, on land or on the water. Liability for "
                    "injury to life, body or health, and for intent or gross negligence, "
                    "remains unaffected."
                ),
                title_de="Haftungsausschluss und Risikoübernahme",
                body_de=(
                    "Ich nehme auf eigenes Risiko an der Segel-Bundesliga teil. Ich "
                    "bestätige, dass ich segeltauglich bin, schwimmen kann und auf dem "
                    "Wasser eine Rettungsweste trage. Die Entscheidung über Start und "
                    "Fortsetzung der Wettfahrt bei den herrschenden Bedingungen liegt bei "
                    "mir (WR 3). Weder der Veranstalter, der ausrichtende Verein, die Liga "
                    "noch deren Beauftragte haften für Sach- oder Vermögensschäden sowie "
                    "Personenschäden, die durch leichte Fahrlässigkeit an Land oder auf "
                    "dem Wasser verursacht werden. Die Haftung für Schäden aus der "
                    "Verletzung von Leben, Körper oder Gesundheit sowie für Vorsatz und "
                    "grobe Fahrlässigkeit bleibt unberührt."
                ),
                notes="Initial version.",
            )
        )

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
        assignments: list[tuple[Series, Club]] = [
            *((first_league, club) for club in clubs),
            *(
                (series, club)
                for series, count in ((juniors, 12), (champions, 6))
                for club in clubs[:count]
            ),
        ]

        teams = [
            (
                series,
                club,
                Team(name=club.short_name, club_id=club.id, series_id=series.id),
            )
            for series, club in assignments
        ]
        session.add_all(team for _, _, team in teams)
        await session.flush()

        # The acts are sailed for the first series. These are the registrations for
        # the series; the participation in each act is created below per event.
        registrations = [team for series, _, team in teams if series is first_league]

        squads: dict[int, list[Sailor]] = {}
        counter = 0
        for _series, club, team in teams:
            squads[team.id] = []
            for position in range(SQUAD_SIZE):
                first_name = rng.choice(FIRST_NAMES)
                last_name = rng.choice(LAST_NAMES)
                counter += 1
                sailor = Sailor(
                    first_name=first_name,
                    last_name=last_name,
                    # Unique via a sequential counter — names repeat
                    # and a club fields multiple teams.
                    email=f"{slugify(first_name)}.{slugify(last_name)}{counter}"
                    f"@{club.slug}.example.com",
                    # Juniors are teenagers — several are minors on a 2026 matchday, which
                    # is what makes the guardian path in Story S-2 testable against the
                    # seed. Everyone else is an adult.
                    birth_date=date(
                        rng.randint(2009, 2011)
                        if _series is juniors
                        else rng.randint(1985, 2004),
                        rng.randint(1, 12),
                        rng.randint(1, 28),
                    ),
                )
                session.add(sailor)
                await session.flush()
                squads[team.id].append(sailor)
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
                title=f"Act {matchday} {venue.city}",
                matchday=matchday,
                starts_on=day,
                ends_on=day + timedelta(days=2),
                status=status,
                # Real matchdays of a running series: visible to visitors.
                published=True,
                team_count=len(registrations),
                boat_count=BOATS,
                flight_count=FLIGHTS,
                series_id=first_league.id,
                venue_id=venue.id,
            )
            session.add(event)
            await session.flush()

            # The participation in this act. This is where pairing list, results, and
            # lineup hang from — the series registration alongside carries the roster.
            entries = [
                Team(
                    name=registration.name,
                    club_id=registration.club_id,
                    series_id=first_league.id,
                    event_id=event.id,
                )
                for registration in registrations
            ]
            session.add_all(entries)
            await session.flush()

            await _seed_matchday(session, event, entries, rng, status)

            # Lineup for the matchday: the first four from the roster sail.
            for registration, entry in zip(registrations, entries, strict=True):
                for position, sailor in enumerate(squads[registration.id][:CREW]):
                    session.add(
                        EventCrew(
                            event_id=event.id,
                            team_id=entry.id,
                            sailor_id=sailor.id,
                            role=CrewRole.HELM if position == 0 else CrewRole.CREW,
                        )
                    )

        await session.commit()

        # Points and standings are derived — build them once after creation.
        for series in series_list:
            await recompute_series(session, series.id)
        await session.commit()

    print(
        f"Seed complete: {len(CLUBS)} clubs with {SQUAD_SIZE} members each, 4 series, 3 acts, "
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
