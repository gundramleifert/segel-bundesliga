---
title: Sources — where every page's evidence comes from
description: The stories and their status marks, the journeys, routes and screens, routers and services, the relation-tuple permission model, the typed errors and the i18n catalogs — what each one proves, what it does not, and which page it becomes.
---

# Sources

The handbook describes **what the site does today**. This repository has an unusually good
map of that: every behaviour is a story with a status and tests. The map is where an
author starts; the code is what an author checks.

## The rule of two

A claim needs **a story that says it and code that does it**.

| Story says it | Code does it | What to do |
|---|---|---|
| ● | yes | document it |
| ◐ / ○, or `Open:` | no | leave it out; it is planned, not shipped |
| ◐ / ○ | yes | document what the code does; report "built, but the story is not ●" |
| ● | no / differently | document the **code**; report the story as wrong — CLAUDE.md: "correct the story, and say what the cause actually was" |
| none | yes | document it if a person can see it; report "behaviour without a story" |

A ◐ story often says inside itself what is built: "**Built** — …", "**Not yet wired** …"
(VA-5). Only the built criteria are evidence.

## The audiences are the story files

| `audience` | Story file | Who in the permission model |
|---|---|---|
| `visitor` | `visitor.md` | not signed in, or signed in with no relation |
| `sailor` | `sailor.md` | in a squad or a crew (`sailor` in `/api/me/contexts`); every account (sign-in, profile, waiver) |
| `club-manager` | `club-manager.md` | `admin`, `manager`, `member` on a club |
| `event-organizer` | `event-organizer.md` | `manager` on an event, its series or its host club |
| `race-committee` | `race-committee.md`, the race-committee parts of `live.md` | `race_officer`, `jury`, `helper` |
| `treasurer` | `treasurer.md` | `treasurer` on a club or event, and anyone filing a claim |
| `administration` | `administration.md` | site `admin` / `editor` |

The letter of a story ID records where it was **first told**, not its audience
(`docs/userstories/README.md`): Z-2 sits in `administration.md`, A-5 in `visitor.md`.
Take the audience from the **file**, and from what the story's "As a …" says.

## Journeys become journey pages

`docs/journeys/<slug>.md`, indexed in `docs/userstories/journeys.md` with the **actors**: a
journey is several stories in the order they really happen, across several people. Each
actor names its help audience there — use it for the page's `audience`.

- **One `journey` page per journey** whose status is ◐ or ●. A ○ journey has no test, so
  nobody has proven its steps fit together — leave it out.
- The page follows the journey's **main steps in order**; each step is one line naming who
  acts and what is then true, and links to the `###` in that person's guide that explains
  how. The journey page itself explains no screen.
- The page's steps carry the journey's **step IDs** (`J-5.4`) — they are permanent, so a
  help page can cite them. Branches (`Path` ≠ `main`, the `opt`/`alt` blocks) become a
  short "If …" list at the end.
- Steps whose story is not ● are written only as far as the code goes, and reported.
- The journey's test is the strongest evidence there is: it proves the order. Read it —
  the walks on the journey's `Tests:` line (`docs/traceability.md` § Journeys lists them) — to learn the starting state and
  what each step leaves behind.

The journey page is what a club or an organizer reads **before** a season; the per-person
guides are what each of them reads **during** it.

## Screens and routes

- `web/src/App.tsx` — the route table. Every `route:` in a page's frontmatter and every
  in-app link must be a route here.
- `web/src/pages/**` — what a screen shows and offers, with `data-testid`s. The `me/`
  pages are "my space" (Stories Z-8, S-7): the place most guides start from.
- `docs/site-structure.md` — the public site's leagues, years, acts and URLs (issue #14).

## API and services

- `api/app/routers/*.py` and `api/app/services/*.py` — what is enforced, with which limits
  (file sizes, counts, states). A screen hiding a button is not a rule; the endpoint
  refusing it is.
- Domain rules that matter to a reader are often stated in CLAUDE.md § Domain decisions
  (no-shows get participants + 1, a cancelled event costs nobody points, closing freezes
  nothing). Use them as a pointer, confirm in code, and phrase them as what the reader
  experiences.

## The permission model → the roles page

- `MODEL` in `api/app/models/auth.py` — object types (`site`, `club`, `series`, `event`),
  relations, and what implies what (`or … from …`).
- `api/app/auth.py` — `require_site`, `require_on_event` and the other dependencies;
  `User.can(relation, on=obj)`.
- Special cases decided on the **tuple**, not on `can()`: expense decisions (F-3,
  `app/services/expenses.py`) — the site's editors are *not* every event's treasurer.
- CLAUDE.md § Permissions by area is a summary to check against, **not** the source.
  Today's `web/src/pages/Help.tsx` says it is built from that table; the roles page
  replaces it with one built from the model.
- How someone **gets** a relation: a club's `admin` writes `member` tuples (Z-5), an
  object's admin writes tuples on it, accounts are created by enrollment or import, not by
  signing up (`allow_self_signup`), registration via `SBL_ALLOW_REGISTRATION`.

## Errors and labels → the FAQ

- `api/app/problems.py` and the routers' `Problem(..., code, ...)` — every typed refusal a
  person can meet. `web/src/i18n/locales/{en,de}/errors.json` holds what the screen says
  for each `code`. A refusal a person meets often (`squad-sailor-in-another-club`,
  `waiver-birth-date-required`, `guardian-confirmation-needed`) is an FAQ entry: what it
  means, what to do.
- `web/src/i18n/locales/{en,de}/*.json` — every label a page quotes, per locale.

## Not evidence

- `docs/PLAN_*.md`, `plan-*.md`, `konzept-*.md`, `docs/findings.md` — plans and research.
- `Open:` paragraphs in stories, `Still to Write` in the stories README.
- `web/src/prototype/` — prototypes, not the site.
- `/api/dev` and the role switcher — development only; never in the handbook.
- `reference/` — other projects.
