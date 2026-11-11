# User stories

Format as in the SBL: ID, status (○ open · ◐ partial · ● implemented and tested), role, wish,
reason, acceptance criteria. Every story is ○; there is no code yet. The phase is given after
the title (see CONCEPT.md § 10).

Roles: **official**, **reporter** (jury chair or chief umpire of a part), **committee** (IJSC
or IUSC), **admin**, **visitor**.

---

## Account and person (K)

### K-1 ○ An official signs in and links their WS ID (phase 0)

*As an official I want to sign in with my email address and store my WS ID, so that all
assignments under that ID are mine.*

- Sign-in by email code or password, optionally Google or Microsoft.
- An account has at most one WS ID; a WS ID belongs to at most one account.
- If a person with this WS ID already exists (because someone entered them), the account is
  linked to it once the address is verified. If the person is already linked to another
  account, the admin decides.
- Name and nation are looked up via XRR (X-1) and can be corrected.

### K-2 ○ An official states their licences (phase 1)

*As an official I want to state which licences I hold (IJ, IU per discipline, NJ, NU) and until
when, so that my renewal overview shows the right period.*

- Licence, discipline (for IU), valid until.
- A self-declaration is shown as such. The committee can confirm it (G-3).

---

## Event and part (E)

### E-1 ○ An official creates an event (phase 1)

*As an official I want to create an event I served at as jury or umpire, so that I and the
other officials can report it.*

- Only the name is required to save. Everything else can come later.
- Fields: name, venue, MNA, first day, first racing day, last day, organising authority,
  website, WS event ID (optional), comment.
- The WS group follows from the MNA and is not entered.
- **Duplicate warning:** if an event with the same MNA, overlapping dates and a similar name
  exists, the site shows it before creating and offers "This is it".
- Whoever creates the event is its owner.

### E-2 ○ An event has parts with their own discipline (phase 1: fleet; phase 2: all)

*As an event owner I want to split an event into parts with a discipline (e.g. the fleet week
with the jury and the medal races with umpires), so that each part counts for the right
officials and at the right level.*

- Disciplines: fleet (protest committee / International Jury), umpired fleet, medal race,
  match, team.
- An event has at least one part. Several parts of the same discipline are allowed (e.g. open
  and women in match racing).
- Each part has its own period within the event, its own racing days and a reporter (jury chair
  or chief umpire, by WS ID).
- The reporter gets a mail with a link if they did not create the part themselves.

### E-3 ○ The jury chair fills in the fleet part, as on wsijreport.org today (phase 1)

*As a jury chair I want to give every item of today's IJ Report, so that nothing the IJSC gets
today is lost.*

- Every field of today's form (list in CONCEPT.md § 4, PartReport *fleet*), including type
  (dinghy, keelboat, mixed …), grade, classes, entries, countries, hearings, Appendix P, flags
  and the jury questions.
- "Number of classes" is counted from the list of classes, not entered.
- Confidential fields (NJ reference form, "out of standard") are marked as such and follow D-1.

### E-4 ○ The chief umpire fills in an umpired part (phase 2)

*As a chief umpire I want to report medal races, umpired fleet, match or team racing, so that
umpires can prove their assignments.*

- Fields per discipline as in CONCEPT.md § 4.
- **Medal race:** number of umpired races, days, participants, classes (Olympic yes/no →
  grade 100/200 possible).
- **Match:** every field of the WS grading form (boats, crew, skippers, format, grade, top-12
  ranking points, MNA shares, assessment of race management and umpire boats).
- **Team:** number of teams, boats per team, format (round robins, knockouts, number of
  races). No ranking.

### E-5 ○ Match and team racing record teams and sailors (phase 2)

*As a chief umpire I want to record the teams with skipper and sailors, so that the event's
field and its international character are documented.*

- Team: name, MNA, final place. Members by WS ID, name and nation via XRR.
- Match racing: the **skipper's ranking at the time of the event** is recorded and never
  changed automatically afterwards.
- Number of teams, number of nations and MNA shares are computed from the teams, not entered.
  Without teams recorded they can be entered by hand.
- Sailors need no account and get no mail.
- Teams can be imported from a CSV file (e.g. the entry list).

### E-6 ○ The site suggests the level (phase 2)

*As a reporter I want to see which level World Sailing's rules give my part, so that I do not
have to look it up in the RQC document.*

- Suggestion per LICENCE_RULES.md, with the criterion that applied.
- If data for a suggestion is missing, the site says which.
- The reporter chooses. A deviation from the suggestion requires a reason.
- Rule sets are versioned; an event is evaluated under the rule set of its year.

### E-7 ○ Saving always works, submitting checks (phase 1)

*As a reporter I want to save at any time and only learn what is missing when I submit, so
that I can write the report in several sittings.*

- Saving requires no fields.
- "Submit" shows a list of what is missing (as codes the interface translates). Only when it
  is empty does the part go to `submitted`.
- A submitted part stays editable until the committee has reviewed it. After that only by the
  committee or with its release. Every change after review is logged.

### E-8 ○ The reporter is reminded of missing reports (phase 2)

*As the committee I want reporters reminded of reports not yet submitted, so that the data is
complete.*

- Mail to the reporter 14 days after the part ended if it is not submitted, then weekly, at
  most three times.
- The committee sees overdue parts in its inbox (G-1).

---

## Assignments (O)

### O-1 ○ The reporter adds the officials (phase 1)

*As a jury chair or chief umpire I want to add my part's officials with WS ID, role, days and
"in person", so that their assignments count.*

- Type the WS ID → name and nation from XRR or our own database. Unknown IDs are created by
  hand with name and nation.
- Role: jury chair, jury member, chief umpire, umpire, assessor. Status at the time: IJ, NJ,
  IU, NU.
- **Days on duty**, pre-filled with all racing days of the part.
- In person yes/no. Remote only for fleet, with a hint about the rule (at most one remote L1
  per application).
- No email address needed. If the person is linked to an account, they get the mail from O-2.

### O-2 ○ An official confirms or disputes an assignment (phase 1)

*As an official I want to see where I was entered and confirm it or have it corrected, so that
my evidence is right.*

- "My assignments" shows every assignment, open ones first.
- Confirm, or dispute with a comment ("was only there 3 of 5 days"). The dispute goes to the
  reporter, who corrects it.
- An official can add **themselves** to an existing part. The reporter has to confirm.

### O-3 ○ An official adds past assignments (phase 2)

*As an official I want to add assignments from events that were never reported, so that my
renewal overview is complete.*

- If the event's reporter is not on the site, the official creates event and part themselves.
  Part and assignment are marked **"added later, unconfirmed"**.
- The committee can confirm assignments added later.
- The status is visible in the renewal overview and the export.

---

## Renewal (R)

### R-1 ○ An official sees where their licence renewal stands (phase 2)

*As an official I want to see, for my licence and a Designated Period, which assignments count
and which rule is still unmet, so that I apply on time and correctly.*

- Choice: licence (IJ, IU per discipline) and Designated Period (from the rule set, e.g.
  14 Oct 2022–13 Oct 2026).
- **IJ:** evaluation of System 2 (and System 1) per LICENCE_RULES.md § 2: number of L1, of
  which International Jury, of which outside, remote, L2/L3 substitution used, overlapping
  events.
- **IU:** option 1 (8 L1 with 3+ days each, 1 outside) and option 2 (28 days, 4 outside) side
  by side, with L2/L3 substitution up to three times.
- Each rule shows: met, still missing (how much), or a note.
- An assignment that does not count is shown with the reason ("umpired fleet does not count
  for IJ").
- The site says clearly: a suggestion; the sub-committee decides.

### R-2 ○ An official exports their evidence (phase 2)

*As an official I want to download my renewal overview as PDF and Excel, so that I can attach
it to my application to World Sailing.*

- PDF with a header (name, WS ID, licence, period), table of assignments, result per rule,
  date of creation and status of each assignment (confirmed, added later, reviewed).
- Excel with the same rows.
- Format per World Sailing's template, once known (CONCEPT.md § 11, question 7).

---

## Committee (G)

### G-1 ○ The committee has an inbox (phase 2)

*As a member of the IJSC or IUSC I want to see every submitted, overdue and disputed part of
my discipline, so that I can review them.*

- IJSC: `fleet` parts. IUSC: `umpired_fleet`, `medal_race`, `match`, `team`.
- Filters by status, year, MNA, level. Server-side.

### G-2 ○ The committee reviews a part (phase 2)

*As the committee I want to review a submitted part, correct its level if needed and mark it
reviewed, so that the data for renewal and grouping is reliable.*

- Level correction with a reason. The reporter is informed.
- Status `reviewed`. After that the reporter can only change it with the committee's release
  (E-7).
- Review comments are confidential (D-1).

### G-3 ○ The committee confirms licences and assignments added later (phase 2)

*As the committee I want to confirm self-declared licences and assignments added later, so
that renewal overviews can be relied on.*

### G-4 ○ The committee analyses (phase 2)

*As the committee I want to analyse the data (events per year, discipline, MNA, level;
assignments per official), so that I can judge, for example, the grouping of IJs or the
distribution of umpires.*

- Tables with filters and export to Excel.
- No assessment of people on the site. Grouping stays with the Grouping Panel.

### G-5 ○ The committee maintains reference data and rule sets (phase 2)

*As the committee I want to maintain MNAs with their WS group, classes (Olympic yes/no), kinds
of event and the rule set of a year, so that suggestions and evaluations are right.*

- A new rule set is a new version. Old events keep their rule set.

---

## Confidentiality and data protection (D)

### D-1 ○ Confidential items are seen only by those who must see them (phase 1)

*As the committee I want to be sure that assessments of officials are seen only by the reporter
and the committee, so that jury chairs report openly.*

- Confidential: NJ reference form, "out of standard" report including its text, review
  comments, possibly the sustainability observation (open question 11).
- Not visible to other officials, the person concerned, or the public.
- Every read is logged with person and time.
- A test proves this for every role.

### D-2 ○ The public sees the event list (phase 1)

*As a visitor I want to see which events had an International Jury or umpires, as on
wsijreport.org today.*

- Event, venue, MNA, dates, parts with discipline and level, the officials' names.
- No email addresses, no assessments, no hearing figures unless the committee releases them.
- Submitted parts only.

### D-3 ○ An official closes their account (phase 5)

*As an official I want to be able to close my account.*

- Login and roles are removed. The assignments stay as facts of the event, with name and WS ID.
- Retention per CONCEPT.md § 8, once the controller has set it.

---

## Integrations (X)

### X-1 ○ People are looked up by WS ID (phase 1)

*As a reporter I want to type only the WS ID, so that names are spelled right and people are
not created twice.*

- Query `datafeed.sailing.org/query?type=Person&IFPersonID=…`, result cached.
- If the service is down, manual entry carries on. No error that blocks the work.
- A value from World Sailing never overwrites a manual correction without asking.
- Tests run against recorded responses, never against the live service.

### X-2 ○ The match race grading form is generated from the data (phase 3)

*As a chief umpire I do not want to fill in World Sailing's grading form by hand again, so that
I enter the data only once.*

- Produces the completed template (docx or PDF) from the match part, sections 1–6, column
  "Chief Umpire Confirmation".
- Reminder of the deadline (24 hours for grades W/1/2, 5 days for grades 3/4/5).

### X-3 ○ An event is linked to World Sailing's calendar (phase 3, with access)

*As an event owner I want to take an event from the WS calendar, so that name, dates and venue
are right and the WS event ID is set.*

- Requires access to an event feed from World Sailing.
- Matched by WS event ID only.

### X-4 ○ Sustainability certificates are recorded on the event (phase 3)

*As a reporter I want to state which sustainability certificates the event holds and what of
it was visible on site, so that the sustainability commission gets feedback from practice.*

- Programme (Clean Regattas, Sailors for the Sea, …), level, link.
- On-site observation as free text and a short checklist (e.g. single-use tableware, waste
  concept).
- Who sees it is open (CONCEPT.md § 11, question 11).

### X-5 ○ The legacy data of wsijreport.org is imported (phase 4)

*As the committee I want the existing reports in the new site, so that renewal and grouping
rest on the complete history.*

- Import from a dump, repeatable, without duplicates (key: old report ID).
- Every old report becomes an event with one `fleet` part. Type "mixed" is kept as a value.
- Imported assignments count as reported by the reporter, but not confirmed by the person.
- A report lists what could not be imported.
