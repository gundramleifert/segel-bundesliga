#!/usr/bin/env bash
# Regenerates web/src/api/schema.d.ts from the backend's OpenAPI document.
#
# Deliberately **without** a running server. `openapi-typescript <url>` is the usual recipe
# and it needs one on port 8000, which means remembering to start it, remembering that it
# has to be the *current* code, and — inside the agent sandbox — that a server started in
# one Bash call is unreachable from the next (docs/gotchas/the-bash-sandbox-has-a-network-
# namespace-per-call.md). FastAPI builds the document in-process, so asking the app object
# directly skips all three problems and can never describe a stale build.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
out="$root/web/src/api/schema.d.ts"
doc="$(mktemp -t openapi-XXXXXX.json)"
trap 'rm -f "$doc"' EXIT

(cd "$root/api" && UV_CACHE_DIR="${UV_CACHE_DIR:-${TMPDIR:-/tmp}/uv-cache}" \
  uv run python -c 'import json; from app.main import app; print(json.dumps(app.openapi()))') > "$doc"

(cd "$root/web" && pnpm exec openapi-typescript "$doc" -o "$out")

echo "Wrote $out — run 'pnpm typecheck' in web/ to see what the change broke."
