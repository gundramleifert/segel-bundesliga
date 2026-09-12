# A server started in one sandboxed Bash call is unreachable from the next one

**Symptom** — `uvicorn` and `vite` started in background calls, both logged "ready", and
`curl http://127.0.0.1:8000` from a *later* call returned nothing (exit 7). Playwright then
failed with `connect ECONNREFUSED 127.0.0.1:5173` while both servers were demonstrably
running.

**Cause** — Each sandboxed Bash call gets its own network namespace. `localhost` works
*within* one call; a listener opened in another call lives in a namespace this one cannot
reach. The servers were fine — the caller was in a different network.

**Rule** — For anything that must be reachable across calls (dev servers for e2e), start it
with `dangerouslyDisableSandbox: true`, and run the client (Playwright, curl) the same way.
Two details that cost extra time: `$TMPDIR` is **unset** when the sandbox is disabled, so
use an absolute scratchpad path for log files or the redirect fails with
`/api.log: Permission denied`; and `git push` prints
`unable to get credential storage lock … Read-only file system` while still succeeding —
verify with `git ls-remote origin main` rather than believing the error.

**Evidence** — `scripts/dev-stack.sh` exists so this does not have to be re-derived.

**Seen** — 2026-09-11.
