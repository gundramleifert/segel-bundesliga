---
title: Validators — accuracy, parity, integration, update review
description: What each read-only validator checks after scripts/check-docs.py has passed, blocking vs advisory, and the update reviewer.
---

# Validators

`python3 scripts/check-docs.py` runs first; its errors are blocking without a validator.
Validators judge what a script cannot. **Blocking**: the help is wrong, padded, or breaks
the site's rules — a fixer runs. **Advisory**: a human should look — it goes to the report.
Verify each finding in the code before reporting it.

## § accuracy

### Blocking
- **Invented behaviour** — sample at least 5 claims per page (a step, a limit, a refusal, a
  state, who may) and find each in the code.
- **Planned presented as built** — a criterion of a ◐/○ story that is not built, an `Open:`
  item, anything from `plan-*.md` / `docs/PLAN_*.md`.
- **Wrong label** — a quoted label not exactly in that locale's catalog.
- **Wrong number** — squad limits, file sizes, crew size, points rules: check the code.
- **Wrong audience** — a guide whose steps the named audience cannot do (the backend
  refuses them); a task told to the wrong person.
- **Journey page out of order** with its journey, or a step whose link lands on the wrong
  person's guide.
- **Roles page** — a ✓ the backend refuses, a – it allows, a cell justified by the screen
  only; the expense decision attributed to `can(manager)` (site editors) instead of the
  tuple (F-3); a relation missing; "how to get it" naming a path that does not exist (self
  sign-up).
- **Privacy softened** — who sees a waiver scan, a personal document, a bank account,
  stated wider or narrower than the endpoint's check.
- **Development features** — `/api/dev`, the role switcher, seeded accounts named in a page.
- **The site called "Segel-Bundesliga"**, or one series' configuration stated as the site's
  (CLAUDE.md, top).
- **Padding** — over budget, warm-up, screen narration, a fact repeated from another page.

### Advisory
- A refusal a person of this audience will meet that no page mentions.
- A guide without a stated starting state or result.
- Screen and backend disagreeing on a permission (a product bug worth an issue).
- A story whose text contradicts the code — propose the story correction.

## § parity

### Blocking
- `de` not fully translated: English sentences left, a stub, a dropped section.
- A screenshot, callout or link in one locale only, or pointing elsewhere.
- A domain word that differs from the `de` catalogs' (*Kader*, *Aufstellung*, *Spieltag*,
  *Ausrichter*, …), or the wrong register (not the one chosen in the interview).
- A caption left in the other language.

### Advisory
- A `de` page markedly shorter than its `en` page.
- A table with a different number of rows between locales.

## § integration

### Blocking
- `/help` or `/help/:page` not routed, or not deep-loadable in a fresh tab.
- A store glob that is not a literal, or lazy (empty help in one of dev/build).
- A dependency added beyond `remark-gfm`; a hand-written copy of something
  `web/src/components/` has (`docs/components.md`); a component importing from `pages/`.
- A handbook path hardcoded outside `web/src/handbook/index.ts` and `App.tsx`.
- An audience tile hiding pages from a signed-in person without that role (the help is for every signed-in account), or any page content reaching a guest.
- A second `h1` on the page; sideways scroll on a phone (`expectNoSidewaysScroll`).
- Tests missing for the story, or not in a `describeStory("B-n: …")`; `data-testid`s
  missing.
- `Help.tsx`'s old matrix still there beside the `roles` page, or its keys left in
  `help.json`.
- `pnpm typecheck` (web and root) or `scripts/check.sh` failing.

### Advisory
- Screens that would benefit from a `HelpLink` to an anchor, listed with the anchor.
- The story's `Tests:` line or `docs/traceability.md` not updated.
- `.handbook-plan.md` not gitignored.

## § update mode

For the one reviewer. Inputs: the confirmed plan (facts per section), the run's diff of
`web/src/handbook/`, the changed screenshots, check-docs.py's output.

### Blocking
- A planned fact not fixed in both locales.
- A changed sentence the code does not support.
- A change outside the plan: a `keep` page touched, or an unlisted section of a `revise`
  page rewritten — that silently reverts a human's edit.
- The clarity pass adding or removing a fact (diff its commit alone).
- A structure-lock violation other than an approved retirement.
- `roles` not following a changed permission; a caption no longer matching its new PNG.
- The baseline written before the checks passed.

### Advisory
- A page plausibly affected but marked `keep`.
- A story newly ● that no page covers.

## Verdict

Any blocking → `"blocking"`; else any advisory → `"advisory"`; else `"pass"`. Findings most
severe first, each with file:line, what, why, minimal fix.
