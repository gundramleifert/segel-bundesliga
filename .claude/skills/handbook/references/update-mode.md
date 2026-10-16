---
title: Update mode — only what the change can have falsified
description: Finding the last baseline, mapping the diff since then to touched pages through the stories, journeys, routes and labels each page cites, the confirmation, the updaters, the reviewer and the new baseline.
---

# Update mode

A handbook is updated after features land — typically after an issue's PR was merged, or
before a stakeholder hand-over. The update touches what the change can have made wrong,
and leaves everything else, including human edits, alone.

## Step 1 — The baseline

`git log -1 --format=%H -- web/src/handbook/.baseline/` is the last reviewed state. No
baseline → this is a first pass after all.

## Step 2 — Diff → touched pages

`git diff --name-only <baseline>..HEAD`, then map. This is where the frontmatter pays: a
page says which stories, journey and route it documents.

| Changed | Touches |
|---|---|
| a story in `docs/userstories/` (its criteria, status, `Endpoints:`/`Screen:`) | every page with that ID in `stories:` — the **Handbook** column of `docs/traceability.md` lists them |
| a story turned ● (or a criterion turned "Built") | a **new** section or page — its audience's guide, and its `start-` page |
| a journey's steps or status | its `journey` page; a journey newly ◐ → a new page |
| `web/src/App.tsx` route | the page with that `route`, every page linking to it |
| `web/src/pages/**`, `web/src/components/**` | the pages whose `route` is that screen; shots taken there |
| a catalog key in `web/src/i18n/locales/` | every page quoting that label (grep the old string, both locales) |
| `api/app/models/auth.py`, `api/app/auth.py`, a permission check | `roles`, and the guides of the affected audience |
| `api/app/problems.py`, an `errors.json` entry | the FAQ pages |
| CLAUDE.md § Domain decisions | `terms`, and pages quoting the rule |

Per touched page: the sections (anchors) and the **facts** behind them, each with
file:line — "F3: squad maximum is now enforced per event too — routers/teams.py:88".

## Step 3 — Confirm

One screen: pages `keep` / `revise` / `new` / `retire`, facts per revised section, new
pages with audience and stories, shots to recapture. `Proceed?` A retirement follows
`content-model.md` § Structure lock (default: keep the page, say what is gone).

## Step 4 — Screenshots first

Rerun the capture spec (`screenshots.md`) before the updaters, so they see today's screens.
List the shots whose PNG changed materially; their captions get checked.

## Step 5 — Updaters ∥ new-page authors

> Update pages `<ids>` — `web/src/handbook/<id>.en.md` and `.de.md`, nothing else.
> Sections and facts: `<per page: anchors + facts with file:line>`. Diff excerpts: `<…>`.
> Current screenshots: `<paths>`. Labels: `<key → en → de>`. For each listed section, check
> every claim against the code now, fix what is false, add what is new and belongs there,
> both locales. **Every section not on your list stays byte-for-byte as it is** — a human
> may have edited it. `id`, `type`, `order`, `audience` and anchors are fixed; `stories:`
> follows the facts. Rules: `writing-guide.md`. A fact on your list that turns out wrong:
> say so, invent nothing. Report one line per fact, anchors before → after.

New pages: the author prompt from `orchestration.md`.

## Step 6 — Clarity, check, review, baseline

One editor on the changed sections; `python3 scripts/check-docs.py`; one reviewer
(`review-checklist.md` § update mode); fixer ≤ 2 rounds; `scripts/check.sh`;
`--handbook-snapshot`; commit.

## Full check instead

Do a full first-pass-style review (discovery agents, all validators) instead of a diff
when: the baseline is older than ~3 months of commits, the viewer was rebuilt, a whole
audience's screens were redesigned, or the reviewer finds two or more stale facts outside
the touched sections.

## Report additions

Pages by status, facts fixed vs open, shots that changed, stories newly ● that no page
covers yet, and what the diff could not see (behaviour changed by data or configuration
only).
