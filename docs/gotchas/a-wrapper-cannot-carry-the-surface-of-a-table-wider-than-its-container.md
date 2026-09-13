# A wrapper cannot carry the surface of a table wider than its container

**Symptom** — a wide table inside the horizontally scrolling content panel had a white
background and a rounded border for the first few columns and then, partway across, sat on
the page's grey for the rest of its width. Scroll right and the table kept going; its frame
did not.

**Cause** — the frame is a block inside the scroll container, so it is sized by that
container's content box while the table inside it is wider and overflows it. Two obvious
repairs both fail, in different and instructive ways:

- **`width: fit-content` (`w-fit`) does nothing.** It is defined as
  `min(max-content, max(min-content, available))` — clamped to the available width, so it
  can never exceed its containing block. That is the opposite of what is wanted.
- **`width: max-content` (`w-max`) widens the frame, and breaks a different page.** It has
  no clamp, so the frame does wrap the table — but it also makes the frame's *min-content*
  width the table's, and that propagates up the block chain. Where a table holds numbers
  this is harmless; where it holds sentences (the role matrix on `/help`) the page's
  minimum width exceeds the phone viewport and mobile Chromium shrinks the whole page to
  fit — `window.innerWidth` 529 in a 412px viewport, which is Story A-10 arriving from the
  other direction.

**Rule** — put the surface on the **table**, not on a box around it. A table is exactly as
wide as its own content, so its background and outline always cover it, at any panel width,
whatever its cells contain. `.data-table` in `web/src/index.css` does this:
`background-color`, `border-radius`, and `box-shadow: 0 0 0 1px` for the outline —
`box-shadow` rather than `border`, because `border-collapse: collapse` hands a table's own
border over to its cells. A tinted header row then needs the table's corner radii repeated
on its first and last `th`, or it squares them off again.

**Also** — I reported the `w-fit` version as fixed after checking that the *document* still
fit its viewport, which is a different number from the one the complaint was about. The
screenshot came back with the grey band still in it. A visual defect needs a visual check.

**Evidence** — `/help` on a Pixel 7: `innerWidth` 412 with no width on the frame, 412 with
`w-fit` (and a grey band), 529 with `w-max` (no band, page zoomed out), 412 with the
surface on the table (no band, no zoom). `/events/1`, whose table is numbers, measured 412
in every variant — which is why the `w-max` version looked correct when only that page was
checked.

**Seen** — 2026-09-13
