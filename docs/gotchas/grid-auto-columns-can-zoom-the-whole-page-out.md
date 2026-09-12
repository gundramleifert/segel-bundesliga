# A Tailwind `grid gap-*` column is sized by its widest item's min-content — and that can zoom the whole page out

**Symptom** — On the `mobile` Playwright project, *every* click on an admin control was
refused with "…intercepts pointer events", and the named interceptor was **different on
each retry**: the row's own title block, an input from a form far above, the header's
language switcher. The same controls worked perfectly at desktop width. It read as "these
buttons are broken".

**Cause** — Nothing was overlapping. `/admin` overflowed horizontally, and mobile Chromium
answers horizontal overflow by **zooming the page out to fit it**: `window.innerWidth`
measured 754px inside a 412px viewport, the page rendered at ~55%, and pointer coordinates
stopped matching what was under them. The overflow itself came from `grid gap-*` used to
stack sections: a grid's `auto` column is sized by its items' **min-content** width, so one
wide box (the boat-setup table) widened its column, and because grid items stretch to the
column, *every sibling section grew with it*, all the way up to the page.

I was confidently wrong twice on the way here. First I blamed the row's `flex-wrap` header
— it was innocent, and the story had recorded that wrong cause for weeks. Then I blamed
`scroll-behavior: smooth` — a real defect, but it only changed which element intercepted.
The shifting cast of interceptors was the clue I misread: it meant the *page* was moving,
not that the target was covered.

**Rule** — Any container that stacks children with `grid gap-*` must be
`grid grid-cols-[minmax(0,1fr)] gap-*`, so the column may be narrower than its content.
A wide table then scrolls inside its own `overflow-x-auto` box, which is where the
scrolling belongs. When a click is refused and the interceptor changes between retries,
measure the layout before you touch the element: `window.innerWidth` against the viewport
you configured.

**Evidence** — `web/src/pages/Admin.tsx`, `web/src/pages/adminBuildingBlocks.tsx`
(`Section`), and 19 grids across the admin pages. Guard: `expectNoSidewaysScroll` in
`e2e/layout.ts`. Story A-10.

**Seen** — 2026-09-11, commit `dcaacde`.
