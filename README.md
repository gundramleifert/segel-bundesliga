# Segel-Bundesliga

Official website of the German Segel-Bundesliga (sailing league), together with the tools that
support a matchday: pairing lists, race result entry by the race committee, a live view for
spectators, and GPS tracking of participant phones.

## What's here

**Public site**
- League standings (season and per matchday), with discards applied
- Event calendar, event/matchday detail pages
- Club pages (squad, participation) and sailor pages
- Pairing lists (boat/team/flight assignment for a matchday)

**Administration**
- Create and manage Series, Events, Clubs, Sailors
- Register clubs for a Series / an Event; manage a club's Squad
- Assign roles (`admin`, `editor`, `race_officer`, `club_manager`)
- Race result entry for the race committee; results are recalculated into standings, never
  entered by hand
- Waiver confirmation flow with RFC 9457 problem-details error responses

**Authentication** — passwordless: Google or Microsoft sign-in (OIDC token verification), or a
one-time code by email. Accounts are linked by verified email address so all paths lead to the
same account; no passwords are stored.

**Internationalization** — English and German throughout (UI and backend error messages), not
German-only source text.

See `docs/userstories/` for the full, tested feature list, and `docs/concepts.md` for the
data model behind it (Series, Event, Team, Squad, Scoring, Errors).

## Repo layout

| Path | Content |
|---|---|
| `api/` | FastAPI backend, SQLAlchemy 2.0 (async), Alembic |
| `web/` | React frontend (Vite, TypeScript, HeroUI, Tailwind) |
| `e2e/` | Playwright tests against the running application |
| `docs/` | Concepts, user stories, research findings, deployment notes |
| `reference/` | Shallow clones of external repos kept for reference, not versioned |

Each reference repo carries its own `CLAUDE.md` with details: `reference/PairingList` (the
pairing generator), `reference/sailing-analytics` (SAP Sailing Analytics API docs),
`reference/segel-bundesliga` (a previous attempt).

## Getting started

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

### Trying out roles

With `SBL_DEV_LOGIN=true` (see `api/.env.example`), `/api/dev` lists the seeded test accounts
and issues access tokens without verification, and a role switcher appears in the UI (bottom
right). This is separate from `debug` and is not meant for a reachable environment — the server
warns on startup while it is enabled.

## Testing

**Backend** (`api/`):

```bash
uv run pytest
```

Organized in three levels:
- `tests/unit/` — scoring logic, pairing quality, parsers
- `tests/stories/` — one test per user story from `docs/userstories/`, named for what someone
  wants to achieve

**Frontend** (`web/`):

```bash
pnpm typecheck   # tsc -b — checks the actual build via project references
pnpm lint        # oxlint
```

**End-to-end** (`e2e/`), Playwright, organized by story: requires the backend (`:8000`) and
Vite (`:5173`) already running — the test config deliberately does not start them itself, so a
missing server shows up as a failure rather than being masked. One-time setup:
`sudo pnpm exec playwright install-deps chromium`.

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
| `docs/userstories/` | Features, by user story, one file per role, each story linked to its test |
| `docs/findings.md` | Research findings — external API formats, league format, open questions |
| `docs/deploy.md` | Free test-instance deployment |
| `CLAUDE.md` | The detailed engineering reference for this repo — layout, dev commands, domain decisions, auth model, testing and i18n/error-handling conventions. Doubles as the instructions file for AI coding assistants working in this repo. |

## Deployment

`docs/deploy.md` and `render.yaml` / `api/Dockerfile` describe a free test deployment (Render,
or Fly.io + Cloudflare Pages) — not production: no backup, the SQLite database resets on
restart, and dev-login is on. Postgres remains the intended production database; the models
avoid Postgres-only types so that migration stays straightforward.

## Status and license

Active work in progress; a test project, not yet in production. No license has been chosen yet.
