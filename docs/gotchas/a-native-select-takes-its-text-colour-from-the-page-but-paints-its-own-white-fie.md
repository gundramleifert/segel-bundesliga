# A native select takes its text colour from the page but paints its own white field and list, so on a white-text surface it is white on white

**Symptom** — on the official pages the pairing list's "all clubs" picker (and its open
list of clubs) showed no text: white on white. The same picker looked fine on the internal
screens.

**Cause** — `.on-glass` (`web/src/index.css`) sets `color: white` for content written for
paper, and a `<select>` inherits that text colour like any element — but the browser
still draws the field and, above all, the open option list in its own light scheme. What
misled: the select had classes, so it looked styled; none of them named a text or
background colour, so the one it showed came from the page around it.

**Rule** — a form control states its own colours, and a surface that changes the text
colour also sets `color-scheme` for the native popups on it. On this site every dropdown
is `components/Select.tsx`; `oxlint` (`react/forbid-elements`) refuses a bare `<select>`.

**Evidence** — `e2e/visitor.spec.ts`, "the pairing list's club picker is legible on the
glass, open or closed": without the `.on-glass select` rule it fails with
`Expected: "dark"`, `Received: "light"`.

**Seen** — 2026-10-18
