# Journeys

Part of the [user stories](README.md); the status marks and the identifier rule are
explained there.

A **journey** is several stories in the order they really happen, walked by one test from
start to finish — a use case's *main success scenario* (Cockburn), laid along the backbone
of a story map (Patton). Every step is already a story with its own tests; what a journey
adds is the **sequence**: that each step's output really is the next step's input. That is
what breaks in practice — a draw keyed on teams while the clubs are added after creation,
an event saved without a date because the date is agreed later — each fine alone, wrong in
order.

## The format

```
### J-1 ◐ <what someone gets done, start to end>
Who: the people who act in it
Starting point: what exists before step 1

Steps:
1. A-1   <who does what, and what is then true>
2. A-6   …

Variations:
4a. VA-7  <a different path that branches off step 4>

Tests: `api/tests/…::TestX::test_y`, `e2e/journeys.spec.ts::J-1: …`
```

- **One story per step**, its ID first. A story may appear in several steps.
- **The test walks the main steps, in this order, and names each one**:
  `step("A-1", "…")` (pytest, `tests/journeys.py`) or `await step("A-1", "…", async () => …)`
  inside a `describeJourney("J-1: …")` (Playwright, `e2e/fixtures.ts`). In evidence mode
  (`EVIDENCE=1`) the steps are the chapters of the trace.
- **Variations are alternatives, not steps of the test.** Each is checked either inside
  the step it branches from, or by its story's own tests.
- **Status:** ● only when the test exists and every story of the main steps is ● itself;
  a journey cannot be more finished than its weakest step. Otherwise ◐, or ○ without a
  test.
- `scripts/check-docs.py` holds all of this: every step ID is a real story, each test's
  `step(...)` IDs match the main steps in order, and the status follows the rule above.

## Running an event

### J-1 ◐ From an empty series to a scored matchday
As the **association** I want **one test that walks the whole way — clubs, series, event,
boats, clubs entered, draw, start, all races sailed, standings, freeze, protest** — so that
**the steps are proven to fit together in the order they actually happen**. (Told first as
Story VA-9.) ◐ and not ●, because step 10 and 13's story WL-2 is not finished yet: a
journey is never more done than its weakest step.

Who: the league office (admin) acting as organizer, race committee and jury.
Starting point: a running installation; none of the clubs, the series or the event exist.

Steps:
1. A-1   admin creates 12 clubs; none is public yet
2. A-6   admin creates "Lifecycle Trophy 2026" with the 12 clubs, as a draft — 404 publicly
3. VA-8  admin publishes the series; it is listed now
4. VA-6  organizer creates the event with a title and boats only; the series' registrations are adopted as entries
5. VA-8  the readiness says what is missing (team count, date), and the organizer fixes it
6. VA-7  organizer draws the pairing list from the catalog, and may draw again
7. VA-8  organizer publishes the event; it is in the public calendar
8. B-3   the pairing list prints — or the server says it cannot, never silently
9. VA-8  organizer starts the event
10. WL-2  race committee enters all 16 races; points add up to what 16 races hand out
11. B-1   the series table has the act in it, every club with its placement
12. VA-8  the configuration is frozen now — but a typo in the title is still fixable
13. WL-2  the jury disqualifies a winner months later, and the points follow on write
14. VA-10 the race committee declares the event final

Variations:
5a. VA-8  the draw is refused while the readiness reasons stand, with the same codes

It runs the catalog's **smallest** configuration (12 clubs, 6 boats, 8 flights = 16
races), not the league's 48 — small enough to sail to the end in a test, large enough to be
a real pairing list. Through the HTTP API only, nothing reached around into the database,
and deliberately **one long test**: a step that only makes sense after the previous one
cannot be a test that runs on its own. The browser half — that each step is *reachable*,
with its button enabled at the right moment — is in `e2e/lifecycle.spec.ts` per story, not
yet as one walk.

Tests: `api/tests/stories/test_complete_lifecycle.py::TestTheCompleteLifecycle::test_from_an_empty_series_to_a_scored_matchday`
