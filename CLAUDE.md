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
| `compose.dev.yml` | **Backing services for development** — Postgres, SeaweedFS (S3), Mailpit; the API and web stay on the host, the header says which `SBL_*` to export |
| `deploy/compose/` | **The whole site in Docker Compose** — Postgres, API, the SPA behind Caddy, SeaweedFS; started with `compose.sh`, secrets sops-encrypted in `secrets.sops.env` (recipients: `.sops.yaml`); `README.md` there |
| `deploy/sap-local/` | **SAP Sailing Analytics on one machine** — the live scoring SAP hosts for us, run locally to build the integration against; the Google Cloud project with the Maps key; `README.md` there |
| `docs/PLAN_SEEDING.md` | **What a fresh installation starts with** — the real 2022–2026 results, news, press and pictures, no examples; the site seed and why nothing invented is in it, sources and their rights, phases S-0…S-6, open questions |
| `docs/PLAN_MEDIA.md` | **Pictures** — the media library and the automatic layout (galleries, shapes, crops), the plan Story R-2 is written from |
| `docs/PLAN_LIVE_IMPLEMENTATION.md` | **Live data, tracking, race control** — the agreed plan, make/buy vs SAP Sailing Analytics, phases |
| `api/app/imports/` | **Imports** from SAP Sailing (past DSBL matchdays, results) and Manage2Sail (entries, notice-board documents) — `uv run python -m app.imports --help`, Story A-14 |
| `api/app/tracking/` | **Boats on the water** — geometry, polar, course, passings, ranking, the emulator; `settings.py` holds every tuned constant (`SBL_TRACKING_*`) |
| `docs/decisions.md` | **Every domain decision in full** — the reasons and history behind the one-liners below |
| `docs/testing.md` | **Tests in full** — e2e stacks, journeys, evidence mode, Allure, traceability; the development details |
| `docs/workflow.md` | **From issue to merge in full**, and the language rules in full |
| `reference/` | Shallow clones of external repos for reference, not versioned |

Each reference repo has its own `CLAUDE.md` with details:
`reference/PairingList` (user's pairing generator), `reference/sailing-analytics`
(SAP Sailing Analytics API docs), `reference/segel-bundesliga` (previous attempt).

## Development

```bash
docker compose -f compose.dev.yml up -d   # Postgres, SeaweedFS, Mailpit (or: tilt up)
cd api
export UV_CACHE_DIR="$TMPDIR/uv-cache"   # ~/.cache is locked
uv sync
uv run python -m app.seed_test_setup     # schema + reference data + accounts; --reset starts over
uv run uvicorn app.main:app --reload
uv run pytest -n auto                    # sandbox off: the tests need the Postgres server
scripts/check.sh                         # everything that must be green, before every commit
```

- **Postgres only**, everywhere (decided 2026-11-11). Tests make their own databases
  (`api/tests/conftest.py`, set at module level).
- **One initial migration**, regenerated when models change, until the first production
  deploy; then migrations chain. `tests/unit/test_migrations.py` fails on drift.
- **The frontend's API client is generated**: after any route or schema change run
  `scripts/gen-api-client.sh`, then `pnpm typecheck` in `web/` (`tsc --noEmit` checks
  nothing here). Nothing under `web/src/api/generated/` is edited; handler names become
  hook names; invalidate with generated keys or a path prefix; a closed set is an enum.
- **Test accounts**: `SBL_DEV_LOGIN=true` enables `/api/dev` and the role switcher —
  never in production or on Compose staging. The seeded cast (ASVW's `board@`, `teams@`,
  `treasurer@`; `serie@`, `orga@`, `regatta@`, …) and the practice season tests build
  (`season` fixtures, `app/practice.py`) are in `docs/decisions.md` § Testing different
  roles. The seed holds nothing invented. Test addresses use `example.com`.
- More: `docs/testing.md` (both suites, e2e stacks, journeys, Allure).

## Domain decisions

One line each; the reasons are in `docs/decisions.md`. **Where a line names a check, the
check is the rule** — change the code, not the list.

**Competition**
- The site is several Series (1./2. Liga, Junioren, Pokal), and a service to other clubs:
  never brand it "Segel-Bundesliga"; an Event need not belong to a Series.
- Series instead of League + Season; a League links a series' years (`/1-liga/2026/act-3`).
- `Team` is the enrollment — `event_id` empty: the Series; set: the Event. A club enters
  up to `teams_per_club` teams per event, registered once per series.
- The Event defines the configuration (`team_count`, `boat_count`, `flight_count`); no
  magic constants. Scoring rules belong to the Series (`Series.scoring`).
- **Points are computed, never stored** (`compute_event`/`compute_series`;
  `test_rules.py::test_no_point_or_standing_is_stored`). Ties: places sailed, then the
  last race; a tie nothing breaks is shared; series ties by the acts in sailing order.
  Missing an event costs participants + 1.
- Four states of an event, not one machine (`event_readiness.py`): saving never requires
  validity, publication is orthogonal to status, validity is computed, **the first race
  freezes the configuration** — never results. "Has racing started?" has one answer,
  `event_readiness.racing_started`; status changes only through `event_state.py`
  (`test_rules.py`); changing who sails before the start clears the draw
  (`tests/stories/test_the_field.py`).
- Closing is a declaration (`finish`, `cancel` from any state, `reopen`); nothing freezes.
- Races one at a time, transitions in `race_state.py`; recall/abandon clear entries.
- Pairing lists come from the Java tool's catalog (`app/pairing/schedules/`), never
  computed here; boats and their colours belong to the Event; the PDF is drawn in Python
  with `Event.print_settings`.
- Live updates are SSE version tokens, **published after the commit** (`app/live.py`).
- Tracking: the tracker belongs to the boat; one course family; legs, passings and rank
  are derived, never stored (`default_pipeline()`).

**Outside systems**
- External systems are matched via `ExternalId`, never by name; the first bridge is the
  club code (at M2S code + name).
- SAP Sailing: configuration flows to SAP (VA-15, refused once frozen), results flow back
  only through `app/imports/sap_results.py::apply_results`, which creates nothing; the
  leaderboard name is fixed at the first send; SAP is credited wherever its results show
  (`SapAttribution`); its tests run against the local SAP (`deploy/sap-local/`). The race
  committee wins over imports; an event scored on SAP refuses result entry.

**People and permissions**
- **Permissions are relation tuples; `MODEL` in `app/models/auth.py` is the truth**, asked
  only through `app/authz.py` and written only through `app/services/grants.py` (ruff
  TID251). Never gate on a summary role (`User.roles`). An event's tools follow
  `GET /api/events/{id}/access`.
- **Who may call what is tested**: every open route has its reason
  (`tests/architecture/test_access.py`); covered routes have a who-may row and everyone
  else is refused (`tests/architecture/test_authorization.py`).
- A host club's `manager` (its team manager) organizes **none** of its events; its admin
  does (review 4.1). A club's treasurer is one of its members (review 4.3).
- A member and a sailor are one `Person`, with an account always, and **one address — the
  account's** (`tests/stories/test_one_address.py`). An active `ClubMembership` is
  "member" and "sails for"; only the membership writes the `member` tuple. Who is in a
  club is its admin's, who sails its manager's. A club keeps one admin.
- A club works with its people only after accepting the DPA, asked of the acting club
  (`dpa.ensure_for_person`).
- Participation is public, membership is not; a profile page can be switched off, a name
  in a result never.
- The waiver is one statement per competition; age picks the path; status is computed.
- "Mine" has one answer (`GET /api/me/contexts`); my space is sections declared per
  relation (`web/src/lib/workspace.ts`).
- A list is narrowed on the server (`app/filters.py`), never in the browser.

**Money and files**
- A claim is on an event or a club; deciders are checked on the tuple, never the claimant.
- **Decided money is frozen and a claim is paid once** (partial unique index; approved
  total, payment amount and SEPA file stored). Money goes to the bank as a SEPA file.
  Formats come from libraries (`sepaxml`, `schwifty`, `openpyxl`, `segno`).
- Every stored file goes through `app/storage.py`; served only through the endpoint that
  checks who asks. An upload's type is its content (`uploads.sniffed`). Pictures are
  library entries (`app/services/media.py`); originals never served.
- Rich text is cleaned to an allowlist on every write (`app/services/rich_text.py`).
- Secrets are sops-encrypted for SSH keys (`scripts/check-sops.py`).

**Guests**: public endpoints use `optional_user`; an invalid token is a guest, not an error.
Public endpoints show published data only and answer 404 for a draft.

## Permissions by area

| Area | Roles |
|---|---|
| Create clubs and enroll in Series | `admin` |
| Create Series | `admin` |
| Set a Series' participants, dates, publication | `admin`; the series' `manager` |
| Create and maintain Events | `admin`, site `race_officer`; the `manager` of the event or its series; the host club's `admin` — never its `manager`, the team manager (review 4.1) |
| Pairing lists, accounts | `admin` |
| See, write and delete tuples on an object | its `admin` — site admin everywhere, a series' admin on its events, the host club's on its events; a club's admin on the club, its treasurer only among its members |
| Enter results, run races, trackers | `race_officer` of the event — held on it, its series or the site |
| Add a person to a club, invite, accept a request, crest | `admin`; the club's `admin` (own club only); a person already in another club is invited and accepts, or asks and the club's admin accepts (V-15); one whose account cannot sign in yet only the site's `admin` adds |
| Register participants for Series/Event, squads, lineups | the club's `manager` or `admin` (own club), site `admin` |
| Create people (sailors) — a member of the club at once | `admin`; the club's `admin` for their own club — never its `manager` |
| Change people (sailors) | `admin`; a club's `manager` (or `admin`) for its active members, or people in no club; an address once set: `admin` only |
| Put a person in a squad | the `manager` of a club they are an active member of (`manager from club`); site `admin` (anyone, who then is a member) |
| Accept an invitation, ask to join, leave | the person (their own account) |
| Link a parent to a person as guardian | the manager or admin of a club the person is a member of; site `admin` |
| Confirm a waiver for a person | the person; `admin`; the manager of a club they are a member of; their linked `guardian` while they are a minor |
| Write news and press releases, keep pictures | `editor` of the site (all); of a series or an event (that regatta's) |
| **Create** Event | additionally the `manager` of the series (its acts, naming any host) or the `admin` of the host club (outside a series only) |
| File an expense claim | `race_officer`/`jury`/`manager`/`helper` held directly on the event (or the first three on its series); `member` of the club |
| Decide and pay a claim | the event's direct `manager`, `treasurer` of event or club (and their admins); never the claimant |
| See a person's documents | the person; `manager` of an event they work at directly or of a club they are a member of |
| Bank account | its owner only |
| Club's bank account, payment runs, SEPA and Excel exports | the club's `treasurer` (and its admin) — not its `manager` |

Defined as dependencies in `api/app/auth.py`; roles are checked fresh from the database on
**every** request so revocation takes effect immediately.

## Tests

- `api/tests/unit/` — logic; `api/tests/stories/` — **one story per test, its ID in the
  docstring**; `api/tests/architecture/` — the rules as checks (below); `web/tests/` —
  Vitest; `e2e/` — Playwright against `scripts/dev-stack.sh --workers 4`, one stack per
  worker, `data-testid` over text, every group a `describeStory("ID: …")`.
- Journeys (`docs/journeys/`) walk several stories in order; step IDs `J-n.k` are never
  renumbered. `scripts/check-docs.py` holds stories, tests, journeys and gotchas together.
- External APIs only through recorded fixtures — except SAP, against the local SAP.
- Details: `docs/testing.md`.

## From issue to merge

Committing directly to `main` is allowed. For an issue: `/issue` (branch, PR with
`Refs #N` — never `Closes`, merge only on the user's word, hand over to the stakeholder;
an issue is done when they accept it on staging). Details: `docs/workflow.md`.

## Working here

- **Before you debug, read `docs/gotchas/INDEX.md`.** When you were confidently wrong or
  lost more than ~15 minutes, write a note (`scripts/check-docs.py --new "…"`), with the
  one line that misled you under **Cause** — before you report the work finished.
- **A rule is a check, not a sentence.** ruff (`TID251`) where an import says it;
  `api/tests/architecture/test_rules.py` for the rest — one writer per status, one creator
  per `Team`, no router importing a router, **no router gaining a query**, no stored point
  or standing, every `Problem` code worded in both languages, this file's permission table
  against `MODEL`; **every route open without sign-in listed with its reason**
  (`test_access.py`); **who may call a covered route on one club, and everyone else
  refused** (`test_authorization.py`). Each keeps its known violations in a list tied to
  `docs/REVIEW_2026-11.md`, and the list is a **ratchet**: a new violation fails, so does
  a fixed one still listed. **Never add to a list to get green; fix the code.** A known
  defect is a `xfail(strict=True)` test (`test_known_defects.py`). A new rule comes with
  its check, and a check is believed only after it was seen failing on purpose.
- **Do something twice, make it a function** — `scripts/check.sh`, `dev-stack.sh`,
  `e2e/layout.ts::expectNoSidewaysScroll`, `web/src/components/` (read
  `docs/components.md` before writing a page; a component never imports from `pages/`),
  `web/scripts/check-colours.mjs` (names, never shades), `scripts/check-docs.py`.
- **Docs in this order**: the story (`docs/userstories/`), then the test (watch it fail),
  then the code, then the status marker and `Tests:` line; a lasting rule gets one line
  here and its reasons in `docs/decisions.md`; a surprise goes in `docs/gotchas/`. If a
  story recorded the wrong cause, correct it.

## Language

**English everywhere** — code, docs, commits, API, UI source; German is a full i18n
translation (`web/src/i18n/locales/{en,de}/`, ICU MessageFormat, `pnpm check:i18n`).
The backend words nothing at a call site: errors are RFC 9457 Problems with a code
(`raise Problem(status, code, title)`, never `HTTPException`), worded by the frontend's
`errors` namespace; mails are Jinja2 templates per language (German by default); the few
sentences a route answers are TOML catalogs (`app/i18n.py`). Domain terms: Wettfahrt →
Race, Spieltag → Matchday, Wettfahrtleitung → Race committee, Serie → Series, Verein →
Club, Segler → Sailor, Mannschaft → Team, Kader → Squad, Aufstellung → Lineup, Liga →
League, Boot → Boat, Ausrichter → Host club, Revier → Venue. Details: `docs/workflow.md`.
