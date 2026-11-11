# Licence rules: what the site evaluates

Source: World Sailing, *Race Officials Roles, Qualifications and Competencies* (RQC), January
2026 (`material/2026-WS-RQC.pdf`). Section 1 covers general rules, 4 International Judges (IJ),
8 International Umpires (IU). This file only summarises what the site has to evaluate. The
document itself is authoritative.

**Principle: the site suggests, it does not decide.** Renewals are decided by the responsible
sub-committee and the Race Officials Committee. Whether an event is L1, L2 or L3 is, in case
of doubt, also the sub-committee's call (RQC 1.5(a), 8.4 note 2). So the site computes a
**suggestion** and shows what it is based on. The chosen level is stored; a deviation from
the suggestion needs a reason.

**The rules change every year.** They are therefore stored as a versioned table in the data
("rule set RQC 2026"), not hard-coded. An event is evaluated under the rule set of its year.

## 1. General (RQC 1)

- **Designated Period:** 4 years, with two cut-off dates per year. For 2026 that is
  14 April 2022 to 13 April 2026, or 14 October 2022 to 13 October 2026, both inclusive.
- **Application deadlines:** 1 March or 1 September. Supporting documents by 13 April or
  13 October, 23:59 UTC. Late applications are rejected.
- **Substitution by L2 and L3 (RQC 1.5(d)):** for a renewal, two L2, or one L2 and two L3, or
  three L3 count as *one* principal event. **Only once per application**, unless the
  discipline's section says otherwise (for IU: up to three times, see below).
- **Groups:** World Sailing assigns MNAs to groups A–Q. "Outside" means *outside one's own
  group* for groups A–H, and *outside one's own MNA* for groups I–Q. The site needs the
  mapping MNA → group for this (today's field "MNA Group").

## 2. International Judge (RQC 4)

Terms: a **fleet racing event** is one where most protests were heard under RRS Part 5. An
**umpired fleet racing event** is one where most protests were decided on the water by
umpires. **Only fleet racing events count for IJ.**

### Renewal, System 2 (RQC 4.3)

| Rule | What the site needs |
|---|---|
| Passed the re-examination | Date, entered by hand or with evidence (cannot be derived from events) |
| At least **6 L1** fleet racing principal events on the protest committee | Part "fleet" with level, the person's role |
| Only one event per time period | Detect and flag overlapping dates |
| At least **4 of them as a member of an International Jury** | Flag "International Jury under Appendix N" on the part |
| At least **2 of them outside** one's group or MNA | The event's MNA, its group, the person's nation |
| At most **1 L1 remote**, and only with an International Jury and video conferencing | Flag "in person" per assignment |
| Substitution by L2/L3 under 1.5(d), served **in person** on an on-site protest committee | Level, in person |

System 1 is the first-appointment route without reference forms (4.2 except (d)): seminar,
exam, at least 4 L1 on site, 2 of them as International Jury and 1 outside. The site evaluates
both systems.

### Levels for fleet racing (RQC 4.4), the basis of the suggestion

**Dinghies**

| Level | Criteria (any one is enough) |
|---|---|
| L1 | Olympic Games · International Class World, Hemispheric and Continental Championships · Grade 200 and 100 Olympic Classes events · National Championship with 50+ entries (min. 3 racing days) · Youth Olympic Games · Youth Sailing World Championships · Regional Games · 50+ entries and more than 3 classes (min. 4 racing days) · international event with 100+ entries from 2+ countries (min. 3 racing days) |
| L2 | National Championship with 50+ entries (min. 2 days) · National Championship with 30–50 entries (min. 3 days) · international event with 30+ entries from 2+ countries (min. 3 days) |
| L3 | International event with 20+ entries from 2+ countries (min. 3 days) |

**Keelboats**

| Level | Criteria |
|---|---|
| L1 | The Ocean Race (each leg one L1) · long-distance race with 50+ entries from 2+ countries · International Class World, Hemispheric and Continental Championships · international event with 50+ entries from 2+ countries (min. 4 days) · National Championship with 30+ entries (min. 4 days) · International Jury on site with 30+ entries (min. 4 days) |
| L2 | International event with 30+ entries from 2+ countries (min. 3 days) · international event with 50+ entries but only 1–2 races (min. 2 days) · National Championship with 30+ entries (min. 3 days) |
| L3 | International event with 20+ entries from 2+ countries (min. 3 days) |

For a suggestion the part therefore needs: boat type (dinghy or keelboat), kind of event (e.g.
world championship, national championship, grade, Ocean Race, long distance), entries, number
of countries, number of classes, racing days, and the flag "International Jury". That is
almost exactly today's set of fields on wsijreport.org.

## 3. International Umpire (RQC 8)

Applies to first appointment **and** renewal (8.3). The exam is per discipline (fleet, match
or team racing).

| Rule | What the site needs |
|---|---|
| **Option 1:** at least **8 L1** events as umpire, each with **at least 3 scheduled days of umpired racing**, 1 of them outside | Part with discipline, level, scheduled days; the person's assignment |
| **Option 2:** at least **28 scheduled racing days** as umpire at L1 events, **4 of those days outside** | **Days per person and part**, not just per event |
| Mixed disciplines are allowed (note 1) | Several parts per event |
| Substitution by L2/L3 under 1.5(d) **up to three times** (note 3) | Level |
| First appointment additionally: 3 positive IUSC reference forms, one from an IU of another MNA or from an event outside | Confidential references, outside the site or as an upload |

### Levels for umpires (RQC 8.4)

| Discipline | L1 | L2 | L3 |
|---|---|---|---|
| Medal racing | Grade 200 and 100 Olympic Classes events · International Class World or Continental Championships · National Championship of an International Class | International Class event | – |
| Umpired fleet racing | High level of competitors · National Sailing League with a high level of competition | Keelboats/dinghies · National Sailing League with a low level of competition | – |
| Match racing | World Championships · Grade 1 and 2 · National Championships (high level) · international Grade 3 (high level) · other continental championships or major international events | National Championship (lower level) · international Grade 3 (lower level) | Regional university events · other regional events |
| Team racing | World Championships · US National Team Race Championship · US University Championships · British University National Championships · Wilson Trophy · British National Championships · other continental championships or major international events | Feeder to a principal event · National Championship (lower level) | Regional university events · regional events with more than 8 teams |

**What cannot be computed:** "high level" is a judgement, not a number. For match racing,
World Sailing's grade (from the grading form) and the ranking points of the top 12 skippers
help. Team racing has no ranking: what counts there is the list of
named events, the number of teams and the MNAs. The suggestion is coarser here, and the chief
umpire's reasoning matters more.

**Note:** National Sailing Leagues are listed explicitly under L1/L2 for umpired fleet racing,
so the matchdays of the Deutsche Segel-Liga count for umpires. For this project that is a use
case, not a reason to connect it to the SBL (see `README.md`).

## 4. What the site does with this

- **A level suggestion per part**, as soon as the data is sufficient, showing the criterion
  that applied ("L1: international, 112 entries from 9 countries, 4 racing days"). Whoever
  writes the report may deviate but has to give a reason.
- **A renewal overview per person and Designated Period:** the assignments that count and the
  result per rule (met / still missing / note), e.g. "6 of 6 L1 ✓ · 3 of 4 International Jury
  ✗ · 2 of 2 outside ✓ · L2/L3 substitution used: 1 of 1". For umpires: option 1 and option 2
  side by side.
- **Export** as PDF and Excel. The format World Sailing expects for the application is still
  to be clarified (CONCEPT.md § 11).
- **Never an automatic rejection or approval.** The evaluation helps fill in the application.
