---
title: Orchestration — agents, prompts, the plan
description: Subagent rosters for the first pass and update mode, every prompt, the .handbook-plan.md format, the clarity pass, validators and the remediation loop.
---

# Orchestration

The main thread owns pre-flight, the synthesis, the interview, the plan, dispatch, the
fixer loop and the report. Subagents cannot ask the user anything. Dispatch each group in
**one** message. Give each agent the reference files it needs **by path**, its slice of
the plan, and its output contract.

```
first pass
Discovery   stories+journeys ∥ screens ∥ api+permissions ∥ vocabulary+errors ∥ runtime   5, read-only
Build       viewer ∥ author×N                                                        1 + one per page
Screenshots capture                                                                  1
Clarity     editor×(≤3)                                                              by type group
Validate    check-docs.py → accuracy ∥ parity ∥ integration                           script + 3
Remediate   fixer (scoped) → re-validate, ≤3

update      diff map (no agents) → updater×(1–3) ∥ author×new → editor×1 → reviewer×1 → fixer ≤2
```

## Discovery (read-only, evidence not prose)

**Stories & journeys**
> Read every file in `docs/userstories/` (and `docs/journeys/` if it exists) and
> `.claude/skills/handbook/references/sources.md`. For each story: ID, status, title, file
> (= audience), the "As a …" role, and its acceptance criteria split into *built* and *not
> built* (a ◐ story says which; `Open:` is never built), its `Endpoints:`/`Screen:` lines.
> For each journey: ID, status, who, starting point, main steps (number, story, who, what
> is then true), variations, its test. Return two tables. Quote; do not summarise criteria.

**Screens**
> Read `web/src/App.tsx` and every file under `web/src/pages/`. Per route: path, component
> + file, what it shows, every action (button, form, upload, download) with `data-testid`
> and file:line, how it is gated (hidden, disabled — by which condition), empty and error
> states. Mark the `me/` pages. Do not read the backend. One table, facts only.

**API & permissions**
> Read `api/app/models/auth.py` (`MODEL`), `api/app/auth.py`, every `api/app/routers/*.py`
> and the services they call for checks (`expenses.py`, `waivers.py`, `personal.py`). Per
> endpoint: method, path, purpose in one clause, who may call it (dependency, `can()`, a
> tuple check) — file:line, limits (sizes, counts, states), irreversible effects. Then the
> relation table: object type, relation, what implies it. Then how each relation is
> granted (which endpoint writes it, who may call that). Four tables. Do not read the UI.

**Vocabulary & errors**
> Read CLAUDE.md § Language and § Domain decisions, `docs/concepts.md`, every catalog in
> `web/src/i18n/locales/en/` and `de/`, and `api/app/problems.py` plus every
> `Problem(` call in `api/app/routers/`. Return: the domain terms en → de as the catalogs
> use them; per screen the labels a page will quote, `key → en → de`; every error code
> with its `errors.json` text in both locales and the situation that raises it (file:line);
> the German register per namespace (*Sie* / *du*). Quote, do not paraphrase.

**Runtime tour**
> Start `scripts/dev-stack.sh --workers 1`. With Playwright, sign in through
> `e2e/session.ts::signIn` as each seeded role (a club manager, `regatta@`, `orga@`,
> `jury@`, `helfer@`, `admin@`, a sailor, a guest) and visit every route that role reaches,
> in `en` and `de` (`localStorage["sbl.language"]`), desktop and Pixel 7. Screenshots into
> the scratchpad. Report what rendered, what failed, what data was there. Stop the stack.
> If it does not start, say exactly where — do not work around it.

## `.handbook-plan.md`

Written by the main thread, confirmed once, then immutable — an agent that thinks a row is
wrong reports it.

```markdown
# Handbook plan

route: /help       locales: en (source), de (register: Sie)       store: web/src/handbook/
story: B-<n> "I find the help for what I do"     absorbs: web/src/pages/Help.tsx (matrix → roles)

## Pages
| id | type | order | audience | stories | journey | route | anchors | shots | evidence |
|---|---|---|---|---|---|---|---|---|---|
| start-club-manager | start | 30 | club-manager | — | — | — | start-club-manager-season, … | — | club-manager.md |
| squad-and-lineup | guide | 20 | club-manager | V-1, V-2, V-12 | — | /me/club/:id | squad-and-lineup-squad, squad-and-lineup-crew, squad-and-lineup-size | lineup-panel, squad-panel | LineupPanel.tsx:…, routers/teams.py:…, test_lineup.py |
| journey-lifecycle | journey | 10 | administration, event-organizer, race-committee | (J-1's stories) | J-1 | — | journey-lifecycle-variations | — | journeys.md J-1, test_complete_lifecycle.py |
| roles | doc | 20 | all seven | Z-2, Z-5, F-3 | — | /help/roles | roles-list, roles-matrix, roles-getting | — | models/auth.py MODEL, auth.py |
| faq-sailor | faq | 10 | sailor | S-1, S-3, V-1 | — | — | faq-sailor-waiver, … | — | problems.py, errors.json |

## Shot list
| shot id | as | path | wait for | clip | phone |
|---|---|---|---|---|---|

## Cross-page links
squad-and-lineup-crew ← start-club-manager, journey-crew-cleared

## Gaps found in discovery (report, do not document)
- VA-5: the waiver lock on the lineup is not wired
```

Before showing it: every page has evidence; every audience in use has its `start-` page;
the reserved pages are there with their anchors; every ◐/● journey has a page; anchors are
unique and page-prefixed; `order` in steps of 10; every shot used is in the shot list; at
most one page per route.

## Build

**Viewer agent** (first pass)
> Build the `/help` viewer in `web/` per `.claude/skills/handbook/references/viewer.md`.
> Read `docs/components.md` and `docs/gotchas/INDEX.md` first, and one existing page to
> match its conventions. You own the files listed in `viewer.md` § The viewer and the
> tests in its § Test ids and tests, under story `<B-n>`. The store may be empty while you
> work. Add only `remark-gfm` (pnpm, in `web/`). Run `pnpm typecheck` in `web/` and at the
> root, `pnpm e2e:list`, and the new specs against `scripts/dev-stack.sh`. Commit. Report
> files written and removed, checks run and their result.

**Author — one per page, writes exactly two files**
> Write page `<id>` in `web/src/handbook/<id>.en.md` and `<id>.de.md`, nothing else. Read
> `.claude/skills/handbook/references/writing-guide.md`, `content-model.md` and
> `sources.md`. Your row: `<row>`. Evidence: `<stories with built/not-built criteria,
> files, endpoints>`. Labels: `<key → en → de>`. Runtime screenshots: `<paths>`.
> English first and complete, then German in the register `<register>`. Every claim
> traceable to code you have read — the story is where you start, not the proof. **No
> evidence → leave it out and list it.** Report: the files, anchors, shot ids, and every
> gap (claim without code, story contradicting code, missing label).

Add for **`roles`**: "Build it from `MODEL`, the dependencies in `api/app/auth.py` and the
tuple checks in the services — not from CLAUDE.md's table and not from what the screens
hide. Read every enforcement site you cite. Follow `writing-guide.md` § The roles page."

Add for a **`journey`** page: "Follow the journey's main steps in order, one row each,
linking to the anchor in that person's guide named in the plan's cross-page links. Read
the journey's test for the starting state and what each step leaves behind."

**Updater — one per cluster of ≤ 4 pages** (update): see `update-mode.md`.

## Screenshots

**Capture agent**
> Write `e2e/handbook-shots.spec.ts` per `.claude/skills/handbook/references/screenshots.md`
> with this shot list: `<list>`. Run it against `scripts/dev-stack.sh --workers 1`, both
> locales, phone shots where marked. Verify each `en`/`de` pair differs and no shot shows
> the role switcher. Commit. Report captured / skipped with reason / referenced but
> missing / captured but unreferenced.

## Clarity pass

One editor per type group (`start`+`journey`, `guide`, `doc`+`faq`) in the first pass; one
in update mode, scoped to the changed sections.

> Edit `<files>` (update: only sections `<anchors>`) per `writing-guide.md` § Concision
> pass and § Short. Never add or remove facts, change a quoted label, frontmatter, an
> anchor or a shot id. Both locales alike. Report words before → after per page.

## Validators and fixer

`python3 scripts/check-docs.py` first — its errors are blocking as they are, a fixer runs
without a validator. Then three read-only validators in one message, each given only its
section of `review-checklist.md`:

> Review the handbook just written. Read `.claude/skills/handbook/references/review-checklist.md`
> § `<section>` and run those checks on the working tree. Be adversarial; verify each
> finding in the code before reporting it. Return `{verdict, findings: [{severity, file,
> line, what, why, fix}]}` and nothing else. Change no files.

Per blocking verdict: a **fixer** scoped to exactly those findings ("fix these and nothing
else; do not rename ids, renumber `order` or touch other pages; rerun check-docs.py"), then
that validator again, at most 3 rounds (update 2). Still blocking → in the report, high
severity. Advisory findings go to the report verbatim.

## Guardrails

- One writer per file. The editor runs after the authors, never beside them.
- The plan is immutable after confirmation.
- Baseline last, after check-docs.py and `scripts/check.sh` are green.
- Report every skip: a page cut for lack of evidence, a shot not taken, a validator left
  blocking, a failing check.
