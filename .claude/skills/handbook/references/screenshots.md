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
  a guest for the public pages. The **role switcher** (bottom right, dev only) must not be
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
HANDBOOK_SHOTS=1 pnpm exec playwright test e2e/handbook-shots.spec.ts --project chromium
HANDBOOK_SHOTS=1 pnpm exec playwright test e2e/handbook-shots.spec.ts --project mobile --grep @phone
```

## The data must say something

An empty table teaches nothing. Use, in this order: the seed (`app.seed_test_setup` — three
series, 360 sailors, a planned matchday); steps inside the spec through the API, the way
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
