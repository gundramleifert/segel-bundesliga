# Checking a path against the app's route patterns proves nothing when a catch-all or a placeholder-only pattern is among them

**Symptom** — the handbook check "every internal link and every `route:` is a route in
`web/src/App.tsx`" was green on the whole store, and stayed green when a page was given
`route: /nowhere` or a link to `/no/such/page`.

**Cause** — `App.tsx` has a catch-all `<Route path="*">` (it redirects to `/`) and the
league routes are placeholders only: `:league`, `:league/:year/:act`. Matched as
patterns, `*` accepts every path and `:league/:year/:act` accepts every path of three
segments. What misled: the check had been run against the real store, all green, and that
looked like proof — it was the first deliberately broken input that showed it could not
fail.

**Rule** — when checking a path against a router's patterns, leave out the catch-all, and
let a pattern made only of placeholders count only when the path *is* that pattern. A
path must agree with at least one literal segment to prove it exists. And break the check
on purpose before believing it (CLAUDE.md, "verify a new check by breaking something").

**Evidence** — `scripts/check-docs.py::app_routes` (drops `*`) and `::_known_route`; the
two cases "bad route" and "internal link to no route" each report one problem only since
then.

**Seen** — 2026-10-17
