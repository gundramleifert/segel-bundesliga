# A stash-and-rerun on the same long-lived dev stack proves the stack, not main

**Symptom** — `help.spec.ts` › *board gets a link to their club's Money tab* failed with
`Expected: "/me/club/7?tab=money"`, `Received: "/me/club/1?tab=money"`; later
`my-space.spec.ts` › *the sailor sees the badge…* (`layout-profile-badge` not found) and
`editorial.spec.ts` › *the list filters…* (`state=published` missing from the URL) joined it.
`git stash`, rerun, still red — so it was reported as "already broken on main".

**Cause** — the suite ran against one `scripts/dev-stack.sh --dev` stack that had been up
for hours, been clicked through by hand and already served a full run: its database was
no longer the seed. What misled: the stash-and-rerun reproduced the failure, which looked
like proof it predated the change — but it ran on the same database, so it proved only
that the *stack* was dirty. On a fresh `dev-stack.sh --workers 4` all three passed.

**Rule** — before calling a browser failure pre-existing, rerun it on a freshly seeded
stack (`dev-stack.sh --workers 4`, the suite's own setup), never on one you have been using.
A run writes (`lifecycle.spec.ts`, waivers, posts), so the second run on the same database
is a different test.

**Evidence** — the same tree: 3 failed of 130 on the hours-old `--dev` stack
(`--workers 1 --project=chromium`), 259 passed of 260 (1 skipped) on a fresh
`--workers 4` stack, 2026-10-21.

**Seen** — 2026-10-21, while moving every page to named colours.
