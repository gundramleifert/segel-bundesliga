# A public endpoint answers 404 for a draft — including in tests you just set up

**Symptom** — A test created a series, registered clubs, created an event, and then got
`404 Series 5 not found` from `GET /api/series/{id}/table`. The series demonstrably existed.

**Cause** — Publication is orthogonal to everything else (Story VA-8), and public endpoints
serve **published** data only. They answer **404 rather than 403** on purpose: a draft's
existence is itself not public. Anything created through the admin API starts unpublished,
so a test that sets something up and then reads it back through a public route has to
publish it first.

**Rule** — Reading back through `/api/...` (public) after creating through
`/api/admin/...`? Publish first — `POST /api/admin/series/{id}/publish`,
`POST /api/admin/events/{id}/publish` — or assert against the admin route instead. A 404
from a public route in a test usually means "unpublished", not "missing".

**Evidence** — `api/tests/stories/test_event_closing.py::test_a_cancelled_event_costs_nobody_points`;
`api/app/routers/public.py`.

**Seen** — 2026-09-12.
