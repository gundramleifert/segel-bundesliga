---
name: finish-pr
description: Take finished work on a branch to a pull request the way CLAUDE.md's "From issue to merge" says — the issue, a fresh rebase on main, scripts/check.sh green, push, `gh pr create` with "Refs #N" — and, only when the user says merge, squash-merge it and hand the issue to the stakeholder on staging. Use when the user says "finish the PR/MR", "open the PR", "ship it", "merge it", or asks to commit and push work that is not on main yet.
argument-hint: "[issue number] | merge [PR number]"
---

# Finish a pull request

CLAUDE.md, section **From issue to merge**, is the rule; this is the procedure, with the
traps this repository and its sandbox have already shown. Work reaches `main` only
through a PR, a PR **refers** to its issue (`Refs #N`, never `Closes`/`Fixes`/
`Resolves`), and an issue is closed only when its stakeholder accepted it on staging.

`$ARGUMENTS` is empty, an issue number, or `merge` with an optional PR number.
`merge` jumps to step 7 — and is the **only** way to get there.

Run every `gh` and `git push`/`fetch` with `allowed_domains: ["api.github.com",
"github.com"]`. Work from the repository root (`segel-bundesliga/`).

## 1. `gh` must work — otherwise stop

```bash
gh auth status
```

Not installed or not signed in: **stop and hand it to the user** — the sandbox cannot
install packages or sign in, and there is no token here to go around it:

    ! sudo apt install gh      # or https://cli.github.com
    ! gh auth login

Do not fall back to pushing to `main`, and do not open the PR some other way.

## 2. Where are we?

```bash
git fetch origin
git status -sb
git log --oneline origin/main..HEAD
```

- **On `main` with commits ahead of `origin/main`:** they belong on a branch. Create it
  (step 3 names it), then move `main` back with `git reset --keep origin/main` — the
  commits are safe on the branch.
- **Uncommitted changes:** commit them on the branch first, in the story → test → code
  order CLAUDE.md asks. Stage paths explicitly — never `git add -A` or `git add .claude`
  (see the trap below).
- **Nothing ahead of `origin/main`:** there is nothing to finish; say so.

**The phantom change.** The sandbox cannot read `**/.env*`, so `git status` may list
`api/.env.example` as modified when nothing changed (docs/gotchas: a sandbox-denied file
looks like an empty file). Never stage or commit it. If it makes `git rebase`,
`git pull` or `git reset --keep` refuse, do the step in a worktree:
`git worktree add --detach "$TMPDIR/wt" origin/main`, cherry-pick there, push from there,
then `git worktree remove --force "$TMPDIR/wt"`.

## 3. The issue

The issue number comes from `$ARGUMENTS`, else from the branch name (`<N>-<slug>`), else
from a `#N` in the branch's commit messages.

**None exists:** create one — the user asked to finish the work, and the workflow needs
an issue. Title: what the change does for someone, not the code. Body: the story IDs it
implements (`docs/userstories/…`), their acceptance criteria in a sentence or two, and
"Opened for work already done on branch `<branch>`."

```bash
gh issue create --title "…" --body "…"
```

**Branch name:** new work gets `gh issue develop <N> --name <N>-<slug> --checkout` (that
links branch and issue). A branch that already exists and is pushed keeps its name — the
PR's `Refs #N` is the link; renaming a pushed branch only leaves a second one behind.

## 4. Rebase on a fresh `main`

```bash
git fetch origin
git rebase origin/main          # or the worktree route from step 2
```

Conflicts in **generated** files are regenerated, never merged by hand:

| File | Regenerate with |
|---|---|
| `docs/traceability.md`, `docs/stories.json`, `docs/gotchas/INDEX.md` | `python3 scripts/check-docs.py --fix` |
| `web/src/api/generated/**` | `scripts/gen-api-client.sh` |
| `api/alembic/versions/*_initial_schema.py` | `rm api/alembic/versions/*.py`, then `alembic revision --autogenerate -m "initial schema"` against a scratch database in `$TMPDIR` (CLAUDE.md, Migrations) |

After a rebase, check that the regenerated migration and client match what the branch
carries — git's rename detection can carry an upstream column across correctly, and then
there is nothing to change.

## 5. Everything green

```bash
scripts/check.sh
```

`check.sh` runs `pnpm` scripts, and pnpm refuses inside the sandbox when its store is not
writable (docs/gotchas: pnpm runs a store-writing lockfile check). Then run the same gates
directly, and report which way they ran:

```bash
python3 scripts/check-docs.py
(cd api && uv run ruff check . && uv run pytest -q)
(cd web && ./node_modules/.bin/tsc -b --force && ./node_modules/.bin/oxlint && ./node_modules/.bin/vite build)
```

`web/node_modules` missing: `pnpm install --frozen-lockfile --store-dir "$TMPDIR/pnpm-store"`
in `web/` (needs `registry.npmjs.org`). In a worktree, symlink the main checkout's
`web/node_modules` instead of installing twice, and remove the link before committing.

Red is not pushed. Fix it, or report it and stop.

## 6. Push and open the PR

```bash
git push -u origin HEAD                 # after a rebase of a pushed branch:
git push --force-with-lease origin HEAD # never a bare --force
```

```bash
gh pr create --base main --title "<what changed, for a person>" --body-file "$TMPDIR/pr.md"
```

The body, in this order:

```markdown
Refs #<N>

## What
<what someone can now do, by story ID>

## Why
<the decision behind it, where it was not obvious>

## How it was tested
<the story tests by name; the gates of step 5 and how they ran; what was not tried —
e.g. "not clicked through in a browser", "no e2e spec">

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

Give the user the PR's URL. **Stop here** unless they said merge.

## 7. Merge — only on the user's word

```bash
gh pr checks <PR>                        # anything red: report, do not merge
gh pr merge <PR> --squash --delete-branch
git switch main && git pull               # worktree route if the phantom blocks it
git branch -D <branch>
```

## 8. Hand over on staging

Staging (`https://sbl-web.onrender.com`, docs/deploy.md) redeploys from `main` in a few
minutes and **resets to the seeded data** each time. Check the change is visible there
before handing over (add `sbl-web.onrender.com` to `allowed_domains`). Then:

```bash
gh label create in-stakeholder-review --color FBCA04 \
  --description "Merged and on staging, waiting for the stakeholder's acceptance" 2>/dev/null
gh issue edit <N> --add-label in-stakeholder-review
gh issue comment <N> --body "…"
```

The comment says: the staging URL and the page, which seeded account to pick in the role
switcher (CLAUDE.md, Testing different roles), and the steps to reach the state the
change is about from fresh seed data — staging has none of the data you tested with.

**Never close the issue.** The stakeholder accepts on staging; then
`gh issue close <N> --comment "Accepted on staging"`. Not accepted: remove the label, and
the feedback is a new branch `<N>-<slug>-2` for the same issue, from step 3.
