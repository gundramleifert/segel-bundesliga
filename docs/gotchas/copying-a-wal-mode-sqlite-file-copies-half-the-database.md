# Copying a WAL-mode SQLite file copies half the database

**Symptom** — After enabling WAL (`app/db.py`, Story L-1), a four-worker e2e run failed
fifteen unrelated tests: `dev login failed`, elements not found, timeouts — but only on
workers 1 to 3, never on worker 0. Their API logs held nineteen
`sqlite3.DatabaseError: database disk image is malformed`, and the worker with the
emulation running was fine.

**Cause** — In WAL mode the recent writes live in `e2e.db-wal` (4 MB here — the whole seed)
until a checkpoint folds them into `e2e.db`. `scripts/dev-stack.sh` seeds once and copies
`e2e.db` to `e2e-N.db`; the copy has the main file's *old* pages, and next to it lay
`e2e-N.db-wal` from the previous run, which SQLite then applied to the wrong file. What
misled: the failures pointed at sign-in and at pages, the emulation was the newest thing and
the obvious suspect, and worker 0 — the only one using the *original* file — passed
everything.

**Rule** — Never copy a SQLite database by copying one file while WAL is on. Checkpoint
first (`PRAGMA wal_checkpoint(TRUNCATE)`) and delete the target's `-wal`/`-shm` before the
copy — `dev-stack.sh` does both now — or use the backup API. The same applies to the Docker
image: `seed_test_setup` at build time must leave no `-wal` behind, or a later layer copies
a torn database.

**Evidence** — `ls api/e2e*.db*` after a run: `e2e.db` 1.1 MB, `e2e.db-wal` 4.1 MB. The
error text above in `$TMPDIR/sbl-dev-stack/api-1.log` and `api-3.log`, none in `api-0.log`.

**Seen** — 2026-09-15
