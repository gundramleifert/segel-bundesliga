# Gotchas — what surprised someone here

Short notes about things that did **not** behave the way a competent person would
reasonably expect. One file per surprise.

`docs/concepts.md` explains the domain as it is meant to be. This folder explains the
places where reality bit — the library that owns a name we also wanted, the assertion that
passes while the thing it guards is broken, the sandbox rule that makes a working command
fail in the next call. None of it is deducible from the code by reading harder, which is
exactly why it is written down.

## Who this is for

Whoever works here next, human or agent. An agent that reads this folder first does not
have to re-lose the afternoon that produced each entry.

## When to write one

Write a note when **any** of these is true:

- You were **confidently wrong**. You stated a cause, acted on it, and it was something
  else. This is the most valuable kind of entry and the easiest to skip out of
  embarrassment — write it anyway; the next agent will make exactly your mistake.
- A surprise cost more than ~15 minutes, or more than two wrong attempts.
- A symptom pointed **away** from its cause. ("The buttons don't work" was a layout
  overflow. "The card is invisible" was a CSS token name.)
- A test, type check, or lint passed while the thing it exists to protect was broken.
- A tool, library, or the environment behaved differently from its documentation, its
  previous version, or plain expectation.

Do **not** write a note for: a normal bug you fixed, something already in `CLAUDE.md` or
`docs/concepts.md`, or a fact the code states plainly. Those are noise, and noise is what
makes the next person stop reading the folder.

## Format

Filename: `kebab-case-of-the-rule.md` — name it after the **rule**, not the incident, so a
listing reads as advice. `grid-auto-columns-can-zoom-the-page-out.md`, not
`admin-page-bug.md`.

Each file, in this order, and short — a screenful:

```markdown
# <The rule, as a sentence>

**Symptom** — what it looked like, in the words you would have searched for.
**Cause** — what was actually happening.
**Rule** — what to do or avoid, stated so it applies next time, not just to this incident.
**Evidence** — the file, command, or measurement that proves it. A note without evidence
is a rumour.
**Seen** — YYYY-MM-DD, and the commit if there is one.
```

If you were wrong on the way to the answer, say so under **Cause**, in one line, with what
misled you. That line is the point of the entry: it is the hint the next agent needs
*before* they start, and it is the part no amount of code-reading would recover.

## Keeping it honest

- **Correct an entry rather than adding a second one** about the same thing. Two entries
  that half-disagree are worse than one that is right.
- **Delete an entry when it stops being true** — a library upgrade that fixes the
  behaviour makes the note misinformation. Removing it is a real contribution.
- Every note is a claim about this repository. If you cannot point at the evidence, you
  are guessing, and a guess here costs the next reader more than it saves.
