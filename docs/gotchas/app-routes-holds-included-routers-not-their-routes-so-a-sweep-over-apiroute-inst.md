# app.routes holds included routers, not their routes, so a sweep over APIRoute instances finds nothing and passes

**Symptom** — a test that loops over every route
(`[r for r in app.routes if isinstance(r, APIRoute)]`) to check something about each one
collected **zero** routes. A parametrized test over that list simply has no cases, and a
loop over it asserts nothing — green either way.

**Cause** — since FastAPI 0.141, `app.include_router` no longer copies the router's routes
into `app.routes`: it appends one `fastapi.routing._IncludedRouter` per router, and the
prefixed route with the router's own `dependencies` only exists as a computed
`RouteContext`. What misled: every FastAPI example and older code here treat `app.routes`
as the flat list of endpoints.

**Rule** — enumerate endpoints with `fastapi.routing.iter_route_contexts(app.routes)`;
each context has `.path` (prefix included), `.methods` and `.dependant` (router-level
dependencies included). Any sweep over routes also asserts it found a plausible number of
them, so an empty sweep fails instead of passing.

**Evidence** — `api/tests/stories/test_guard_problems.py::TestGuardProblems::test_the_sweep_finds_the_guarded_routes`
(> 50 guarded routes); `api/app/main.py::_openapi_with_problems` uses the same iteration.

**Seen** — 2026-10-18
