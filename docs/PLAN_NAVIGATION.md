# Plan: the signed-in workspace — context switcher and section sidebar

Status: **agreed, not built** (2026-10-25; decisions in §9). Story Z-10, issue #28. Chosen in a TOAD (`low`) over five options — object
first with a context switcher and a section sidebar (E) scored 20, object first with a
to-do home and jump search (D) 19, today's object-first pages polished (A) 18, a dashboard
14, task first 12. E is the structure; D's to-do list becomes each context's *Overview*,
its jump search a later addition. Wireframes: the "Navigation wireframes" canvas.

The problem it solves, in the user's words: people cannot find the page for an action
(where are the minors, where do I add a new person) and cannot tell where they are.

## 1. The rules

1. **All work happens in the user space — My space — and only there has a sidebar.**
   Every change anyone makes on the site (a squad, a claim, an event's set-up, a post)
   is made in My space; the public site only shows. A guest never sees the sidebar. The public site — leagues, events, clubs, results, news — keeps its top
   navigation and its full width for everyone, signed in or not: it is read on phones by
   people who sail and watch, and a sidebar there would serve nobody — **no sidebar on a
   public page, signed in or not** (decided). Signed-in people get
   **one** door from the public header, *My space*, and from every public page of an
   object they work on a *Work on this* link to that object's context (an event page →
   its context in the workspace).
2. **Two levels, never a tree.** Top: the **context switcher** — which club, series or
   event (or *Me*, or the *League office*) I am working in. Below: the **sections of that
   one context**. A tree of every context with every section would be 40 lines for a
   team manager and 400 for the league office.
3. **What I hold decides what I see — the model, not a role.** A section is shown when
   I hold one of its relations on the object (directly, or through the model: a series
   manager on its events, the host club's on its events). The rule is declared once
   (`web/src/lib/workspace.ts`, which replaced `spaceTabs.ts`) and read by the sidebar, the routes' guards and
   the handbook's places, as the tabs are today.
4. **Several roles on one object add up; they never duplicate.** A club admin who is
   also its treasurer sees one *Money* group, with every page either role brings. Groups
   are ordered by the work, not by the role.
5. **Absent, never disabled.** A section I cannot use does not exist for me (the
   project's rule since A-12). A group whose sections are all absent disappears; a group
   with one section shows as that section, without a heading.
6. **Every page answers "where am I" twice**: the switcher names the context
   (`Club · ASVW`), the sidebar highlights the section, and the breadcrumb in the header
   joins them (`ASVW › Sailors › Minors & guardians`).
7. **What waits for me is never more than one click away** — the to-do list from
   option D, built into the structure rather than beside it (§4): every context opens on
   its *Overview* with its to-dos, *Me* on all of them, and the switcher and the sidebar
   carry the counts. Counts, not alarms.
8. **One home per object.** An object's administration lives in its own sidebar, not in a
   second place: `/admin` shrinks to the *League office* context (the site's own work).

## 2. The context switcher

```
┌───────────────────────────────┐
│ 🔍 Find a club, series, event │   (shown from 8 entries on; the league office: always)
├───────────────────────────────┤
│ Me                             │
│ League office      admin       │   only with a site relation
├─ Clubs ───────────────────────┤
│ ASVW               admin·mgr   │
├─ Series ──────────────────────┤
│ 2. Segel-Bundesliga 2026  sail │
│ Junioren-Segelliga 2026   mgr  │
├─ Events ──────────────────────┤
│ Act 3 · Warnemünde   host  ③   │   next first; ③ = waiting
│ Act 2 · Kiel         race off. │
│ ▸ Earlier (4)                  │   past events folded
└───────────────────────────────┘
```

- **The entries are "mine"** — exactly `GET /api/me/contexts`: a relation held directly,
  or sailing there. Each shows its relations as short chips (the order of
  `RELATION_ORDER`), and its waiting count.
- **Inherited objects are reached inside, not listed.** A series manager's events are
  under the series' *Events* section; opening one makes the event the context, and the
  breadcrumb says `Junioren 2026 › Act 2`. The switcher then shows it under **Recent**
  (last five), so it is one click the next time — without listing every event of every
  series a person manages.
- **The league office reaches anything** by the search at the top (any club, series,
  event, sailor), not by a list.
- **Order**: Me, League office, clubs, series (current year first, drafts after), events
  (upcoming by date, then past folded).
- **Recent** (the last five contexts opened) and **last visited** are kept **per
  browser** (decided) — a convenience, never needed to work; a phone starts without them.

## 3. The sections, per context

Each table lists every section a context can have and who has it. "Organizers" = the
object's `admin` and `manager` (for an event also: the series' and host club's, and the
site's race committee, as the model says).

### Me — everyone signed in

| Group | Section | Who |
|---|---|---|
| — | **Overview** — every to-do of every context (§4), each a link to its section | all |
| Me | Profile & account · My waivers · My claims · Documents · Bank account | all |
| | **My clubs** — my memberships, invitations to accept or decline, *Ask to join* (V-15; after #40) | all |
| My children | each linked child: waiver status, *Accept online* | `guardian` |

### Club

| Group | Section | Who |
|---|---|---|
| — | **Overview** — waiting: crews, waivers, minors without guardian, claims | member, organizers, treasurer |
| People | **People** — one list of everyone with a membership (`ClubMembership`, any status), filtered and sorted on the server (`PersonFilter`); *＋ Person* (new, or existing by email — an invitation when they are in another club); roles, membership, a person's details (V-8, V-4, V-15) | member reads the active roster · club `admin` writes membership and roles · organizers write details |
| | **Minors & guardians** | organizers |
| | **Waivers** — who is cleared for which series/event | organizers |
| Racing | **Squads** — one section; a picker for the series registration (or stand-alone event) whose squad it shows | member reads · organizers write |
| | **Events & crews** — each event the club is entered in, with its crew (an act of a series or a stand-alone event); a **team picker** when the club enters several teams (`KYC 1`, `KYC 2`, VA-13) | member reads · organizers write |
| | **Hosting** — events the club hosts, *+ New event* | organizers |
| Money | **My claims** to the club | member |
| | **Decide claims** · **Payment runs** · **Bank account** | organizers, `treasurer` |
| Club | **Club page** — name, crest, address | club `admin` |

*People* replaces *Members* and *Sailors* (decided 2026-10-25, #40, `docs/PLAN_PEOPLE.md`
§4): members and sailors are one `Person`, membership one `ClubMembership`. Until #45
builds it, the club has *Members* and *Sailors* as before; their addresses then redirect
to *People*.

**Series and event are the two objects; "matchday" is not a third.** A matchday is an
event's number within its series (`Event.matchday`, "Matchday 2 · Kiel"); a stand-alone
event has none. So the sidebar says *Events & crews*, never *Matchdays*, and an event's
row shows its matchday when it has one. The same word in the series
(*Events*) and the club (*Events & crews*) means the same rows.

A hosted event is *not* edited here: *Hosting* lists them and opens the event's context.

### Series

| Group | Section | Who |
|---|---|---|
| — | **Overview** — readiness, open registrations, waiting | everyone with a relation |
| Sailing | **My team** — the squad I am in, my waiver for the series | `sailor` |
| Series | **Events** — its acts, each opening the event's context | all |
| | **Standings** (links to the public table) | all |
| Organize | **Clubs & registrations** · **Dates & publication** · **Squad size & scoring** | organizers |
| Officials | **Race committee & jury** of the series | organizers |
| Editorial | **News & pictures** for the series | `editor` |

### Event

| Group | Section | Who |
|---|---|---|
| — | **Overview** — readiness reasons (VA-8), what waits | everyone with a relation |
| Sailing | **My crew** | `sailor` |
| Set up | **General** · **Clubs** · **Boats** · **Pairing list** · **Publication** | organizers |
| | **People** — officials and helpers | organizers |
| Race day | **Check-in** — crews and waivers | organizers, `race_officer` |
| | **Race control** · **Results** · **Trackers** | organizers, `race_officer` |
| | **Notice board** — announcements | organizers, `race_officer`, `jury` |
| Money | **My claims** on this event | its `manager`, `race_officer`, `jury`, `helper`, `treasurer` held directly |
| | **Decide claims** | the event's `manager`, the host club's `manager`, `treasurer` |
| Editorial | **News & pictures** for the event | `editor` |

The event's state shapes the order, not the content: before the start *Set up* is open
and *Race day* folded; from the first race the reverse (set-up is frozen anyway, VA-8).

### League office — only with a site relation

| Section | Who |
|---|---|
| **Clubs** · **Series** (+ new) · **Events** · **Sailors** · **Accounts** | site `admin` |
| **Events** — those it runs | site `race_officer` |
| **News** · **Media** | site `editor`, `admin` |
| **Imports** (SAP, Manage2Sail) | site `admin` |

An object opened from here becomes the context, as from the switcher.

## 4. To do — option D, built in

D's best idea was a list of what waits for me, each line one click from where it is
done. In E it is not a separate page competing with the structure; it **is** the first
page of the structure, in three places that all read the same items:

| Where | Shows | Example |
|---|---|---|
| **Me › Overview** — the landing page after sign-in | **Live now** (below), then **To do** — every to-do of every context, grouped by context, most urgent first — then **Last visited** | *ASVW — 2 minors without a guardian · Act 3 — 3 waivers missing · Me — 1 claim rejected*, then *ASVW › Squads · Act 3 › Check-in* |
| **<Context> › Overview** — what a context opens on | that context's to-dos, then its state (readiness, next date) | *Act 3: not ready — 2 clubs missing, no pairing list* |
| **Counts** in the switcher (per context) and the sidebar (per section) | the number only | `ASVW ③` · `Minors & guardians 2` |

**The landing page, in this order** (decided): *To do* first, then *Last visited* (the
last five sections opened, per browser — straight to the section, not to the context's
overview). With nothing to do, *Nothing waits for you* in one line, and *Last visited*
moves up.

**Live now — when an event I work on is live**, the landing page opens with it, above
the to-dos, so the race day does not start with a search (decided). One block per live
event (`status` `live`, or a race day today), holding the sections *my* relations give me
there, in the order the day needs them:

| My relation there | Live now offers |
|---|---|
| `race_officer`, organizers | **Race control** (full screen) · Results · Check-in · Notice board |
| `jury` | **Notice board** · Results |
| `helper` | the event's Overview (times, people) · My claims |
| `sailor` | **My crew** · the public live view |
| editors | the public live view · News & pictures |

The event's own *Overview* leads with the same block while it is live.

**One to-do = one row of data** — what the API already returns, extended by where it is
done:

```
{ code: "minor_without_guardian", count: 2,
  context: { kind: "club", id: 7 }, section: "minors",   // the link
  severity: "soon" }                                     // now | soon | info
```

- **Every line is a link to the section that clears it**, never to a page that merely
  explains. Clearing it there makes it disappear (the mutation invalidates
  `/api/me/contexts`, as today).
- **Computed, never stored** — like waiver status and readiness: no to-do table, no
  "mark as done". Something that is no longer true is no longer listed.
- **Worded by the page from the code** (`needs.<code>` in i18n, ICU plurals), as now.
- **Only what I can act on.** A to-do appears for those who hold the section it links to;
  a member sees *their* missing waiver, not the club's.
- **Severity orders, colour does not shout**: *now* (a race day within 7 days, a deadline),
  *soon*, *info*. Within one, by date.
- **Nothing waiting** says so in one line — *Nothing waits for you* — and the overview
  shows the context's next dates instead.

**The to-dos** — today's codes, and the ones the roles of §5 need. **All of them are
built** (decided), the new ones one by one:

| Code | Context › section | For | |
|---|---|---|---|
| `waiver` | series/event › My team / My crew; Me › My waivers | `sailor` | exists |
| `ward_waiver` | Me › My children | `guardian` | exists |
| `documents_expired` | Me › Documents | all | exists |
| `claim_rejected` | Me › My claims | the claimant | exists |
| `claims` | club/event › Decide claims | organizers, `treasurer` | exists |
| `squad_below_min` | club › Squads | organizers | exists |
| `crew_missing` | club › Events & crews | organizers | exists |
| `crew_waiver_missing` | club › Waivers | organizers | exists |
| `minor_without_guardian` | club › Minors & guardians | organizers | new |
| `sailor_without_birth_date` | club › People, filtered *No date of birth* (no waiver possible without it; *Sailors* until #40) | organizers | new |
| `membership_requested` | club › People, filtered by status *requested* (V-15) | club `admin` | after #40 |
| `membership_invited` | Me › My clubs (V-15) | the person | after #40 |
| `payment_run_open` | club › Payment runs (issued, not booked) | organizers, `treasurer` | new |
| `event_not_ready` | event › Overview (the readiness reasons, VA-8) | organizers | new |
| `event_unpublished` | event/series › Publication (dates set, still a draft) | organizers | new |
| `checkin_waivers_missing` | event › Check-in (race day within 7 days) | organizers, `race_officer` | new |
| `results_missing` | event › Results (live event, races without results) | `race_officer` | new |
| `registrations_open` | series › Clubs & registrations (applications to decide) | organizers | new, when applying exists |
| `league_office` items | League office › … (clubs not yet in a league, imports failed) | site `admin` | new |

Each new code is a story's acceptance criterion and a test (`test_my_space.py`), as the
existing ones are.

## 5. Combinations — what real people see

| Person | Switcher | Notable |
|---|---|---|
| Sailor, adult (ASVW, 2. Liga) | Me · ASVW · 2. Liga 2026 · Act 3 | ASVW: Overview, Members (read), Squads, Events & crews, My claims. Series: My team. Event: My crew |
| Parent, no club | Me | Me: *My children* only — no empty contexts |
| Team manager, ASVW (G. Voigt) | Me · ASVW · (series/events they sail in) | ASVW: everything but *Club page*; *Hosting* lists Act 3 → its context |
| Club admin + treasurer | Me · ASVW | one *Money* group with all four pages |
| Event manager of Act 3 (orga@) | Me · Act 3 | Act 3: Set up, Race day, Money (both), no Editorial |
| Race officer at Act 2, jury at Act 3 | Me · Act 2 · Act 3 | Act 2: Race day + My claims; Act 3: Notice board + My claims |
| Series manager (Junioren) | Me · Junioren 2026 · Junioren 2027 (draft) | events via *Events*, then under Recent |
| Series editor (presse@) | Me · 2. Liga 2026 | Series: Overview, Events, Standings, **News & pictures** — nothing to organize |
| Site editor (redaktion@) | Me · League office | League office: News, Media only |
| Site admin | Me · League office · (search) | League office complete; any object by search |
| Sailor who also helps at an event | Me · club · series · Act 3 | Act 3: My crew **and** My claims (helper) |

## 6. Layout

- **Laptop (≥1100 px)**: header 60 px (logo · switcher · breadcrumb · search · account),
  sidebar 248 px, content fluid to 1200 px. Groups are small uppercase headings; a group
  never collapses on its own — the list is short because it is one context.
- **Narrow laptop/tablet (768–1100)**: the sidebar shrinks to 64 px icons with tooltips,
  opens over the content on demand.
- **Phone**: no sidebar. Under the header one bar with two buttons —
  `ASVW ▾` (switcher, full-screen sheet) and `Minors & guardians ▾` (sections, bottom
  sheet). Two taps to any section, and the bar itself says where I am.
- **Public pages for a signed-in person**: the public layout plus *My space* in the header
  (and *Work on this* on an object's own page) — no sidebar.

## 7. URLs

| Today | New |
|---|---|
| `/me` | `/me` — *Me › Overview*, the to-dos (§4) |
| `/me/profile?tab=…` | `/me/profile/<section>` |
| `/me/club/:id?tab=…` | `/me/club/:id/<section>` |
| `/me/series/:id?tab=…` | `/me/series/:id/<section>` |
| `/me/event/:id?tab=…` | `/me/event/:id/<section>` |
| `/admin?tab=…`, `/admin/<area>/new` | `/office/<section>`, `/office/<area>/new`; an object's admin work moves into its context |
| `/events/:id/race-control` | stays (full-screen tool), reached from *Race day* |

Old URLs redirect; the handbook's `place:` links follow the declaration, so they move
with it (B-18).

## 8. Steps

1. **Story first**: A-11 (the administration's tabs), A-12 (doors), Z-8/S-7 (my space)
   are rewritten into one story for the workspace; acceptance criteria from §1 and the
   combinations of §5 as its examples.
2. **The declaration**: `spaceTabs.ts` becomes `workspace.ts` — contexts, groups,
   sections, each with its `for` rule; the switcher entries from `/api/me/contexts`
   (+ `recent`). Unit-tested against the §5 table.
3. **Shell**: `WorkspaceLayout` (header switcher, breadcrumb, sidebar, phone bar) around
   today's context pages; today's tab panels become sections unchanged. *Visible win,
   no backend change.*
4. **Move the admin work**: the event panel's steps become the event's *Set up* and
   *Race day* sections, the series panel the series' *Organize*; `/admin` becomes
   `/office` for site relations. Squads, sailors and minors split out of *Members*.
5. **To do** (§4): `section` on every need, the new codes one by one, each context's
   *Overview*, then *Me › Overview* as the landing page; counts in switcher and sidebar.
6. **Search** in the switcher (league office, then everyone over their own contexts and
   sections — "minors" finds *Minors & guardians*).
7. Handbook and e2e: specs address sections by `data-testid`
   (`workspace-section-<context>-<key>`); one spec walks the §5 table per account of the
   seed.

## 9. Decisions (2026-10-25)

| Question | Decided |
|---|---|
| Landing page | *Me › Overview*: **To do first, then Last visited**; *Live now* above both while an event I work on is live (§4) |
| Recent / last visited | **per browser** |
| Several teams of a club in one series | **one section with a picker**: *Squads* picks the registration, *Events & crews* the team |
| Race officer at the venue | the landing page's **Live now** block leads to Race control and the day's sections |
| `/admin` | becomes **`/office`**, the league office's own work; every object's admin work moves into its context |
| Public pages | **no sidebar**, signed in or not — all work is done in My space |
| New to-do codes | **all of them** |

Still open: none for the structure. Wording of sections and to-dos is the i18n's business,
settled in the story.
