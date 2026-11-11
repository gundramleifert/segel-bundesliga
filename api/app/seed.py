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
from typing import NamedTuple

from sqlalchemy import delete, select

from app.db import SessionLocal
from app.imports.m2s import import_recorded_league
from app.imports.tractrac import import_tractrac
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
    Series,
    SeriesStanding,
    Team,
    TeamMembership,
    Venue,
    WaiverText,
)
from app.models.auth import Grant, Relation, User  # noqa: TID251 — REVIEW 4.5
from app.models.racing import BOAT_COLORS
from app.pairing.catalog import load_entry, shuffle_pairing
from app.seed_junioren import seed_cup, seed_junioren
from app.seed_posts import seed_posts
from app.services import people
from app.services.event_readiness import event_readiness
from app.services.pairing_service import PairingDraft, publish_pairing
from app.services.participation import activate
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
    # The juniors' 2027 stops (deutsche-segelliga.de, "Termine 2027", 13 Oct 2026).
    ("Konstanz", "Konstanz", "Bodensee", 47.668, 9.190),
    ("Borgwedel", "Borgwedel", "Schlei", 54.500, 9.700),
]


class Act2027(NamedTuple):
    """One weekend of the 2027 season, as announced."""

    place: str
    #: Its act number in the 1. Liga, and in the 2. Liga — None where it does not sail.
    first: int
    second: int | None
    #: The first day, where announced.
    starts_on: date | None
    #: The host clubs' codes; the first is the event's host club, a co-host is named in
    #: the comment only — an event has one host (`Event.host_club_id`).
    hosts: tuple[str, ...]


# The 2027 season as announced (yacht.de, 18 Oct 2026; acts and hosts from the league
# office, 2026-11-01). The 2. Liga sails the same weekends but one act fewer, as every
# year since 2018: Kiel/Strande is the 1. Liga's alone, so from Warnemünde on the 2. Liga
# counts one lower. Dates from the association's "Termine 2027" (deutsche-segelliga.de,
# 13 Oct 2026). Friedrichshafen
# is hosted by WYC with KYC (Konstanz), Überlingen by BYCÜ with SMCÜ. Warnemünde's host
# is the test club, so its people have a season to prepare (`seed_users`).
ACTS_2027: list[Act2027] = [
    Act2027("Friedrichshafen", 1, 1, date(2027, 4, 16), ("WYC", "KYC (BA)")),
    Act2027("Überlingen", 2, 2, date(2027, 4, 30), ("BYCÜ", "SMCÜ")),
    Act2027("Berlin-Wannsee", 3, 3, date(2027, 7, 2), ("BYCB",)),
    Act2027("Kiel-Strande", 4, None, date(2027, 7, 30), ("KYC (SH)",)),
    Act2027("Warnemünde", 5, 4, date(2027, 9, 17), ("ASVW",)),
    Act2027("Hamburg-Alster", 6, 5, date(2027, 10, 14), ("NRV",)),
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


def pseudonym(numbers: dict[str, int], club: Club) -> tuple[str, str]:
    """A sailor's first and last name: `Alice1 ASVW`, `Bob1 ASVW`, `Alice2 ASVW`, … per
    club."""
    i = numbers[club.short_name] = numbers.get(club.short_name, -1) + 1
    return f"{('Alice', 'Bob')[i % 2]}{1 + i // 2}", club.short_name


async def seed() -> None:
    rng = random.Random(20260829)
    numbers: dict[str, int] = {}

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
        # The real series' registrations come with the import, without squads — no source
        # says who sailed (the demo series that carried made-up ones are gone, 2026-11-06).
        # Not the juniors: their real 2026 field comes with their results, below.
        assignments: list[tuple[Series, Club]] = [(champions, club) for club in clubs[:6]]

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

        squads: dict[int, list[Person]] = {}
        counter = 0
        for _series, club, team in teams:
            squads[team.id] = []
            for position in range(SQUAD_SIZE):
                # Drawn still, so the rest of the seed's random sequence stays as it was.
                rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
                first_name, last_name = pseudonym(numbers, club)
                counter += 1
                # With their account (#52), unverified: nobody signs in as an invented
                # sailor, but every person has one.
                person = await people.new_person(
                    session,
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
                squads[team.id].append(person)
                await activate(session, person, club.id)
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

        by_short = {club.short_name: club for club in clubs}

        # Next year's 1. and 2. Liga, being prepared: a draft series each with its announced
        # acts — the 1. Liga's clubs follow from this year's tables once they are in
        # (`_first_division_next_year`); the 2. Liga's are still to be entered. Drafts, so
        # the public site stays on this year.
        venue_by_slug = {venue.slug: venue for venue in venues}
        for level, league in ((1, first_division), (2, second_division)):
            next_year = Series(
                slug=f"dsbl-{level}-{YEAR + 1}",
                name=f"{level}. Segel-Bundesliga {YEAR + 1}",
                short_name=f"{level}. Liga {YEAR + 1}",
                year=YEAR + 1,
                level=level,
                league_id=league.id,
                published=False,
                scoring=scoring,
            )
            session.add(next_year)
            await session.flush()
            for planned in ACTS_2027:
                act = planned.first if level == 1 else planned.second
                if act is None:
                    continue
                venue = venue_by_slug[slugify(planned.place)]
                day = planned.starts_on
                session.add(
                    Event(
                        slug=f"dsbl-{level}-{YEAR + 1}-{venue.slug}",
                        title=f"Act {act} {venue.city}",
                        matchday=act,
                        starts_on=day,
                        ends_on=day + timedelta(days=2) if day else None,
                        status=EventStatus.PLANNED,
                        published=False,
                        team_count=sum(1 for *_, lvl in CLUBS if lvl == level),
                        boat_count=BOATS,
                        flight_count=FLIGHTS,
                        series_id=next_year.id,
                        venue_id=venue.id,
                        host_club_id=by_short[planned.hosts[0]].id,
                    )
                )

        await session.commit()

        # The Junioren-Liga as it really sailed 2026 — its clubs, second teams and results,
        # from SAP's recorded answer (`app.seed_junioren`) — and a made-up squad for each of
        # its real teams, teenagers, so a minor's waiver stays testable against the seed.
        await seed_junioren(SessionLocal)
        # The DSL-Pokal 2026 from the same host's recorded answer.
        report = await seed_cup(SessionLocal)
        if report.errors or report.conflicts:
            raise SystemExit(f"The DSL-Pokal import did not come in cleanly:\n{report.render()}")
        await _junior_squads(session, juniors, numbers)
        await session.commit()

        # The 1. and 2. Liga 2026 as they really sailed — every act, its clubs and results,
        # from TracTrac's scoreboards and the league's pairing lists, recorded in
        # `app/seed_data/dsbl-2026/` (Story A-14).
        report = await import_tractrac(SessionLocal, publish=True, log=lambda _: None)
        if report.errors or report.conflicts or report.warnings:
            raise SystemExit(f"The 2026 import did not come in cleanly:\n{report.render()}")
        # Their notice boards and entries from Manage2Sail — the only source of documents
        # (decided 2026-10-28), recorded in `app/seed_data/m2s-2026/`.
        report = await import_recorded_league(SessionLocal, log=lambda _: None)
        if report.errors or report.conflicts or report.warnings or report.unassigned:
            raise SystemExit(f"The Manage2Sail import did not come in cleanly:\n{report.render()}")

        # Points and standings are derived — build them once after creation.
        for series in series_list:
            await recompute_series(session, series.id)
        await session.commit()

        # The 1. Liga 2027 is the 2026 tables' outcome, so its clubs are known.
        await _first_division_next_year(session)
        await _juniors_and_cup_next_year(session)
        await session.commit()

        # What the news and press pages showed when they were static content (Story R-1).
        await seed_posts(session)
        await session.commit()

    print(
        f"Seed complete: {len(CLUBS)} clubs, the 1. and 2. Liga {YEAR} as sailed (11 acts) and "
        f"the Junioren-Liga's; the 1. and 2. Liga {YEAR + 1} as drafts with "
        f"{len(ACTS_2027)} and {sum(a.second is not None for a in ACTS_2027)} acts"
    )


async def publish_preview() -> None:
    """The Render preview (branch `vorschau`, `api/Dockerfile`): the 1. Liga 2027
    published, whose clubs and draws are known. Public, yet the site stays on 2026: the
    current year is the newest one not in the future."""
    async with SessionLocal() as session:
        series = (
            await session.execute(select(Series).where(Series.slug == f"dsbl-1-{YEAR + 1}"))
        ).scalar_one()
        series.published = True
        for event in (
            await session.execute(select(Event).where(Event.series_id == series.id))
        ).scalars():
            event.published = True
        await session.commit()


# The league's rule (deutsche-segelliga.de/wettbewerbe, `web/src/content/index.ts`): the 1.
# Liga's last four go down, the 2. Liga's first four come up.
STAY_UP = 14
GO_UP = 4


async def _ranked_clubs(session, slug: str) -> list[Club]:
    """A series' clubs in the order of its final table."""
    return list(
        (
            await session.execute(
                select(Club)
                .join(Team, Team.club_id == Club.id)
                .join(SeriesStanding, SeriesStanding.team_id == Team.id)
                .join(Series, Series.id == SeriesStanding.series_id)
                .where(Series.slug == slug)
                .order_by(SeriesStanding.rank)
            )
        ).scalars()
    )


class Weekend2027(NamedTuple):
    """One junior act or the cup in 2027, as announced: series slug, matchday, venue slug,
    first day, the host's code."""

    series: str
    matchday: int
    venue: str
    starts_on: date
    host: str


# deutsche-segelliga.de, "Termine 2027" (13 Oct 2026). Konstanz is hosted by KYC with the
# Schüler Segel-Club Konstanz, named in this comment only — an event has one host.
WEEKENDS_2027: list[Weekend2027] = [
    Weekend2027("junioren-2027", 1, "konstanz", date(2027, 5, 7), "KYC (BA)"),
    Weekend2027("junioren-2027", 2, "berlin-wannsee", date(2027, 7, 9), "PYC"),
    Weekend2027("junioren-2027", 3, "borgwedel", date(2027, 8, 13), "SSVL"),
    Weekend2027("junioren-2027", 4, "warnemuende", date(2027, 9, 10), "ASVW"),
    Weekend2027("dsl-pokal-2027", 1, "hamburg-alster", date(2027, 10, 22), "NRV"),
]


async def _juniors_and_cup_next_year(session) -> None:
    """The juniors' four acts and the cup of 2027 as announced — drafts with dates, venue
    and host, sized like this year's Finale and cup; no teams yet. The cup's series is
    made here, like the import made this year's."""
    cup_2026 = (
        await session.execute(select(Series).where(Series.slug == f"dsl-pokal-{YEAR}"))
    ).scalar_one()
    cup = Series(
        slug=f"dsl-pokal-{YEAR + 1}",
        name=f"DSL-Pokal {YEAR + 1}",
        short_name=f"DSL-Pokal {YEAR + 1}",
        year=YEAR + 1,
        league_id=cup_2026.league_id,
        published=False,
        scoring=cup_2026.scoring,
    )
    session.add(cup)
    await session.flush()
    # This year's last act of each series is the size the next year's is planned at.
    like = {}
    for slug in (f"junioren-{YEAR}", f"dsl-pokal-{YEAR}"):
        like[slug.replace(str(YEAR), str(YEAR + 1))] = (
            await session.execute(
                select(Event)
                .join(Series, Event.series_id == Series.id)
                .where(Series.slug == slug)
                .order_by(Event.matchday.desc())
                .limit(1)
            )
        ).scalar_one()
    series = {
        each.slug: each
        for each in (await session.execute(select(Series).where(Series.slug.in_(like)))).scalars()
    }
    venues = {v.slug: v for v in (await session.execute(select(Venue))).scalars()}
    clubs = {c.short_name: c for c in (await session.execute(select(Club))).scalars()}
    for weekend in WEEKENDS_2027:
        size, venue = like[weekend.series], venues[weekend.venue]
        session.add(
            Event(
                slug=f"{weekend.series}-act-{weekend.matchday}",
                title=f"Act {weekend.matchday} {venue.city}",
                matchday=weekend.matchday,
                starts_on=weekend.starts_on,
                ends_on=weekend.starts_on + timedelta(days=2),
                status=EventStatus.PLANNED,
                published=False,
                team_count=size.team_count,
                boat_count=size.boat_count,
                flight_count=size.flight_count,
                teams_per_club=size.teams_per_club,
                series_id=series[weekend.series].id,
                venue_id=venue.id,
                host_club_id=clubs[weekend.host].id if weekend.host in clubs else None,
            )
        )


async def _first_division_next_year(session) -> None:
    """The 1. Liga 2027 with its clubs: places 1–14 of the 1. Liga 2026 and 1–4 of the 2.
    Liga 2026, registered for the series and entered in every act, each act with its six
    boats. An act with announced dates also has its pairing list from the catalog, as
    `pairing/from-catalog` draws it — an act without dates is not ready for a draw (VA-8),
    and no date is invented. Still drafts. The 2. Liga 2027 waits: its places 13–18 of 2026
    requalify at the DSL-Pokal (`dsl-pokal-2026`), whose 2. Liga clubs are not
    yet picked out of its table."""
    first = await _ranked_clubs(session, f"dsbl-1-{YEAR}")
    second = await _ranked_clubs(session, f"dsbl-2-{YEAR}")
    clubs = first[:STAY_UP] + second[:GO_UP]
    assert len(clubs) == STAY_UP + GO_UP, "the 2026 tables are incomplete"
    series = (
        await session.execute(select(Series).where(Series.slug == f"dsbl-1-{YEAR + 1}"))
    ).scalar_one()
    session.add_all(Team(name=c.short_name, club_id=c.id, series_id=series.id) for c in clubs)
    events = (
        await session.execute(
            select(Event).where(Event.series_id == series.id).order_by(Event.matchday)
        )
    ).scalars()
    for n, event in enumerate(events):
        entries = [
            Team(name=c.short_name, number=1, club_id=c.id, series_id=series.id, event_id=event.id)
            for c in clubs
        ]
        session.add_all(entries)
        session.add_all(
            Boat(
                event_id=event.id, number=b, color=BOAT_COLORS[b - 1], sail_number=f"GER {700 + b}"
            )
            for b in range(1, BOATS + 1)
        )
        await session.flush()
        if await event_readiness(session, event):
            continue
        pairing = shuffle_pairing(load_entry(len(entries), BOATS, FLIGHTS), seed=n)
        await publish_pairing(
            session, event, PairingDraft.from_import(pairing, [t.id for t in entries])
        )


async def _junior_squads(session, juniors: Series, numbers: dict[str, int]) -> None:
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
            rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
            first_name, last_name = pseudonym(numbers, club)
            person = await people.new_person(
                session,
                first_name=first_name,
                last_name=last_name,
                email=f"{slugify(first_name)}.{slugify(last_name)}.j{counter}x{position}"
                f"@{club.slug}.example.com",
                # Teenagers: several are minors on a 2026 matchday (Story S-2).
                birth_date=date(rng.randint(2009, 2011), rng.randint(1, 12), rng.randint(1, 28)),
            )
            await activate(session, person, club.id)
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
    # Every person has an account (#52): the accounts nobody ever signed in to — the
    # invented sailors' — go with their people and their tuples, and every membership's
    # ``member`` tuple with the memberships. Someone who signed in keeps their account and
    # their person, in no club now.
    unused = list(
        (
            await session.execute(
                select(User.id).where(
                    User.id.in_(select(Person.user_id)), User.email_verified.is_(False)
                )
            )
        ).scalars()
    )
    await session.execute(
        delete(Grant).where((Grant.relation == Relation.MEMBER) | Grant.user_id.in_(unused))
    )
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
        Club,
        Venue,
        Series,
        League,
    ):
        await session.execute(delete(model))
    await session.execute(delete(Person).where(Person.user_id.in_(unused)))
    await session.execute(delete(User).where(User.id.in_(unused)))
    await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
