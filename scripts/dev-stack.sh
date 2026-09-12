#!/usr/bin/env bash
# Brings up everything the Playwright suite needs, against a throwaway database.
#
# The e2e specs deliberately do not start servers (see playwright.config.ts), so this is
# the step before `pnpm exec playwright test`. It exists because getting it right by hand
# takes four commands and two environment variables that are easy to forget — and because
# `e2e/lifecycle.spec.ts` *writes* (clubs, series, events), so pointing it at `api/sbl.db`
# would quietly fill your development database with "E2E Draft Cup 1789…" rows.
#
#   scripts/dev-stack.sh          # reseed the throwaway DB, then run both servers
#   scripts/dev-stack.sh --keep   # leave the database as it is
#
# Ctrl-C stops both. Logs go to the paths printed on startup.
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$PWD"
LOGS="${TMPDIR:-/tmp}/sbl-dev-stack"
mkdir -p "$LOGS"

# A database of its own, so a run that writes cannot touch `api/sbl.db`. Both are
# gitignored (`*.db`).
export SBL_DATABASE_URL="sqlite+aiosqlite:///./e2e.db"
# `e2e/lifecycle.spec.ts` signs in through /api/dev/login, which only exists with this on.
# It issues tokens without verification — never set it anywhere reachable.
export SBL_DEV_LOGIN=true
export UV_CACHE_DIR="${UV_CACHE_DIR:-${TMPDIR:-/tmp}/uv-cache}"

if [[ "${1:-}" != "--keep" ]]; then
  echo "seeding api/e2e.db (fresh) …"
  (cd "$ROOT/api" && uv run python -m app.seed_test_setup --reset > "$LOGS/seed.log" 2>&1) \
    || { echo "seeding failed — see $LOGS/seed.log"; exit 1; }
fi

echo "api  → $LOGS/api.log"
echo "vite → $LOGS/vite.log"

(cd "$ROOT/api" && uv run uvicorn app.main:app --port 8000 --host 127.0.0.1 > "$LOGS/api.log" 2>&1) &
api_pid=$!
(cd "$ROOT/web" && pnpm dev --port 5173 --host 127.0.0.1 > "$LOGS/vite.log" 2>&1) &
vite_pid=$!

trap 'kill $api_pid $vite_pid 2>/dev/null || true' EXIT INT TERM

# Wait for both to actually answer. A server that is "starting" is not a server, and a
# suite launched against one fails in ways that look like application bugs.
for _ in $(seq 1 40); do
  api=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/series || true)
  vite=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5173/ || true)
  [[ "$api" == "200" && "$vite" == "200" ]] && break
  sleep 1
done

if [[ "${api:-}" != "200" || "${vite:-}" != "200" ]]; then
  echo "not ready — api:$api vite:$vite (see the logs above)"
  exit 1
fi

echo
echo "ready. now run:  pnpm exec playwright test"
echo "Ctrl-C stops both."
wait
