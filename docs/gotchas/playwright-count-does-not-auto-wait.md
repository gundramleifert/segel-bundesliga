# `locator.count()` does not auto-wait; `toHaveCount()` does

**Symptom** — A spec read `await list.count()` straight after an action and got the
pre-action number. It passed locally whenever the machine was slow enough to make the
timing work out, which is the worst possible failure mode.

**Cause** — `count()` is an immediate query: it returns what is in the DOM at that instant.
Only the `expect(...)` matchers retry.

**Rule** — Assert with `await expect(list).toHaveCount(n)`. Use `count()` only for a number
you have already waited for by other means. The same applies to `textContent()` versus
`toHaveText()`. And when a list is expected to be empty, check what the component actually
renders — several panes here render a "none available" `<li>`, so `toHaveCount(0)` is
wrong even when the list is logically empty.

**Evidence** — `e2e/lifecycle.spec.ts`, `e2e/visitor.spec.ts`.

**Also** — `locator.isVisible()` has the same shape and the same trap: asked before the
element has painted it answers `false` with no waiting, so `if (await x.isVisible())` is a
coin flip on timing. `openNavigation` in `e2e/layout.ts` used it to decide whether this
viewport has a burger menu, and now decides from the viewport width instead. Decide from
something settled — a viewport size, a URL — or use an assertion, which waits.

**Seen** — 2026-09-09, commit `0893578`.
