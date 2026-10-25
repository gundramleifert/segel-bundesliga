# position: sticky inside Layout's main never sticks, it only shifts down — main is a scroll container (panel-scroll)

**Symptom** — the workspace's sidebar (`sticky top-32`) stood about 120 px lower than the
content beside it on first load, and did not stay put when the page scrolled.

**Cause** — `Layout`'s `<main>` carries `panel-scroll` (Story A-10: a wide table scrolls
the panel, not the document), which gives it an `overflow` and so makes it the sticky
element's scroll container. The document scrolls, `main` never does vertically, so the
element never "sticks" — and `top-32` is measured from `main`'s own top, so it is applied
at once as an offset. What misled: `top-32` was chosen to clear the sticky header, as if
the viewport were the reference.

**Rule** — inside `Layout` (`main#content`), don't use `position: sticky` for something
that should follow the window; it cannot. Keep such a column short enough not to need it,
or put the sticky element in the header (outside `main`), as the bars are.

**Evidence** — `web/src/components/Layout.tsx` (`panel-scroll` on `main`);
`web/src/pages/me/Workspace.tsx` — the sidebar's `aside` lost `sticky top-32`, and the
laptop screenshot of `/me/club/:id/members` shows switcher and content top-aligned.

**Seen** — 2026-10-25
