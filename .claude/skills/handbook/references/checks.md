---
title: Checks — the handbook in scripts/check-docs.py
description: What to add to scripts/check-docs.py so the handbook proves itself — parity, anchors, links, story and journey references, staleness against story status, screenshots — plus the structure baseline and the traceability column.
---

# Checks

`scripts/check-docs.py` already makes the stories, tests, journeys and gotchas prove
themselves, and `scripts/check.sh` runs it. The handbook joins it there — not a separate
script: one place that answers "do the docs still match". The first pass adds
`check_handbook()`; every rule below is verified by **breaking it on purpose** once
(CLAUDE.md: "A check that has never failed has not been tested").

## Errors (fail `check.sh`)

Store:
- a page missing a locale; frontmatter (other than `title`) differing between locales;
  the file name's id ≠ `id`; frontmatter the restricted parser cannot read;
- an unknown `type` or `audience`; a `guide` with ≠ 1 audience; `order` not unique in its
  type;
- the same `###` anchor twice in the store; a `###` without an anchor; a `#anchor` link no
  page owns; the anchor sets of the two locales differ;
- an internal link or `route` that is not a route in `web/src/App.tsx`;
- a `shot:` id differing between locales;
- a reserved page (`roles`, `terms`, a `start-<audience>` for each audience in use) missing,
  or missing its fixed anchors.

Against the stories and journeys:
- a `stories:` ID that is not a story (`STORY_HEADING`, the same index the other checks use);
- a `journey` page whose `journey:` is not a journey, or whose step list (the `#` column)
  does not follow the journey's main steps in order;
- a page citing **only** stories marked ○ — it documents nothing that exists.

Structure lock (`content-model.md` § Structure lock): compare with
`web/src/handbook/.baseline/` and report `removed-page`, `reorder`, `retype`,
`lost-anchor`, `lost-locale`, `audience-dropped`. No baseline → every page is new, no error.

## Warnings (printed, not failing)

- a page citing a story that is ◐ — check the page documents only the built part;
- a `shot:` with no PNG under `web/public/handbook/screenshots/`; a PNG no page uses;
- a ● story in a story file of an audience whose pages cite it nowhere — a task nobody
  explains yet;
- a page over the length budget (`writing-guide.md` § Short), counted without tables.

`check-docs.py` has no warnings channel yet: add one, printed after the problems, so a
warning never fails the gate and never hides.

## `--fix`

- `--fix` keeps doing what it does (stories.json, traceability, the gotchas index) and adds
  a **Handbook** column to `docs/traceability.md`: story → the pages that cite it. That
  column is also what update mode reads (`update-mode.md`).
- `--handbook-snapshot` writes `web/src/handbook/.baseline/` (frontmatter and anchors of
  every page, not the prose). Run only as the last step of a reviewed run, and commit it on
  its own: that commit is what the next update diffs against.

## Proving the checks

Before believing them, break each once and watch it fail: a deleted `de` file, a duplicate
anchor, a link to `#nonexistent`, a `route: /nowhere`, an invented story ID, a changed
`order` against the baseline, a journey page with two steps swapped. Restore, rerun, green.
