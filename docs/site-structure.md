# Site structure — pages, URLs, what expands

**Decided 2026-10-11:** option E of issue #14, *"chapters on top, depth behind"*, in the
look of wireframe 8 (*"Chapters"*, issue #13). This file is the lasting record of that
concept; the issues hold the discussion and the alternatives. **Built into the real site
on 2026-10-12** (Stories B-13–B-16, `web/src/pages/league/`, `web/src/components/site/`):
the leagues are data (`League`, `GET /api/leagues`, `GET /api/leagues/{slug}`), news,
press, media and documents static content behind hooks (`web/src/content/`). The
clickable prototype under **`/prototype`** stays until the open variants are decided, then
goes; the wireframes of #13 were removed on 2026-10-12.

## What the site is

One application for the association's competitions and for the association itself. **Changed
2026-10-16:** the 1. and 2. Liga were one league, *DSBL* (`/dsbl`, two series a year); they
are two leagues now, each a top-level entry like on deutsche-segelbundesliga.de, and the old
`/dsbl/…` addresses go to the 1. Liga's same page.

| Competition | Path | Made of |
|---|---|---|
| **1. Liga** — 1. Segel-Bundesliga | `/1-liga` | one series a year: 18 clubs, 6 matchdays |
| **2. Liga** — 2. Segel-Bundesliga | `/2-liga` | one series a year: 18 clubs, 5 matchdays, sailed at the 1. Liga's venues and weekends |
| **Junioren** — Deutsche Junioren Segel-Liga | `/junioren-liga` | one series a year, AK16–AK21 |
| **DSL-Pokal** | `/dsl-pokal` | one event a year, autumn |
| the association, Deutsche Segel-Liga e.V. | `/` | its own pages |

The association's members are the 36 clubs of the 1. and 2. Liga. The last four of the
1. Liga go down and the first four of the 2. Liga go up. Places 13–18 of the 2. Liga have
to requalify at the DSL-Pokal.

## The one navigation row

Every page has the same row at the top, and only one: the **logo** and **Verein**
(*Association*, both the association's home) · **1. Liga · 2. Liga · Junioren · DSL-Pokal**
· the **account** at the right (*Sign in*, or *My space*). Topics such as
results, media and press are not in the row. Each one is a chapter of the league's page
and has a full page behind that chapter. An earlier row of topics under the league bar
made two navigation rows and was dropped (#13).

On a chapter page the row lies over the picture. On a depth page it is solid and sticky,
with the same entries and the current league marked (changed 2026-10-16: it used to turn
the league into a switch with its pages beside it). The league's own pages — *Standings ·
Season · Notice board · Clubs · News · Media · Press · About* — are a row of links under
the depth page's picture (layout A), the sheet's pills (B) or the left column (C).

**At most two rows of navigation, ever.** The second exists only on a matchday page: it
names the matchday (*"Act 5 · Berlin, 18–20 Sep"*) and lists what it has (*notice board,
results, pairing list, crews, live, media*). It sticks under the first, so which matchday
you are on and what else it has stay in view while you scroll. A separate row of the
league's pages under the bar made three rows on a matchday page and was dropped
(2026-10-11), and so was the breadcrumb: the top row already says where you are.

## The league's page: chapters

`/1-liga` is one page of chapters over one picture that stands still (changed 2026-10-18;
they were full-screen chapters, each over its own picture), with a column of
dots on the right to jump between them. A thumb can slide along the dots, which shows
every chapter's name, and the page follows. Each chapter is a **preview** that ends in a
link to its **own page**. That link is what option E adds to option A.

```mermaid
flowchart TD
  top["Top bar: logo · Verein · 1. Liga · 2. Liga · Junioren · DSL-Pokal · account"]
  top --> lg["/1-liga — the chapter page"]
  lg --> ch1["Standings"] & ch2["Results (while live)"] & ch3["News"] & ch4["Media"] & ch5["About"] & ch6["Archive"]
  ch1 -->|"full standings"| p2["/1-liga/standings"]
  ch2 -->|"results of the act"| p1["/1-liga/2026/act-6/results"]
  ch3 -->|"all news"| p5["/1-liga/news"]
  ch4 -->|"photos & videos"| p6["/1-liga/media"]
  ch5 -->|"how it works · clubs · press"| p8["/1-liga/about"]
  ch5 --> p4["/1-liga/clubs"] & p7["/1-liga/press"]
  ch6 -->|"a year"| p9["/1-liga/2025/standings"]
  p2 --> p3["/1-liga/season"]
  p3 --> nb["/1-liga/notice-board — season documents"]
  p1 --> tabs["tabs: Notice board · Results · Pairing list · Crews · Live · Media"]
```

| Chapter | Preview | Its page |
|---|---|---|
| **Standings** | the top five; the page's title | `/:league/standings` |
| **Results** | only while a matchday is live: the act, venue, host; links to live map and notice board | the act's results |
| **News** | three headlines | `/:league/news` |
| **Media** | what there is to watch | `/:league/media` |
| **About** | what the league is, its clubs, links to all clubs and the press centre | `/:league/about` |
| **Archive** | the earlier years; left out when there is none | `/:league/:year/standings` |

**A chapter's title is its name** (*Standings*, not *"Where everyone stands."*) — changed
2026-10-16; on the association's home only the first chapter carries the page's name.

The association's home `/` is a chapter page as well: *Now* (every league's current
matchday), *Leagues*, *News*, *For clubs* (the association's service: run your own event
here), *About* (history, board, member clubs → `/about`).

## The depth pages

| URL | Content | Expands in place |
|---|---|---|
| `/:league/standings` | the full table of each division, one under the other, a column per act; promotion, relegation and requalification marked; archive by year | — |
| `/:league/season` | every matchday: dates, venue, host, divisions, state; calendar file | a matchday → its details and links into its tabs |
| `/:league/notice-board` | the **season's** documents: rules, notice of race, boats, entry | each group of documents |
| `/:league/clubs` | the clubs of each division | — |
| `/:league/news`, `/:league/news/:slug` | articles | — |
| `/:league/media` | videos and photo galleries | — |
| `/:league/press` | press releases, press kit, print photos, accreditation, contact | a release → its text and download |
| `/:league/about` | what the league is, what is at stake, the boat | — |
| `/about` | the association: history, board, member clubs | — |

## The matchday page

`/:league/:year/:act`, for example `/1-liga/2026/act-6`. The tab is the last path
segment (`…/act-6/results`), so every tab has its own URL. Without a tab the page opens
on *Results* once racing is done, and on *Notice board* before that.

| Tab | Content | Expands |
|---|---|---|
| **Notice board** | the matchday's announcements, newest first, marked by who issued them (race committee, jury, organizer); its documents (NoR, SIs, amendments) | an announcement → its text |
| **Results** | the ranking of the act; race by race | a flight → its three races, each in finishing order with the boats' colours |
| **Pairing list** | who sails which boat in which race | — |
| **Crews** | who sails for each club | a club → its crew |
| **Live** | the live map while racing, a replay afterwards | — |
| **Media** | the matchday's video and photos | — |

The matchday is also where its own notice board, media and press release belong: option
C's idea, kept inside E.

## URLs and redirects

- **The league's path is stable across years.** `/1-liga` is the current season, by the
  existing rule for "the current year" (the newest one not in the future). A past year is
  `/1-liga/2025/…`.
- **Short paths are redirects, never copies:** `/:league/live` goes to the running act,
  else the next one (`…/live`); `/:league/results` goes to the last act sailed
  (`…/results`); `/:league/notice-board` holds the season's documents and links on to the
  current act's own notice board.
- **Other domains only choose the league.** A domain for the DSBL, the Junioren-Liga or
  the Pokal redirects permanently (301) to its path, and the association's domain serves
  `/`. This is how vodafone.de folds in old brands: kabeldeutschland.de lands on the
  matching topic, not on the home page. Old paths are redirected to the matching new page
  as well.
- **Today's URLs** (`/series/:id`, `/events/:id`) redirect permanently to the new ones.
- Route words are English (`results`, `notice-board`). The league's slug is data.

## Design

Clean: white and slate, one accent (the brand blue), generous space, type doing the work.
Pictures carry the chapter pages. A depth page opens on a big picture with its kicker
(*"DSBL · 15–17 Oct 2026 · Wannsee"*) and title (*"Final · Berlin"*) on it — decided
2026-10-11; the title below the picture made the picture a thin strip. The content follows
on white. How the frame looks otherwise is still open (variant "Detail page" below). A
slideshow shows no slide marks: on a chapter they read as a second set of dots beside the
chapter dots.

## Variants still open

A development switch (the **DEV** button, bottom left, wherever the dev tools are built in — the dev server and staging) toggles these.
Each is to be decided on the real device, not argued in the abstract:

| Variant | Options |
|---|---|
| Pictures | **photo** · **fade** (cross-fade, slow zoom) · **slide** (pushed in from the right) · **video** (a muted loop; only the chapter on screen plays) |
| Glass | card darkness, card blur, picture shade, text strength — sliders, with a reset |

**Decided 2026-10-18:** the layout with a sub-menu (like my space: the rows on the
picture, a sticky sub-menu of pills with crumbs, one fixed picture, the content in glass
cards), chapters scrolling freely at their own height. The classic layout, chapters
snapping into place and the depth frames A band, B sheet, C split were removed.

## Content sources

- **deutsche-segelliga.de** is the user's own site. Its texts (competitions, about, board,
  member clubs, news) and pictures may be taken over and copied here.
- **deutsche-segelbundesliga.de** belongs to the league's GmbH. Its photos are **linked,
  never copied**, because this repository is public. Its YouTube videos are embedded.

## Open before the real build

From #14, still unanswered:

1. ~~**"DSBL" spans two series a year.**~~ Decided 2026-10-12: a `League` row, and
   `Series.league_id`. An act is the year's events that share a matchday number. Revised
   2026-10-16: the 1. and 2. Liga are two leagues, one series a year each.
2. Which domains exist or are planned.
3. Who writes news and press releases, and whether they need a review before publishing.
4. Videos on YouTube (embedded) or hosted here; galleries uploaded here or linked.
5. Whether the notice of race declares this site the official notice board. If it does,
   entries get timestamps, are never edited silently, and an amendment is a new entry.
6. How far back the archive goes.

Each piece becomes a story in `docs/userstories/` before it is built.
