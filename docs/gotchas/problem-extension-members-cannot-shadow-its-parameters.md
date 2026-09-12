# An RFC 9457 extension member may not be named `status`, `title`, `code` or `type`

**Symptom** — `TypeError: Problem.__init__() got multiple values for argument 'status'` at
runtime, from a line that looked entirely reasonable:
`Problem(409, "event-not-started", "…", event_id=event.id, status=event.status)`.

**Cause** — `Problem(status, code, title, **extra)` takes `status` as its own positional
parameter (`api/app/problems.py`). An extension member with the same name collides with it.
The failure is only visible when that error path actually executes — so a typed refusal can
ship broken while every green-path test passes.

**Rule** — Prefix an extension member that would otherwise shadow a Problem parameter:
`event_status`, not `status`. The reserved names are `status`, `code`, `title`, `type`. Any
new typed refusal needs a test that *triggers* it, not only one that avoids it.

**Evidence** — `api/app/routers/events.py::finish_event` / `reopen_event`;
`api/tests/stories/test_event_closing.py` asserts `event_status` in the problem body.

**Seen** — 2026-09-12.
