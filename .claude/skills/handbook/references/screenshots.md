---
title: Screenshots — captured from the dev stack, per role and locale
description: The capture spec under e2e/, signing in per role through /api/dev/login, forcing the locale, desktop and phone shots, seeded data, naming, and how missing shots degrade.
---

# Screenshots

Captured from the running site, never snipped by hand, re-captured on every update.

## How

One spec, `e2e/handbook-shots.spec.ts`, kept out of the normal run (`test.skip` unless
`HANDBOOK_SHOTS=1`) so `playwright test` stays fast. It reuses what the suite has:

- **The stack**: `scripts/dev-stack.sh --workers 1` — seeded throwaway database,
  `SBL_DEV_LOGIN=true`. Never `api/sbl.db`.
- **The role**: `signIn(page, email)` from `e2e/session.ts`, with the seeded accounts
  (CLAUDE.md § Testing different roles): a club's `manager`, `regatta@` (race officer),
  `orga@` (manager), `jury@`, `helfer@`, `admin@`, `redaktion@`, one sailor account,
  — no guest: the help explains no public page. The **role switcher** (bottom right, dev only) must not be
  in any shot — hide it in the spec, or clip.
- **The locale**: the i18n detector reads `localStorage["sbl.language"]`
  (`web/src/i18n/`); set it with `page.addInitScript` before the first navigation. Check
  that the `en` and `de` PNG of one shot differ — a wrong key yields English twice.
- **Desktop and phone**: desktop at 1280×800, phone with Playwright's `Pixel 7` device (the
  suite's `mobile` project). A phone shot only where the plan asks for it — the things
  done on the water or at the dock (race control, results entry, the waiver on a phone, the
  live view).

```ts
// e2e/handbook-shots.spec.ts — one entry per shot of the plan's shot list
const SHOTS = [
  { id: "lineup-panel", as: "manager-of-club@…", path: (d) => `/me/club/${d.clubId}`,
    waitFor: "[data-testid=lineup-panel]", clip: "[data-testid=lineup-panel]" },
  …
];
```

- **`waitFor` a `data-testid`**, never a bare timeout. No such test id? The capture agent
  adds it to the screen (it is required anyway) and reports it.
- **Ids from the API, not hardcoded**: look the club, series or event up through the
  generated paths (`bearer()` from `e2e/session.ts`) — the seed may change.
- **Clip** dialogs and panels; a full-page shot of a panel is mostly chrome.
- Write to `web/public/handbook/screenshots/<id>_<locale>.png` and `<id>_<locale>_phone.png`.

Run:

```bash
scripts/dev-stack.sh --workers 1 &      # in the background, wait for it
HANDBOOK_SHOTS=1 pnpm exec playwright test e2e/handbook-shots.spec.ts --project chromium --workers 1   # one stack: more workers look for :5174+
HANDBOOK_SHOTS=1 pnpm exec playwright test e2e/handbook-shots.spec.ts --project mobile --grep @phone --workers 1
```

## Marks: where to click

A shot may carry **marks**: a soft amber glow around a control with a numbered badge just
outside its top-left corner, drawn into the page before the picture is taken.

```ts
{ id: "help-claim-new", …,
  marks: () => [
    { target: tid("my-space-claim-target") },   // ①
    { target: tid("my-space-claim-title") },    // ②
    { target: tid("my-space-claim-create") },   // ③
  ] }
```

- **When:** mark the control the paragraph next to the shot tells the reader to click or
  tap — a step's button, field or toggle. Not decoration: a shot of a list to *read* (a
  status table, the check-in list) gets none.
- **At most about three per shot.** More marks than steps teach nothing; split the shot.
- **Numbered in the order the text names them** — `{ target, n? }`, `n` defaults to the
  mark's place in the list from 1. The text says ①②③ in **both** locales, beside the label
  it quotes (*Save squad* ③), and the shot's alt text names them too.
- **`target` is a selector for one visible element** — prefer the `data-testid`; for a
  field with its label above it, mark the `label:has(…)` so the badge does not cover the
  label; for a file drop zone, the visible zone, not the hidden input. A missing or
  invisible target **fails the shot** — never a picture whose text refers to a mark it lacks.
- The spec waits until the targets stop moving (a list that lands late pushes the rest
  down) and widens the clip to cover every glow and badge. Only a glow, two layers, no
  frame or ring (2026-10-19, the user's call: the glow alone looks better and reads on
  white cards and on the dark glass pages alike).
- A phone shot of the viewport (`phoneViewport`) shows only marks inside the viewport —
  look at the PNG.

Look at every marked PNG after capturing: a badge over a neighbour's glow, a mark cut by
the clip, or a glow beside its control (layout moved) are the failures to catch.

## The data must say something

An empty table teaches nothing. Use, in this order: the seed (`app.seed_test_setup` — the real
2026 clubs of both divisions, four series, 540 sailors, a planned matchday per league; the
test club ASVW and its 2. Liga act 3); steps inside the spec through the API, the way
`lifecycle.spec.ts` builds an event; nothing else. Dates relative to "now" change every
capture — clip them out or pick seeded fixed dates.

## Privacy in shots

The seed's people are invented, but a shot of a waiver scan, an IBAN or a personal document
is still a shot of the most sensitive screens: capture the **list with its status**, never
an opened scan or document, and never a full IBAN — clip the bank-account form (S-6) out,
or capture it empty.

## Missing shots degrade

A missing PNG renders a "screenshot pending" box; the run reports every skipped shot and
why; the report lists captured / skipped / referenced-but-missing /
captured-but-unreferenced.
