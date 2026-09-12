# `require_ready` answers with a *different* code depending on how many things are missing

**Symptom** — Creating an event with only a title showed a red "the draw failed" error in
the UI, every time, for the most normal case there is. The frontend was checking for the
code it had seen during development.

**Cause** — `require_ready` (`api/app/services/event_readiness.py`) returns the **single
reason's own code** when exactly one applies — e.g. `pairing-team-count-mismatch` — but
`event-not-ready` (409, carrying `reasons[]`) as soon as two or more do. An event saved with
a title alone is always missing both its clubs and its date, so it takes the second path,
and a frontend that only knew the first showed an error for the expected case.

**Rule** — Any client handling a readiness refusal must accept **both** shapes: the
single-reason code *and* `event-not-ready` with `reasons[]`. Render the reasons; never
branch on one code alone.

**Evidence** — `web/src/pages/AdminEvents.tsx::isSetupIncompleteNotice`;
`api/tests/stories/test_event_lifecycle.py::TestStarting` asserts both shapes.

**Seen** — 2026-09-09, commit `0893578`.
