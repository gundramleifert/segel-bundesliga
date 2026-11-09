# Two Playwright actions in a row never catch a stale-render bug: dispatch both events in one task

**Symptom** — a handler that writes from the values of the last render (two filter changes
before React renders again: the second drops the first) passes a spec that does
`selectOption(a)` then `selectOption(b)` — green on the build with the bug and on the build
without it.

**Cause** — Playwright waits for each action to settle, so React renders between the two
and the second handler sees the first's result. The spec looked like a test of "two
changes in a row" and could never fail; the bug only shows when both events land before
the next render, as in one handler or one task.

**Rule** — to test that a change builds on the one before it, fire both in one browser task
(`page.evaluate` setting each control and dispatching `change`), and check the spec fails
on the old build before believing it.

**Evidence** — `e2e/editorial.spec.ts` "the list filters by league and state": with two
`selectOption` calls, 6 of 6 passed on both builds; with one `page.evaluate`, the build
before `web/src/lib/listParams.ts`'s ref fails (address `?league=2-liga`, the state lost)
and the fixed build passes.

**Seen** — 2026-11-09
