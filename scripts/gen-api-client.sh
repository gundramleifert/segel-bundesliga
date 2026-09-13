#!/usr/bin/env bash
# Regenerates the frontend's API client from the backend's OpenAPI document:
#
#   web/openapi.json              the document itself (gitignored, a build input)
#   web/src/api/generated/sbl.ts  every endpoint plus its React Query hooks
#   web/src/api/generated/model/  the request and response types
#
# Nothing under `generated/` may be edited by hand — the next run overwrites it silently.
# Run this whenever an endpoint or a schema changes, then `pnpm typecheck` in web/ to see
# what the change broke. That failing build is the point of generating at all.
#
# Deliberately **without** a running server. `openapi-typescript <url>` and `orval` both
# take a URL, and that needs one on port 8000, which means remembering to start it,
# remembering that it has to be the *current* code, and — inside the agent sandbox — that
# a server started in one Bash call is unreachable from the next (docs/gotchas/the-bash-
# sandbox-has-a-network-namespace-per-call.md). FastAPI builds the document in-process, so
# asking the app object directly skips all three and can never describe a stale build.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# SBL_DEV_LOGIN decides whether `/api/dev` is mounted at all (app/main.py), so without it
# the document would simply lack those routes and the generated client would lack the
# calls the role switcher makes — a frontend that stops compiling depending on how the
# backend happened to be configured when someone last ran this.
(cd "$root/api" && SBL_DEV_LOGIN=true \
  UV_CACHE_DIR="${UV_CACHE_DIR:-${TMPDIR:-/tmp}/uv-cache}" \
  uv run python -c 'import json; from app.main import app; print(json.dumps(app.openapi(), indent=2))'
) > "$root/web/openapi.json"

# Cleared first, because orval only ever *writes*: a renamed or deleted operation leaves
# its old file behind, `model/index.ts` keeps re-exporting it, and it compiles — so the
# one thing generation is supposed to prevent, a type that no longer matches the backend,
# creeps back in through the files nobody looked at.
rm -rf "$root/web/src/api/generated"

# `node_modules/.bin/orval`, not `pnpm exec orval`: pnpm checks that the lockfile and the
# installed tree agree before running anything, and that check writes to the pnpm store —
# which fails outright wherever the store is not writable
# (docs/gotchas/pnpm-runs-a-store-writing-lockfile-check-before-every-script-so-pnpm-script-fail.md).
(cd "$root/web" && ./node_modules/.bin/orval)

echo
echo "Wrote web/openapi.json and web/src/api/generated/."
echo "Now run 'pnpm typecheck' in web/ to see what the change broke."
