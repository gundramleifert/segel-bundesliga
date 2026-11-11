# Concept: Race Officials Report (IJ/IU)

Status 11 November 2026, draft. **Not part of the Deutsche Segel-Liga website**, see
[README.md](README.md).

## 1. Background

**wsijreport.org** is the reporting system of World Sailing's *International Judges
Sub-Committee* (IJSC). After every event with an International Jury (RRS Appendix N), the jury
chair reports the key data: event, dates, type, grade, level, classes, entries, hearings,
Appendix P flags, jury members with WS ID and "in person", plus confidential items (NJ
reference form, "out of standard" report). The site has a list with filter and grouping, a
detail view and a "WS Renewal Report" (screenshots in `material/`). The data is used for:

- **Licence renewal** of IJs (RQC 4.3), see [LICENCE_RULES.md](LICENCE_RULES.md).
- **Grouping** of IJs (Developing Lead, Lead, Chief). According to the *IJ Grouping System
  2023* it is based on the IJ Report's event database. World Sailing appoints the juries of
  major events from these groups.

**What is missing:**

- **International Umpires** have no event register. Their renewal counts L1 events or racing
  days (RQC 8.3), and today they collect this evidence themselves.
- **Match racing** has a Word form (*grading form*) sent to World Sailing by email. There is
  also a Google Form.
- **Team racing** has nothing: no form, no ranking.
- **Mixed events** (a fleet week with the jury, then medal races with umpires) cannot be
  represented. Today an event is exactly one type.

**What World Sailing is planning itself:**

- **eROC** is a central database of all race officials. The project started in 2021, was due
  in 2024, then 2026, and in March 2026 was called a "persistent outstanding issue".
- ROC minutes of March 2026: "launch of a new IJ report website designed to streamline judge
  entries and reviews", plus a new working team for requests for digital tools.

The proposal: extend the IJ
Report to a joint **IJ/IU Report**, "one system for everyone, with one login". The site should
above all **collect data cleanly** and so make licence renewal easier. Later, a sync via XRR
with World Sailing's calendar, the grading data and sustainability certificates.

## 2. Goals and non-goals

**Goals**

1. An event is recorded **once**, even if it has several disciplines. Each part (fleet with
   jury, medal races, umpired fleet, match, team) has its own officials, days and level.
2. Every official sees **all their assignments** in one place and produces their **renewal
   overview** for IJ and IU from it.
3. The sub-committees (IJSC, IUSC) get a **clean dataset they can analyse**, e.g. for
   grouping, statistics, or where events take place.
4. The **level** of each part is **suggested** from its data, by World Sailing's rules.
5. **Confidential stays confidential:** assessments of officials are seen only by the
   responsible committee.
6. **Ready to sync with World Sailing:** WS ID on every person and WS event ID on every event,
   from the start.

**Non-goals (for now)**

- **No staffing of juries or umpire teams.** That is the Event Appointment Working Party's
  job. The site reports, it does not plan.
- **No results, no scoring, no ranking calculation.** Rankings are taken over, not computed.
- **No licence decisions.** The site shows where someone stands; the sub-committee decides.
- **Not a replacement for eROC.** If eROC arrives, this site feeds it (export) instead of
  competing with it.
- **Not part of the Deutsche Segel-Liga website.**

## 3. Roles

| Role | Who | May |
|---|---|---|
| **Official** | Every IJ, NJ, IU, NU with an account | See and confirm their own assignments, their renewal overview, create events |
| **Reporter of a part** | Jury chair (fleet) or chief umpire (umpired parts) | Fill in the part, add officials, enter confidential items, submit |
| **Event owner** | Whoever created the event, or a reporter | The event's master data, create parts, name reporters |
| **Committee** | IJSC (jury parts), IUSC (umpired parts), each with its own role | Read every report of its discipline including confidential items; review reports, correct levels, maintain reference data |
| **Admin** | Operator | Accounts, roles, rule sets, imports |
| **Public** | No login | Public event list, without personal data beyond the officials' names (as today) |

As in the SBL, permissions are **relation tuples** (`user:reporter:part`,
`user:committee:discipline`, `user:admin:site`), checked fresh on every request.

## 4. Domain model

```
Event ──< Part ──< Assignment >── Person ──< Licence
  │         │
  │         ├──< Team ──< TeamMember >── Person      (match, team racing)
  │         └── PartReport (fields per discipline)
  ├──< Certificate                                  (sustainability)
  └──< ExternalId                                   (WS event ID, grading)
```

### Event: what takes place once

Name · venue · MNA (giving the WS group A–Q) · first day, first racing day, last day ·
organising authority · website · comment · **sustainability**: certificates (Clean Regattas,
Sailors for the Sea …) and an on-site observation (free text: "what of it was actually put
into practice?") · external IDs (WS event ID `IFEventID`, grading number).

An event happens only once at a given time. So when a new event is created, the site
warns if one with a similar name, the same MNA and overlapping dates already exists, so that
two people do not create the same event twice.

### Part: one part of the event with one discipline

| Field | Note |
|---|---|
| Discipline | `fleet` (protest committee / International Jury), `umpired_fleet`, `medal_race`, `match`, `team` |
| Period, scheduled and actual racing days | IU option 2 counts *scheduled* days |
| Boat type | Dinghy, keelboat, multihull, board/kite, radio controlled |
| Classes, entries, countries | Today's fields |
| Kind and grade | e.g. world championship, national championship, grade 1/2/3 (MR), grade 100/200 (Olympic classes) |
| International Jury under Appendix N | Yes/no, `fleet` only |
| **Level**: suggested, chosen, reason for deviating | See LICENCE_RULES.md |
| Status | `draft` → `submitted` → `reviewed` |

Typical combinations: *one* fleet week (`fleet`) plus medal races (`medal_race`) for Olympic
classes, or match and team racing at the same event.

### PartReport: the fields per discipline

- **fleet** (today's IJ Report): total hearings · requests for redress · of which for OCS ·
  of which granted · hearings with a support person · Appendix P applied · first/second/
  third/fourth+ flags · jury properly constituted under Appendix N · N1.4(b) applied ·
  parties made aware of the right to appeal · jury on the water · NJ reference form to be
  sent · "out of standard" report · comment on the event and its management.
- **medal_race / umpired_fleet**: number of umpired races · participants · umpire boats ·
  on-the-water decisions (optional) · hearings · comment.
- **match**: number of boats, boat type and length, crew size, spinnaker/gennaker yes/no ·
  skippers · format (round robins, quarter-finals, semi-finals, finals) · number of matches ·
  grade (applied for and confirmed) · ranking points of the top 12 skippers · share of skippers
  from the host MNA, largest share from another MNA, share from the continent · race
  management acceptable · umpire boats acceptable. This is the **content of the grading
  form**, so the site can pre-fill it.
- **team**: number of teams and boats per team · format (round robins, knockouts, number of
  races) · comment. No ranking.

### Person, Licence, Assignment

- **Person**: WS ID (unique), name, nation (MNA). Optionally with an account. Sailors in teams
  need **no** account.
- **Licence**: kind (IJ, IU, NJ, NU, IRO …), discipline (for IU), valid until. Self-declared,
  can be confirmed by the committee; later perhaps from World Sailing.
- **Assignment** links a person and a part, with:
  - role: jury chair, jury member, chief umpire, umpire, assessor
  - status at the time: IJ/NJ or IU/NU
  - **days on duty** (default: all racing days of the part)
  - in person / remote
  - confirmation by the person: open, confirmed, or disputed with a comment

Days per assignment are the most important addition compared with today. Without them the
umpires' 28-day rule cannot be evaluated.

### Team, TeamMember (match, team racing)

Team name · MNA · skipper · further sailors (WS ID, name, nation) · **ranking at the time of
the event** (match racing, kept as a fixed number, never overwritten later) · final place.

### External IDs

As in the SBL: **external systems are matched by ID, never by name.** Every person has the WS
ID, every event optionally the WS event ID and the grading number. So the sync can come later
without changing the model.

## 5. Workflows

**A. Reporting an event (normal case, afterwards)**

1. An official creates the event, or finds it already there. The site warns about duplicates.
2. They create the parts and name each part's reporter (jury chair, chief umpire). If that is
   themselves, they carry on directly.
3. The reporter adds the officials by WS ID. Name and nation are looked up via XRR where
   possible. They fill in the part's fields; the site suggests the level.
4. Saving works at any time, with no required fields. **Submitting** checks completeness and
   says what is missing.
5. The officials entered get a mail: "You were entered at X for Y days as Z. Confirm or
   dispute."
6. The committee sees submitted parts, reviews them, corrects the level with a reason if
   needed, and sets them to `reviewed`.

**B. Deadline and reminder:** reference forms must reach World Sailing within 30 days of the
event, grading results within 24 hours to 5 days depending on grade. The site reminds the
reporter if a part has not been submitted 14 days after the event ended, and shows the
committee overdue reports.

**C. Renewing a licence:** the official picks licence and Designated Period. The site shows the
assignments that count and the result per rule; they export it as PDF or Excel and attach it
to their application.

**D. Match race grading (phase 3):** before the event the organising authority or chief umpire
fills in the application part. After the event the chief umpire confirms the values. The site
produces the completed grading form from them, as long as World Sailing wants it as a file.

## 6. Screens

| Page | Content |
|---|---|
| My assignments | All own assignments with open confirmations; button "Report an event" |
| Events | List with search, filters (year, MNA, discipline, level, status) and grouping; server-side |
| Event | Master data, parts as tabs, per part officials, fields and status |
| Edit part | Form per discipline, level suggestion with reasoning, "Submit" with the list of what is missing |
| Renewal | Choice of licence and period, result per rule, export |
| Committee | Inbox (submitted, overdue, disputed), review, reference data (MNA → group, classes, rule sets) |
| Public | Event list and event page without confidential items |

Usable on a phone, because reports are often written in the jury room right after the event.
English as the main language, further languages via i18n.

## 7. Integrations

| What | Status | Plan |
|---|---|---|
| **XRR person** (`datafeed.sailing.org/query?type=Person&IFPersonID=…`) | Service answers (tested 11 Nov 2026), no login | Phase 1: pre-fill name and nation when a WS ID is typed. Cache the result, never overwrite blindly |
| **XRR event** | Documented, but currently answers "IFPersonID required" | Phase 3, with access from World Sailing |
| **IJ/IU status from WS** | Not in XRR | Self-declared, confirmed by the committee. Later eROC |
| **WS calendar** | No open access found | Phase 3, with access. Link events by WS event ID |
| **Match race grading** | Word form by email | Phase 3: generate the form from the data; later an interface if WS offers one |
| **Match race ranking** | Public at WS | Record the ranking value when a skipper is entered (by hand, later automatically) |
| **Sustainability certificates** | No interface found | Phase 1: by hand (programme, level, link). Matching later |
| **eROC** | Not finished | Export the data in the format eROC expects, once it exists |
| **Legacy data wsijreport.org** | approx. 2,000 reports | Phase 4: import from a database dump |

## 8. Data protection and confidentiality

- **Settle the data controller before real data arrives.** Ideally World Sailing or the IJSC,
  with a data processing agreement for the operator. Until then, test data only.
- **Confidential fields** (NJ reference form, "out of standard" report, the committee's review
  comments) are seen only by the part's reporter and the responsible committee. Not by the
  other officials, not by the public, and not by the person concerned through the normal
  view. Every read is logged.
- **Public**, as today: event, dates, discipline, level and the officials' names. No email
  addresses, no assessments.
- **Sailors** (match, team) are people without an account. Only WS ID, name, nation and
  ranking are stored, data World Sailing publishes anyway.
- **Retention:** assignments are kept as long as they can count for a renewal (at least the
  Designated Period of 4 years plus the application window). After that they are anonymised,
  unless the committee needs them longer (grouping). To be decided with the controller.
- **Closing an account** deactivates the login. The assignments stay as facts of the event.

## 9. Technology

Skeleton as a **copy** of the SBL's technology (see [README.md](README.md) on the boundary):

| Building block | Origin in the SBL | Here |
|---|---|---|
| Backend FastAPI, SQLAlchemy 2 async, Alembic | `api/` | Same |
| Frontend React, Vite, TypeScript, HeroUI, Tailwind, generated API client (orval) | `web/` | Same |
| Login by email code, password, Google, Microsoft | `app/auth.py`, `services/login.py`, `services/passwords.py` | Same; account via verified email, WS ID as an attribute |
| Permissions as relation tuples | `app/authz.py`, `services/grants.py`, `MODEL` | Own model: `site`, `event`, `part`, `discipline` |
| Server-side list filtering and sorting | `app/filters.py`, `app/listing.py` | Same |
| Saving without validity, validity computed | `services/event_readiness.py` | The principle behind "Submit" |
| Errors as RFC 9457 with codes, mails as Jinja templates, i18n | `app/problems.py`, `app/mail.py`, `app/i18n.py` | Same |
| Audit log | `services/audit.py` | For confidential fields |
| PDF and Excel | reportlab, openpyxl | Renewal export, grading form |
| Hosting with Docker Compose, Caddy, Postgres, secrets with sops | `deploy/compose/` | Same, own server, own domain |
| Way of working story → test → code, `check.sh`, Playwright | `docs/userstories/`, `scripts/` | Same |

Everything domain-specific to the SBL (series, matchdays, pairing, tracking, SAP, finance,
waivers, editorial) is left out.

**Database:** Postgres from the start. There is no reason for an SQLite stage: the data volume
is small and hosting runs in Compose anyway.

## 10. Phases and effort

Effort in person-days (PD), with the same way of working as in the SBL.

| Phase | Content | Effort | Result |
|---|---|---|---|
| 0 | Repo from the SBL skeleton, everything SBL-specific removed, login, permissions, deploy | 1–2 PD | Empty, running site with login |
| 1 | Events, `fleet` parts, assignments with days, today's IJ Report in full, list, filters, detail, public view, XRR person lookup, confirmation by officials | 3–5 PD | Replacement for wsijreport.org (without legacy data) |
| 2 | Parts `medal_race`, `umpired_fleet`, `match`, `team`; teams and sailors; level suggestion; renewal overview IJ and IU with export; committee inbox; reminders | 3–5 PD | **IJ/IU Report, ready to demo** |
| 3 | Grading form from the data; WS calendar and event sync once there is access; sustainability fields | 1–3 PD without access, open with | Less double entry |
| 4 | Import of the legacy data from wsijreport.org | 1–3 PD, given a dump | History for renewal and grouping |
| 5 | Privacy texts, data processing agreement, operations, acceptance with the committees | 1–2 PD | Production |
| | **Total** | **approx. 10–20 PD** | |

A **prototype of phases 0–2 with test data** is realistic in about 1.5 weeks. It is the tool
for talking to the IJSC and the IUSC.

**Running costs:** a small server (2 vCPU, 4 GB RAM) is enough, approx. €10–20 a month plus
domain and backup. Maintenance approx. 1–2 PD a year for updates and the yearly rule-set
change.

## 11. Open questions

**Before any implementation (to be clarified with the IJSC/IUSC)**

1. **Who wants this?** Do the IJSC (working team "IJ Report", the new working team for digital
   tools) and the IUSC back it? Or would it be a parallel site?
2. **What is the "new IJ report website"** in the ROC minutes of March 2026? Is it wsijreport.org
   in a new form, or is it still to come? Could it be extended instead of building anew?
3. **Status of eROC:** is it coming, and can this site feed it?
4. **Who operates it, who is the data controller, who pays?**

**For the implementation**

5. Is there a **dump** of today's site, and who owns the data?
6. How does login work today? Are there accounts to take over?
7. Which **format** does World Sailing expect for the renewal application? Is there a template
   for umpires?
8. Is the **group per MNA** (A–Q) available in machine-readable form anywhere?
9. **Team racing:** which data exactly? Still open.
10. Should the site **replace the match race Google Form and the grading form**, or only
    pre-fill both at first?
11. **Sustainability:** which programmes and levels, and who sees the on-site observation? It
    is an assessment of the organiser and so possibly confidential too.
12. **Access to WS data:** who asks World Sailing about the calendar, the event feed and
    official status?

## 12. Risks

| Risk | Consequence | Mitigation |
|---|---|---|
| No support from IJSC/IUSC | Data does not count for renewal and grouping; the site is not used | Prototype and conversation first, then expand |
| World Sailing delivers eROC or the new IJ report site | Duplicate work | Do not compete; think of the site as a supplier or export |
| No access to WS data | More manual entry | The model is prepared anyway (external IDs); the sync comes later |
| No legacy data | Renewal overview incomplete for earlier years | Officials add old assignments by hand, marked "added later" |
| Data protection unresolved | No production use | Test data only until the controller is settled |
| Rules change yearly | Wrong suggestions | Rule sets as versioned data, suggestion only, the committee decides |
