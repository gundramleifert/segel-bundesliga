# A "page doesn't scroll sideways" assertion passes while the page is unusably zoomed out

**Symptom** — `visitor.spec.ts`'s "the page never scrolls sideways — not even with a wide
table" passed on the `mobile` project for the entire time the admin screens were unusable
on a phone. The guard existed, ran, and was green.

**Cause** — The two symptoms mask each other. Honest overflow gives
`documentElement.scrollWidth > clientWidth`. But mobile Chromium responds to that overflow
by widening the layout viewport to fit the content — after which `scrollWidth ===
clientWidth` again and the overflow is *invisible to exactly the assertion written to
catch it*.

**Rule** — Overflow needs **two** assertions, not one: `scrollWidth <= clientWidth` for
honest overflow, **and** `window.innerWidth === <the viewport you configured>` for the
zoom-out. Read the expected width off `testInfo.project.use.viewport`, never a hardcoded
412 — then the same helper works in every project. More generally: when a guard protects
against X, ask whether X changes the thing the guard measures.

**Evidence** — `e2e/layout.ts::expectNoSidewaysScroll`; the failure it would have caught is
in `grid-auto-columns-can-zoom-the-whole-page-out.md`.

**Seen** — 2026-09-11.
