#!/usr/bin/env bash
# Brings up everything the Playwright suite needs, against throwaway databases.
#
# The e2e specs deliberately do not start servers (see playwright.config.ts), so this is
# the step before `pnpm exec playwright test`. It exists because getting it right by hand
# takes several commands and a few environment variables that are easy to forget — and
# because `e2e/lifecycle.spec.ts` *writes* (clubs, series, events), so pointing it at
# `api/sbl.db` would quietly fill your development database with "E2E Draft Cup 1789…".
#
#   scripts/dev-stack.sh                # one stack, built bundle — what the suite wants
#   scripts/dev-stack.sh --workers 4    # four isolated stacks, for a parallel run
#   scripts/dev-stack.sh --dev          # Vite dev server instead, for editing by hand
#   scripts/dev-stack.sh --keep         # leave the databases as they are
#
# **Why a built bundle by default.** The suite is dominated by page loads, and an unbundled
# dev server answers one with hundreds of module requests. Building takes about two
# seconds and cuts the suite's wall-clock roughly in half. `--dev` is for when you want
# hot reload, not for running the tests.
#
# **Why several stacks.** Every spec talks to one database and `lifecycle.spec.ts` writes
# to it, so a parallel run against a single stack has tests reading lists another test is
# changing. One stack per Playwright worker removes the shared data rather than trying to
# order the writes; `e2e/fixtures.ts` points each worker at its own.
#
# Ctrl-C stops everything. Logs go to the paths printed on startup.
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$PWD"
LOGS="${TMPDIR:-/tmp}/sbl-dev-stack"
mkdir -p "$LOGS"

WORKERS=1
RESEED=1
MODE=built
while [[ $# -gt 0 ]]; do
  case "$1" in
    --workers) WORKERS="$2"; shift 2 ;;
    --keep) RESEED=0; shift ;;
    --dev) MODE=dev; shift ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

# `e2e/lifecycle.spec.ts` signs in through /api/dev/login, which only exists with this on.
# It issues tokens without verification — never set it anywhere reachable.
export SBL_DEV_LOGIN=true
# A signing secret, so the stack is self-contained: signing in needs one, and relying on
# `api/.env` means the suite fails with "No signing secret is configured" on any checkout
# that has not got one yet. This value is deliberately not a secret and is only ever used
# against the throwaway databases below — next to SBL_DEV_LOGIN, which hands out tokens
# without verification at all, it is not the weak link. Set SBL_JWT_SECRET to override.
export SBL_JWT_SECRET="${SBL_JWT_SECRET:-dev-stack-throwaway-not-a-secret}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-${TMPDIR:-/tmp}/uv-cache}"

if [[ "$RESEED" == 1 ]]; then
  echo "seeding api/e2e.db (fresh) …"
  (cd "$ROOT/api" && SBL_DATABASE_URL="sqlite+aiosqlite:///./e2e.db" \
     uv run python -m app.seed_test_setup --reset > "$LOGS/seed.log" 2>&1) \
    || { echo "seeding failed — see $LOGS/seed.log"; exit 1; }
  # Seeded once and copied, rather than seeded N times: the seed takes about ten seconds
  # and produces the same rows every time, so copying the file is the same result in
  # milliseconds.
  #
  # The database runs in WAL mode (app/db.py, Story L-1), so the freshly seeded rows may
  # still sit in `e2e.db-wal` rather than in `e2e.db` — a copy of the main file alone is a
  # database with the schema of an earlier checkpoint and none of the seed, and the workers
  # that got one failed every sign-in with a 500 while worker 0 was fine
  # (docs/gotchas). Checkpoint first, and clear a stale side file of the target.
  (cd "$ROOT/api" && uv run python -c "import sqlite3; c = sqlite3.connect('e2e.db'); c.execute('PRAGMA wal_checkpoint(TRUNCATE)'); c.close()")
  for ((i = 1; i < WORKERS; i++)); do
    rm -f "$ROOT/api/e2e-$i.db-wal" "$ROOT/api/e2e-$i.db-shm"
    cp "$ROOT/api/e2e.db" "$ROOT/api/e2e-$i.db"
  done
fi

if [[ "$MODE" == built ]]; then
  echo "building web …"
  # `node_modules/.bin/…`, not `pnpm …`: pnpm checks the lockfile against the installed
  # tree before running any script, and that check writes to the pnpm store — which fails
  # outright wherever the store is not writable (docs/gotchas/pnpm-runs-a-store-writing-
  # lockfile-check-before-every-script-so-pnpm-script-fail.md).
  (cd "$ROOT/web" && ./node_modules/.bin/vite build > "$LOGS/build.log" 2>&1) \
    || { echo "build failed — see $LOGS/build.log"; exit 1; }
fi

pids=()
for ((i = 0; i < WORKERS; i++)); do
  api_port=$((8000 + i))
  web_port=$((5173 + i))
  db=$([[ $i == 0 ]] && echo "e2e.db" || echo "e2e-$i.db")

  (cd "$ROOT/api" && SBL_DATABASE_URL="sqlite+aiosqlite:///./$db" \
     uv run uvicorn app.main:app --port "$api_port" --host 127.0.0.1 \
     > "$LOGS/api-$i.log" 2>&1) &
  pids+=($!)

  if [[ "$MODE" == built ]]; then
    (cd "$ROOT/web" && SBL_API_PORT="$api_port" \
       ./node_modules/.bin/vite preview --port "$web_port" --host 127.0.0.1 \
       > "$LOGS/web-$i.log" 2>&1) &
  else
    (cd "$ROOT/web" && SBL_API_PORT="$api_port" \
       ./node_modules/.bin/vite --port "$web_port" --host 127.0.0.1 \
       > "$LOGS/web-$i.log" 2>&1) &
  fi
  pids+=($!)
  echo "stack $i → api :$api_port ($db), web :$web_port — $LOGS/api-$i.log, $LOGS/web-$i.log"
done

trap 'kill "${pids[@]}" 2>/dev/null || true' EXIT INT TERM

# Wait for all of them to actually answer. A server that is "starting" is not a server,
# and a suite launched against one fails in ways that look like application bugs.
ready=0
for _ in $(seq 1 60); do
  ready=1
  for ((i = 0; i < WORKERS; i++)); do
    a=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$((8000 + i))/api/series" || true)
    v=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$((5173 + i))/" || true)
    [[ "$a" == "200" && "$v" == "200" ]] || { ready=0; break; }
  done
  [[ "$ready" == 1 ]] && break
  sleep 1
done

if [[ "$ready" != 1 ]]; then
  echo "not ready — stack $i answered api:$a web:$v (see the logs above)"
  exit 1
fi

echo
echo "ready. now run:  node_modules/.bin/playwright test"
echo "Ctrl-C stops everything."
wait
