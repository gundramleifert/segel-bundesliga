# Deutsche Segel-Liga

Website of the **Deutsche Segel-Liga e.V.**, together with the tools that support a matchday:
pairing lists, race control and result entry by the race committee, a live view for
spectators, and GPS tracking from participant phones.

The association runs several series — 1. Liga, 2. Liga, Junioren-Liga, DSL-Pokal — and each
is configured on its own (teams, boats, flights, scoring). The site is also a **service to
other clubs**: a club can organise and run its own events here, inside a series or standing
alone.

## What's here

**Public site**
- Series standings (per series and per matchday), with discards applied
- Event calendar and event pages: pairing list, results, who sails for each team
- Live view of a running event, with boats on the water from the phones' GPS
- Club pages and sailor pages (a sailor can switch their own profile page off)

**Running events**
- Create series and events; an event defines its own configuration (teams, boats, flights)
- Draft, publish, start, finish or call off an event; the first race freezes its setup
- Pairing lists from a precomputed catalog, printable per event
- Race control: start sequence, recalls, finishes and result entry from one screen; points
  are always derived from the raw results, never entered by hand
- Name the event's race officers, jury and helpers

**Clubs and sailors**
- A club's admin decides who is in the club; its manager registers squads for a series and
  names the crew for each matchday
- Liability waivers: adults confirm online, minors bring a guardian's signed form
- Personal documents and a saved bank account per person

**Money**
- Expense claims on an event or a club, decided by the manager or treasurer
- Approved claims paid in SEPA payment runs, with Excel exports

**Access** — sign in with Google, Microsoft, a one-time code by email, or a password. Accounts
are linked by verified email address, so every method leads to the same account.
Permissions are relation tuples (person · relation · object): `admin`, `editor`,
`manager`, `race_officer`, `jury`, `helper`, `treasurer` and `member`, each held on the
site, a club, a series or an event.

**Languages** — English and German throughout, UI and backend error messages alike.

`docs/userstories/` is the full feature list, each story with its status and the tests that
cover it; `docs/concepts.md` is the data model behind it (Series, Event, Team, Squad,
Scoring, Errors).

## Repo layout

| Path | Content |
|---|---|
| `api/` | FastAPI backend, SQLAlchemy 2.0 (async), Alembic |
| `web/` | React frontend (Vite, TypeScript, HeroUI, Tailwind) |
| `e2e/` | Playwright tests against the running application |
| `scripts/` | `check.sh` (every gate), `dev-stack.sh` (servers for e2e), `gen-api-client.sh` (the frontend's API client) |
| `docs/` | Concepts, user stories, gotchas, plans, deployment notes |
| `reference/` | Shallow clones of external repos kept for reference, not versioned |

Each reference repo carries its own `CLAUDE.md` with details: `reference/PairingList` (the
pairing generator), `reference/sailing-analytics` (SAP Sailing Analytics API docs),
`reference/segel-bundesliga` (a previous attempt).

## Getting started

The quickest way is **`tilt up`** at the repo root (`Tiltfile`): backend with dev login and
frontend in one dashboard, the API client regenerated when a route or schema changes, and
buttons for resetting the database and running the checks. Or by hand:

### Backend

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
cd api
export UV_CACHE_DIR="$TMPDIR/uv-cache"   # if ~/.cache is not writable
uv sync
uv run python -m app.seed_test_setup     # migrations + reference data + accounts, in one step
uv run uvicorn app.main:app --reload
```

The API runs on `http://localhost:8000`; the OpenAPI/Swagger UI is at
`http://localhost:8000/docs`. The database is SQLite (`api/sbl.db`) — no server to start.
`app.seed_test_setup --reset` drops all tables and migration state first, for a clean rebuild.

### Frontend

Requires Node.js and [pnpm](https://pnpm.io/).

```bash
cd web
pnpm install
pnpm dev
```

Opens on `http://localhost:5173` and talks to the backend on `:8000`.

The frontend's API client under `web/src/api/generated/` is **generated, never written**:
after changing a route or a schema, run `scripts/gen-api-client.sh`, then `pnpm typecheck`.

### Trying out roles

With `SBL_DEV_LOGIN=true` (see `api/.env.example`), `/api/dev` lists the seeded test accounts
and issues access tokens without verification, and a role switcher appears in the UI (bottom
right). This is separate from `debug` and is not meant for a reachable environment — the server
warns on startup while it is enabled.

## Testing

**`scripts/check.sh`** runs every gate that must be green before a commit — docs check, lint,
backend tests, frontend type check — in the order that fails fastest (`--fast` skips the
backend tests).

Three levels of tests:
- `api/tests/unit/` — scoring logic, pairing quality, parsers
- `api/tests/stories/` — one test per user story from `docs/userstories/`, named for what
  someone wants to achieve (`uv run pytest` in `api/`)
- `e2e/` — Playwright against the running application, organized by story

The end-to-end suite needs its servers, which it deliberately does not start itself:

```bash
scripts/dev-stack.sh --workers 4   # one backend + one built frontend per worker, throwaway databases
pnpm e2e                           # in another terminal, at the repo root
```

One-time setup: `sudo pnpm exec playwright install-deps chromium`.
`scripts/allure-report.sh` renders one report over both suites, grouped by story, and
`docs/traceability.md` lists every story with the tests that cover it.

In `web/`, `pnpm typecheck` is the real type check (`tsc -b`; `tsc --noEmit` checks nothing in
this project) and `pnpm lint` runs oxlint.

External APIs are never called live in tests; recorded fixtures live under `api/tests/fixtures/`.

## Contributing

Work is tracked as [GitHub issues](https://github.com/gundramleifert/segel-bundesliga/issues)
and reaches `main` only through a pull request: **issue → branch → PR → merge → staging →
stakeholder review → close**. `main` deploys to the staging instance
(`https://sbl-web.onrender.com`); an issue is done when its stakeholder accepts it there,
so a PR refers to its issue and never closes it.

```bash
gh issue view 42                                   # 1. read the issue
git switch main && git pull
gh issue develop 42 --name 42-short-slug --checkout   # 2. branch, linked to the issue
# ... commit ...
scripts/check.sh                                   # 3. everything must be green
git push -u origin HEAD
gh pr create --base main                           # 4. body starts with "Refs #42", not "Closes"
gh pr merge --squash --delete-branch               # 5. merge → staging redeploys
gh issue edit 42 --add-label in-stakeholder-review # 6. once it is live: label + comment
gh issue comment 42                                #    (where to look, what to try)
gh issue close 42 --comment "Accepted on staging"  # 7. accepted → close
```

Not accepted: the label comes off and the feedback is a new branch for the same issue.
`gh issue list --label in-stakeholder-review` shows what waits on stakeholders.
One issue per branch and per PR; anything else found along the way becomes a new issue.
`CLAUDE.md` ("From issue to merge") has the details.

## Documentation

| Doc | Content |
|---|---|
| `docs/concepts.md` | Terms and data model — start here |
| `docs/userstories/` | Features, by user story, one file per role, each story linked to its tests |
| `docs/traceability.md` | Every story with the tests that cover it (generated) |
| `docs/components.md` | The frontend's building blocks — read before writing a page |
| `docs/gotchas/` | Things that surprised someone — read the index before debugging anything odd |
| `docs/findings.md` | Research findings — external API formats, league format, open questions |
| `docs/PLAN_LIVE_IMPLEMENTATION.md` | Live data, tracking and race control — the agreed plan |
| `docs/deploy.md` | The staging deployment |
| `CLAUDE.md` | The detailed engineering reference — domain decisions, permissions, testing and i18n conventions, the issue workflow. Doubles as the instructions file for AI coding assistants working in this repo. |

## Deployment

The Render instance described in `docs/deploy.md` (`render.yaml`, `api/Dockerfile`) is
**staging**: it redeploys from `main`, and stakeholders review changes there. It is not
production — no backup, the SQLite database resets to the seeded data on every restart, and
dev login is on. Postgres remains the intended production database; the models avoid
Postgres-only types so that migration stays straightforward.

## Status and license

Active work in progress, not yet in production. No license has been chosen yet.
