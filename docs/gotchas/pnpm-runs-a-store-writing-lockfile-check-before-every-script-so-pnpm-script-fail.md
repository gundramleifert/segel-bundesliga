# pnpm runs a store-writing lockfile check before every script, so `pnpm <script>` fails where the store is read-only

**Symptom** — `scripts/dev-stack.sh` reported `not ready — api:200 vite:000`. The backend
was up, Vite was not, and `$TMPDIR/sbl-dev-stack/vite.log` contained no Vite output at all
— only `[ERR_SQLITE_ERROR] unable to open database file` and a pnpm stack trace ending in
`runDepsStatusCheck`. The same failure came out of `pnpm typecheck` and `pnpm exec orval`,
which have nothing to do with each other.

**Cause** — before running any script, pnpm verifies that `node_modules` matches the
lockfile, and that check opens its store index (`~/.local/share/pnpm/store`, a SQLite
file) **for writing**. In the agent sandbox that path is not writable, so the check dies
and the script never starts. What misled me: the error surfaces in the *child's* log, so
every symptom names the child — Vite didn't start, orval didn't run, tsc didn't run — and
none of them names pnpm.

**Rule** — call the binary directly when a tool has to run somewhere the pnpm store may be
read-only: `./node_modules/.bin/vite`, `./node_modules/.bin/tsc -b`,
`./node_modules/.bin/orval`, `node_modules/.bin/playwright`. `scripts/dev-stack.sh` and
`scripts/gen-api-client.sh` already do, with the reason written where they do it. Installing
packages genuinely needs the store, and for that there is no way around unsandboxing the
call.

**Evidence** — `scripts/dev-stack.sh` reached `ready.` in the same sandbox immediately
after `pnpm dev --port 5173` was replaced by `./node_modules/.bin/vite --port 5173`, with
nothing else changed. pnpm 11.24.0.

**Seen** — 2026-09-13
