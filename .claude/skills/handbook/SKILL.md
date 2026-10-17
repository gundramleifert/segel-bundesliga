---
name: handbook
description: "Builds and updates the site's in-app help — the handbook at /help — for everyone signed in — sailor, club admin and team manager, event organizer, race committee, treasurer, administration. Pages are derived from the user stories (only what is built) and the journeys in docs/journeys/: one guide per journey, one starting page per audience, a roles page from the permission model, an FAQ from the typed errors. English source, German translation, screenshots from the running stack, and checks in scripts/check-docs.py that keep pages, stories and journeys in step. Use for 'write the help', 'document this for team managers', 'update the handbook', 'Hilfe/Handbuch', 'user docs from the journeys', or after a feature changed what someone does on the site. Adapted from the Planet AI vertical-docs skill. NOT for engineering docs under docs/, the user stories themselves, or the public content pages (news, press)."
argument-hint: "[first-pass | update | page <id> | audience <name> | journey <J-n>]"
---

# Handbook — the help for everyone who uses the site

Adapted from the Planet AI `vertical-docs` skill (claude-plugin-marketplace,
`plugins/vertical-docs`). What it keeps: evidence before prose, short pages, two locales
with identical structure, screenshots from the running app, a structure lock, agents per
page, an update mode that touches only what changed. What it changes, because this site is
not a Planet AI vertical:

| vertical-docs | here |
|---|---|
| `@planet-ai/handbook` renders the store | the site renders it itself: `react-markdown` (already a dependency), HeroUI, `web/src/components/` — `references/viewer.md` |
| German authoritative, `react-intl` | **English authoritative**, German a full translation, `react-i18next` (CLAUDE.md § Language) |
| evidence = routes, routers, i18n | the same, **plus the user stories and journeys** — they say what is built (● / ◐ / ○) and in which order things happen (`references/sources.md`) |
| one reader, a professional mid-task | **six audiences**, the files of `docs/userstories/` except `visitor.md` — every page says whom it is for (`references/content-model.md` § Audiences). **The help is internal**: signed-in accounts only; the public site explains itself, and what a page would have had to explain to a visitor is reported as a UX fix instead |
| roles page from the gateway catalogue | roles page from the relation-tuple model (`MODEL` in `api/app/models/auth.py`) and the `require_*` checks |
| `pai-handbook check` / `lock` | `scripts/check-docs.py`, which `scripts/check.sh` already runs (`references/checks.md`) |
| a welcome dialog | none — "my space" (`/me`) already tells a person what waits for them (Story Z-8) |

## The five non-negotiables

1. **Every sentence is provable in the code.** A story marked ● is a pointer to evidence,
   not evidence: the claim is checked in the router, the service and the screen. A ◐
   story documents only the criteria it marks as built; a ○ story nothing. Missing
   evidence → leave it out and report the gap. Never document an `Open:` paragraph.
2. **Short.** The reader is on a pontoon with a phone, or at a desk between two other jobs.
   Length budget in `references/writing-guide.md`. Fewer complete pages beat many thin ones.
3. **Written for one person at a time.** Every page names its audience; a guide is written
   for exactly one of them. A journey page is the exception that links the people together
   — and hands each step over to that person's own guide.
4. **Two locales, one structure.** `en` is written first and completely, `de` is a full
   translation with byte-identical frontmatter except `title`. UI labels are quoted from
   the catalogs (`web/src/i18n/locales/{en,de}/*.json`), never re-translated.
5. **The project's rules win.** CLAUDE.md, `docs/components.md`, the story-first order, the
   issue workflow (`/issue`), `scripts/check.sh` green before a commit. Domain words are
   CLAUDE.md's (Series, Event, Squad, Lineup, Host club, …) — never "Segel-Bundesliga" for
   the site (CLAUDE.md, top).

## Two modes

**Detection:** `web/src/handbook/` holds `<id>.<locale>.md` pairs → **update**. Otherwise
**first pass** (which also absorbs the hand-written `web/src/pages/Help.tsx`).

```
first pass   pre-flight → discovery (5 ∥) → interview → PLAN (one confirmation)
             → story → viewer ∥ authors (one per page) → screenshots → clarity (≤3 editors)
             → check-docs.py → validators (3 ∥) → [fixer loop] → baseline → report

update       pre-flight → diff since the baseline → touched pages → confirm
             → recapture screenshots → updaters (1–3) ∥ new-page authors
             → clarity (1 editor, touched sections) → check-docs.py → reviewer → baseline → report
```

Rosters, prompts, the plan format: `references/orchestration.md`. Update mode:
`references/update-mode.md`.

## Autonomy contract

1. **All decisions in the interview.** Subagents cannot ask; after the plan is confirmed
   there are no questions until the report.
2. **Defaults from the repo**; ask only what it cannot decide.
3. **Catch errors, don't pause** — a failing command is recorded and reported.
4. **Progress** with the task list per phase and per subagent.
5. **Idempotent** — a second run is an update and leaves human edits outside its scope alone.
6. **Commit in chunks on the issue's branch**, in this repo's commit style
   (`git log --oneline -20`). Never on `main`, never push, never merge — that is `/issue`'s
   job and the user's word.

## Workflow

### Phase 1 — Pre-flight (write nothing)

- `git status`; on `main` → stop and propose `/issue new` + `/issue start` (CLAUDE.md: one
  issue, one branch). Dirty tree → ask.
- Read `docs/gotchas/INDEX.md` (CLAUDE.md, "Before you debug").
- Inventory `[HAVE]/[MISSING]`: the store, its baseline (`web/src/handbook/.baseline/`),
  the viewer (`web/src/pages/Help.tsx` — hand-written roles matrix today), the `/help`
  route in `web/src/App.tsx`, the `help` i18n namespace, the journeys and their format
  (`docs/journeys/`, `J-n.k` step tables, actors in `docs/userstories/journeys.md`), the screenshot spec, `scripts/check-docs.py`'s handbook checks.
- The stack must start: `scripts/dev-stack.sh --workers 1` (seeded throwaway database,
  `SBL_DEV_LOGIN=true`). If it does not, stop after discovery — never author from source
  alone and call it verified.

### Phase 2 — Discovery (first pass) · Diff map (update)

First pass: five read-only agents in **one** message (`references/orchestration.md`):
stories & journeys, routes & screens, API & permissions, vocabulary & errors, runtime
tour. Synthesis: per audience, *task → stories → screen → endpoint → evidence*, plus the
role inventory for the roles page. Update: no agents — `references/update-mode.md`.

### Phase 3 — Interview (one batch)

`AskUserQuestion`, each with a default:

| Question | Default |
|---|---|
| Audiences to cover now | all six; `live` folded into race committee |
| German register | **"Sie"** — and report that the `de` catalogs mix *Sie* and *du* (`account.json` vs the waiver texts) |
| Journeys as pages | every journey with ≥ ◐ status |
| Route | `/help`, absorbing today's `Help.tsx` roles matrix into the reserved `roles` page |
| Screenshots | desktop 1280×800 **and** phone (Pixel 7) for guides a person does on the water |
| Page plan | the Phase-2 candidates, for trimming |

### Phase 4 — Plan (one confirmation)

Write `.handbook-plan.md` at the repo root (gitignored — add the line if missing), format
in `references/orchestration.md`. Show it on one screen. `Proceed? (yes / no)`.

### Phase 5 — Story, then build

- **The story first** (CLAUDE.md, "How to update the docs"): the first pass adds one story
  for the help itself — "As anyone using the site I find the help for what I do" — in
  `docs/userstories/sailor.md` (B-18), acceptance criteria from the plan.
  Update mode edits that story only if the viewer's behaviour changes.
- In one message: the **viewer agent** (first pass, or update when the viewer is missing
  something) and **one author per page** (update: 1–3 updaters plus authors for new pages).

### Phase 6 — Screenshots

`references/screenshots.md`: a Playwright spec under `e2e/` against the dev stack, both
locales, signed in per role through `/api/dev/login`.

### Phase 7 — Clarity pass

Editors cut and clarify; they never add or remove facts, labels, anchors or shot ids
(`references/writing-guide.md` § Concision pass).

### Phase 8 — Check, validate, baseline

`python3 scripts/check-docs.py` (handbook checks, `references/checks.md`), `pnpm
typecheck` in `web/`, then the validators (`references/review-checklist.md`), fixer loop
≤ 3 (update ≤ 2). Then `scripts/check.sh`, then the baseline snapshot, committed last.

### Phase 9 — Report

One screen: commits; pages per audience and type, words per page; screenshots captured vs
planned; **gaps** — behaviour without evidence, ◐ criteria left out, stories whose text
and code disagree (those are story bugs: say which, CLAUDE.md says to correct the story);
the roles page's mismatches between screen and backend; follow-ups. If a wrong turn cost
time, a `docs/gotchas/` note (CLAUDE.md, "When you were wrong, write it down").

## References

| File | Content |
|---|---|
| `references/sources.md` | Where evidence comes from: stories (and their status), journeys, routes, routers, the permission model, the error codes — and how each becomes a page |
| `references/content-model.md` | Store layout, frontmatter (`audience`, `stories`, `journey`, `route`), types, anchors, the reserved pages, the structure lock |
| `references/writing-guide.md` | Length budget, English and German register, page anatomy per type incl. journey and roles pages, concision pass |
| `references/viewer.md` | The `/help` page in `web/`: loading the store, rendering, audience filter, help for this page, tests |
| `references/screenshots.md` | The capture spec, roles, locales, phone shots, seeded data |
| `references/checks.md` | The handbook checks to add to `scripts/check-docs.py`, and the baseline |
| `references/orchestration.md` | Agents, prompts, `.handbook-plan.md` |
| `references/update-mode.md` | Diff → touched pages, through the stories and journeys the pages cite |
| `references/review-checklist.md` | Validators: accuracy, parity, integration; the update reviewer |
