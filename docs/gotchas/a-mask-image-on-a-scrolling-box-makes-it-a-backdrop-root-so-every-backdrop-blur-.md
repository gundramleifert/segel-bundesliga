# A mask-image on a scrolling box makes it a backdrop root, so every backdrop-blur inside it blurs nothing

**Symptom** — on the chapter page (sub-menu layout) the glass cards looked darkened but
sharp: the DEV switch's *Card blur* slider changed nothing there, while the same cards on
a page deeper blurred their picture as they should. `getComputedStyle(card).backdropFilter`
said `blur(32px)` on both.

**Cause** — the chapters' scrolling box had `mask-image` (to fade the text out under the
top row). A mask — like `filter`, `opacity < 1`, `clip-path`, `mix-blend-mode` or its own
`backdrop-filter` — makes an element a **backdrop root**: a `backdrop-filter` inside it
only sees what is painted *within* that element. The picture is a sibling behind the box,
so the cards' blur had nothing to blur. What misled: the computed style was right and the
card was visibly darker, so the glass looked like it worked.

**Rule** — no `mask-image`, `filter`, `opacity`, `clip-path` or `backdrop-filter` on any
ancestor between a glass card and the picture it should blur. To check a blur, compare
pixels with the blur at 0 and at 32px; the computed style proves nothing.

**Evidence** — a Playwright probe screenshotted the 1. Liga's top-five card with
`--site-card-blur` at `0px` and `32px`: identical bytes with the mask, different without
it; a card on `/1-liga/clubs` differed in both runs. Guarded by `e2e/visitor.spec.ts` › *the glass blurs the
picture behind it — on the chapters too*, which fails with the mask put back. Its first
version passed with the mask in place: the photo was still loading between the two shots,
so they differed anyway — it now waits for the picture and takes the sharp shot twice.

**Seen** — 2026-10-18
