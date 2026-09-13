# A card grid's 1fr track is floored at min-content, so the overflow only appears once test data is long enough

**Symptom** — two `mobile` tests failed in the full suite and **passed when their spec ran
alone**. One timed out after 30 s clicking the language switcher, with the call log saying
`<nav data-testid="layout-nav" …> intercepts pointer events` about a button it also
described as "visible, enabled and stable". The other reported the home page as 445 px
wide in a 412 px viewport.

**Cause** — one thing, not two: `grid gap-4 sm:grid-cols-2` on the home page's event list.
A `1fr` track — and the single implicit column a plain `grid` gets on a phone — has a
minimum of its items' **min-content** width, so one card whose title does not fit widened
the list, the page, and with it the layout viewport. Mobile Chromium answers a page wider
than the viewport by zooming everything out, and pointer coordinates then no longer match
what is under them: that is the "intercepts pointer events" line, and why the element it
blames is never the element at fault (Story A-10).

It passed alone because the overflow needs a long name, and the only long names in the
database are the ones `lifecycle.spec.ts` writes — `E2E Draft Cup 1789234123-456`. Run the
visitor spec first and there are none; run the whole suite, or the same suite twice, and
there are. **A green suite on a freshly seeded database proves less than you think.**

What misled me, twice: the failure looked like a test race, so I rewrote the helper
(`isVisible()` really does not auto-wait — that bug was real, just not this one), and then
it looked like a flex-layout overlap, so I added `min-h-0` to the scrolling nav (also
right, also not this). The call log had said "intercepts pointer events" from the first
run onward, and Story A-10 says in as many words what that means. Reading the failure
would have been faster than reasoning about the failure.

**Rule** — every grid track that holds page content is `minmax(0, 1fr)`, never `1fr` and
never a bare `grid`. Use `CardGrid` and `Stack` from `web/src/components/Layouts.tsx`,
which is where that now lives; nine hand-written copies of this class string all carried
the same latent bug. And when a visible control cannot be clicked, suspect the page's
width before the element named in the log.

**Evidence** — `expectNoSidewaysScroll`'s own output named
`ul[] .grid gap-4 sm:grid-cols-2` inside `section[start-events-section]` at 428 px in a
380 px cell; `<a class="group block h-full">` measured 428 px inside a 380 px `ul`.
Switching `CardGrid` to `minmax(0,1fr)` tracks took the suite to 55 passed, twice in a row,
including against the database the previous run had written to.

**Seen** — 2026-09-13
