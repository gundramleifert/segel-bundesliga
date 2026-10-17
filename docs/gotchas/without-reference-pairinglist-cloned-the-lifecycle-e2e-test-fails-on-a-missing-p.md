# Without reference/PairingList cloned, the lifecycle e2e test fails on a missing PDF link, not on a missing tool

**Symptom** — `e2e/lifecycle.spec.ts` "VA-8: … a complete event can be drawn, published
and started" fails on both projects with `getByTestId('admin-events-pairing-pdf-link')`
— *element(s) not found*, while the other ~150 browser tests pass. Looks like a broken
admin events panel.

**Cause** — the page is right: `renderer_available()` (`api/app/pairing/pdf.py`) is false
when the JAR from `reference/PairingList` is absent, and the panel then deliberately leaves
the download out (Story B-3). `reference/` is not versioned, so a fresh machine has no
clone; Java being installed is not enough. What misled: the failure names a UI element,
not the tool, and it appeared right after a frontend change.

**Rule** — before reading a missing `…-pdf-link` as a regression, check
`uv run python -c "from app.pairing.pdf import renderer_available; print(renderer_available())"`
in `api/`. False → clone and build `reference/PairingList` (its own `CLAUDE.md`), or
accept the two failures as environmental and say so.

**Evidence** — 2026-10-17 on the `journeys` branch: `reference/PairingList` absent,
`renderer_available()` → `False`, the full suite 149 passed / 2 failed, the two being this
test on chromium and mobile.

**Seen** — 2026-10-17
