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
| `docs/userstories.md` | What the system should do, with tests included |
| `docs/findings.md` | **Research findings** — API formats, League format, open questions |
| `docs/deploy.md` | Free test-instance deployment (`render.yaml`, `api/Dockerfile`) |
| `reference/` | Shallow clones of external repos for reference, not versioned |
| `~/.claude/plans/iterative-jingling-willow.md` | The agreed overall plan |

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
uv run pytest
```

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

**Authentication:** We store **no passwords**. Identity comes from Google, Microsoft
(OIDC token verification against provider keys) or via one-time code by email. Accounts are
linked via verified email address, so both methods lead to the same account. Roles (`admin`,
`editor`, `race_officer`, `club_manager`) are separate records and are verified fresh on every
request so revocation takes effect immediately. Accounts are created by explicit enrollment or
import, not by signing up (`allow_self_signup`).

## Testing different roles

**Registration:** `POST /api/auth/register` creates an account and sends a confirmation code.
Until redeemed, the address is unverified (`User.email_verified`) — without proof the account
cannot request club membership. Such an account has neither role nor club. Controllable via
`SBL_ALLOW_REGISTRATION`; distinct from `allow_self_signup`, which only controls **silent**
account creation when logging in with an unknown address.

**Club membership (`ClubMember`) requires mutual consent** — person applies, club approves, or
vice versa. This differs from series and event participation, where management can add unilaterally.

`SBL_DEV_LOGIN=true` enables `/api/dev`: there you can list test accounts and issue access tokens
**without verification**. A role switcher then appears in the UI (bottom right). Deliberately a
separate setting, not tied to `debug` — in a reachable environment this would be a security hole,
and the server warns on startup while it is on.

`app.seed_users` creates: one account **per registered sailor** (180) — without login, no one can
submit their waiver — one person per club with `club_manager`, plus `admin@`, `redaktion@`, `wl@`,
`beides@`, and `gast@sbl.example.com`.

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
- **The pairing list belongs to the Event, as do the teams in it.** Draw and scoring work on
  this Event's participants, not all Series registrations. When creating an Event, Series
  registrations are pre-selected by default.
- **A club appears publicly only when enrolled.** `GET /api/clubs` filters by year;
  a newly created club is visible only in `/api/admin/clubs`.
- **Who misses an Event gets that Event's participant count + 1 points.** Not showing up must
  never be better than showing up and finishing last
  (`app/services/standings.py::compute_series`).
- **The current year is the newest one not in the future** — not simply the highest ID. Otherwise
  creating "DSBL 2027" would immediately switch the public page to a year where no one is registered
  yet (`app/services/series.py`).
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
  (`BYC (BA)`, `BYCÜ`, `KYC (SH)`).
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
- **In conflicts, the race committee wins over imports.** Otherwise polling overwrites a
  protest decision just entered.

## Logged in or guest

Most requests carry a user, but the public site also serves guests.
Endpoints open to everyone use `app/auth.py::optional_user` — which returns
`User | None`. An **invalid or expired** token is treated as "not logged in"
not an error: otherwise the public site would be unusable for someone with an old session instead
of just treating them as a guest. Protected areas still use `current_user` and respond with 401.

## Permissions by area

| Area | Roles |
|---|---|
| Create clubs and enroll in Series | `admin`, `editor` |
| Create Series and set participants | `admin` |
| Create and maintain Events | `admin`, `editor`, `race_officer` |
| Pairing lists, accounts, roles | `admin` |
| Enter results | `admin`, `race_officer` |
| Assign user to club | `admin`, `club_manager` (own club only) |
| Register participants for Series/Event | `club_manager` (own club), `admin` |
| Create and maintain sailors | `admin`, `editor`, `club_manager` |
| Register Squad for Series | `admin`, `club_manager` (own club only) |
| Accept club members | `club_manager` (own club), `admin` |
| **Create** Event | additionally `club_manager` if own club hosts |

Defined as dependencies in `api/app/auth.py`; roles are checked fresh from the database on
**every** request so revocation takes effect immediately.

## Tests

Three levels, all three are desired:

- `api/tests/unit/` — Scoring logic, pairing quality, parsers.
- `api/tests/stories/` — **User story level**: one story per test, named for what someone wants
  to achieve ("As a visitor I see the league table").
Each story in `docs/userstories.md` lists the tests that cover it — and each story test names its
story ID in the docstring. New features are added to stories first, then tested.

- `e2e/` — Playwright against the running application, also organized by stories.
  Prerequisites: Backend on port 8000 **and** Vite on 5173 already running; the configuration
  deliberately does not start servers so a missing server is not a test failure.
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

  **One-time setup:** `sudo pnpm exec playwright install-deps chromium` (or
  `sudo apt install -y libnss3 libnspr4 libasound2t64`). Chromium will not start without these
  system libraries.

External APIs are never called live in tests; we test against recorded fixtures (`api/tests/fixtures/`).

## Language

**English is the working language everywhere** — code, identifiers, comments, docstrings, commit
messages, API responses, and UI are all English first. We maintain German as a full, real second
language using **i18n (internationalization)**, not as German-only source text or loanwords.

**Frontend:** React uses `react-i18next`. Locale files live in `web/src/i18n/locales/`:
- `en/*.json` — English source strings (one namespace per page: `common`, `start`, `events`,
  `standings`, `clubs`, `club`, `sailor`, `matchday`, `account`, `admin`, `dev`)
- `de/*.json` — German translations of the same namespaces

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
