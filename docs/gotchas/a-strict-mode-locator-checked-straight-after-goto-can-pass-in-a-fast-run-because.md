# A strict-mode locator checked straight after goto can pass in a fast run because the duplicate it should catch has not rendered yet

**Symptom** — `visitor.spec.ts` "the home page leads into a series" failed only under
`EVIDENCE=1` (video recording), on both projects, with `strict mode violation:
getByRole('heading', { level: 1 }) resolved to 2 elements`. The same test passed in every
normal run.

**Cause** — The home page really had two `h1`s: the breadcrumb's last crumb (every page's
heading since Story A-12) and the hero tagline, which renders only after the page's data
has loaded. `expect(locator).toBeVisible()` right after `goto` resolved while only the
breadcrumb existed, so a fast run passed; recording slowed the page enough for the hero to
be there in time. What misled: "fails only with recording on" read as "recording breaks
the test", when the recording was the only run slow enough to tell the truth.

**Rule** — Assert a count or uniqueness only after waiting for something that proves the
page has finished loading (a `data-testid` of the loaded content), and use
`toHaveCount(n)`, not a strict-mode locator, when the number is the point. A test that
passes only when it is fast is checking timing, not the page.

**Evidence** — `e2e/visitor.spec.ts` ("the home page leads into a series") waits for
`start-series-card-1`, then expects one `h1`. Without the fix in `web/src/pages/Start.tsx`
(tagline back to a `<p>`) it now fails in a normal run with "Expected: 1, Received: 2".

**Seen** — 2026-10-04
