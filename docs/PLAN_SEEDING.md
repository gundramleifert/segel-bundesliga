# Plan: what a fresh installation starts with

A new installation of the site — the server, staging, a laptop — should open on the
association's **real history**: the results of the last five seasons and the news,
press releases and pictures of the current one, not a demo. Today it opens on a mixture: real clubs and series, but
made-up sailors and crews, a matchday whose results are drawn by `random`, and thirteen
example posts. This plan separates the two and fills the real half.

Inventory taken 2026-10-27 (the numbers below); the decisions in § Rules were given by the
project lead the same day.

## Rules

1. **Nothing made up on the public site.** No example posts in news or press, no
   invented sailors in a squad, crew or lineup, no generated results. What a visitor reads
   happened.
2. **Results of the last five seasons, 2022–2026,** wherever a source has them. **News,
   press releases and pictures of 2026 only** — the current season; older news is not
   brought over.
3. **Per source, what may be done with its text:**

   | Source | Who it is | Text | Pictures |
   |---|---|---|---|
   | `deutsche-segelliga.de` | the association, Deutsche Segel-Liga e.V. — this site's owner | **copy** as written | copy |
   | `deutsche-segelbundesliga.de` | the league's former site (DSBL GmbH) | **rewrite** — facts taken, text our own, never copied | not taken — pictures come from the photo desk |
   | Sven Jürgensen's SmugMug galleries (`konzeptwerft.smugmug.com`) | the league's photographer and press contact | — | **taken; every picture credits him as the photographer** — no permission to ask |
   | SAP Sailing Analytics | the results service | — (data) | — |

   `segel-bundesliga.de` is not a source: it only redirects to dsv.org.
4. **The repository is public.** Texts (copied or rewritten) may live in it as data files,
   as `app/seed_press.py` already does; **pictures never do.** A picture goes from its
   source **straight into the storage backend** — S3 or the local uploads directory,
   whichever the installation runs (`app/storage.py`) — through `app.services.media.store`,
   like any upload. No download cache beside it: the library *is* the cache. A run finds
   a picture it stored before by its `ExternalId` and does not download it again.
5. **Every item says where it came from**, so a later run can find it again and a reader
   can see the original: a copied post links its original, a rewritten one names its
   source, a picture names its photographer.

## Two layers: the site, and the demo on top

| | `app.seed_site` — every installation | `app.seed_demo` — development, tests, staging only |
|---|---|---|
| Leagues, clubs, series, acts (2022–2027) | yes | — |
| Results 2022–2026 | yes, imported (§ Results) | — |
| News and press releases 2026 | yes (§ News) | — |
| Pictures 2026 | yes (§ Pictures) | — |
| Test accounts (`@example.com`) and their tuples | — | yes (`app.seed_users`) |
| Made-up people (the ASVW cast, its squad) | — | yes — **only on drafts**, see below |
| Example posts | — | **none** (rule 1) |
| Generated matchday (`_seed_matchday`) | — | **removed** — the imported seasons replace it |

**What the demo layer still needs, and where it goes.** The test accounts and the specs
need people to work with: a club admin, a team manager, sailors who sign a waiver, a crew
to name. They stay — on the **ASVW** club and on **unpublished** competitions only (the
2027 drafts, a draft act made for the purpose), so nothing invented reaches a public page,
not even on staging. The squads, crews and waivers of real 2022–2026 acts stay empty:
no source publishes who sailed (SAP lists clubs, not people).

**Repeatable without clobbering.** `seed()` today deletes its rows and creates them again
— right for a test database, wrong for a server where editorial has since corrected a
post or a club its crest. `seed_site` only **adds what is missing**, matched by
`ExternalId` — results as the imports already do, and posts and pictures the same way
(`source` the site or `smugmug`, `external_key` the WordPress id or the SmugMug image
key): one mechanism for everything that came from outside (CLAUDE.md, "External systems
are matched via `ExternalId`"). Run it on every start; it changes nothing the second time.

`seed_test_setup` keeps running both layers, so development, the test suite, staging
and the journeys behave as they do now. The Compose stack runs `seed_site` only
(`SBL_SEED=site`, the default there; `demo` for a demonstration server).

## Two instances: prod and staging

Decided 2026-10-27:

- **prod** holds real data only. It is seeded once, on an empty database, with the site
  layer, and from then on is backed up nightly (`docs/deploy-server.md`, "Backups": the
  database dump and `app.storage_copy export`).
- **staging** is **prod's latest backup, restored** — database and uploads — with the demo
  layer **added on top** when wanted, published or not. So staging always looks like prod
  plus what there is to try, and a restore drill happens every time staging is refreshed.

What that asks of the seed: the demo layer has to be a step of its own that **only adds**
— the demo series, their made-up squads and weekends, the test accounts — and finds its
own rows again on a second run, because it lands on a database it did not create. Today's
`seed()` wipes everything first; that is the part of S-0 still to build (below).

**Done (2026-10-27):** the real 2026 season is in the seed (TracTrac and SAP recordings);
everything invented moved into the unpublished demo series `demo-1-2026` / `demo-2-2026`;
`seed_test_setup --publish-demo` publishes them in a league of their own (`/demo`) — on by
on staging, off on prod (the Compose stack's
`SEED_PUBLISH_DEMO`), on in the test suite and the e2e stacks. The thirteen example
posts are drafts, published by `--publish-demo` with the demo (`app/seed_posts.py`). The
DSBL press pictures of the Finale are out of the seed (`app/seed_media.py` lists none):
they were not Sven's, so no credit to him would have been true. Nothing invented is on a notice board any
more: the season's documents are Manage2Sail's (`app/seed_data/m2s-2026/`, Story A-14).

**Still open in S-0:** the test accounts (`app.seed_users`) are still created on every
fresh database, prod included; and `seed()` cannot run
on top of a restored backup. Next: `seed_site` (real data, additive) and `seed_demo`
(demo series, squads, test accounts, additive) as two commands; prod runs the first,
staging restores prod and runs the second; `seed_test_setup` keeps running both for
development and the tests.

## Results

| Season | 1. Liga | 2. Liga | Junioren-Liga | Source |
|---|---|---|---|---|
| 2022 | 11 regattas (both divisions) | | 3 | SAP `www` / `hnv` |
| 2023 | 11 regattas (both divisions) | | 4 | SAP `www` / `hnv` |
| 2024 | **missing** | **missing** | 4 | — / `hnv` |
| 2025 | **missing** | **missing** | 5 | — / `hnv` |
| 2026 | **missing** (TracTrac only) | **missing** | 5 (recorded already) | TracTrac / `hnv` |

- **2022–2023, all three leagues, and the Junioren-Liga 2024–2026** need no new code:
  `app.imports sap --years 2022-2023 --publish` and the same with
  `--base-url https://hnv.sapsailing.com/sailingserver/api`. The seed does not call SAP
  live: like `app/seed_junioren.py`, it replays **recorded answers** from
  `app/seed_data/sap-<host>-<year>/` (one `regattas.json`, one leaderboard per act), so
  every installation, the tests and a laptop offline get the same seasons. A script
  records them once (`app.imports sap … --record <dir>`); refreshing is re-recording.
- **1./2. Liga 2024–2026 are on no SAP host we can find** (`www`, `my`, `hnv`, the old
  per-year hosts — checked 2026-10-27; the per-year names redirect to `www`).
  **`deutsche-segelbundesliga.de` holds none either** (searched 2026-10-27: every page,
  post, press release, matchday page and all 361 media files):
  - **2026:** each matchday page (`/dsbl-event/<n>-spieltag-2026/`) links notices,
    pairing lists, crew lists, a Google sheet that is the Thursday training plan, and a
    **TracTrac** event — whose data API answers 401. No table, no result file. The
    league's own results page (`/ergebnisse-2024/`, titled "Ergebnisse 2026") links a
    season table and each matchday's results for both divisions — all on TracTrac, and
    in a browser (2026-10-27) the scoreboard link of the Kiel act redirected to
    TracTrac's home page and the "Saison Tabelle" viewer stayed an empty canvas. The
    2026 results are TracTrac's, reachable only as an **export from the organizer**
    (DSBL GmbH, the TracTrac customer for these events).
  - **2025:** the matchday pages are gone (404); the press releases say "all results are
    on the matchday's event page", which no longer exists. They carry the standings in
    prose only. The 1st matchday's PDF is its pairing list.
  - **2024:** nothing but the Finale's news post (prose).
  - The **results archive** page links SAP for 2013–2023 (what we import), the DSL-Pokal
    2020 (`www`) and 2021 (`my`) on SAP, and a Google sheet with a Pokal's flight results.
  Until the league office names a source — SAP export files, TracTrac, a spreadsheet —
  these seasons have **no results**: the acts are there with their dates and clubs, the
  tables are empty. The generated 2026 matchday goes (rule 1). That leaves the 2026 news
  (§ News) reporting acts whose tables are empty — the strongest reason to settle open
  question 2 first.
- The **DSL-Pokal** is on SAP only for 2017 and 2018 — outside the five years, not
  imported. The importer skips cups by design (Story A-14).
- **Lineups stay empty** for every imported act: SAP holds teams, not crews.

## News and press releases — 2026

| Source | 2026 (inventory 2026-10-27) | Handling |
|---|---|---|
| `deutsche-segelliga.de` posts | 7: the new board (Jan), partners Elvstrøm and Pantaenius (Feb), Kieler Woche Inklusiv (four, June), the 2027 dates (Oct) | **copy** — the Kieler Woche Inklusiv series only if editorial says so (open question 1) |
| `deutsche-segelbundesliga.de` posts | 4: Kiel (July), the Hamburg preview, Hamburg, Wannsee (Aug–Sept) | **rewrite** — already done: the seed's four 2026 reports are these |
| `deutsche-segelbundesliga.de` press releases | none in 2026 (its 13 are all 2025) | — |
| `deutsche-segelbundesliga.de` `dsbl-event` | the six 2026 matchdays | not posts — dates and venues, which the acts already carry |
| Sven Jürgensen's press release of 2026-09-16 | 1 | already in the seed, taken over with his agreement |
| The Junioren-Liga | no news anywhere | **one 2026 season report**, written from the imported results — a rewrite of facts we hold ourselves |

So the 2026 news is mostly **there already**: the board election (copied), the four
league reports (rewritten), the press release. What is new: the remaining association
posts, the Junioren report — and removing the thirteen example posts (rule 1), which
leaves the press centre with one release until editorial writes more.

**Club news on the association's site.** `/news-aus-den-vereinen/` is a Feedzy RSS import
of the clubs' own news — other people's text, not taken. The Kieler Woche Inklusiv series
is a club project's report published there; it is copyable, but whether it is the
association's news is editorial's call (open question 1).

**How they come in.** `deutsche-segelliga.de` is WordPress with an open REST API
(`/wp-json/wp/v2/posts`, `/media`), so nothing is scraped:

1. **Copy** — a small importer, `app.imports wp`, reads the association's 2026 posts,
   keeps title, date, body, featured image and link, runs the body through
   `app/services/rich_text.py` (the same cleaner as every write), takes each picture into
   the library through `app.services.media.store` (a web picture is copied, never
   hot-linked — Story R-2) and rewrites its address in the text. Its output — the text,
   not the pictures (rule 4) — is recorded once into `app/seed_data/news/segelliga/`
   and the seed replays it.
2. **Rewrite** — the Junioren report, one data file in `app/seed_data/news/rewritten/`
   like the four league reports: our title, teaser and text, the date and league, and
   the facts' source. **Read and approved in its pull request before it is merged** —
   nothing rewritten is published unread.

**What the model needs:** `Post` has no field for where a post came from. It gets a
`source_url` — shown as "Originally published at …" under a copied post, kept for a
rewrite (the four league reports get theirs too). What makes the seed repeatable is an
`ExternalId` per post (`segelliga`/`post`/`4711`, `segelbundesliga`/`post`/`23675`,
`junioren-report`/`post`/`2026`), not a column. Kind (`news`/`press`) and league come
from the source: a league report is `news` of that league, an association post `news`
without one, Sven's release `press`.

## Pictures — Sven Jürgensen, photographer

**Only pictures Sven Jürgensen took, and every one says "Foto: Sven Jürgensen"** — the
credit is the acknowledgement, and nothing has to be asked for (decided 2026-10-27).
**Never a picture of DSBL GmbH** (galleries marked `c-DSBL`), whatever its press release
allows: the 35 Finale press pictures that were seeded came from such a gallery and were
taken out on 2026-10-27 — relabelling them would have credited him with someone else's
work. `app/seed_media.py` lists no picture until a gallery of his own is confirmed.

The plan: **the press galleries of the 2026 acts**, attached to their event, plus the
pictures the 2026 posts above need as covers. Earlier seasons' acts get results but no
pictures (rule 2).

- **Where — open:** `konzeptwerft.smugmug.com` holds the league's galleries, but the
  ones seen so far are marked `c-DSBL` (the Finale's
  `06-Finale-…/DSBL-CLUBS-c-DSBL/…`, the 3rd act's `PRESSE-c-DSBL/…`): DSBL GmbH's, not
  usable. Which galleries are Sven's own is for him to name; only those are taken.
- **Finding the galleries ourselves:** the account's pages load their folder list from
  SmugMug's API, which answers 401 without a key. A **SmugMug API key of our own** (free,
  read-only, public content only — no access to the account) lists every 2026 folder,
  gallery and image key; the list is then recorded into the repo. Without a key, the
  gallery links in the 2026 press release and posts are the fallback.
- **How many:** a selection, made by us — the gallery's `PRESSE` / `High-Res-ONLY-PRESS`
  part where there is one, otherwise about 10–20 per act: six acts in two divisions are
  some 150–250 pictures (~1–2 GB of originals, WebP sizes on top). The list lives in the
  repo, the files in the storage backend (rule 4) — so the bucket or the uploads
  directory needs that much room, and the backup (`docs/deploy-server.md`) carries it.
- **How they come in:** downloaded and handed to `media.store`, which keeps the
  original and its WebP sizes in the storage backend, with an `ExternalId`
  (`smugmug`/`media`/the image key) — so the next run skips it without a download; from
  a list file per act (`app/seed_data/pictures/2026-<act>.yaml`: image key, file name,
  the club when the picture is one club's). Later, the photo desk can deliver new ones
  itself through an upload link (Story R-2's import key) — the seed is only for what is
  already there.
- **The former site's media library** (366 files) is **not** taken: everything wanted is
  in the galleries, under his name.
- **The association site's pictures** come along with the posts copied from it (rule 3),
  with the credit the original gives.

## Order of work

| Phase | What | Needs | Gives |
|---|---|---|---|
| **S-0** | Split `seed_site` / `seed_demo`; remove the example posts and the generated matchday; demo people only on drafts; `SBL_SEED` in Compose; `seed_media` without `api/.seed-cache/` — the Finale pictures straight into the storage backend, found again by `ExternalId`, credited "Foto: Sven Jürgensen" | nothing | rules 1 and 4 and the two layers; staging loses no flow (journeys, specs); a container keeps no files |
| **S-1** | Record and replay SAP 2022–2023 (both divisions) and Junioren 2022–2026 | `--record` on the importer | real results: five junior seasons, two league seasons |
| **S-2** | `Post.source_url` and the posts' `ExternalId`s; `app.imports wp`; copy the association's 2026 posts; the Junioren 2026 report | open question 1; the report reviewed in its pull request | the 2026 news complete |
| **S-3** | Sven's 2026 galleries | a SmugMug API key of our own | pictures on every 2026 act |
| **S-4** | 1./2. Liga results 2024–2026 | open question 2 | the missing three league seasons — and tables for the acts the 2026 news reports |

S-0 is the precondition for the server (`docs/deploy-server.md`, "not ready for real
data"); S-1 and S-3 need no one outside the project; S-2 waits on one answer from
editorial; S-4 on the league office.

**Stories.** A new administration story, *A fresh installation opens on the real history*
(acceptance criteria = the Rules and the layers above), carries S-0 to S-4; R-1 gains the
source of a post (copied / rewritten), R-2 the photo desk's galleries, A-14 the recording.
Each phase's test: the site seed run twice changes nothing — and downloads nothing the
second time; no file written outside the storage backend; no post without a source; no
`@example.com` account and no made-up person after `seed_site`; the imported seasons'
tables match SAP's.

## Open questions — for editorial and the league office

1. **Editorial:** which 2026 posts of `deutsche-segelliga.de` are the association's to
   carry — the Kieler Woche Inklusiv series included or not?
2. **League office:** where are the 1./2. Liga results of 2024, 2025 and 2026 — an SAP
   host, TracTrac, files? Without them those seasons show acts but no tables, while the
   2026 news reports their results.
