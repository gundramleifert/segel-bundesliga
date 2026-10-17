---
title: Writing guide — length, language, page anatomy
description: How to write handbook pages for this site. The length budget, English first and German as a full translation, quoting UI labels, the domain vocabulary, the anatomy of start, guide, journey, doc and faq pages, the roles page, and the concision pass.
---

# Writing guide

The reader is a **volunteer**: a club's sports manager on a weekday evening, a race officer
on a committee boat, a seventeen-year-old sailor whose waiver is missing, a treasurer once
a quarter. Mostly on a phone (CLAUDE.md: "the site is read mostly on mobile"). They want
one answer, now.

## Short

| Budget | |
|---|---|
| `start` | ≤ 250 words |
| `guide` | 100–350 words |
| `journey` | ≤ 300 words plus the step list |
| `doc` | 150–450 words (a table counts lightly) |
| `faq` answer | 1–3 sentences |
| any page | over ~600 words → two pages, or padding |

- No warm-up ("This page explains …"). Start with the fact.
- Don't narrate the screen; say what the screen does **not** say: why a button is
  disabled, what a badge means, what cannot be undone.
- A fact lives on one page; others link to its anchor.
- Lists and tables over paragraphs.
- No closing summary. End a guide with the link into the site.
- Cut: *simply, just, basically, please note*; *einfach, grundsätzlich, bitte beachten Sie*.

## Language

**English is the source** (CLAUDE.md § Language). Write `en` completely, then `de` as a
full translation — same sections, same depth, same screenshots, never a summary.

- **UI labels are quoted from the catalogs**, in italics, exactly: the English page
  quotes `en/*.json`, the German page `de/*.json`. Never translate a label yourself; if a
  label is missing in one catalog, that is a finding.
- **Domain words are fixed** (CLAUDE.md § Language, `docs/concepts.md`): Series / Serie,
  Event / Veranstaltung, Matchday / Spieltag, Act, Squad / Kader, Lineup / Aufstellung,
  Host club / Ausrichter, Venue / Revier, Race committee / Wettfahrtleitung, Pairing list,
  Flight. Use what the catalogs use in that locale. Never call the site "Segel-Bundesliga":
  that is one series' name.
- **English**: plain, second person, active, present tense, imperatives in steps; no
  contractions outside FAQ answers.
- **German**: the register chosen in the interview (default *Sie*, capitalized, consistent
  on every page). The catalogs mix *Sie* and *du* today — do not mirror the mix; report it.
- Never translate identifiers: route paths, error codes, file formats (`pain.001`, PDF).

## What to write — and what not

Write: every task a person of this audience does, end to end; the boundaries (what is
refused, why, and what to do); what is irreversible or frozen (an event's configuration
after the first race, CLAUDE.md § Domain decisions); who to ask when the site cannot do it
(a club's admin, the event's organizer).

Do not write: anything without evidence (`sources.md`); anything planned; internals (tables,
tuples, SSE, job queues — a reader sees "updates live", not "Server-Sent Events");
development features (`/api/dev`, the role switcher); marketing.

**Privacy and the waiver are written exactly.** Who can see a scan, a document, a bank
account (S-1, S-5, S-6) — copy the substance of the story and the endpoint's check, never
soften it.

## Anatomy

### `start` — one per audience

```markdown
## Help for team managers

You register your club's people for a series, name the crew for each matchday, and keep
the member list. All of it is on your club's page in *My space*.

### Before the season {#start-club-season}
- [Register the squad](#squad-and-lineup-squad) for each series your club is entered in.
- [Accept members](#club-members-add) who belong to the club.

### Before each matchday {#start-club-matchday}
- [Name the crew](#squad-and-lineup-crew) — from the squad, by the organizer's deadline.
- Check that everyone's waiver is cleared: [waivers](#waiver-club-check).

### Where this fits {#start-club-journeys}
- [A crew is cleared for a matchday](#journey-crew-cleared) — what the sailors and the organizer do around you.

[Open my space](/me)
```

Ordered like the person's year (the story files are ordered by phase: master data, season,
matchday, aftermath).

### `guide` — one task, one audience

- State the **starting state** before the steps ("Your club is entered in the series.")
  and the **result** after them ("The squad shows *4 of 4–10 registered*.").
- Numbered steps, one action each, labels quoted.
- One screenshot per `###` at most; a phone screenshot for anything done on the water.
- The refusals a person meets here, each in one line with what to do — or a link to the FAQ.
- End with the link into the site.

### `journey` — the order across people

```markdown
## From an empty series to a scored matchday

Who: the league office, the organizer, the race committee, the jury.

| # | Who | What happens | How |
|---|---|---|---|
| 1 | Administration | creates the clubs — none is public yet | [Create clubs](#admin-clubs-create) |
| 2 | Administration | creates the series as a draft, with its clubs | [Series](#admin-series-create) |
| … |

### If … {#journey-lifecycle-variations}
- **The draw is refused:** the event's readiness list names what is missing — fix it and draw again.
```

The step numbers follow the journey file (or its `J-n.k` IDs once they exist), so a
stakeholder can compare the page with the diagram. Explain nothing a guide explains.

### `doc`

`terms` first: a table, term → meaning, in the catalogs' words; every other page reuses it.
Event states (draft / published, planned / live / final / cancelled, frozen) belong here,
as a table of what each state allows.

### `faq`

Question in the reader's words ("Why can't I add Anna to our squad?"), answer in 1–3
sentences: what it means, what to do. Group by audience with `###`.

### The roles page (`roles`)

Three sections, anchors fixed (`content-model.md`):

1. **`roles-list`** — every relation a person can hold, in the UI's words, grouped by
   where it is held (site, club, series, event), each in one line. The derived "implies"
   in plain words: "An event's organizers include the manager of its series and of its
   host club."
2. **`roles-matrix`** — rows are actions in the UI's words, columns the roles. A cell is ✓
   only if the **backend** allows it (`require_*`, `can()`, the tuple checks in services);
   "own club" / "own events" where it is scoped. Where the screen and the backend
   disagree, write the backend's truth and report the mismatch. The tuple-checked expense
   decisions (F-3) are spelled out: an editor of the site is **not** a payer.
3. **`roles-getting`** — how one gets a role: who writes which tuple (a club's admin adds
   members; an object's admin grants on it; the league office for site roles); accounts
   are not created by signing up.

Never the words *tuple*, *relation*, *object* in the prose — those are the model's, not
the reader's.

## Concision pass

The editor, after authoring and screenshots: cut, merge, shorten, reorder within a
section, turn prose into a list or table. Never add or remove a fact, change a quoted
label, frontmatter, an anchor or a shot id, or touch a section outside the scope. Every
edit to both locales. Report words before → after per page.
