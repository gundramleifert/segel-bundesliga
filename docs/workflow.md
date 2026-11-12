# From issue to merge — the full text

Moved out of `CLAUDE.md` on 2026-11-12 (review 8.1), word for word — the issue workflow (the `/issue` skill walks it), the habits and the language rules.

### From issue to merge

Work is tracked as **GitHub issues** on `gundramleifert/segel-bundesliga`. **Committing
directly to `main` is allowed** (the user's decision): a branch and a pull request are for
work someone should read before it lands, not a gate on every change. The steps below are
that branch-and-PR path; **`/issue`** (`.claude/skills/issue/`) walks it — `start <N>`,
`pr`, `merge` (only on the user's word), `handover`, `accepted` / `rejected`, plus `new`
and `status`. The tool is the `gh` CLI (`gh auth login` once; in the sandbox it needs
`api.github.com` and `github.com`).

**An issue is done when its stakeholder accepts it on staging, not when its PR merges.**
Many issues come from stakeholders, and they judge a change by using it, not by reading a
diff — and the place they can use it is **staging**. Today that is still the Render
instance (`render.yaml`, free tier, reseeded on every start, **with** the dev login);
it is to be replaced by a second Compose stack (`docs/deploy-server.md`) which, like
production, runs **without the dev login** (`compose.yaml` fixes it off). So the
PR **refers** to the issue and never closes it, and between merge and close the issue
carries the label **`in-stakeholder-review`**. While nothing is in production, `main` is
allowed to hold changes not yet accepted; that changes when there is a production.

1. **Read the issue** — `gh issue view <N> --comments`. If it describes new or changed
   behaviour, its acceptance criteria become a story (or an edit to one) in
   `docs/userstories/`, as below; the story is the lasting record, the issue the request.
   Ask on the issue (`gh issue comment <N>`) rather than guessing when it is ambiguous.
2. **Branch from a fresh `main`** — `git switch main && git pull`, then
   `gh issue develop <N> --name <N>-<short-slug> --checkout`, which also links the branch
   to the issue. English, kebab-case: `42-waiver-reminder-mail`.
3. **Commit on the branch** as usual — the story, test, code order below still holds.
   Mention `#<N>` in the message body where it helps; the PR carries the link anyway.
4. **`scripts/check.sh` green, then push and open the PR** —
   `git push -u origin HEAD`, then `gh pr create --base main` with a title saying what
   changed and a body that starts with **`Refs #<N>`** — never `Closes`/`Fixes`/`Resolves`,
   which would close the issue on merge, before anyone has seen it — followed by what
   changed, why, and how it was tested.
5. **Merge only when the user says so** — `gh pr merge <PR> --squash --delete-branch`.
   Squash keeps `main` one commit per PR; its message is the PR title. Then
   `git switch main && git pull` and delete the local branch.
6. **Hand over to the stakeholder once staging runs the change** — the deploy takes a
   few minutes; check the change is visible there first. Then
   `gh issue edit <N> --add-label in-stakeholder-review` and comment on the issue
   (`gh issue comment <N>`): the staging URL, which role their own staging account
   needs (granted to it there — staging has no role switcher), and what to try. Staging resets to the seeded data on every deploy, so
   say how to get to the state the change is about.
7. **Accepted → close** — `gh issue close <N> --comment "Accepted on staging"` (or the
   stakeholder closes it). **Not accepted** → remove the label, and the feedback is a new
   branch for the **same** issue (`<N>-<slug>-2`) from step 2; the issue stays open until
   it is accepted. Feedback that is really a new wish becomes a new issue.

`gh issue list --label in-stakeholder-review` is the list of what waits on stakeholders.
The label is created once: `gh label create in-stakeholder-review --color FBCA04
--description "Merged and on staging, waiting for the stakeholder's acceptance"`.

Work found along the way that is not this issue's becomes **a new issue**
(`gh issue create`), not an extra commit on this branch — a PR about one issue is one a
reviewer can read.


### Language

**English is the working language everywhere** — code, identifiers, comments, docstrings, commit
messages, API responses, and UI are all English first. We maintain German as a full, real second
language using **i18n (internationalization)**, not as German-only source text or loanwords.

**Frontend:** React uses `react-i18next`. Locale files live in `web/src/i18n/locales/`:
- `en/*.json` — English source strings (one namespace per page: `common`, `start`, `events`,
  `standings`, `clubs`, `club`, `sailor`, `matchday`, `account`, `admin`, `dev`)
- `de/*.json` — German translations of the same namespaces

Messages are **ICU MessageFormat** (`i18next-icu`): `{name}` for a value, and a plural is one
key — `{count, plural, one {# event} other {# events}}` — never i18next's `{{name}}` or
`_one`/`_other` keys. A message that does not parse is shown raw without an error, so
`pnpm check:i18n` (part of `check.sh`) parses every one and compares placeholders across
languages.

A language switcher in the UI lets visitors choose English or German at runtime. English is the
default and source language.

**Backend** (decided 2026-10-28) — what the server words itself, in three places, never a
sentence written twice at a call site:
- **Errors** are typed Problems, worded by the frontend (below) — the backend sends a code.
- **Mails** are **Jinja2 templates**, one file per mail and language,
  `app/templates/mail/<lang>/<name>.txt`, each extending its language's `_base.txt` (the
  footer every mail ends with — the association, why the mail came, whom to write to,
  privacy and legal notice, linked on `SBL_SITE_URL`) and filling the blocks `subject`,
  `reason` and `body`; `app/mail.py::render_mail` renders them, `StrictUndefined`, so a
  missing value raises instead of leaving a hole. The common shape for mail in Python.
- **The few sentences a route answers** are TOML catalogs,
  `app/locales/<lang>/<namespace>.toml`, read by `t(locale, "auth.register.sent",
  minutes=10)` (`app/i18n.py`); placeholders are `{name}`, the ICU simple argument the
  frontend uses too. `resolve_locale` reads `Accept-Language` and defaults to English;
  docstrings and Field descriptions stay plain English.

`tests/unit/test_i18n.py` and `tests/unit/test_mail.py` are the gate, as `pnpm check:i18n`
is the frontend's: every language has the same keys and mails with the same placeholders,
and every key the code names exists.

**Mails are German by default** (decided 2026-10-28, `app/mail.py::MAIL_LOCALE`): a
mail has no language switcher and its readers are German clubs and sailors; English is
the other template, for a caller that knows the reader's language.

**Errors — RFC 9457 Problem Details** (`api/app/problems.py`, `web/src/api/problems.ts`,
concept in `docs/concepts.md`): error responses are `application/problem+json`. A router
raises `Problem(status, code, title, **extra)`; the stable `type` (`/errors/<code>`) is the
contract, and the frontend maps `<code>` to the `errors` i18n namespace. Typed errors carry
**no** sentence of their own. Routers raise only `Problem`, never a bare `HTTPException`;
validation errors are rendered as problem+json too (generic type, `detail` preserved).

**Domain terms** — the German word and the English one used in code, docs and comments:
Wettfahrt → Race, Flight → Flight (unchanged), Spieltag → Matchday, Wettfahrtleitung → Race
committee, Serie → Series, Verein → Club, Segler → Sailor, Mannschaft → Team, Kader → Squad,
Aufstellung → Lineup, Liga → League, Jahrgang → Year, Boot → Boat, Pairing-Liste → Pairing
list, Ausrichter → Host club, Revier → Venue.

### Working here

Four habits. They exist because each one was learned the expensive way, and the cost of
re-learning falls on whoever comes next.

#### Before you debug, read `docs/gotchas/INDEX.md`

One line per note — the whole folder skimmable for the price of one file. Read it at the
start of a task, and open the note whose rule matches what you are about to touch or what
just surprised you. These are things **not** deducible by reading the code harder: a library
that owns a CSS token name we also wanted, an assertion that passes because the bug it
guards against hides itself, a sandbox rule that makes a working command fail in the next
call.

The index is generated — `scripts/check-docs.py --fix` — and `scripts/check.sh` fails if it
is stale, so it cannot quietly drift out of date.

#### When you were wrong, write it down

This is the part that is easy to skip and the part that pays. Write a note when you were
**confidently wrong** — you named a cause, acted on it, and it was something else — or when
a surprise cost more than ~15 minutes, or when a symptom pointed away from its cause, or
when a green check turned out to protect nothing.

Say *what misled you*, in one line, under **Cause**. That line is the whole point: it is
the hint the next agent needs before they start, and the part no amount of code-reading
recovers. `docs/gotchas/README.md` has the format and the rules for keeping the folder
honest — including deleting an entry once it stops being true, which is a real
contribution, not housekeeping.

    scripts/check-docs.py --new "a sentence stating the rule"   # scaffolds the note
    scripts/check-docs.py --fix                                 # refreshes the index

Do not write a note for an ordinary bug you fixed, or for something `CLAUDE.md` and
`docs/concepts.md` already say. Noise is what makes the next person stop reading the folder.

**Do this before you report the work finished, not after.** By the next session the
reasoning is gone and only the diff is left — and the diff is precisely the part that does
*not* carry why you first went the wrong way. A task where you were wrong at least once,
and no note came out of it, is a task that quietly threw away its most useful product.

#### A rule is a check, not a sentence

A rule that lives only in this file gets broken — by the next agent that never read the
paragraph. So every rule that can be checked is: **ruff** where an import says it
(`TID251` in `api/pyproject.toml` — `HTTPException`, the `Grant` table outside
`authz.py`/`grants.py`), and **`api/tests/architecture/test_rules.py`** for the rest —
one writer per status, one creator per `Team`, no router importing a router, **no router
gaining a query** (a router parses, authorizes, calls a service, serializes — review 7.3),
no stored point or standing, **every route open without sign-in listed with its reason**
(`tests/architecture/test_access.py`), **who may call a covered route on one club, and
everyone else refused** (`tests/architecture/test_authorization.py` — a row per route,
modules not yet covered in its `NOT_YET` ratchet), every
`Problem` code worded in both languages, `CLAUDE.md`'s permission table against `MODEL`.
Each rule keeps its known violations in a list with their item in
`docs/REVIEW_2026-11.md`, and the list is a **ratchet**: a new violation fails, and so
does a fixed one still listed — `RUF100` does the same for a `# noqa` that suppresses
nothing. **Never add to a list to get green; fix the code.** A known defect in behaviour
is a test of the right behaviour marked `xfail(strict=True)`
(`tests/architecture/test_known_defects.py`): it passes the day the fix lands, and
`strict` makes that a failure until the marker goes. A new rule in this file comes with
its check, or says why there cannot be one.

#### When you do something twice, make it a function

Repeated work is a design signal, not a chore. The rule of thumb: the second time, notice;
the third time, extract — and put the reasoning in the extracted thing, where it will be
read.

What already exists, and what each one replaced:

- **`scripts/check.sh`** — every gate that must be green, in fail-fastest order. Run it
  before you commit. It encodes two traps: `tsc --noEmit` checks *nothing* in the web
  project (project references — the real check is `pnpm typecheck`), and the Playwright
  specs plus `playwright.config.ts` are only covered by the **root** tsconfig.
- **`scripts/dev-stack.sh`** — seeds a throwaway database and runs both servers, which is
  what the e2e suite needs and deliberately does not start itself. It also keeps the suite
  away from the development database, which `lifecycle.spec.ts` would otherwise fill with
  test rows.
- **`e2e/layout.ts::expectNoSidewaysScroll`** — the "does this page fit its viewport"
  check, which has to assert *two* numbers to work at all, and which names the offending
  boxes when it fails so nobody writes that probe again.
- **`web/src/components/`** — the pieces every screen is assembled from, listed in
  `docs/components.md`: `Async` (one request, rendered: loading, error, empty, content),
  `Stack` and `CardGrid` (the two layouts, one of which *is* Story A-10 — a bare `grid`
  zooms the page out on a phone), `LinkCard`, `TabbedView`, and the form primitives. Read
  that file before writing a page; each entry replaced three or more hand-written copies
  that had already drifted apart. A component never imports from `pages/`.
- **`web/scripts/check-colours.mjs`** — a page names its colours (`text-muted`,
  `bg-warning-soft`), never shades (`text-slate-500`): the theme is the variables behind
  the names, so a shade is a page that breaks in the other theme. `docs/components.md`
  § Colours.
- **`scripts/check-docs.py`** — makes the documentation prove itself: every `Tests:`
  reference must resolve to something that exists, every story ID a test claims must be a
  real story, every gotcha must carry its Evidence, and the index must be current. It is
  part of `check.sh`, so the docs cannot rot silently between commits.

A tool nobody trusts is worse than none, so **verify a new check by breaking something on
purpose** and watching it fail. `check-docs.py` was run against a renamed class, a deleted
file, an invented story ID and a note with its Evidence removed before it was believed —
each one caught. A check that has never failed has not been tested; it has only been run.

#### How to update the docs when you change something

Order matters, and it is the order the project already follows:

1. **The story first** (`docs/userstories/`, the file of the person who tells it). New behaviour is described before it is
   built — a story with acceptance criteria, and the reasoning for any decision that was
   not obvious. If you are changing existing behaviour, edit that story rather than adding
   a second one beside it.
2. **Then the test**, naming its story ID in the docstring. Watch it fail for the reason
   you expect; a test that passes before the code exists is testing nothing.
3. **Then the code.**
4. **Then the status marker and the `Tests:` line** — ○ open, ◐ partial, ● implemented
   *and tested*. Every `Tests:` reference must resolve to a node that actually exists;
   stale references are worse than none, because they make the document look checked when
   it is not.
5. **A domain rule that will outlive the story goes in this file**, under Domain decisions,
   in one or two sentences. A surprise that will not goes in `docs/gotchas/`.

If a story turns out to have recorded the wrong cause — it happens; A-10 blamed a
`flex-wrap` header for weeks — **correct the story**, and say what the cause actually was.
The narrative in a story is read by the next person as fact.

