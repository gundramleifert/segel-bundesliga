# An sr-only label inside a scroller widens the page unless the scroller is positioned

**Symptom**: on the phone project only, a dialog's *Add* button can't be clicked
("modal-backdrop intercepts pointer events", or the dialog's own input does), and the
dialog sits half off the screen. On desktop the same test passes.

**Cause**: the page behind the dialog was wider than the phone (`scrollWidth` 759 for a
412 px viewport), and the dialog was laid out against that width. Wrapping the table in an
`overflow-x: auto` box did not fix it. The table's new *Actions* header carries an
`sr-only` label, which is `position: absolute`. An absolutely placed element is clipped
only by a scroller that is (or sits inside) its containing block, and nothing up the tree
was positioned, so the label was placed against the page and stretched it. What misled me:
the failure was a blocked click in a modal, nowhere near the table, and the table scrolled
inside its box just as intended.

**Rule**: a sideways scroller gets `position: relative` (`DataTable`'s wrapper has
`panel-scroll relative`) whenever anything inside it can be absolutely placed: `sr-only`
text, badges, popover anchors. To find what widens a page, walk the ancestors and compare
`scrollWidth` with the viewport. The element that sticks out is often not the one the
failure points at.

**Evidence**: probe on `/me/club/1/people` (mobile): `HTML sw=759` with the table's own
scroller already at `sw=779 w=380`. After adding `relative`, `doc 412/412`, and
`e2e/club.spec.ts` plus `e2e/join-consent.spec.ts` pass on mobile.

**Seen**: 2026-10-26
