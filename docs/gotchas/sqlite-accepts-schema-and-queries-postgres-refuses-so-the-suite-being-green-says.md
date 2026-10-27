# SQLite accepts schema and queries Postgres refuses, so the suite being green says nothing about Postgres

**Symptom** — the first run against Postgres (`deploy/compose/`) fails in the one initial
migration, although every test passes: `relation "uq_external_id_source" already exists`,
then `operator does not exist: boolean + boolean`; after that, `GET /api/clubs` is a 500
with `could not identify an equality operator for type json`.

**Cause** — four things SQLite lets through:
- **Constraint names** are unique per schema in Postgres, per table (and loosely) in
  SQLite. The naming convention `uq_%(table_name)s_%(column_0_name)s` names a constraint
  after its *first* column, so two unique constraints starting with the same column got
  the same name (`external_id`, `race_entry`).
- **Adding booleans** — `(a IS NOT NULL) + (b IS NOT NULL) <= 1` in a check constraint —
  is SQLite's; Postgres has no `boolean + boolean`.
- **`SELECT DISTINCT` over a row with a JSON column** (`Club.expense_policy`): Postgres'
  `json` has no equality.
- **Foreign keys are not enforced** — `app/db.py` never sets `PRAGMA foreign_keys=ON`.
  Deleting an account that a `waiver_confirmation.recorded_by_user_id` points at passes on
  SQLite and is a `ForeignKeyViolationError` on Postgres (`tests/accounts.py::forget`,
  8 waiver tests).

**Rule** — name a unique constraint by hand when a second one on the table starts with the
same column; count non-null columns with `CASE WHEN … THEN 1 ELSE 0 END` or compare
`(a IS NULL) <> (b IS NULL)`; select ids with `IN (subquery)` instead of `DISTINCT` over a
whole entity. Before trusting a model change on Postgres, run the suite against it once
(below).

**Evidence** — the suite against `postgres:17.6-alpine`, with `SBL_DATABASE_URL` and a
`NullPool` engine patched into `tests/conftest.py` for the run (asyncpg connections are
bound to one event loop, and every test gets its own): 925 passed, 8 failed, all the
foreign-key one above. `alembic check` against it: no differences.

**Seen** — 2026-10-27, branch `compose-setup`.
