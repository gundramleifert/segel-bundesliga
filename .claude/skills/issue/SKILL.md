---
name: issue
description: The whole life of a GitHub issue in this repository, as CLAUDE.md's "From issue to merge" lays it down — start work on an issue (read it, story first, branch), open the PR (rebase, checks, "Refs #N"), merge only on the user's word, hand over on staging with the in-stakeholder-review label and the board's Review column, and close only when the stakeholder accepted. Also files new issues for work found on the way and shows what waits on whom. Use for "work on issue 42", "start #42", "open/finish the PR", "ship it", "merge it", "hand it over", "it was accepted", "make an issue for this", "what is waiting", or any commit-and-push of work that is not on main yet.
argument-hint: "start <N> | pr [N] | merge [PR] | handover <N> | accepted <N> | rejected <N> | new <title> | status"
---

# One issue, from request to accepted

CLAUDE.md, section **From issue to merge**, is the rule; this is the procedure, with the
traps this repository and its sandbox have already shown. The invariants, whichever step:

- **Nothing reaches `main` except through a PR**, and nothing is merged without the
  user's explicit word.
- **A PR refers to its issue** — `Refs #N`, never `Closes`/`Fixes`/`Resolves`.
- **An issue is done when its stakeholder accepts it on staging**, not when its PR merges.
  This skill never closes an issue on its own initiative.
- **One issue, one branch, one PR.** Work found on the way that is not this issue's
  becomes a new issue (`new`), not an extra commit.

`$ARGUMENTS` picks the phase. Empty: work it out from the state (`status` first) and say
which phase you are in before acting.

| Phase | Does | Ends with |
|---|---|---|
| `start <N>` | read the issue, story first, branch | the user's go, then the work on the branch |
| `pr [N]` | issue found or created, rebase, checks, push, PR | the PR's URL — **stop** |
| `merge [PR]` | checks, squash-merge, `main` pulled | then `handover` |
| `handover <N>` | staging checked, label, comment | the stakeholder's turn |
| `accepted <N>` / `rejected <N>` | close, or the next round | — |
| `new <title>` | an issue for something found on the way | its number |
| `status` | what waits on whom | — |

## Before any phase: `gh` must work

Every `gh`, `git fetch`, `git pull` and `git push` runs with
`allowed_domains: ["api.github.com", "github.com"]`, from the repository root.

```bash
gh auth status
```

Not installed or not signed in: **stop and hand it to the user** — the sandbox cannot
install packages or sign in, and there is no token to go around it:

    ! sudo apt install gh      # or https://cli.github.com
    ! gh auth login

Never fall back to pushing to `main`, or opening anything some other way.

**The board.** Every issue is a card on the project board
[MVP Segel-Bundesliga Webpage](https://github.com/users/gundramleifert/projects/1)
(user project 1, linked to the repository). Its **Status** field is the column:
**Todo → In Progress → Review → Done**, where Review means what the
`in-stakeholder-review` label means — merged, on staging, waiting for the stakeholder.
The phases below move the card; label and column always change together. Moving it:

```bash
# the card's item id (add the issue first if it is not on the board yet)
gh project item-add 1 --owner gundramleifert --url "$(gh issue view <N> --json url -q .url)" --format json -q .id
# the ids of the project, the Status field and the wanted option — looked up by name,
# so a renamed or re-created option never sends a card to the wrong column
gh project view 1 --owner gundramleifert --format json -q .id
gh project field-list 1 --owner gundramleifert --format json \
  -q '.fields[] | select(.name=="Status") | .id, (.options[] | "\(.name)=\(.id)")'
gh project item-edit --project-id <project id> --id <item id> \
  --field-id <Status field id> --single-select-option-id <option id>
```

`item-add` is idempotent: for a card already on the board it returns the existing item.
Needs the token's `project` scope (`gh auth status`); without it, say so and leave the
column to the user rather than skipping the label.

**The phantom change.** The sandbox cannot read `**/.env*`, so `git status` may list
`api/.env.example` as modified when nothing changed (docs/gotchas: a sandbox-denied file
looks like an empty file). Never stage it. If it makes `git switch`, `git pull`,
`git rebase` or `git reset --keep` refuse, do that step in a worktree:
`git worktree add --detach "$TMPDIR/wt" origin/main`, work and push from there, then
`git worktree remove --force "$TMPDIR/wt"`; or ask the user to run the one git command
outside the sandbox with `!`.

---

## `start <N>` — from request to branch

1. **Read it all:** `gh issue view <N> --comments`. Who asked (the stakeholder — they
   accept it later), what they want to be able to do, and any decision already made in
   the comments.
2. **Ambiguous?** Ask **on the issue** (`gh issue comment <N>`) and tell the user you did —
   not a guess in code. Ask the user directly only for what they decide themselves.
3. **The story first** (CLAUDE.md, How to update the docs). New or changed behaviour
   becomes a story, or an edit of the existing one, in `docs/userstories/` — the file of
   the person who tells it, the next free ID of its letter, status ○, acceptance criteria
   from the issue, and a line "Issue #N". The story is the lasting record; the issue is
   the request. A pure bug fix in already-described behaviour needs no new story, but the
   story whose criterion broke gets its test.
4. **Show the plan and wait for the user's go** when the issue leaves real choices open;
   a small, clear issue goes straight on.
5. **Branch from a fresh `main`:**
   ```bash
   git switch main && git pull
   gh issue develop <N> --name <N>-<slug> --checkout   # links branch and issue
   ```
   English, kebab-case, a few words: `42-waiver-reminder-mail`.
6. **Do the work** in the order CLAUDE.md fixes: story → test (watch it fail for the
   right reason) → code → status mark and `Tests:` line → domain rule in CLAUDE.md if it
   outlives the story → a gotcha if you were wrong on the way. Commit on the branch,
   staging paths explicitly — never `git add -A`, never `git add .claude`. Mention `#N` in
   the commit body where it helps.
7. Card → **In Progress** (see The board) once the branch exists.
8. When it is done, go on with `pr`.

## `pr [N]` — from branch to pull request

1. **Where are we?**
   ```bash
   git fetch origin && git status -sb && git log --oneline origin/main..HEAD
   ```
   On `main` with commits ahead: they belong on a branch — create it (step 2 names it),
   then `git reset --keep origin/main` on `main`; the commits are safe on the branch.
   Uncommitted work: commit it first. Nothing ahead of `origin/main`: nothing to do, say so.
2. **The issue:** from `$ARGUMENTS`, else the branch name (`<N>-<slug>`), else a `#N` in
   the branch's commits. **None exists** — work done before the workflow, or without an
   issue: create it with `new` (title: what someone can now do; body: the story IDs and
   their criteria in a sentence or two, "Opened for work already done on branch
   `<branch>`"). A branch already pushed keeps its name; `Refs #N` is the link, and
   renaming a pushed branch only leaves a second one behind.
3. **Rebase on a fresh `main`:** `git fetch origin && git rebase origin/main` (or the
   worktree route). Conflicts in **generated** files are regenerated, never merged by hand:

   | File | Regenerate with |
   |---|---|
   | `docs/traceability.md`, `docs/stories.json`, `docs/gotchas/INDEX.md` | `python3 scripts/check-docs.py --fix` |
   | `web/src/api/generated/**` | `scripts/gen-api-client.sh` |
   | `api/alembic/versions/*_initial_schema.py` | `rm api/alembic/versions/*.py`, then `alembic revision --autogenerate -m "initial schema"` against a scratch database in `$TMPDIR` (CLAUDE.md, Migrations) |

   Then compare: git's rename detection sometimes carries an upstream column into the
   regenerated migration correctly, and then there is nothing to change.
4. **Everything green:** `scripts/check.sh`. pnpm refuses inside the sandbox when its store
   is not writable (docs/gotchas: pnpm runs a store-writing lockfile check) — then run the
   same gates directly and say so:
   ```bash
   python3 scripts/check-docs.py
   (cd api && uv run ruff check . && uv run pytest -q)
   (cd web && ./node_modules/.bin/tsc -b --force && ./node_modules/.bin/oxlint && ./node_modules/.bin/vite build)
   ```
   `web/node_modules` missing: `pnpm install --frozen-lockfile --store-dir
   "$TMPDIR/pnpm-store"` in `web/` (needs `registry.npmjs.org`); in a worktree, symlink the
   main checkout's instead and remove the link before committing. **Red is not pushed** —
   fix it, or report it and stop.
5. **Push** — `git push -u origin HEAD`; after rebasing a pushed branch
   `git push --force-with-lease origin HEAD`, never a bare `--force`.
6. **Open the PR** — `gh pr create --base main --title "<what changed, for a person>"
   --body-file "$TMPDIR/pr.md"`, the body in this order:
   ```markdown
   Refs #<N>

   ## What
   <what someone can now do, by story ID>

   ## Why
   <the decision behind it, where it was not obvious>

   ## How it was tested
   <story tests by name; the gates and how they ran; what was not tried —
   "not clicked through in a browser", "no e2e spec">

   🤖 Generated with [Claude Code](https://claude.com/claude-code)
   ```
7. Give the user the URL. **Stop.** Merging is `merge`, on their word only.

## `merge [PR]` — only on the user's word

"Looks good" is not a merge instruction; "merge it" is. The PR defaults to the current
branch's.

```bash
gh pr checks <PR>                          # anything red: report, do not merge
gh pr merge <PR> --squash --delete-branch  # main stays one commit per PR
git switch main && git pull                # worktree route if the phantom blocks it
git branch -D <branch>
```

Then `handover`.

## `handover <N>` — the stakeholder's turn

Staging (`https://sbl-web.onrender.com`, docs/deploy.md) redeploys from `main` in a few
minutes and **resets to the seeded data** on every deploy.

1. **Check the change is live** before telling anyone — fetch the page or endpoint it is
   about (add `sbl-web.onrender.com` to `allowed_domains`). Not there after ten minutes:
   look at the deploy (the render plugin's skills), don't hand over.
2. **Label** — created once, harmless when it exists:
   ```bash
   gh label create in-stakeholder-review --color FBCA04 \
     --description "Merged and on staging, waiting for the stakeholder's acceptance" 2>/dev/null
   gh issue edit <N> --add-label in-stakeholder-review
   ```
   and the card → **Review** (see The board).
3. **Comment** (`gh issue comment <N>`), written for the stakeholder, not a developer —
   in the language the issue was written in: the staging URL of the page; which seeded
   account to pick in the role switcher (CLAUDE.md, Testing different roles); the steps
   from fresh seed data to the state the change is about, since staging has none of the
   data the work was tested with; and what to look at.

## `accepted <N>` / `rejected <N>`

- **Accepted** (the stakeholder said so, on the issue or to the user):
  `gh issue close <N> --comment "Accepted on staging"`, after removing the label; the
  card → **Done** (the board's "Item closed" workflow may already have moved it — check,
  don't assume).
- **Not accepted:** `gh issue edit <N> --remove-label in-stakeholder-review`, and the
  card back → **In Progress** when the next round starts (**Todo** until then). Feedback on
  *this* request is a new branch `<N>-<slug>-2` for the same issue — back to `start`, from
  step 3. Feedback that is really a new wish becomes a new issue (`new`); this one stays
  open until it is accepted.

## `new <title>` — something found on the way

`gh issue create --title "…" --body "…"`: what someone cannot do today, where it was
noticed (file, story ID), and why it is not part of the current issue. Add it to the
board in **Todo** (`gh project item-add`, then the Status as in The board). Give the user its
number; don't start it unasked.

## `status` — what waits on whom

The board shows the same at a glance:
<https://github.com/users/gundramleifert/projects/1>.

```bash
gh issue list --label in-stakeholder-review     # waiting on stakeholders
gh pr list --author @me                         # waiting on the user's merge
gh issue list --assignee @me                    # waiting on us
git log --oneline origin/main..HEAD             # this branch, not yet in a PR
```
