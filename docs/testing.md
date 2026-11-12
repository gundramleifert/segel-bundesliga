# Tests — the full text

Moved out of `CLAUDE.md` on 2026-11-12 (review 8.1), word for word.

### Tests

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
  over N Postgres databases and N web servers; `e2e/fixtures.ts` points each worker at its own
  via `parallelIndex` (**not** `workerIndex`, which keeps climbing as workers are
  replaced) — `lifecycle.spec.ts` writes, so workers must not share a database. It runs
  against a **built** bundle rather than the dev server: the suite is dominated by page
  loads, and a build costs two seconds.
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
  showed. Off by default — it about doubles the run and writes ~450 MB. Being slower, it
  also catches render races a fast run misses (docs/gotchas).

  **One report over both suites: Allure** — `scripts/allure-report.sh` (`--no-e2e` for the
  backend alone) runs pytest with `--alluredir`, the browser suite in evidence mode, and
  renders `allure-report/` grouped by **story** (`allurerc.mjs`). No test carries an
  Allure decorator: `api/tests/conftest.py` reads the story IDs from the docstrings,
  `e2e/fixtures.ts` from the `describeStory` titles, both take titles, roles and phases
  from `docs/stories.json`. A journey's `step()`s are Allure steps; videos, screenshots
  and traces are attached.

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
The one exception is **SAP Sailing as the live scoring** (decided 2026-11-02): its tests run
against the local SAP (`deploy/sap-local/`, `api/tests/sap_double.py`) — the real software,
never SAP's hosted server, never an imitation — and are skipped when it is not running.


### Development

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
buttons for `reset-db` and `check`. It starts `compose.dev.yml` (Postgres, SeaweedFS,
Mailpit — Docker required, `scripts/install-docker-wsl.sh`) and points the API at it; the
e2e stacks stay `scripts/dev-stack.sh`'s job.

`app.seed_test_setup` sets up a **fresh installation** completely: migrations,
reference data (`app.seed`), accounts (`app.seed_users`). Repeatable; `--reset` drops all
tables and migration state first. Individual steps still work.

**Migrations:** There is **one** initial migration. As long as nothing is in production, it is
regenerated when models change rather than creating a chain —
`rm alembic/versions/*.py`, then `alembic revision --autogenerate` against an empty
database, then `seed_test_setup --reset`. **The first production deploy with real data
ends this** (decided 2026-11-11): the migration it ran is the baseline, never regenerated
again, and every model change after it is a new migration on top, with its data carried
over — tried on a copy of production first. `tests/unit/test_migrations.py` fails whenever
the models and the migrations differ, so a forgotten migration is red in CI.

**Database: Postgres, and nothing else** (decided 2026-11-11) — production, development
and both test suites. No SQLite path, no second dialect to stay compatible with: Postgres
types and functions are fair game. Start it with `docker compose -f compose.dev.yml up -d
db` (or `tilt up`); `app.config`'s default URL is that server, and a `postgres://…` URL a
host hands out gets the asyncpg driver there. The **test suite** makes fresh databases of
its own on it — `sbl_test_<worker>`, plus `empty_database` for a test that builds its own
small world — set in `api/tests/conftest.py` **at module level**, not in a fixture,
because `app.config` builds its settings on import; `SBL_TEST_DATABASE_URL` names another
server. The e2e stacks use `sbl_e2e_<i>` (`scripts/dev-stack.sh`). A command run in the
agent sandbox cannot reach the server (its own network, no docker group): run tests with
the sandbox off.

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

