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
    ClubMembership,
    CrewRole,
    Event,
    EventCrew,
    EventStanding,
    EventStatus,
    ExternalId,
    Flight,
    ImportRun,
    League,
    Person,
    Post,
    Race,
    RaceEntry,
    RaceStatus,
    ResultCode,
    Series,
    SeriesStanding,
    Team,
    TeamMembership,
    Venue,
    WaiverText,
)
from app.models.racing import BOAT_COLORS
from app.pairing import build_pairing
from app.seed_junioren import seed_junioren
from app.seed_posts import seed_posts
from app.services.standings import recompute_series
from app.text import slugify

YEAR = 2026
BOATS = 6
FLIGHTS = 16
# A club registers ten members for the season (Story V-1); four of them sail
# at one matchday (Story V-2).
SQUAD_SIZE = 10
CREW = 4

# The real 2026 line-ups of both divisions: (name, code, home, division). A code is the
# seed's key for a club (its slug), so it is unique here even where the real one is not:
# the two KYCs carry their state, as the league writes them (`KYC (SH)` Kiel, `KYC (BA)`
# Konstanz), and the Berliner YC is `BYCB` beside the Bayerischer `BYC`.
CLUBS: list[tuple[str, str, str, int]] = [
    # The test club (`seed_users`) — first, so its teams come first: it sails the 2. Liga,
    # the juniors and the SCL, and it hosts the test event.
    ("Akademischer Segelverein Warnemünde", "ASVW", "Warnemünde", 2),
    ("Bayerischer Yacht-Club", "BYC", "Starnberg", 1),
    ("Berliner Yacht-Club", "BYCB", "Berlin", 1),
    ("Blankeneser Segel-Club", "BSC", "Hamburg", 1),
    ("Bocholter Yachtclub", "BoYC", "Bocholt", 1),
    ("Bodensee-Yacht-Club Überlingen", "BYCÜ", "Überlingen", 1),
    ("Düsseldorfer Yachtclub", "DYC", "Düsseldorf", 1),
    ("Entdecker- und Seefahrerfördervereinigung", "EnSFr", "Hamburg", 1),
    ("Joersfelder Segel-Club", "JSC", "Berlin", 1),
    ("Kieler Yacht-Club", "KYC (SH)", "Kiel", 1),
    ("Klub am Rupenhorn", "KaR", "Berlin", 1),
    ("Mühlenberger Segel-Club", "MSC", "Hamburg", 1),
    ("Münchner Yacht-Club", "MYC", "München", 1),
    ("Norddeutscher Regatta Verein", "NRV", "Hamburg", 1),
    ("Potsdamer Yacht Club", "PYC", "Potsdam", 1),
    ("Segel- und Motorboot Club Überlingen", "SMCÜ", "Überlingen", 1),
    ("Seglervereinigung Itzehoe", "SVI", "Itzehoe", 1),
    ("Segler-Vereinigung Wuppertal", "SVW", "Wuppertal", 1),
    ("Württembergischer Yacht-Club", "WYC", "Friedrichshafen", 1),
    ("Bucerius Sailing", "BUC", "Hamburg", 2),
    ("Deutscher Touring Yacht-Club", "DTYC", "Tutzing", 2),
    ("Essener Turn- und Fechtklub", "ETUF", "Essen", 2),
    ("Flensburger Segel-Club", "FSC", "Flensburg", 2),
    ("Frankfurter Yachtclub", "FYC", "Frankfurt", 2),
    ("Hamburger Segel-Club", "HSC", "Hamburg", 2),
    ("Konstanzer Yacht-Club", "KYC (BA)", "Konstanz", 2),
    ("Lübecker Segler-Verein von 1885", "LSV", "Lübeck", 2),
    ("Lübecker Yacht-Club", "LYC", "Lübeck", 2),
    ("Münchener Ruder- und Segelverein „Bayern“ von 1910", "MRSV", "München", 2),
    ("Regatta-Segler Neuruppin", "RSN", "Neuruppin", 2),
    ("Segel-Club Hansa Münster", "SCHM", "Münster", 2),
    ("Segelclub Rheingau", "SCRh", "Rheingau", 2),
    ("Segel-Club Ville", "SCV", "Erftstadt", 2),
    ("Seglervereinigung 1903", "SV03", "Berlin", 2),
    ("Verein Seglerhaus am Wannsee", "VSaW", "Berlin", 2),
    ("Wir sind Wir e.V.", "WsW", "Sachsen", 2),
]

# Name, city, water, and where on the water the boats sail — real coordinates, so the
# default course (Story L-2) lands on the real lake or fjord on the map.
VENUES: list[tuple[str, str, str, float, float]] = [
    ("Tutzing", "Tutzing", "Starnberger See", 47.912, 11.298),
    ("Kiel", "Kiel", "Kieler Förde", 54.424, 10.190),
    ("Friedrichshafen", "Friedrichshafen", "Bodensee", 47.648, 9.487),
    ("Berlin-Wannsee", "Berlin", "Wannsee", 52.437, 13.170),
    # The 2027 stops (yacht.de, 18 Oct 2026) the 2026 acts do not already sail at.
    ("Warnemünde", "Warnemünde", "Ostsee", 54.190, 12.060),
    ("Überlingen", "Überlingen", "Bodensee", 47.760, 9.170),
    ("Kiel-Strande", "Strande", "Kieler Förde", 54.440, 10.180),
    ("Hamburg-Alster", "Hamburg", "Außenalster", 53.565, 10.003),
]

# The 1. Liga's 2027 as announced (yacht.de, 18 Oct 2026): it opens at Friedrichshafen and
# ends in Hamburg; Überlingen, Berlin, Kiel/Strande and Warnemünde lie between, with no
# dates or order yet — so those carry neither, the normal early state of an event. Hosts
# are not announced; Warnemünde's is the test club, so its people have a season to
# prepare (`seed_users`). (venue, act, first day, host's code)
ACTS_2027: list[tuple[str, int | None, date | None, str | None]] = [
    ("Friedrichshafen", 1, date(2027, 4, 16), None),
    ("Überlingen", None, None, None),
    ("Berlin-Wannsee", None, None, None),
    ("Kiel-Strande", None, None, None),
    ("Warnemünde", None, None, "ASVW"),
    ("Hamburg-Alster", 6, date(2027, 10, 14), None),
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
        # The association's competitions — the public site's top row
        # (docs/site-structure.md). A series names its year; the league links the years.
        # The 1. and 2. Liga are two leagues (Story B-14): they sail the same weekends,
        # but each is its own entry on the site.
        first_division = League(
            slug="1-liga",
            short_name="1. Liga",
            name="1. Segel-Bundesliga",
            tagline="18 clubs, six weekends — the last four go down.",
            position=1,
        )
        second_division = League(
            slug="2-liga",
            short_name="2. Liga",
            name="2. Segel-Bundesliga",
            tagline="18 clubs, five weekends — the first four go up.",
            position=2,
        )
        junior_league = League(
            slug="junioren-liga",
            short_name="Junioren",
            name="Deutsche Junioren Segel-Liga",
            tagline="AK16 to AK21 — the talent school of club sailing.",
            position=3,
        )
        cup = League(
            slug="dsl-pokal",
            short_name="DSL-Pokal",
            name="DSL-Pokal",
            tagline="One weekend where amateur meets professional.",
            position=4,
        )
        session.add_all([first_division, second_division, junior_league, cup])
        await session.flush()

        scoring = {"discard_after": [], "penalty_percent": 20}
        first_league = Series(
            slug="dsbl-1-2026",
            name="1. Segel-Bundesliga 2026",
            short_name="1. Liga 2026",
            year=YEAR,
            level=1,
            league_id=first_division.id,
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
            league_id=second_division.id,
            published=True,
            scoring=scoring,
        )
        juniors = Series(
            slug="junioren-2026",
            name="Junioren-Segelliga 2026",
            short_name="Junioren 2026",
            year=YEAR,
            league_id=junior_league.id,
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
        # Next year's juniors, being prepared: a draft with no events and no teams yet, so
        # the public site stays on this year (the current year is the newest one not in the
        # future). Its manager is the juniors' (`seed_users`).
        session.add(
            Series(
                slug=f"junioren-{YEAR + 1}",
                name=f"Junioren-Segelliga {YEAR + 1}",
                short_name=f"Junioren {YEAR + 1}",
                year=YEAR + 1,
                league_id=junior_league.id,
                published=False,
                scoring=scoring,
            )
        )

        # The liability waiver in force. One version is enough for the seed; a wording
        # change would be version 2 (Story S-2).
        session.add(
            WaiverText(
                version=1,
                title_en="Liability waiver and assumption of risk",
                body_en=(
                    "I take part in this competition at my own risk. I confirm that "
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
                    "Ich nehme auf eigenes Risiko an dieser Veranstaltung teil. Ich "
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
            Venue(slug=slugify(name), name=name, city=city, water=water, lat=lat, lon=lon)
            for name, city, water, lat, lon in VENUES
        ]
        session.add_all(venues)

        clubs = [
            Club(
                slug=slugify(short),
                name=name,
                short_name=short,
                city=city,
                description=(
                    f"{name} segelt seit Jahren in der Segel-Bundesliga. Heimatrevier ist {city}."
                ),
            )
            for name, short, city, _division in CLUBS
        ]
        session.add_all(clubs)
        await session.flush()

        # The teams of all leagues. A club can compete in several; each
        # team has its own roster — juniors are different people than the first.
        division = {1: first_league, 2: second_league}
        assignments: list[tuple[Series, Club]] = [
            *((division[level], club) for club, (_, _, _, level) in zip(clubs, CLUBS, strict=True)),
            # Not the juniors: their real 2026 field comes with their results, below.
            *((champions, club) for club in clubs[:6]),
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

        # The acts are sailed in both divisions. These are each one's registrations for
        # the series; the participation in each act is created below per event.
        registrations = {
            series.id: [team for each, _, team in teams if each is series]
            for series in (first_league, second_league)
        }

        squads: dict[int, list[Person]] = {}
        counter = 0
        for _series, club, team in teams:
            squads[team.id] = []
            for position in range(SQUAD_SIZE):
                first_name = rng.choice(FIRST_NAMES)
                last_name = rng.choice(LAST_NAMES)
                counter += 1
                person = Person(
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
                        rng.randint(2009, 2011) if _series is juniors else rng.randint(1985, 2004),
                        rng.randint(1, 12),
                        rng.randint(1, 28),
                    ),
                )
                session.add(person)
                await session.flush()
                squads[team.id].append(person)
                session.add(ClubMembership(person_id=person.id, club_id=club.id))
                session.add(
                    TeamMembership(
                        team_id=team.id,
                        person_id=person.id,
                        role=(
                            CrewRole.HELM
                            if position == 0
                            else CrewRole.CREW
                            if position < CREW
                            else CrewRole.SUBSTITUTE
                        ),
                    )
                )

        # Three matchdays: one finished, one live, one planned — each with a host club, who
        # pays its claims (Story F-2). The planned one is the test club's: its 2. Liga act
        # is the test event. Both divisions sail each weekend at the same venue, the 1.
        # Liga's acts first, so they keep the lowest ids.
        by_short = {club.short_name: club for club in clubs}
        weekends = [
            (venues[0], "DTYC", EventStatus.FINAL, date(2026, 5, 8)),
            (venues[1], "KYC (SH)", EventStatus.LIVE, date(2026, 6, 12)),
            (venues[2], "ASVW", EventStatus.PLANNED, date(2026, 7, 17)),
        ]
        for league_series, level, (matchday, (venue, host, status, day)) in (
            (league_series, level, act)
            for league_series, level in ((first_league, 1), (second_league, 2))
            for act in enumerate(weekends, start=1)
        ):
            roster = registrations[league_series.id]
            event = Event(
                slug=f"dsbl-{level}-2026-act-{matchday}",
                title=f"Act {matchday} {venue.city}",
                matchday=matchday,
                starts_on=day,
                ends_on=day + timedelta(days=2),
                status=status,
                # Real matchdays of a running series: visible to visitors.
                published=True,
                team_count=len(roster),
                boat_count=BOATS,
                flight_count=FLIGHTS,
                series_id=league_series.id,
                venue_id=venue.id,
                host_club_id=by_short[host].id,
            )
            session.add(event)
            await session.flush()

            # The participation in this act. This is where pairing list, results, and
            # lineup hang from — the series registration alongside carries the roster.
            entries = [
                Team(
                    name=registration.name,
                    club_id=registration.club_id,
                    series_id=league_series.id,
                    event_id=event.id,
                )
                for registration in roster
            ]
            session.add_all(entries)
            await session.flush()

            await _seed_matchday(session, event, entries, rng, status)

            # Lineup for the matchday: the first four from the roster sail.
            for registration, entry in zip(roster, entries, strict=True):
                for position, person in enumerate(squads[registration.id][:CREW]):
                    session.add(
                        EventCrew(
                            event_id=event.id,
                            team_id=entry.id,
                            person_id=person.id,
                            role=CrewRole.HELM if position == 0 else CrewRole.CREW,
                        )
                    )

        # Next year's 1. Liga, being prepared: a draft series with its announced acts, no
        # clubs yet — registering them is what there is to practise. Drafts, so the public
        # site stays on this year.
        next_year = Series(
            slug=f"dsbl-1-{YEAR + 1}",
            name=f"1. Segel-Bundesliga {YEAR + 1}",
            short_name=f"1. Liga {YEAR + 1}",
            year=YEAR + 1,
            level=1,
            league_id=first_division.id,
            published=False,
            scoring=scoring,
        )
        session.add(next_year)
        await session.flush()
        venue_by_slug = {venue.slug: venue for venue in venues}
        for place, act, day, host in ACTS_2027:
            venue = venue_by_slug[slugify(place)]
            session.add(
                Event(
                    slug=f"dsbl-1-{YEAR + 1}-{venue.slug}",
                    title=f"Act {act} {venue.city}" if act else f"{venue.city} {YEAR + 1}",
                    matchday=act,
                    starts_on=day,
                    ends_on=day + timedelta(days=2) if day else None,
                    status=EventStatus.PLANNED,
                    published=False,
                    team_count=sum(1 for *_, level in CLUBS if level == 1),
                    boat_count=BOATS,
                    flight_count=FLIGHTS,
                    series_id=next_year.id,
                    venue_id=venue.id,
                    host_club_id=by_short[host].id if host else None,
                )
            )

        await session.commit()

        # The Junioren-Liga as it really sailed 2026 — its clubs, second teams and results,
        # from SAP's recorded answer (`app.seed_junioren`) — and a made-up squad for each of
        # its real teams, teenagers, so a minor's waiver stays testable against the seed.
        await seed_junioren(SessionLocal)
        await _junior_squads(session, juniors)
        await session.commit()

        # Points and standings are derived — build them once after creation.
        for series in series_list:
            await recompute_series(session, series.id)
        await session.commit()

        # What the news and press pages showed when they were static content (Story R-1).
        await seed_posts(session)
        await session.commit()

    print(
        f"Seed complete: {len(CLUBS)} clubs with {SQUAD_SIZE} members each, 4 series and "
        f"two drafts for {YEAR + 1}, 3 acts in each division and {len(ACTS_2027)} draft acts, "
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


async def _junior_squads(session, juniors: Series) -> None:
    """A squad for each club registered for the juniors' series — after the import, which
    is what registers them. Its own random sequence, so the other leagues' sailors are the
    same as before the juniors were real."""
    rng = random.Random(20261023)
    registrations = (
        await session.execute(
            select(Team, Club)
            .join(Club, Team.club_id == Club.id)
            .where(Team.series_id == juniors.id, Team.event_id.is_(None))
            .order_by(Club.short_name)
        )
    ).all()
    for counter, (team, club) in enumerate(registrations):
        for position in range(SQUAD_SIZE):
            first_name, last_name = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
            person = Person(
                first_name=first_name,
                last_name=last_name,
                email=f"{slugify(first_name)}.{slugify(last_name)}.j{counter}x{position}"
                f"@{club.slug}.example.com",
                # Teenagers: several are minors on a 2026 matchday (Story S-2).
                birth_date=date(rng.randint(2009, 2011), rng.randint(1, 12), rng.randint(1, 28)),
            )
            session.add(person)
            await session.flush()
            session.add(ClubMembership(person_id=person.id, club_id=club.id))
            session.add(
                TeamMembership(
                    team_id=team.id,
                    person_id=person.id,
                    role=(
                        CrewRole.HELM
                        if position == 0
                        else CrewRole.CREW
                        if position < CREW
                        else CrewRole.SUBSTITUTE
                    ),
                )
            )


async def _wipe(session) -> None:
    # Order by foreign keys: Team points to Event and Series, so it must
    # be deleted before both. The import's links and runs go too: they name rows the wipe
    # removes (the juniors are imported, `app.seed_junioren`).
    for model in (
        ExternalId,
        ImportRun,
        Post,
        RaceEntry,
        Race,
        Flight,
        Boat,
        EventCrew,
        EventStanding,
        SeriesStanding,
        TeamMembership,
        Team,
        Event,
        ClubMembership,
        Person,
        Club,
        Venue,
        Series,
        League,
    ):
        await session.execute(delete(model))
    await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
