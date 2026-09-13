# Playwright's workerIndex keeps climbing past the worker count; parallelIndex is the bounded slot

**Symptom** — with `workers: 4` and four servers running on ports 5173–5176, thirty tests
failed with `connect ECONNREFUSED 127.0.0.1:5177`, then `5178`, then `5179` — one higher
each time, addressing servers that were never started. The first few tests passed.

**Cause** — the worker fixture computed its port from `workerInfo.workerIndex`.
`workerIndex` is not "which of the N slots am I": it counts **every worker the run has
ever started**, and Playwright discards a worker and starts a fresh one after a test
fails. So the index climbs for the rest of the run, and once it passes the number of
stacks every remaining test aims at a port nothing is listening on. The first failure
therefore causes all the later ones, which is why the run looked like a cascade with no
first cause. `parallelIndex` is the slot — `0 .. workers-1`, reused when a worker is
replaced.

**Rule** — anything indexed by "which parallel stack is mine" uses `parallelIndex`:
ports, database files, fixture directories. `workerIndex` is for telling two runs of the
same slot apart in a log, and almost nothing else. See `e2e/fixtures.ts`.

**Evidence** — the same suite went from 30 failed to 1 failed with `workerIndex` →
`parallelIndex` as the only change; the failing ports in the log were 5177…5190 against
four servers on 5173…5176.

**Seen** — 2026-09-13
