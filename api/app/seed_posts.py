"""The posts the site starts with — Story R-1.

What the public pages showed as static content before editorial could write on the site:
the association's real articles and press releases, and examples that fill the pages and
say so on them (``example``). The examples are **drafts** — a real site shows none of
them (docs/PLAN_SEEDING.md), and since the demo is gone (2026-11-06) nothing publishes them.
"""

from __future__ import annotations

import html
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import League, Post
from app.seed_press import PRESS_RELEASES
from app.services.rich_text import clean_html
from app.text import slugify

POSTS: list[dict] = [
    {
        "kind": "news",
        "slug": "prototyp-der-neuen-website",
        "title": "Die neue Website: Prototyp auf der Jahreshauptversammlung",
        "published_on": "2026-11-07",
        "league": None,
        "teaser": "Morgen stellen wir auf der Jahreshauptversammlung der Deutschen Segel-Liga "
        "den Prototyp der neuen Website vor – und freuen uns auf eure Verbesserungsvorschläge.",
        "body": "Morgen, am 8. November 2026, stellen wir auf der Jahreshauptversammlung der "
        "Deutschen Segel-Liga den Prototyp der neuen Website vor – die Seite, auf der ihr "
        "gerade lest.\n"
        "\n"
        "Es ist ein Prototyp: Vieles funktioniert schon, manches fehlt noch, und einiges wird "
        "sich ändern. Genau dafür brauchen wir euch. Was fällt euch auf, was fehlt, was sollte "
        "anders sein?\n"
        "\n"
        "Verbesserungsvorschläge nehmen wir gern per E-Mail an website@deutsche-segelliga.de "
        "entgegen.",
        "author": "Redaktion",
        "photo_url": None,
        "photo_credit": None,
        "example": False,
    },
    {
        # Copied from deutsche-segelliga.de (WordPress post 432), without its picture, which
        # is the association's site's, and the PDF link.
        "kind": "news",
        "slug": "termine-2027-segel-bundesliga-junioren-liga-und-pokal",
        "title": "Termine 2027: Segel-Bundesliga, Junioren-Liga und Pokal",
        "published_on": "2026-10-13",
        "league": None,
        "teaser": "Die Termine für die Saison 2027 stehen fest: alle Spieltage der 1. und 2. "
        "Segel-Bundesliga, die ACTs der Deutschen Junioren Segel-Liga und der gemeinsame Pokal.",
        "body_html": (
            "<p>Die Termine für die Saison 2027 stehen fest. Hier der Überblick über alle Spi"
            "eltage der 1. und 2. Segel-Bundesliga, die ACTs der Deutschen Junioren Segel-Lig"
            "a sowie den gemeinsamen Pokal.</p><h2>1. und 2. Segel-Bundesliga (DSBL)</h2><p><"
            "em>Regatten jeweils Freitag bis Sonntag</em></p><table><thead><tr><th>Spieltag</"
            "th><th>Termin</th><th>Ort / Revier</th><th>Ausrichter</th><th>Liga</th></tr></th"
            "ead><tbody><tr><td>1</td><td>16.–18.04.2027</td><td>Friedrichshafen / Bodensee</"
            "td><td>Württembergischer Yacht-Club / Konstanzer Yacht-Club</td><td>1. + 2. Liga"
            "</td></tr><tr><td>2</td><td>30.04.–02.05.2027</td><td>Überlingen / Bodensee</td>"
            "<td>Bodensee Yacht-Club Überlingen / Segel- und Motorbootclub Überlingen</td><td"
            ">1. + 2. Liga</td></tr><tr><td>3</td><td>02.–04.07.2027</td><td>Berlin / Wannsee"
            ", Havel</td><td>Berliner Yacht-Club</td><td>1. + 2. Liga</td></tr><tr><td>4</td>"
            "<td>30.07.–01.08.2027</td><td>Strande / Kieler Außenförde</td><td>Kieler Yacht-C"
            "lub</td><td>1. Liga</td></tr><tr><td>5</td><td>17.–19.09.2027</td><td>Warnemünde"
            " / Ostsee</td><td>Akademischer Segelverein Warnemünde</td><td>1. + 2. Liga</td><"
            "/tr><tr><td>6 (Finale)</td><td>14.–16.10.2027</td><td>Hamburg / Außenalster</td>"
            "<td>Norddeutscher Regatta Verein</td><td>1. + 2. Liga</td></tr></tbody></table><"
            "h2>Deutsche Junioren Segel-Liga (DJSL)</h2><p><em>Freitag nur Training, Regatten"
            " Samstag und Sonntag</em></p><table><thead><tr><th>ACT</th><th>Termin</th><th>Or"
            "t / Revier</th><th>Ausrichter</th></tr></thead><tbody><tr><td>ACT 1</td><td>07.–"
            "09.05.2027</td><td>Konstanz / Bodensee</td><td>Konstanzer Yacht-Club / Schüler S"
            "egel-Club Konstanz</td></tr><tr><td>ACT 2</td><td>09.–11.07.2027</td><td>Berlin "
            "/ Wannsee</td><td>Potsdamer Yacht-Club</td></tr><tr><td>ACT 3</td><td>13.–15.08."
            "2027</td><td>Borgwedel / Schlei</td><td>Schulsportverein Louisenlund</td></tr><t"
            "r><td>ACT 4</td><td>10.–12.09.2027</td><td>Warnemünde / Ostsee</td><td>Akademisc"
            "her Segelverein Warnemünde</td></tr></tbody></table><h2>Gemeinsamer Pokal: DSL-P"
            "okal und DJSL-Pokal</h2><p><strong>Termin:</strong> 22.–24.10.2027<br><strong>Or"
            "t / Revier:</strong> Hamburg / Außenalster<br><strong>Ausrichter:</strong> Nordd"
            "eutscher Regatta Verein</p><p><em>Derzeitige Planung: Freitag nur Training, Rega"
            "tten Samstag und Sonntag. Aus Kapazitätsgründen ist eine Anpassung auf Regatten "
            "von Freitag bis Samstag möglich.</em></p><p><strong>Vorbehaltlich etwaiger Änder"
            "ungen bis zur Veröffentlichung der endgültigen Ausschreibung.</strong></p>"
        ),
        "author": "Redaktion",
        "photo_url": None,
        "photo_credit": None,
        "example": False,
    },
    {
        "kind": "news",
        "slug": "neuer-vorstand-gewaehlt",
        "title": "Neuer Vorstand gewählt – es geht los!",
        "published_on": "2026-01-27",
        "league": None,
        "teaser": "Was für ein Tag in Düsseldorf! Mitten im Trubel der boot haben wir uns mit 34 "
        "von 36 Vereinen getroffen.",
        "body": "Was für ein Tag in Düsseldorf! Mitten im Trubel der boot haben wir uns mit 34 von "
        "36 Vereinen getroffen – und gemeinsam die Weichen für die Zukunft der "
        "Segel-Bundesliga gestellt.",
        "author": "Gundram Leifert",
        "photo_url": None,
        "photo_credit": None,
        "example": False,
    },
    {
        "kind": "news",
        "title": "Wannsee: NRV und ASVW gewinnen den fünften Spieltag",
        "published_on": "2026-09-20",
        "league": None,
        "teaser": "Beim Potsdamer Yacht Club sind in beiden Ligen alle 16 Flights gesegelt worden. "
        "Den Spieltag gewinnen der Norddeutsche Regatta Verein in der 1. und der Akademische "
        "Segelverein Warnemünde in der 2. Liga.",
        "body": "Das Wochenende auf dem Wannsee hat den Crews keine Pause gegönnt: An den ersten "
        "beiden Tagen wehte nur wenig Wind, der dazu ständig die Richtung wechselte, am Sonntag "
        "kamen kräftige "
        "Böen. Trotzdem ist das komplette Programm geschafft worden – 16 Flights in jeder der "
        "beiden Ligen.\n"
        "\n"
        "In der 1. Liga war es lange ein Zweikampf. Der Berliner Yacht-Club, auf seinem "
        "Heimrevier, hielt sich bis weit ins Wochenende hinein ganz vorn, doch der Norddeutsche "
        "Regatta Verein kam heran und behielt am Ende die Oberhand. Für die Berliner bleibt Rang "
        "zwei, Dritter wird der Joersfelder Segel-Club, der das ganze Wochenende über "
        "gleichmäßig punktete.\n"
        "\n"
        "Die 2. Liga hatte früh einen klaren Favoriten: Der Akademische Segelverein Warnemünde "
        "ging bald in Führung und gab sie bis zum letzten Rennen nicht mehr her. Spannend wurde "
        "es um die Plätze dahinter. Der Flensburger Segel-Club und der Segel-Club Ville kamen mit "
        "dem auffrischenden Wind am Sonntag am besten zurecht und segelten sich in der "
        "Schlussphase noch auf die Ränge zwei und drei.\n"
        "\n"
        "1. Liga: 1. Norddeutscher Regatta Verein, 2. Berliner Yacht-Club, 3. Joersfelder "
        "Segel-Club.\n"
        "\n"
        "2. Liga: 1. Akademischer Segelverein Warnemünde, 2. Flensburger Segel-Club, 3. "
        "Segel-Club Ville.\n"
        "\n"
        "Glückwunsch an alle Crews zu diesem Wochenende!",
        "author": "Redaktion",
        "photo_url": None,
        "photo_credit": None,
        "example": False,
    },
    {
        "kind": "news",
        "title": "Hamburg: Der NRV gewinnt zu Hause und führt die Tabelle an",
        "published_on": "2026-08-03",
        "league": "1-liga",
        "teaser": "Auf der Außenalster holt der Norddeutsche Regatta Verein den Sieg am 4. "
        "Spieltag – vor eigenem Publikum. Damit steht er nun allein an der Spitze der "
        "Gesamtwertung.",
        "body": "Der Gastgeber hat seinen eigenen Spieltag gewonnen: Beim vierten Wochenende "
        "der 1. Liga lag am Ende der Norddeutsche Regatta Verein vorn. Zweiter wurde der "
        "Bayerische Yacht-Club, knapp dahinter belegte der Mühlenberger Segel-Club Rang drei.\n"
        "\n"
        "Der Wind auf der Außenalster blieb das ganze Wochenende unberechenbar. Wer vorn landen "
        "wollte, musste vor allem ohne große Ausrutscher durch die Rennen kommen.\n"
        "\n"
        "In der Gesamtwertung hat sich der NRV mit diesem Ergebnis deutlich an die Spitze "
        "gesetzt. Auf den Plätzen folgen der Joersfelder Segel-Club und der Mühlenberger "
        "Segel-Club – entschieden ist der Kampf um den Titel also noch nicht.\n"
        "\n"
        "Wir gratulieren allen Crews und danken den Helferinnen und Helfern, den Offiziellen und "
        "dem Norddeutschen Regatta Verein als Ausrichter für ein gelungenes Wochenende in "
        "Hamburg.",
        "author": "Redaktion",
        "photo_url": None,
        "photo_credit": None,
        "example": False,
    },
    {
        "kind": "news",
        "title": "Vorschau: Gleichstand an der Spitze vor dem Spieltag in Hamburg",
        "published_on": "2026-07-30",
        "league": "1-liga",
        "teaser": "Vom 30. Juli bis 2. August segelt die 1. Liga auf der Außenalster, "
        "Gastgeber ist der Norddeutsche Regatta Verein. Ausgerechnet er führt die Tabelle an "
        "– punktgleich mit dem Joersfelder Segel-Club.",
        "body": "Der vierte Spieltag der Saison 2026 führt die 1. Liga nach Hamburg. Der "
        "Norddeutsche Regatta Verein lädt vom 30. Juli bis 2. August auf die Außenalster ein.\n"
        "\n"
        "Spannender könnte die Ausgangslage kaum sein: Der Gastgeber und der Joersfelder "
        "Segel-Club haben vor dem Wochenende exakt gleich viele Punkte. Was an diesen Tagen "
        "passiert, kann die Tabelle kräftig durcheinanderwirbeln.\n"
        "\n"
        "Die Prognose verspricht allerdings wenig Wind. Bei solchen Bedingungen kommt es auf "
        "jeden Meter an, auf die richtige Taktik und eine kluge Strategie – und am Saisonende "
        "kann jeder einzelne Punkt entscheiden.\n"
        "\n"
        "Wir wünschen allen Crews viel Erfolg und hoffen auf möglichst viele Rennen.",
        "author": "Redaktion",
        "photo_url": None,
        "photo_credit": None,
        "example": False,
    },
    {
        "kind": "news",
        "title": "Kiel: Mühlenberger SC und SC Ville gewinnen den dritten Spieltag",
        "published_on": "2026-07-12",
        "league": None,
        "teaser": "Sonne, Wärme und Bilderbuchwind zum Abschluss auf der Kieler Förde: Nach 16 "
        "Läufen gewinnt der Mühlenberger Segel-Club die 1. Liga, der Segel-Club Ville die 2. "
        "Liga.",
        "body": "Am Hotel Kieler Yacht Club blieb es bis zum letzten Rennen offen. Der Schlusstag "
        "brachte Sonnenschein, warme Temperaturen und angenehmen Wind – ein schöner Ausklang für "
        "einen gelungenen dritten Spieltag.\n"
        "\n"
        "In der 1. Liga führte der Mühlenberger Segel-Club vom ersten Tag an und gab die Spitze "
        "nicht mehr ab: 33 Punkte nach 16 Läufen. Der Norddeutsche Regatta Verein folgt mit 38 "
        "Punkten, der Münchner Yacht-Club mit 45.\n"
        "\n"
        "In der 2. Liga legte der Segel-Club Ville am Schlusstag noch einmal zu und gewann den "
        "Spieltag mit 35 Punkten. Zweiter wurde der Flensburger Segel-Club (38), Dritter der "
        "Konstanzer Yacht-Club (42).\n"
        "\n"
        "Zur Halbzeit der 1. Liga – drei von sechs Spieltagen sind gesegelt – teilen sich der "
        "Norddeutsche Regatta Verein und der Joersfelder Segel-Club mit je 9 Punkten die "
        "Tabellenspitze, dahinter liegt der Münchner Yacht-Club (17). In der 2. Liga stehen nach "
        "drei von fünf Spieltagen der Verein Seglerhaus am Wannsee (13), der Konstanzer "
        "Yacht-Club (14) und der Lübecker Yacht-Club (16) vorn.",
        "author": "Redaktion",
        "photo_url": None,
        "photo_credit": None,
        "example": False,
    },
    {
        "kind": "news",
        "slug": "asvw-takes-the-lead",
        "title": "ASVW takes the lead after a perfect Sunday",
        "published_on": "2026-09-21",
        "league": "1-liga",
        "teaser": "Six wins in eight races — and the table has a new name at the top.",
        "body": "Saturday had been a day of waiting: the wind came late, turned twice and left the "
        "race committee with four flights. Sunday made up for it. A steady 12 knots from the "
        "west, flat water, and a crew from Hamburg that did not put a foot wrong.\n"
        "\n"
        "Six wins in eight races carried them past the leaders of the morning, who lost two "
        "places in the last flight after a penalty at the leeward gate. The gap at the top "
        "is now two points with one matchday to go.\n"
        "\n"
        "Behind them the table is as tight as it has been all season. Four clubs are "
        "separated by three points between places five and eight, and the fight against "
        "relegation will be decided on the final weekend.",
        "author": "League office",
        "photo_url": None,
        "photo_credit": None,
        "example": True,
        "quote": "We kept it simple: good starts, the right side, no fouls. Everything else "
        "followed.",
        "quote_by": "the winning helm",
    },
    {
        "kind": "news",
        "slug": "promotion-race",
        "title": "Promotion race: three clubs within two points",
        "published_on": "2026-09-14",
        "league": "2-liga",
        "teaser": "Before the final act, nothing is decided.",
        "body": "Four places go up to the 1. Liga, and five clubs still have a realistic chance of "
        "one of them. The leaders are safe; behind them, three clubs are within two points "
        "of each other.\n"
        "\n"
        "The last matchday is sailed at the same venue as the 1. Liga's final, which means a "
        "full harbour, a broadcast and the knowledge that every race counts double in the "
        "minds of the crews.\n"
        "\n"
        "At the other end of the table, places 13 to 18 will have to requalify at the "
        "DSL-Pokal in autumn.",
        "author": "League office",
        "photo_url": None,
        "photo_credit": None,
        "example": True,
    },
    {
        "kind": "news",
        "slug": "junioren-liga-champion",
        "title": "Junioren-Liga crowns its champion on the Alster",
        "published_on": "2026-08-30",
        "league": "junioren-liga",
        "teaser": "The youngest crew in the field wins the last flight and the title.",
        "body": "The average age of the crew was seventeen. Their lead before the last flight was "
        "one point. They won the race, and with it the title.\n"
        "\n"
        "Three days on the Alster brought every condition the city lake has to offer: gusts "
        "off the buildings, holes behind the trees and a final day with a breeze that made "
        "the J/70s plane downwind.\n"
        "\n"
        "The best teams of the season qualify for the DSL-Pokal, where they meet crews of "
        "the 1. and 2. Liga.",
        "author": "League office",
        "photo_url": None,
        "photo_credit": None,
        "example": True,
        "quote": "We trained for exactly this: one race, everything on it.",
        "quote_by": "the champions' helm",
    },
    {
        "kind": "news",
        "slug": "dsl-pokal-registration",
        "title": "DSL-Pokal: registration opens",
        "published_on": "2026-08-12",
        "league": "dsl-pokal",
        "teaser": "Every member club can enter one crew. Deadline 31 January.",
        "body": "The DSL-Pokal is the one weekend of the year on which clubs of every level race "
        "each other — and the way into the 2. Liga for clubs not yet in a Bundesliga.\n"
        "\n"
        "Each member club can enter one crew. Entries are made by the club's team manager on "
        "this site, under the club's page in My space. Squads can be completed until the "
        "deadline.\n"
        "\n"
        "The notice of race and the entry fee will be published on the notice board.",
        "author": "League office",
        "photo_url": None,
        "photo_credit": None,
        "example": True,
    },
    {
        "kind": "news",
        "slug": "live-tracking",
        "title": "Live tracking: every boat on the map, from every phone",
        "published_on": "2026-07-28",
        "league": None,
        "teaser": "From this season the tracker is the sailor's own phone.",
        "body": "No more boxes to charge and hand out on the pontoon: from this season a phone on "
        "board is the tracker. The race committee's phone marks the start and finish lines.\n"
        "\n"
        "Spectators see every boat on the map, the ranking of the race and the wind, while "
        "it happens. After the race the replay stays on the matchday's page.\n"
        "\n"
        "The tracking is the association's own and comes with every event organised on this "
        "site, the clubs' own regattas included.",
        "author": "League office",
        "photo_url": None,
        "photo_credit": None,
        "example": True,
    },
    {
        "kind": "news",
        "slug": "season-2027-calendar",
        "title": "Season 2027: six weekends, six venues",
        "published_on": "2026-10-02",
        "league": "1-liga",
        "teaser": "The calendar for next season is set — two venues are new.",
        "body": "The league office and the host clubs have agreed the calendar for 2027. The "
        "season opens in May and ends in late September with the final.\n"
        "\n"
        "Two venues are new to the league, and both bring a sailing area close to the shore "
        "— good for spectators and for the broadcast.\n"
        "\n"
        "Every matchday is shared with the 2. Liga, which sails the same weekends at the "
        "same venues.",
        "author": "League office",
        "photo_url": None,
        "photo_credit": None,
        "example": True,
    },
    {
        "kind": "news",
        "slug": "relegation-battle",
        "title": "Relegation: one weekend, four clubs, two places",
        "published_on": "2026-09-07",
        "league": "1-liga",
        "teaser": "The last four go down — and nobody below seventh is safe.",
        "body": "The rules are simple and hard: the last four of the 1. Liga go down to the 2. "
        "Liga. With one matchday left, the clubs between places 12 and 16 are separated by four "
        "points.\n"
        "\n"
        "A matchday is scored by the sum of all races, so a single bad flight can cost three "
        "places. Consistency, not brilliance, is what keeps a club in the league.",
        "author": "League office",
        "photo_url": None,
        "photo_credit": None,
        "example": True,
    },
    {
        "kind": "news",
        "slug": "media-kit",
        "title": "Broadcast and media: every matchday live",
        "published_on": "2026-05-15",
        "league": None,
        "teaser": "A studio on the pontoon, cameras on the water, the live map on screen.",
        "body": "Every matchday of the 1. Liga is broadcast live: a studio on the pontoon, cameras "
        "on RIBs, commentary and the live map with the boats' positions.\n"
        "\n"
        "Journalists find photos, the press kit and the accreditation form in each league's "
        "press centre.",
        "author": "Press office",
        "photo_url": None,
        "photo_credit": None,
        "example": True,
    },
    {
        "kind": "news",
        "slug": "junioren-new-clubs",
        "title": "Junioren-Liga grows: five new clubs",
        "published_on": "2026-03-20",
        "league": "junioren-liga",
        "teaser": "More youth teams than ever have entered this season.",
        "body": "Five clubs sail the Junioren-Liga for the first time this season. The league is "
        "open to youth teams of every German sailing club, from AK16 to AK21.\n"
        "\n"
        "The boats are provided by the Heinz Nixdorf Verein, so a club needs a crew, a coach "
        "and the will to travel — nothing more.",
        "author": "League office",
        "photo_url": None,
        "photo_credit": None,
        "example": True,
    },
    {
        "kind": "news",
        "slug": "club-service",
        "title": "Run your own regatta here",
        "published_on": "2026-04-10",
        "league": None,
        "teaser": "Pairing lists, results, tracking and waivers — the association's service for "
        "every club.",
        "body": "Everything the league uses on a matchday is available to every club that "
        "organises its own event: the pairing list, the race committee's result entry, "
        "live tracking from phones, the liability waivers and the expense claims afterwards.\n"
        "\n"
        "An event need not belong to a league. A club's leadership creates it, names its "
        "boats and invites its helpers — and the event has its own page on this site.",
        "author": "Deutsche Segel-Liga e.V.",
        "photo_url": None,
        "photo_credit": None,
        "example": True,
    },
    {
        "kind": "press",
        "title": "Act 5: ASVW takes over the lead",
        "published_on": "2026-09-21",
        "league": "1-liga",
        "body": "Placeholder text of the release: the facts in the first paragraph, a quote, the "
        "next dates, and the press contact.",
        "example": True,
    },
    {
        "kind": "press",
        "title": "Season 2027: calendar and venues confirmed",
        "published_on": "2026-09-02",
        "league": "1-liga",
        "body": "Placeholder text of the release: the facts in the first paragraph, a quote, the "
        "next dates, and the press contact.",
        "example": True,
    },
    {
        "kind": "press",
        "title": "Media kit 2026: logos, fact sheet, contacts",
        "published_on": "2026-04-01",
        "league": "1-liga",
        "body": "Placeholder text of the release: the facts in the first paragraph, a quote, the "
        "next dates, and the press contact.",
        "example": True,
    },
]


def _paragraphs(text: str) -> str:
    """The rows' plain paragraphs, separated by an empty line, as the editor's HTML."""
    return "".join(f"<p>{html.escape(part)}</p>" for part in text.split("\n\n"))


async def seed_posts(session: AsyncSession) -> None:
    """Adds the posts: the real ones published, the examples as drafts."""
    leagues = dict((await session.execute(select(League.slug, League.id))).tuples().all())
    for row in [*POSTS, *PRESS_RELEASES]:
        fields = dict(row)
        league = fields.pop("league")
        # A release taken over as written is the editor's HTML — cleaned like any write,
        # so nothing reaches the table around the cleaner (Story R-1).
        html_body = fields.pop("body_html", None)
        session.add(
            Post(
                **fields
                | {
                    "slug": fields.get("slug") or slugify(fields["title"]),
                    "published_on": date.fromisoformat(fields["published_on"]),
                    "body": clean_html(html_body)
                    if html_body is not None
                    else _paragraphs(fields["body"]),
                    "league_id": leagues.get(league),
                    "published": not fields.get("example", False),
                },
            )
        )
