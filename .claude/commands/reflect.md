---
description: Review the work just done for wrong turns and repeated effort, then record and extract what came out of it
---

Look back over the work in this session and turn what you learned into something the next
agent inherits. Do it now, while the reasoning still exists — by the next session only the
diff survives, and the diff is exactly the part that does not say why you first went the
wrong way.

Work through these in order. Report what you found for each, including "nothing" — a
reflection that invents lessons to look thorough is worse than a short honest one.

## 1. Where were you wrong?

Not "what bugs did you fix" — where were **you** mistaken? A cause you named and acted on
that turned out to be something else. A confident explanation you later retracted. A
symptom you read as one thing when it was another. A fix you made that did not fix it.

For each, ask whether the next agent would make the same mistake from the same starting
point. If yes, it is a note:

    scripts/check-docs.py --new "a sentence stating the rule"

Fill in Symptom, Cause, Rule, Evidence. Under **Cause**, one line on *what misled you* —
that line is the reason the note exists. Then `scripts/check-docs.py --fix`.

If a story or a comment in the code records the cause you now know was wrong, **correct it
there too**. A wrong explanation left in place is read as fact by whoever comes next, and it
is more expensive than no explanation at all.

## 2. What did you do more than twice?

Repeated work is a design signal. Look for:

- the same shell incantation typed again with small variations
- the same probe or diagnostic written more than once
- the same multi-step setup done by hand
- the same class of mistake corrected in several places

Second time, notice. Third time, extract — into `scripts/`, into a test helper, into a
function — and put the reasoning inside the extracted thing, where it will actually be
read. Adding it to `scripts/check.sh` is what makes it stick.

## 3. Does the new check actually work?

If you added a check, **break something on purpose and watch it fail**. A check that has
never failed has not been tested, it has only been run. This project has a worked example
of why: a "page never scrolls sideways" test passed for weeks while the page it guarded was
unusable, because the browser hid the symptom the assertion measured.

## 4. Do the docs still tell the truth?

- Story status markers: ○ open, ◐ partial, ● implemented **and** tested. Did anything move?
- `Tests:` lines pointing at what now covers the story.
- A domain rule that will outlive this task belongs in `CLAUDE.md` under Domain decisions.
  A surprise that will not belongs in `docs/gotchas/`.

Then run `scripts/check-docs.py` and `scripts/check.sh`.

## 5. What is still unfinished?

Name anything you left open, blocked, or deliberately did not do, and where the next person
should pick it up. Say it plainly rather than leaving it implied by an absence.
