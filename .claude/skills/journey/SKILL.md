---
name: journey
description: Writes, extends and checks user journeys in docs/journeys/ — several stories in the order they really happen, across the people who take part, as a Mermaid sequence diagram plus a step table with stable step IDs (J-n.k), walked by pytest or Playwright tests, and traced through to the help pages and the Allure report. Use for "make a journey for …", "user journey", "Ablauf/Prozess von … bis …", "draw the flow", "which tests prove this flow", "add a step/branch to J-3", "a feature changed — which journeys does it touch", or a stakeholder's journey issue. NOT for a single story (docs/userstories/) or the in-app help (the handbook skill).
argument-hint: "new <what someone gets done> | extend <J-n> <change> | check [J-n] | touched <story or path>"
---

# Journeys

A journey answers one question a single story cannot: **does each step's output really
feed the next step**, across people, in the order it happens. It is the stakeholder's view
(a diagram they can read), the developer's contract (a step table the checker enforces) and
the head of the traceability chain:

```
journey step J-5.4 ──names──▶ story V-2 ──Tests:──▶ test_lineup.py, club.spec.ts
      │                            │                         │
      └──walked by step("J-5.4")   └──cited by help page ────┴──▶ Allure: story "V-2 · …",
         in a journey test            (web/src/handbook/)         step "J-5.4 · V-2: …"
```

`docs/traceability.md` (generated, § Journeys) is that chain written down, one table per
journey. Read **`docs/userstories/journeys.md`** first — it is the format, the **actor
list** and the index; this skill is the procedure. `$ARGUMENTS` picks the mode.

## Invariants

- **The story first.** Every step names exactly one existing story. A step without one is
  a missing story: write it (`docs/userstories/<person>.md`, CLAUDE.md "How to update the
  docs") before the journey uses it — never invent behaviour inside a journey.
- **Describe what is built.** Verify each step against the router, the permission check
  and the service before writing it. What is decided but not built goes under `Open:`,
  not into a step.
- **Actors only from the list** in `journeys.md` § Actors, with their diagram alias. Need
  a new one? Add the row (who it is, relation, story file, help audience) first, and say
  why in the report — usually it means a new relation or story file too.
- **Step IDs are permanent.** `J-n.k` is never renumbered or reused; a new step takes the
  next free `k`, a removed one goes on `Retired steps:`. Tests and help pages carry them.
- **The table is the truth, the diagram its view** — same steps, same order.
- **Through the HTTP API only** in a pytest walk; nothing reached around into the
  database except to arrange what no endpoint creates (and say so in a comment).

## `new` — a journey from a request

1. **Pin it down** (from the issue — stakeholders use the form `.github/ISSUE_TEMPLATE/journey.yml`, whose fields map onto the file's sections — or ask once if genuinely unclear): what someone gets
   done, start state, goal, who takes part. One journey = one goal. "Create a club and
   manage it" and "a sailor joins" are two journeys, not one with branches.
2. **Map the stories.** `grep -n "^### " docs/userstories/*.md`; read each candidate's
   acceptance criteria and `Endpoints:`. Prefer ● stories; a ◐/○ step is allowed but
   keeps the journey ◐.
3. **Verify against the code** — for every step: the endpoint, who may call it
   (`api/app/auth.py`, `User.can`, the tuple checks in `app/services/`), what it returns,
   what it refuses. Note where a story and the code disagree: that is a story to correct,
   and worth reporting.
4. **Number it**: the next free `J-n` (`ls docs/journeys/`, the index in `journeys.md`).
5. **Write `docs/journeys/<slug>.md`** in the format: heading `# J-n ○ <goal>`, the why,
   `Who:` `Starting point:` `Goal:`, the diagram, the table, `Retired steps: none`,
   `Open:`, `Tests:`. Branches: `opt` for "may happen", `alt`/`else` for "one or the
   other" — each arm's steps carry the branch's name in `Path`. Offline steps (a guardian
   signing paper) say `(offline)` in `Who`.
6. **Add it to the index** in `journeys.md` (the checker refuses an unlisted file).
7. **Walk it** — see Tests below. Then set the marker by the rule (○/◐/●).
8. `python3 scripts/check-docs.py --fix` and `python3 scripts/check-docs.py`; then the
   walk(s) and `scripts/check.sh`.
9. **Report**: the diagram's step list, stories used, stories found wrong or missing,
   `Open:` decisions for the stakeholder, the warnings (uncovered steps).

## `extend <J-n> <change>`

New step → next free number, inserted where it happens in the table **and** the diagram;
the walk gets its `step()` in the same place. Removed step → out of table, diagram and
walks, onto `Retired steps:`. Changed step → same ID if it is still the same step;
otherwise retire and add. Re-check the status marker.

## `touched <story or path>` — after a feature changed

`grep -l "| <STORY> |" docs/journeys/*.md` (or map the path to its stories first, via the
`Endpoints:` lines). For each journey found: does the step still say what the code does,
does its walk still pass (`pytest -k <walk>`)? Fix the step text, or retire and add. The
help pages citing those stories are the `handbook` skill's update mode.

## `check [J-n]`

`python3 scripts/check-docs.py` and read its journey lines: problems (✗) fail
`scripts/check.sh`, warnings (!) are steps no test covers. Then run the walks named on
the journey's `Tests:` line.

## Tests

**A walk** is one long test through one path, `step()` marking where each step begins:

```python
"""Journey J-5 (``docs/journeys/crew-cleared.md``) — the adult crew; Stories V-1, V-2, S-1, VA-5."""
from tests.journeys import step

class TestACrewIsCleared:
    async def test_adult_crew(self, client, caplog):
        step("J-5.1", "club manager registers the squad")
        ...
        step("J-5.4", "club manager names the crew")
```

```ts
describeJourney("J-5: a crew is cleared — adult crew", () => {
  test("walks it", async ({ page }) => {
    await step("J-5.1", "club manager registers the squad", async () => { … });
  });
});
```

- A walk holds every `main` step that is not offline, plus the branch steps of its path,
  **in table order**; one walk per path that cannot share a test (adult vs minor).
- **pytest first** (fast, in `check.sh`, `api/tests/stories/test_journey_<slug>.py`);
  a Playwright walk in `e2e/journeys.spec.ts` when the journey is about screens and a
  stakeholder should see the video (`EVIDENCE=1`). Both may exist; list both.
- Fresh data with unique names (`uuid4().hex[:8]`): the suite runs in parallel
  (`pytest -n auto`) and counts against seeded rows break there (docs/gotchas).
- Switching people inside one walk: `make_user` + `login_as` (pytest), `signIn` from
  `e2e/session.ts` (Playwright).
- A branch covered elsewhere: the story test says `Journey step J-5.6` in its docstring.
  It then shows under the journey in Allure too (`api/tests/conftest.py`).
- `step()` looks the step's story up in `docs/stories.json` — run `check-docs.py --fix`
  after adding rows, or the Allure step lacks its story.

## What the checker enforces (`scripts/check-docs.py`)

Heading and index entry; actors in `Who:`, the `Who` column and the diagram (with their
aliases); unique step IDs belonging to the journey; every story real; diagram ⇄ table,
same order; no retired ID anywhere (table, tests); every `step()` and `Journey step …` a
real step; each walk in table order without skipping a main step; the status marker.
Generated: `docs/stories.json` (journeys and steps), `docs/traceability.md` § Journeys.

## Report

What exists now, what the stakeholder must decide (`Open:`), what is not tested (the
warnings), and any story found to contradict the code — those are the useful products of
drawing a journey at all.
