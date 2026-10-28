# Deutsche Segel-Liga — Website

Official website of the **Deutsche Segel-Liga e.V.** plus the tools that support a matchday:
race result entry by the race committee, pairing lists, live view, and GPS tracking via
participant phones.

**The site is not one league.** The association runs several Series — 1. Liga, 2. Liga,
Junioren-Liga, DSL-Pokal — and the 1. Segel-Bundesliga is only *one* of them. Never brand the
site, its title, or its copy as "Segel-Bundesliga" / "Sailing Bundesliga", and never state one
series' configuration (18 teams, 6 boats, 48 races) as if it were a property of the site;
that name belongs only to an individual Series, e.g. as an example series name.

Beyond the association's own competitions, the site is a **service the association offers to
other clubs**, so that a club can organise its own events here. That is why an Event need not
belong to any Series, and why a club's leadership can create an event their own club hosts
(see Domain decisions and Permissions below).

## Where things are

| Path | Content |
|---|---|
| `api/` | FastAPI backend, SQLAlchemy 2.0 (async), Alembic |
| `web/` | React frontend (Vite 8 + TypeScript, HeroUI 3, Tailwind 4) |
| `e2e/` | Playwright tests against the running application |
| `docs/concepts.md` | **Terms and data model** — Series, Event, Squad, Scoring. Start here. |
| `docs/userstories/` | What the system should do, with tests included — one file per role, `README.md` is the index |
| `docs/journeys/` | **Journeys** — stories in the order they happen, across people: diagram, step table, walked by one test; `docs/traceability.md` § Journeys traces each step to story, tests, help and report |
| `docs/findings.md` | **Research findings** — API formats, League format, open questions |
| `docs/manage2sail.md` | **Manage2Sail** — the event token, the check-in report, the public entry/result endpoints, what cannot be written |
| `docs/gotchas/` | **Things that surprised someone** — read this before debugging anything odd |
| `docs/components.md` | **The frontend's building blocks** — read before writing a page |
| `docs/site-structure.md` | **The site structure** — leagues, chapter pages, depth pages, URLs and redirects (option E of #14), built in `web/src/pages/league/` |
| `scripts/` | `dev-stack.sh` (servers for e2e), `check.sh` (everything that must be green), `gen-api-client.sh` (the frontend's API client) |
| `docs/deploy-server.md` | **Running the site on a server** — the Compose stack's runbook: machine, first install with sops, HTTPS, updates, backups; what still makes it pre-production |
| `deploy/compose/` | **The whole site in Docker Compose** — Postgres, API, the SPA behind Caddy, SeaweedFS; started with `compose.sh`, secrets sops-encrypted in `secrets.sops.env` (recipients: `.sops.yaml`); `README.md` there |
| `docs/PLAN_SEEDING.md` | **What a fresh installation starts with** — the real 2022–2026 results, news, press and pictures, no examples; the site seed vs the demo layer, sources and their rights, phases S-0…S-6, open questions |
| `docs/PLAN_MEDIA.md` | **Pictures** — the media library and the automatic layout (galleries, shapes, crops), the plan Story R-2 is written from |
| `docs/PLAN_LIVE_IMPLEMENTATION.md` | **Live data, tracking, race control** — the agreed plan, make/buy vs SAP Sailing Analytics, phases |
| `api/app/imports/` | **Imports** from SAP Sailing (past DSBL matchdays, results) and Manage2Sail (entries, notice-board documents) — `uv run python -m app.imports --help`, Story A-14 |
| `api/app/tracking/` | **Boats on the water** — geometry, polar, course, passings, ranking, the emulator; `settings.py` holds every tuned constant (`SBL_TRACKING_*`) |
| `reference/` | Shallow clones of external repos for reference, not versioned |
| `~/.claude/plans/iterative-jingling-willow.md` | The original overall plan — its Phase 5 (live, tracking) is superseded by `docs/PLAN_LIVE_IMPLEMENTATION.md` |

Each reference repo has its own `CLAUDE.md` with details:
`reference/PairingList` (user's pairing generator), `reference/sailing-analytics`
(SAP Sailing Analytics API docs), `reference/segel-bundesliga` (previous attempt).

## Development

```bash
cd api
export UV_CACHE_DIR="$TMPDIR/uv-cache"   # ~/.cache is locked
uv sync
uv run python -m app.seed_test_setup     # Schema + reference data + accounts in one step
uv run uvicorn app.main:app --reload
uv run pytest -n auto                    # one worker per core; plain `pytest` for one test
```

Or **`tilt up`** at the repo root (`Tiltfile`): backend with `SBL_DEV_LOGIN=true` and
frontend in one dashboard, the API client regenerated when a route or schema changes, and
buttons for `reset-db` and `check`. It uses the real `api/sbl.db`; the e2e stacks stay
`scripts/dev-stack.sh`'s job.

`app.seed_test_setup` sets up a **fresh installation** completely: migrations,
reference data (`app.seed`), accounts (`app.seed_users`). Repeatable; `--reset` drops all
tables and migration state first. Individual steps still work.

**Migrations:** There is **one** initial migration. As long as nothing is in production, it is
regenerated when models change rather than creating a chain —
`rm alembic/versions/*.py`, then `alembic revision --autogenerate`, then
`seed_test_setup --reset`.

**Database:** **SQLite** for now — `api/sbl.db`, no server to start. The default is
`sqlite+aiosqlite:///./sbl.db` in `app.config`. Postgres stays the eventual production
target, so Postgres-specific types (JSONB, ARRAY) are still avoided in the model, and
Alembic runs in **batch mode** for SQLite (see `api/alembic/env.py`). The **test suite**
uses its own SQLite file so tests run without any external state; the test URL is set in
`api/tests/conftest.py` **at module level**, not in a fixture, because `app.config` builds
its settings on import.

**The frontend's API client is generated, never written.** `scripts/gen-api-client.sh`
reads the OpenAPI document straight off the FastAPI app object — no server to start, and
no way to describe a stale build — and `orval` turns it into `web/src/api/generated/`: one
function and one TanStack Query hook per endpoint, plus every request and response type.
Run it after any change to a route or a schema, then `pnpm typecheck` in `web/`: that
failing build is the whole point, and is what a hand-written client could not give.

- **Nothing under `generated/` is edited.** The next run overwrites it silently.
- **Names come from the route handler's own name** (`app/main.py::_operation_id`), so
  `async def list_series` becomes `listSeries` / `useListSeries`. Renaming a handler
  renames it in the frontend — which is a reason to name handlers well, and a reason the
  rename shows up as a compile error rather than a 404.
- **`web/src/api/http.ts`** is the one place a request leaves the browser: it attaches the
  bearer token, turns an RFC 9457 body into an `ApiError` carrying its problem code, and
  handles a 204. orval routes every generated call through it, and reads `ErrorType` from
  it so every hook's `error` is typed as `ApiError`.
- **`web/src/api/types.ts`** renames the generated types to the names the app uses
  (`EventOut` → `EventSummary`). It declares nothing: a hand-written copy of a response
  shape drifts, and the one that existed had been missing a field for months without a
  single compile error.
- **`useAsync(useListClubs())`** narrows a hook to the `{ data, error, loading }` the pages
  want, translating the error on the way. Reach past it for `isFetching` or `refetch`.
- **Invalidate with generated keys** — `invalidate(getListAllClubsQueryKey())` — or with a
  **path prefix**, `invalidate("/api/clubs")`, which covers the list, each club and each
  club's members in one. Never a key written out by hand: one that matches no query
  invalidates nothing, silently.
- **A closed set is an enum in the schema, never `str`** — `status: EventStatus`, not
  `status: str`. It becomes a named OpenAPI schema and a generated constant
  (`EventStatus.live`, re-exported from `types.ts`), so the frontend compares against a
  member the compiler knows, and an unknown value in a request is a 422 at validation
  rather than a check written again in the router.

**Authentication:** Identity comes from Google, Microsoft (OIDC token verification against
provider keys), a one-time code by email, or a **password** (Story Z-9, since 2026-10-05 —
not every sailor has or wants a Google/Microsoft account, and a code on every sign-in is
slow on a pontoon). Accounts are linked via verified email address, so every method leads
to the same account. Passwords are Argon2id in their own table (`PasswordCredential`, never
read by a serializer), only for a verified address, and the one-time code *is* the reset. Permissions are
relation tuples (`Grant`: user · relation · object, see Domain decisions), verified fresh on
every request so a deleted tuple takes effect immediately. Accounts are created by explicit enrollment or
import, not by signing up (`allow_self_signup`).

## Testing different roles

**Registration:** `POST /api/auth/register` creates an account and sends a confirmation code.
Until redeemed, the address is unverified (`User.email_verified`) — without proof the account
cannot request club membership. Such an account has neither role nor club. Controllable via
`SBL_ALLOW_REGISTRATION`; distinct from `allow_self_signup`, which only controls **silent**
account creation when logging in with an unknown address.

**Club membership is a `ClubMembership` row — person · club · status** (decided 2026-10-25,
#40, `docs/PLAN_PEOPLE.md`; Stories Z-5, V-15). The club's admin adds a person in no club at
once — the club knows who is in it (2026-09-24); a person **already in another club** joins
only with consent, invited by the club or asking themselves, the other side accepting. A
member leaves by ending their own membership. The club's half is
`/api/clubs/{id}/members`, the person's `/api/me/memberships` (*Me › My clubs*, *Ask to
join* on the club page); either side deletes a waiting row to decline or withdraw.

`SBL_DEV_LOGIN=true` enables `/api/dev`: there you can list test accounts and issue access tokens
**without verification**. A role switcher then appears in the UI (bottom right). Deliberately a
separate setting, not tied to `debug` — in a reachable environment this would be a security hole,
and the server warns on startup while it is on. **Never on in production or staging**
(decided 2026-10-28): the Compose stack fixes it off in `compose.yaml`; it is for `tilt up`
and `scripts/dev-stack.sh` only.

`app.seed_users` creates a **small cast on one club, one series, one event** — 44 accounts
(decided 2026-10-17; it was 370). **The 2026 season is real** (decided 2026-10-27,
`docs/PLAN_SEEDING.md`): the 1. and 2. Liga's 11 acts as sailed — clubs, pairing lists,
results, dates — imported from TracTrac's recorded scoreboards
(`app/seed_data/dsbl-2026/`, `app.imports tractrac`), and **the Junioren-Liga's** four acts
(decided 2026-10-23) from SAP's recorded answer (`app/seed_junioren.py`,
`app/seed_data/junioren-2026/`); `app.imports sap` refreshes them from SAP. No
source names who sailed, so the real acts have no squads or crews. **Everything invented
is in the demo series** `demo-1-2026` / `demo-2-2026` — the same 36 clubs with made-up
squads and three made-up weekends each (one final, one live, one planned) — **never
published by the seed**; `seed_test_setup --publish-demo` (`app.seed.publish_demo`)
publishes them in a league of their own, `/demo`: the test suite, the e2e stacks and
staging (`SEED_PUBLISH_DEMO=true`, `deploy/compose/`), never a real site. The people who sign in are
concentrated:

- **club** ASVW, a 2. Liga club (decided 2026-10-21; it was NRV): `board@asvw.example.com` (its `admin`,
  Gundram Leifert), `teams@` (its `manager`, the team manager, Gunnar Voigt),
  `treasurer@`, and every ASVW sailor — all members of it. A sailor needs an
  account to sign a waiver; a sailor of any other club has none, and the specs pick their
  adults and juniors from ASVW's squad;
- **series** the demo's 2. Liga 2026 (`demo-2-2026`), ASVW's: `serie@` (its `manager`, and
  of the 1. Liga's 2027 draft); `presse@` (its `editor`, Paula Presse — writes about its
  matchdays, organizes nothing);
  `junioren@` (Jocki Hellmich, `manager` of the Junioren-Segelliga 2026 and its 2027
  draft);
- **event** its act 3 (`demo-2-2026-act-3`), still planned, **hosted by ASVW** — so its claims are ASVW's to pay
  and ASVW's officials are the event's too: `orga@` (manager, Peter Weichel), `regatta@`
  (race officer, Malte Rackow), `jury@` (Heiko Thölmann), `helfer@` (helper, Johannes
  Machur). Every demo act has a host club (DTYC, KYC, ASVW);
- the **league office** `admin@`, `redaktion@` (editor — the journalist, Sven Jürgensen,
  who writes and keeps pictures and organizes nothing), `wl@` (race officer, Christoph Zanter), and
  `gast@sbl.example.com` with no relation.

**Next year, to practise on** (`app.seed`, decided 2026-10-22): the 1. Segel-Bundesliga
2027 and the Junioren-Segelliga 2027 are **drafts**, so the public site stays on 2026.
The 1. Liga's has its six announced acts — Friedrichshafen (act 1, 16–18 April) and
Hamburg (act 6, 14–16 October) with dates, Überlingen, Berlin, Strande and Warnemünde
without (none announced) — and no clubs yet: entering them, the squads and a draw is
what there is to practise. **ASVW hosts Warnemünde 2027**, so its officials are that
event's organizers. Only what was announced is seeded; nothing invented.

The role switcher groups them the same way (league office · series · event · club ·
sailors · guest, the `group` of `/api/dev/users`), the sailors folded until searched.

Test addresses use `example.com`: `.test` and `.example` are reserved domains that email validation
rejects — including in real login flows.

## Domain decisions

These points were deliberately decided this way; bypassing them costs a lot later:

- **Points are derived, not entered.** The source of truth is raw data in
  `RaceEntry` (`code`, `finish_position`, `redress_points`). From that,
  `app/services/standings.py::recompute_event` writes `points`/`is_discarded` fields and
  `EventStanding` and `SeasonStanding` records. Stored for queries, sorting and export — **never
  set by hand**. A protest decision changes one row of raw data, then recalculate; it never
  becomes a data migration. Read endpoints recalculate fresh anyway, so forgotten recalculation
  never shows wrong numbers.
- **Series instead of League + Season.** A `Series` is a set of events scored together —
  "1st Segel-Bundesliga 2026". The name carries the year; there is no separate season field.
  Terms: see `docs/concepts.md`.
- **`Team` is the enrollment** — to a Series, to an Event, or to both.
  `event_id` empty means **registration for the Series** (Squad and public visibility depend on
  this), `event_id` set means **participation in an Event** (Pairing list, results and lineup
  depend on this). Who participates in an Event must also be registered for that Series; the
  row carries both IDs then. Both cannot be null. This also means: a club can participate in
  multiple Series, and enrollment in "DSBL 2026" does not apply in 2027.
- **A club enters one team per event — or as many as the event's `teams_per_club`
  allows** (Story VA-13, decided 2026-10-23; the Junioren-Liga has `KiYC 1` and `KiYC 2`).
  `Team.number` tells a club's teams in one event apart and names them (`KYC (SH) 2`); the
  club stays registered **once** for the series, and every team it enters is lined up
  from that one squad — a sailor may sail for team 1 at one act and team 2 at the next,
  never for two teams in one act. In the series table each team is its own row.
- **The pairing list belongs to the Event, as do the teams in it.** Draw and scoring work on
  this Event's participants, not all Series registrations. When creating an Event, Series
  registrations are pre-selected by default.
- **A club appears publicly only when enrolled.** `GET /api/clubs` filters by year;
  a newly created club is visible only in `/api/admin/clubs`.
- **Participation is public, affiliation is not.** Whoever is registered for a Series or
  entered into an Event is named publicly — the pairing list, the results and the standings
  carry that name anyway, so hiding it on the club page would be theatre. Plain club
  **membership** (an active `ClubMembership`) is different: it is shown only to that club's own
  members and organizers and to the site's `admin` (`GET /api/clubs/{id}/members`, Story
  V-10). Never widen
  the roster to guests, and never gate a squad or a lineup behind a login.
  A person may additionally switch off their own **profile page** (`Person.profile_public`, `Person` after #40,
  Story S-4) — that hides the collection (photo, club and matchday history, the page
  itself), while the **name** stays on every competition record, as plain text instead of a
  link. So: a name in a result is never hidden, and a profile page is never forced.
- **A tie is broken by places sailed: more firsts, then more seconds, …, finally the last
  race** (decided 2026-10-27, `app/scoring/low_point.py::_tiebreak_key`). Only a finish
  is a place — a redress, a penalty or a did-not-finish counts towards the points, never
  as a place. That is how the league's scoring (TracTrac) ranks; comparing scores (RRS
  A8.1 read literally) would count a redress 3.0 as a third place and ranked one tie of
  2026 the other way.
- **Who misses an Event gets that Event's participant count + 1 points.** Not showing up must
  never be better than showing up and finishing last
  (`app/services/standings.py::compute_series`).
- **The current year is the newest one not in the future** — not simply the highest ID. Otherwise
  creating "DSBL 2027" would immediately switch the public page to a year where no one is registered
  yet (`app/services/series.py`).
- **A League is what links the years: `/1-liga` is the league, its series are its years**
  (issue #14, Story B-14, `docs/site-structure.md`). The 1. and 2. Liga are **two
  leagues** (decided 2026-10-16 — each is a top-level entry of the site, like
  deutsche-segelbundesliga.de's), though they sail the same weekends; `Series.level` still
  says which division a series is. An **act** is the events of a league's year sharing a
  matchday number — one page, `/:league/:year/act-:n`. `Series.league_id` is optional:
  a series or event in no league keeps its own page at `/series/:id` / `/events/:id`.
  The current year is asked **per league**. News, press, pictures and documents come from
  the API; only the videos and the association's own texts are static content behind
  hooks (`web/src/content/`). **Nothing invented is static content**: an example belongs
  to the demo layer (`publish_demo`), and a notice board shows what Manage2Sail published
  (Story A-14).
- **An Event can belong to a Series, but need not.** `series_id` and `matchday`
  are optional. The normal case is an Event within a Series; a cup or training weekend stands
  alone, appears in the calendar, and scores in no Series ranking. The **Event number belongs to
  the Event**, not the Series.
- **Host club and Venue are different.** `Event.host_club_id` is the club running the Event,
  `Event.venue_id` the sailing area — and the latter is **optional** because it is often not
  set when the Event is created. `Event.logo_url` defaults to the host's emblem.
- **The Event defines the configuration.** `Event.team_count`, `boat_count` and `flight_count`
  determine everything else: `races_per_flight = ceil(team_count / boat_count)`. No magic constants
  in code.
- **Scoring rules belong to the League** (`League.scoring` as JSON), not in code.
  Women's and youth leagues score differently, and rules change between years.
- **External systems are matched via `ExternalId`, never by name comparison.** Club
  and team names are spelled differently in SAP Sailing, manage2sail, and here
  (`BYC (BA)`, `BYCÜ`, `KYC (SH)`). The one bridge on a first import is the club
  **code** (`app/imports/`, Story A-14) — and at Manage2Sail a code is *not* unique
  (`KYC` is Kiel and Konstanz), so there a club's key is code plus M2S's club name, and a
  shared code is never matched.
- **Boats have colors** (BLACK, GREEN, DARKBLUE, RED, GRAY, ORANGE) **and belong to the Event**,
  not the draw: the organizer assigns color and name when creating the Event; a new pairing list
  only swaps the assignment.
- **One Flight = 3 races**, each with all 18 teams, each on a different one of 6 boats.
  16 flights = 48 races per matchday.
- **Pairing lists are generated by the Java tool**, exposed via `api/app/pairing/generator.py`
  (process call, JAR from `reference/PairingList`). The Python generator in
  `api/app/pairing/schedule.py` is **not a replacement**: it does not optimize boat swaps
  between flights and creates roughly 27 instead of 0. Before porting, this metric must be
  included — see `docs/findings.md`, section 2.
- **An optimization run takes minutes, not seconds.** It belongs in a background job with
  progress indication, never in an HTTP request.
- **The default is therefore the catalog** (`api/app/pairing/schedules/`): per configuration
  (teams/boats/flights) **one** stored `out.yml`, computed once. A seed value shuffles starting
  positions in milliseconds and leaves every quality metric unchanged — they depend on structure,
  not names. Extend with:
  `uv run python -m app.pairing.catalog --teams 18 --boats 6 --flights 16`.
- **Four states of an event, deliberately not one state machine** (Story VA-8,
  `app/services/event_readiness.py`): **Saving never requires validity** — title alone is
  enough, and an event with no date, no boats and the wrong number of clubs is the normal
  early state. **Publication is orthogonal to status**: `published` on `Event` and `Series`
  decides who can see it, `status` where it stands sportingly, and publishing **locks
  nothing** — a published event stays fully editable and need not be complete; public
  endpoints show published data only and answer 404 for a draft. **Validity is computed,
  never stored**, and returns a list of machine-readable reasons (the UI must say *what* is
  missing); it gates the **draw** and the **start** (`POST …/start`, which also needs a
  pairing list). **The first race freezes the configuration** — dimensions, series/matchday,
  clubs, boats, pairing list — the trigger being any race no longer `scheduled` or any
  result recorded. It **never** freezes results: correcting a result, including a protest
  decision months later, is the point of the race-committee screens.
- **Closing an event is a declaration, never a consequence** (Story VA-10). `finish`
  (`live` → `final`) is the race committee saying racing is over; it deliberately does
  **not** require a complete race list, because a day that loses its last flights to dying
  wind is still over. `cancel` works from `planned` and from `live`, deletes nothing, and
  takes the event out of `SCORED_STATES` — so a called-off day costs nobody the
  "participants + 1" that missing an event would. Both undo via `reopen` (`final` → `live`,
  `cancelled` → `planned`). Closing freezes nothing: a protest heard weeks later still has
  to land on a `final` event. The status changes **only** through these transitions
  (`app/services/event_state.py`) — `PATCH` does not carry it.
- **An event's tools are gated on what the model answers for that event**
  (`GET /api/events/{id}/access`, Story WL-3), never on `hasRole`: a summary role says
  someone is a race officer *somewhere*, not here.
- **The printed pairing list is the Java tool's job, and its settings belong to the Event.**
  `api/app/pairing/pdf.py` calls `PdfExport` in `reference/PairingList` — the layout lives
  there and is not reimplemented here. What varies per event is stored in
  `Event.print_settings` (JSON, like `Series.scoring`): the **organizer** sets font size,
  landscape and whether the per-team pages are included, because they know the venue and
  the printer. Empty is the normal case and is then **not sent** — the tool picks the size
  from the number of rows and reads the `#rrggbb` a color picker produced. Anything the
  tool can decide for every caller belongs in the tool, not in an adapter here: a rule that
  lives only in `pdf.py` gives the site a good sheet and a command-line run a bad one.
  `?team=` renders one crew's own page, and `renderer_available()` says whether this
  installation can print at all, so the page can leave the download out.
- **In conflicts, the race committee wins over imports.** Otherwise polling overwrites a
  protest decision just entered.
- **Permissions are relation tuples, `user:relation:object`, and the model is OpenFGA's
  DSL without the server** (Story Z-2, `MODEL` in `app/models/auth.py`, the facade
  `app/authz.py`, the writes `app/services/grants.py`). Object types `site`, `club`, `series`, `event`, `sailor`; relations
  `admin` (site), `editor` (site, series, event — news, press and pictures, nothing
  else), `manager` (the organizer — club, series, event),
  `race_officer` (site, series, event), `jury` (series, event), `helper` (event — works
  the day, holds no power on it, Story VA-12), `treasurer` (club,
  event — the host club pays its events' costs, so its treasurer is every hosted event's,
  Story F-1), `guardian` (sailor — a parent the child's club linked, who accepts a
  minor's waiver online, Stories V-13, S-8), and `admin` on every object — everything
  within it, people included (a sailor's is only derived: the site's); on a club the `admin` decides who is *in* it
  and the `manager` who *sails*. `or … from …` lines say what implies what: an object's
  admin is each of its relations, a series' people are its events', the host club's
  people are its events', the site's race committee are managers of every event, and
  an editor of the site or a series is one of each event below it. **Every permission question goes through `app/authz.py`**, named after
  OpenFGA's API so the interpreter behind it could become an OpenFGA server: `check`
  (`User.can` is its one-line sugar), `read` for the rare place where the tuple itself is
  the fact, `list_objects`, `ensure`, objects as `ObjectRef` (`club:3`). Nothing outside
  it and `grants.py` touches the `Grant` table or walks `user.grants`, and never ask a
  summary role (`User.roles`, navigation only) or a "holds directly" shortcut what the
  model answers. `require_site` guards the league office's screens, `require_on_event` a
  route about one event. An object's admin sees and writes its tuples
  (a club's admin among the club's members). Write and delete one tuple at a time — never
  rebuild a person's rows from a list of names, that is how every per-club grant was once
  silently dropped. Membership implies nothing else; it is a `ClubMembership` row, not a
  tuple (#40): the model types `member` on a club, nobody writes it, and the facade
  hands the account's person's active memberships to every check as *contextual* tuples
  (`CONTEXTUAL` in `app/models/auth.py`) — so `check(user, member, club)` still answers.
  A club always keeps one `admin` (Story A-8): removing the last one is refused even
  while managers remain, or nobody could add a member any more.
  Four foreign keys and one small interpreter are the whole model: no authorization
  service.
- **A member and a sailor are one `Person`, and the model knows their clubs** (decided
  2026-10-25, #40, `docs/PLAN_PEOPLE.md`; Stories V-4, Z-5, V-15). A person exists once,
  may have an account (`Person.user_id` — every account has exactly one person, linked by
  verified address), and an **active** `ClubMembership` is both "member" and "sails for";
  a person's `manager` is `manager from club` over those. That one answer decides who
  puts them in a squad, changes them, signs their waiver forms and links their parents.
  A club's organizer creates people for their own club; a second club takes consent
  (invited/requested, accepted by the other side), and a person in another club without
  an account only the league office adds — no club can simply take anyone. The link is
  made in `app/services/people.py` (registration, enrollment, every sign-in); deleting an
  account keeps its person and clears `user_id`. An `invited` or `requested` row grants
  nothing — only `active` rows are the edge and the `member`.
- **A person can be in several clubs, and an account has no club of its own.** Membership
  and organizing (`manager` or `admin` on it) are both per
  club and independent; there is no `User.club_id` (removed 2026-09-25, Story Z-3). Which
  club a screen shows is the URL's business (`/me/club/:id`), the account remembers
  nothing; several clubs are several cards in my space, not a choice in the navigation.
  The club's page there is where its people are managed (V-8, Z-5, A-8; one *People*
  section, #45), squads registered
  (V-1) **and crews named** for the club's matchdays (V-2), reached through
  `GET /api/clubs/mine`, never through an admin-only list.
- **A list is narrowed on the server, never in the browser** (Story A-13, decided
  2026-10-25): every paged list's search, sort and filters are one `ListFilter` class in
  `app/filters.py` (on `fastapi-filter`, rules in `app/listing.py`), taken with
  `ListDepends(...)` and applied as `filters.sort(filters.filter(stmt))` before
  `paginate`. A screen showing "this series' events" asks for them; a page of everything
  filtered client-side stops at the page's end without a word.
- **"Mine" has one answer, and my space is assembled from it** (Stories Z-8, S-7,
  `app/services/contexts.py`, `web/src/pages/me/`). `GET /api/me/contexts` lists every
  club, series and event a person is part of: a relation held **directly** on it, or
  **sailing** there (a squad → series, a crew → event — no tuple, reported as `sailor`).
  Site relations are not "mine" — that is the league office, `/office`. What needs the person there comes back
  as **codes with counts**, worded by the page. Each context page is built from sections
  that declare which relations show them, so a new role or panel is a line in that list,
  never a new screen per role — the screens per role (`/club`, `/reimbursements`) are what
  this replaced, and each knew only one role. A mutation that changes what needs someone
  invalidates `/api/me/contexts` along with its own data.
- **The squad's size belongs to the series, or to the event when it stands alone**
  (`squad_min`/`squad_max`, Story V-1) — never a constant in code or in the screen. The
  maximum is enforced when a squad is saved; the minimum is guidance the club screen
  shows, because a squad is built up over weeks and a club must be able to save two
  names in March.
- **The liability waiver is one statement per competition, and age picks the path**
  (Stories S-1, S-3, VA-5, `app/services/waivers.py`). A sailor signs once per **Series**
  they are registered in, which covers every event of it; an event that belongs to no
  series needs its own. The text is versioned and frozen — a new wording is a new version
  that everyone confirms again, never an edit. An **adult** confirms online from their
  own account; a **minor** on the reference date (series start, else 1 January of its
  year; event start) needs a guardian's wet-ink signature: the site prints the form
  (`GET /api/waiver/form`, reportlab) and takes the scan back
  (`POST …/waiver/scan`). The scan is the most sensitive file here: random name under
  `uploads/waivers/`, one serving endpoint that checks who asks, every look in
  `AuditLog`. A minor's **guardian** may instead accept online from their own account
  (`guardian_online`), once the child's club — its manager or admin, nobody else — linked
  that account to the child (`user:guardian:sailor`, decided 2026-10-17). A sailor who is
  not cleared **can still be lined up**: the waiver is said to the sailor, the guardian,
  the club's organizer (`crew_waiver_missing`) and the check-in list, never locked
  (Story VA-5). Without a date of birth nothing can be confirmed — the status says so
  instead of failing open. Status is **computed, never stored**, by the one function the
  account page and the organizer's check-in list both use.
- **Live updates are Server-Sent Events carrying a version token, published after the
  commit** (Story B-5, `api/app/live.py`). The browser invalidates the query keys it was
  given and refetches through the generated client — the stream never carries a second
  copy of a table, except boat positions. Publishing inside the transaction makes the
  subscriber refetch the *old* data and stay stale; that is the one trap. The hub is
  in-process, one uvicorn process, like `app/jobs.py`.
- **Races run one at a time, and one service owns their transitions**
  (`app/services/race_state.py`, Story WL-3). Recall and abandon **clear the race's
  entries** — that is what makes "unscored" true, because scoring reads `RaceEntry`, never
  `Race.status`. A race that has started once keeps the event frozen (the freeze counts
  `AuditLog` rows, not only the current status).
- **The tracker belongs to the boat, not the team, and the committee boat is a tracker
  too** (Stories L-1, L-4). Who sails which boat is what the pairing list says; the
  committee boat's phone *is* the boat end of the start and finish lines.
- **One course family: windward/leeward with a leeward gate** (Story L-2) — start line pin
  to port of the committee boat, port rounding at the windward mark, either gate mark,
  finish pin left or right. Nothing else is modelled until real data asks for it.
- **Legs, passings, distance to go and rank are derived, never stored** — the same rule as
  points. The algorithms sit behind Protocols (`api/app/tracking/`) and are chosen in one
  place, `default_pipeline()`, so a change can be decided on recorded data (a `compare.py` for that is planned).
- **A claim is on an event or on a club; the event's manager or treasurer, or the club's
  treasurer, settles it**
  (Stories F-2, F-3, decision of 2026-10-07, `app/services/expenses.py`). On an event the
  host club pays and those holding a relation *directly* on it (or its series) file; on a
  club the club pays and its members file. Who decides is checked on the **tuple** — the
  event's own manager, the treasurer by the model (the host club's included) — never
  `can(manager)`, which would hand every event's purse to the site's editors. A club's
  `manager` is its team manager and holds none of the club's money (decided 2026-10-26):
  its claims, account and payment runs are the treasurer's and the admin's. Nobody
  decides their own claim. Holder and IBAN are **copied onto the claim at submission**
  from the person's saved bank account (Story S-6), which only its owner ever reads.
- **A person's documents are seen by their organizers, and every look is logged**
  (Story S-5, `app/services/personal.py`): the managers of events they work at directly
  and of clubs they are members of. Private uploads — waiver scans, receipts, personal
  documents — share one validator and store (`app/services/uploads.py`): checked by
  content, random names, one serving endpoint each.
- **Money goes to the bank as a file, never through a bank login** (Story F-7,
  `app/services/payments.py`). A payment run turns approved claims into one `issued`
  payment per payee and one SEPA file (pain.001.001.09, `sepaxml`, XSD-validated) the
  treasurer uploads to the club's online banking; "booked" settles the run, a return fails
  one payment and its claims open again. The run keeps its message id, so the bank
  refuses the same file twice. Formats come from libraries — `sepaxml`, `schwifty` (IBAN,
  BIC), `openpyxl` (the spreadsheets), `segno` (the GiroCode for one claim, Story F-8) —
  never written by hand.
- **News and press releases are posts editorial writes on the site** (Story R-1,
  `app/routers/posts.py`): the `editor` alone (and `admin`) — the site's for every post,
  a series' or an event's for posts and pictures about that regatta, whose league they
  then appear in (`app/services/editorial.py`, decided 2026-10-24). **Editorial writes;
  it organizes nothing**: no clubs, sailors, events or rosters — that is `admin` and the
  objects' own managers. A draft until published, like an event; one league's or the
  association's. The text is HTML from a
  TipTap editor, **cleaned to an allowlist on every write** (`app/services/rich_text.py`,
  `nh3`) — the public page shows the stored HTML as it is, so nothing may reach the table
  around that cleaner. An editor library must be MIT or Apache licensed (decided
  2026-10-19), which ruled out CKEditor 5 and TinyMCE.
- **Every stored file goes through `app/storage.py`, and where it lives is a setting**
  (`SBL_STORAGE=local` under `SBL_UPLOADS_DIR`, or `s3` with the `SBL_S3_*` settings,
  decided 2026-10-27). Callers speak in keys (`clubs/3.png`), never in paths: no `Path`,
  `open` or `FileResponse` on an upload outside that module. A file is served through
  the endpoint that checks who asks, on S3 as on disk — no presigned links. **A deployment
  keeps its files in S3, and the provider is interchangeable** (decided 2026-10-27):
  `deploy/compose/` has no uploads volume, SeaweedFS is only its default provider, and a
  key means the same file everywhere, so moving between disk and S3 or between providers
  is `python -m app.storage_copy` — nothing provider-specific beyond the `SBL_S3_*`
  settings. Local disk stays for development, the tests and staging.
- **A deployment's secrets are sops-encrypted in the repository, for SSH public keys**
  (decided 2026-10-27, `.sops.yaml`, `deploy/compose/secrets.sops.env`): no age keys to
  hand out — a recipient decrypts with their `~/.ssh/id_ed25519`, as in the team's other
  repositories. Only secrets go in the file; settings stay in `.env`. Decrypted values
  reach `docker compose` as environment (`compose.sh`, `sops exec-env`), never as a file.
  A new recipient means `sops updatekeys`; `scripts/check-sops.py` fails until it is done,
  and on any value committed in plaintext.
- **An upload's type is its content, never its name** (decided 2026-10-19,
  `app/services/uploads.py::sniffed`, libmagic): a browser declares a file's type from its
  extension, so neither the name nor `content_type` is read; the browser checks early by
  first bytes (`web/src/lib/sniff.ts`). Pictures must also decode in Pillow.
- **Every picture is a library entry, fed through one import API** (Story R-2,
  `app/services/media.py`, `docs/PLAN_MEDIA.md`): editorial's uploads and every outside
  source (our `/upload` page first, later Nextcloud or Flickr bridges) end in `MediaItem`;
  a source holds an **import key** (hashed, shown once, revocable) and uses only
  `/api/import/*`. A picture may belong to an event *or* a series; a web picture is
  copied, never hot-linked — a post's text and cover take only the library's or the
  site's own addresses. **The upload is kept as it came, privately, and never served**
  (it carries the camera's location); the site serves WebP at 480/960/1600/2400 px made
  from it, a cache rebuilt from the original when a size is missing (decided
  2026-10-20). A post's text stores only the address; alt text, size and credit come
  from the library when it is read (`media.for_readers`).
- **SAP Sailing Analytics is an offline oracle, never a runtime.** Self-hosting it for six
  boats is the wrong size (8 GB, MongoDB, RabbitMQ, one maintainer); its recorded
  Mövenstein dataset and its detectors are used once, locally, to check ours
  (`docs/PLAN_LIVE_IMPLEMENTATION.md` §2).

## Logged in or guest

Most requests carry a user, but the public site also serves guests.
Endpoints open to everyone use `app/auth.py::optional_user` — which returns
`User | None`. An **invalid or expired** token is treated as "not logged in"
not an error: otherwise the public site would be unusable for someone with an old session instead
of just treating them as a guest. Protected areas still use `current_user` and respond with 401.

## Permissions by area

| Area | Roles |
|---|---|
| Create clubs and enroll in Series | `admin` |
| Create Series | `admin` |
| Set a Series' participants, dates, publication | `admin`; the series' `manager` |
| Create and maintain Events | `admin`, site `race_officer`; the `manager` of the event, its series or its host club |
| Pairing lists, accounts | `admin` |
| See, write and delete tuples on an object | its `admin` — site admin everywhere, a series' admin on its events, the host club's on its events; a club's admin among the club's members |
| Enter results, run races, trackers | `race_officer` of the event — held on it, its series, its host club or the site |
| Add a person to a club, invite, accept a request, crest | `admin`; the club's `admin` (own club only); a person already in another club is invited and accepts, or asks and the club's admin accepts (V-15); one without an account only the site's `admin` adds |
| Register participants for Series/Event, squads, lineups | the club's `manager` or `admin` (own club), site `admin` |
| Create and maintain people (sailors) | `admin`; a club's `manager` for their own club (changing one: its active members, or people in no club; an address once set: `admin` only) |
| Put a person in a squad | the `manager` of a club they are an active member of (`manager from club`), or of any club while they are in none; site `admin` |
| Accept an invitation, ask to join, leave | the person (their own account) |
| Link a parent to a person as guardian | the manager or admin of a club the person is a member of; site `admin` |
| Confirm a waiver for a person | the person; `admin`; the manager of a club they are a member of; their linked `guardian` while they are a minor |
| Write news and press releases, keep pictures | `editor` of the site (all); of a series or an event (that regatta's) |
| Register Squad for Series | `admin`, `team_manager` (own club only) |
| **Create** Event | additionally the `manager` of the series (its acts, naming any host) or of the host club (outside a series only) |
| File an expense claim | `race_officer`/`jury`/`manager`/`helper` held directly on the event (or the first three on its series); `member` of the club |
| Decide and pay a claim | the event's direct `manager`, `treasurer` of event or club (and their admins); never the claimant |
| See a person's documents | the person; `manager` of an event they work at directly or of a club they are a member of |
| Bank account | its owner only |
| Club's bank account, payment runs, SEPA and Excel exports | the club's `treasurer` (and its admin) — not its `manager` |

Defined as dependencies in `api/app/auth.py`; roles are checked fresh from the database on
**every** request so revocation takes effect immediately.

## Tests

Three levels, all three are desired:

- `api/tests/unit/` — Scoring logic, pairing quality, parsers.
- `web/tests/test_*.ts` — **Vitest**, for frontend logic that has rules of its own (the
  workspace's declaration, `lib/workspace.ts`): `pnpm test` in `web/`, part of `check.sh`.
  A co-located `*.test.ts` would not run.
- `api/tests/stories/` — **User story level**: one story per test, named for what someone wants
  to achieve ("As a visitor I see the league table").
Each story in `docs/userstories/` lists the tests that cover it — and each story test names its
story ID in the docstring. New features are added to stories first, then tested.

- `e2e/` — Playwright against the running application, also organized by stories.
  Prerequisites: `scripts/dev-stack.sh --workers 4`, then `playwright test`. The
  configuration deliberately does not start servers, so a missing server is not a test
  failure.

  **The suite is parallel, with one stack per worker.** `dev-stack.sh` runs N backends
  over N SQLite files and N web servers; `e2e/fixtures.ts` points each worker at its own
  via `parallelIndex` (**not** `workerIndex`, which keeps climbing as workers are
  replaced). The shared database was what forced a single worker: `lifecycle.spec.ts`
  writes, and a second worker read lists while the first changed them. It also runs
  against a **built** bundle rather than the dev server — the suite is dominated by page
  loads, and a build costs two seconds. Together: 3.7 minutes down to 34 seconds.
  Two projects: `chromium` and `mobile` (Pixel 7) — the site is read mostly on mobile.
  `e2e/lifecycle.spec.ts` signs in through `/api/dev/login`, so the backend needs
  `SBL_DEV_LOGIN=true`; it also **writes** (clubs, series, events), so point it at a
  throwaway database rather than one whose contents matter.

  Specs address elements by `data-testid`, not by visible text, wherever a test is about
  structure rather than wording: the site is bilingual and the copy is edited often, and a
  spec that breaks on a reworded heading tests the translator, not the application. The
  locale is pinned to `en-US` for the same reason — English is the source language.

  **Frontend type check:** `pnpm typecheck` in `web/` (i.e., `tsc -b`). `tsc --noEmit` checks
  **nothing** in this Vite template — it uses project references. The **specs** have their
  own root `tsconfig.json`, run with `pnpm typecheck` at the repo root; it borrows
  `@types/node` from `web/node_modules` because the root package has no install of its own.
  `pnpm e2e:list` loads and enumerates every spec without starting a browser — the quickest
  check that a spec still parses.

  **Every group of tests that covers a story is a `describeStory("VA-8/VA-9: …", …)`**
  (`e2e/fixtures.ts`), not a bare `test.describe`: the IDs at the start of the title become
  Playwright tags, so the HTML report filters by story and `playwright test --grep
  "@VA-8\b"` runs one story's tests (the `\b` matters — `--grep` is a regex, and `@V-1`
  alone also matches `@V-10`). A title without IDs is refused at load, and
  `scripts/check-docs.py` checks each ID is a real story. Only a group that covers no
  story ("Foundations") stays a plain `test.describe`.

  **Journeys** (`docs/journeys/<slug>.md`, indexed with the **actors** and the format in
  `docs/userstories/journeys.md`; the `journey` skill writes them) are several stories in
  the order they really happen: a Mermaid sequence diagram for the stakeholder and a step
  table for the tests. Step IDs are `J-n.k` — **never renumbered or reused**; a removed
  step goes on `Retired steps:`. A *walk* is one long test whose stretches are
  `step("J-5.4", "…")` — `tests/journeys.py` in pytest, `describeJourney` + `step` from
  `e2e/fixtures.ts` in Playwright — and the step's story comes from `docs/stories.json`.
  `check-docs.py` holds the walk to the table's order, every branch to a walk or a
  `Journey step J-n.k` docstring, the actors to the list, and the status: ● only when
  every step is covered and every story it names is ●. A changed feature means checking
  the journeys whose steps name its story.

  **Evidence mode** — `EVIDENCE=1 playwright test` (`pnpm e2e:evidence`) records a video,
  a final screenshot and a full trace of every test, and writes an HTML report to
  `e2e-evidence/report/` (`pnpm e2e:evidence:show`): what each story's test actually
  showed. Off by default — it about doubles the run and writes ~450 MB. It is also a
  slower run, and that is useful in itself: it is what exposed a duplicate `h1` a fast
  run never saw (docs/gotchas).

  **One report over both suites: Allure** — `scripts/allure-report.sh` (`--no-e2e` for the
  backend alone) runs pytest with `--alluredir`, the browser suite in evidence mode, and
  renders `allure-report/` grouped by **story** (`allurerc.mjs`). No test carries an
  Allure decorator: `api/tests/conftest.py` reads the story IDs from the docstrings,
  `e2e/fixtures.ts` from the `describeStory` titles, both take titles, roles and phases
  from `docs/stories.json`. A journey's `step()`s are Allure steps; videos, screenshots
  and traces are attached. Chosen over ReportPortal (a server of ~11 containers) and the
  test-management SaaS tools (a second home for the stories) on 2026-10-04.

  **`docs/traceability.md`** is the static half: every story with the tests its `Tests:`
  line names, the browser groups tagged with it and the journeys that walk it — including
  the stories no test covers, which a test report cannot show. Generated with
  `docs/stories.json` by `scripts/check-docs.py --fix`; `check.sh` fails when either is
  stale.

  **One-time setup:** `sudo pnpm exec playwright install-deps chromium` (or
  `sudo apt install -y libnss3 libnspr4 libasound2t64`). Chromium will not start without these
  system libraries.

**The backend suite runs in parallel** — `uv run pytest -n auto` (pytest-xdist), as
`check.sh` does. Every worker imports `conftest.py` and so builds its own database and
uploads directory; anything a test reads from the environment must be **assigned** there,
never `setdefault` — workers inherit the starting process's environment. A test that needs
rows another test created only passes in one order: the seed is what each worker starts
from, so count on the seed alone.

External APIs are never called live in tests; we test against recorded fixtures (`api/tests/fixtures/`).

## From issue to merge

Work is tracked as **GitHub issues** on `gundramleifert/segel-bundesliga` and reaches
`main` only through a pull request. **`/issue`** (`.claude/skills/issue/`) walks every step
below — `start <N>`, `pr`, `merge` (only on the user's word), `handover`, `accepted` /
`rejected`, plus `new` and `status`. One issue, one branch, one PR — never commit to
`main` directly. The tool is the `gh` CLI (`gh auth login` once; in the sandbox it needs
`api.github.com` and `github.com`).

**An issue is done when its stakeholder accepts it on staging, not when its PR merges.**
Many issues come from stakeholders, and they judge a change by using it, not by reading a
diff — and the place they can use it is **staging**, which runs `main` (decided
2026-10-28: the Render instance is gone; staging is to be a second Compose stack with the demo published (`docs/deploy-server.md`) — and, like production, **without the dev login**, which `compose.yaml` fixes off (decided 2026-10-28); until it runs, a change is shown on a local stack). So the
PR **refers** to the issue and never closes it, and between merge and close the issue
carries the label **`in-stakeholder-review`**. While nothing is in production, `main` is
allowed to hold changes not yet accepted; that changes when there is a production.

1. **Read the issue** — `gh issue view <N> --comments`. If it describes new or changed
   behaviour, its acceptance criteria become a story (or an edit to one) in
   `docs/userstories/`, as below; the story is the lasting record, the issue the request.
   Ask on the issue (`gh issue comment <N>`) rather than guessing when it is ambiguous.
2. **Branch from a fresh `main`** — `git switch main && git pull`, then
   `gh issue develop <N> --name <N>-<short-slug> --checkout`, which also links the branch
   to the issue. English, kebab-case: `42-waiver-reminder-mail`.
3. **Commit on the branch** as usual — the story, test, code order below still holds.
   Mention `#<N>` in the message body where it helps; the PR carries the link anyway.
4. **`scripts/check.sh` green, then push and open the PR** —
   `git push -u origin HEAD`, then `gh pr create --base main` with a title saying what
   changed and a body that starts with **`Refs #<N>`** — never `Closes`/`Fixes`/`Resolves`,
   which would close the issue on merge, before anyone has seen it — followed by what
   changed, why, and how it was tested.
5. **Merge only when the user says so** — `gh pr merge <PR> --squash --delete-branch`.
   Squash keeps `main` one commit per PR; its message is the PR title. Then
   `git switch main && git pull` and delete the local branch.
6. **Hand over to the stakeholder once staging runs the change** — the deploy takes a
   few minutes; check the change is visible there first. Then
   `gh issue edit <N> --add-label in-stakeholder-review` and comment on the issue
   (`gh issue comment <N>`): the staging URL, which role their own staging account
   needs (granted to it there — staging has no role switcher), and what to try. Staging resets to the seeded data on every deploy, so
   say how to get to the state the change is about.
7. **Accepted → close** — `gh issue close <N> --comment "Accepted on staging"` (or the
   stakeholder closes it). **Not accepted** → remove the label, and the feedback is a new
   branch for the **same** issue (`<N>-<slug>-2`) from step 2; the issue stays open until
   it is accepted. Feedback that is really a new wish becomes a new issue.

`gh issue list --label in-stakeholder-review` is the list of what waits on stakeholders.
The label is created once: `gh label create in-stakeholder-review --color FBCA04
--description "Merged and on staging, waiting for the stakeholder's acceptance"`.

Work found along the way that is not this issue's becomes **a new issue**
(`gh issue create`), not an extra commit on this branch — a PR about one issue is one a
reviewer can read.

## Working here

Three habits. They exist because each one was learned the expensive way, and the cost of
re-learning falls on whoever comes next.

### Before you debug, read `docs/gotchas/INDEX.md`

One line per note — the whole folder skimmable for the price of one file. Read it at the
start of a task, and open the note whose rule matches what you are about to touch or what
just surprised you. These are things **not** deducible by reading the code harder: a library
that owns a CSS token name we also wanted, an assertion that passes because the bug it
guards against hides itself, a sandbox rule that makes a working command fail in the next
call.

The index is generated — `scripts/check-docs.py --fix` — and `scripts/check.sh` fails if it
is stale, so it cannot quietly drift out of date.

### When you were wrong, write it down

This is the part that is easy to skip and the part that pays. Write a note when you were
**confidently wrong** — you named a cause, acted on it, and it was something else — or when
a surprise cost more than ~15 minutes, or when a symptom pointed away from its cause, or
when a green check turned out to protect nothing.

Say *what misled you*, in one line, under **Cause**. That line is the whole point: it is
the hint the next agent needs before they start, and the part no amount of code-reading
recovers. `docs/gotchas/README.md` has the format and the rules for keeping the folder
honest — including deleting an entry once it stops being true, which is a real
contribution, not housekeeping.

    scripts/check-docs.py --new "a sentence stating the rule"   # scaffolds the note
    scripts/check-docs.py --fix                                 # refreshes the index

Do not write a note for an ordinary bug you fixed, or for something `CLAUDE.md` and
`docs/concepts.md` already say. Noise is what makes the next person stop reading the folder.

**Do this before you report the work finished, not after.** By the next session the
reasoning is gone and only the diff is left — and the diff is precisely the part that does
*not* carry why you first went the wrong way. A task where you were wrong at least once,
and no note came out of it, is a task that quietly threw away its most useful product.

### When you do something twice, make it a function

Repeated work is a design signal, not a chore. The rule of thumb: the second time, notice;
the third time, extract — and put the reasoning in the extracted thing, where it will be
read.

What already exists, and what each one replaced:

- **`scripts/check.sh`** — every gate that must be green, in fail-fastest order. Run it
  before you commit. It encodes two traps: `tsc --noEmit` checks *nothing* in the web
  project (project references — the real check is `pnpm typecheck`), and the Playwright
  specs plus `playwright.config.ts` are only covered by the **root** tsconfig.
- **`scripts/dev-stack.sh`** — seeds a throwaway database and runs both servers, which is
  what the e2e suite needs and deliberately does not start itself. It also keeps the suite
  away from `api/sbl.db`, which `lifecycle.spec.ts` would otherwise fill with test rows.
- **`e2e/layout.ts::expectNoSidewaysScroll`** — the "does this page fit its viewport"
  check, which has to assert *two* numbers to work at all, and which names the offending
  boxes when it fails so nobody writes that probe again.
- **`web/src/components/`** — the pieces every screen is assembled from, listed in
  `docs/components.md`: `Async` (one request, rendered: loading, error, empty, content),
  `Stack` and `CardGrid` (the two layouts, one of which *is* Story A-10 — a bare `grid`
  zooms the page out on a phone), `LinkCard`, `TabbedView`, and the form primitives. Read
  that file before writing a page; each entry replaced three or more hand-written copies
  that had already drifted apart. A component never imports from `pages/`.
- **`web/scripts/check-colours.mjs`** — a page names its colours (`text-muted`,
  `bg-warning-soft`), never shades (`text-slate-500`): the theme is the variables behind
  the names, so a shade is a page that breaks in the other theme. `docs/components.md`
  § Colours.
- **`scripts/check-docs.py`** — makes the documentation prove itself: every `Tests:`
  reference must resolve to something that exists, every story ID a test claims must be a
  real story, every gotcha must carry its Evidence, and the index must be current. It is
  part of `check.sh`, so the docs cannot rot silently between commits.

A tool nobody trusts is worse than none, so **verify a new check by breaking something on
purpose** and watching it fail. `check-docs.py` was run against a renamed class, a deleted
file, an invented story ID and a note with its Evidence removed before it was believed —
each one caught. A check that has never failed has not been tested; it has only been run.

### How to update the docs when you change something

Order matters, and it is the order the project already follows:

1. **The story first** (`docs/userstories/`, the file of the person who tells it). New behaviour is described before it is
   built — a story with acceptance criteria, and the reasoning for any decision that was
   not obvious. If you are changing existing behaviour, edit that story rather than adding
   a second one beside it.
2. **Then the test**, naming its story ID in the docstring. Watch it fail for the reason
   you expect; a test that passes before the code exists is testing nothing.
3. **Then the code.**
4. **Then the status marker and the `Tests:` line** — ○ open, ◐ partial, ● implemented
   *and tested*. Every `Tests:` reference must resolve to a node that actually exists;
   stale references are worse than none, because they make the document look checked when
   it is not.
5. **A domain rule that will outlive the story goes in this file**, under Domain decisions,
   in one or two sentences. A surprise that will not goes in `docs/gotchas/`.

If a story turns out to have recorded the wrong cause — it happens; A-10 blamed a
`flex-wrap` header for weeks — **correct the story**, and say what the cause actually was.
The narrative in a story is read by the next person as fact.

## Language

**English is the working language everywhere** — code, identifiers, comments, docstrings, commit
messages, API responses, and UI are all English first. We maintain German as a full, real second
language using **i18n (internationalization)**, not as German-only source text or loanwords.

**Frontend:** React uses `react-i18next`. Locale files live in `web/src/i18n/locales/`:
- `en/*.json` — English source strings (one namespace per page: `common`, `start`, `events`,
  `standings`, `clubs`, `club`, `sailor`, `matchday`, `account`, `admin`, `dev`)
- `de/*.json` — German translations of the same namespaces

Messages are **ICU MessageFormat** (`i18next-icu`): `{name}` for a value, and a plural is one
key — `{count, plural, one {# event} other {# events}}` — never i18next's `{{name}}` or
`_one`/`_other` keys. A message that does not parse is shown raw without an error, so
`pnpm check:i18n` (part of `check.sh`) parses every one and compares placeholders across
languages.

A language switcher in the UI lets visitors choose English or German at runtime. English is the
default and source language.

**Backend:** `api/app/i18n.py` provides:
- `Locale` — enum for supported languages
- `resolve_locale(request)` — FastAPI dependency that reads `Accept-Language` header, defaults
  to English
- `tr(locale, en=..., de=...)` — for user-facing strings a router builds directly, on routes
  not yet migrated to typed errors. Only literal runtime-visible text uses `tr()`; docstrings
  and Field descriptions are plain English.

**Errors — RFC 9457 Problem Details** (`api/app/problems.py`, `web/src/api/problems.ts`,
concept in `docs/concepts.md`): error responses are `application/problem+json`. A router
raises `Problem(status, code, title, **extra)`; the stable `type` (`/errors/<code>`) is the
contract, and the frontend maps `<code>` to the `errors` i18n namespace. Typed errors carry
**no** `tr()` sentence. Plain `HTTPException` / validation errors are also rendered as
problem+json (generic type, `detail` preserved). `app/routers/waivers.py` is the worked
example; other routers migrate incrementally.

**Domain terms** are now consistently translated throughout the codebase (code, docs, comments):
Wettfahrt → Race, Flight → Flight (unchanged), Spieltag → Matchday, Wettfahrtleitung → Race
committee, Serie → Series, Verein → Club, Segler → Sailor, Mannschaft → Team, Kader → Squad,
Aufstellung → Lineup, Liga → League, Jahrgang → Year, Boot → Boat, Pairing-Liste → Pairing
list, Ausrichter → Host club, Revier → Venue.
