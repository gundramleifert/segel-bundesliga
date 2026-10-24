# Administration

Part of the [user stories](README.md); the format, the status marks and the
identifier rule are explained there.

Administration sets up what everyone else works on: clubs, the series of a year and
who sails in it, the accounts and their roles. The last group is the screens themselves,
which have to work on a phone because the administrator stands on a jetty as often as
at a desk.

## Master data

### A-1 ● Create clubs
As **administration or editorial** I want to **create and maintain clubs**,
so that **teams, accounts, and matchdays can reference them**.

Acceptance criteria:
- Name, abbreviation, and location are required; website and crest optional.
- The address (slug) is created from the abbreviation; umlauts are spelled out so `BYCÜ` and
  `BYC` don't collide. A taken address is rejected rather than silently overwritten.
- Abbreviations are **not** normalized: `BYC (BA)` and `BYC (BE)` are different clubs.
- Race committee and club accounts cannot do this.

Endpoints: `POST /api/admin/clubs`, `PATCH /api/admin/clubs/{slug}`

Tests: `api/tests/stories/test_master_data.py::TestClubCreation`

### A-7 ● Club can exist without competition
As **administration** I want to **create a club that does not yet participate in any competition**,
so that **master data and participation remain separate**.

Already built that way (see [A-1](#a-1--create-clubs) and
[A-3](#a-3--assign-clubs-to-series)) and recorded here because it is easily forgotten:

- A club is created with its **name**, nothing else.
- It can maintain its page, have organizers and sailors, without belonging to a series.
- Publicly, it only appears with its first **accepted** participation.

Tests: `api/tests/stories/test_series_assignment.py::TestClubCreationAndAssignment`

### A-14 ● Import clubs, past seasons and event documents from SAP Sailing and Manage2Sail
As **administration** I want to **pull what SAP Sailing Analytics and Manage2Sail already
hold into this site with one command**, so that **past seasons, the clubs and the
notice-board documents are here without being typed in**.

The two systems hold different halves of a competition (`docs/manage2sail.md` §6): SAP
the league's matchdays — races, boats, the scored results; Manage2Sail the registrations
and the event's documents (notice of race, sailing instructions, notices to competitors).

Acceptance criteria:
- **A command, not a screen:** `uv run python -m app.imports sap …` and
  `… m2s …` in `api/`. Only public endpoints are read — no SAP secret, no M2S token — and
  nothing is ever written back to either system.
- **SAP** (`sap --year 2023`, `sap --years 2021-2023`, `sap --regatta "<name>"`,
  `sap --all`): every regatta named
  `1./2. Segel-Bundesliga YYYY - City (n)` becomes an **event** in the series
  `1./2. Segel-Bundesliga YYYY` of the league `dsbl`, with its clubs entered, its boats
  (sail number and the colour SAP has), 16 flights of races and every team's result.
  The matchday is the `(n)` in the name, or the order of the dates where the year's
  names carry none. Points are then **derived** here (`recompute_event`), never copied.
- **The Junioren-Liga** is on another SAP host, `hnv.sapsailing.com` (`--base-url`,
  decided 2026-10-23 — `docs/findings.md` §3a): every regatta named
  `Deutsche Junioren Segel-Liga YYYY - Act n …` becomes act *n* of the series
  `Junioren-Segelliga YYYY` of the league `junioren-liga` — the seed's series of that
  year when there is one. A suffix like `(Finale)`, `Nord` or `Mitte` goes into the
  title. The names carry no city, so the act has no venue until someone sets it. The
  cup (`… Pokal …`) is no act and is not imported.
  - **A club can sail two teams in one act** (`KiYC 1`, `KiYC 2`): the number after the
    code is the team, the code before it the club. The second is a team of its own —
    `KYC (SH) 2`, in the act and in the series, scored on its own as SAP scores it.
  - **The Junioren host spells some codes differently**, and an explicit alias table maps
    those to ours (`BaYC` → `BYC`, `KiYC` → `KYC (SH)`, … in `app/imports/sap.py`) — a
    reviewed line per club, still never a name comparison.
  - A placeholder competitor (`No Show`) is no club: it is reported, not entered.
  - Without tracked starts an act takes the dates the regatta list gives (`startDate`,
    `endDate`) — the juniors' acts track none — and counts as over once its last day, or
    else SAP's last scoring update, lies a day back.
- **Manage2Sail** (`m2s --event <uuid>`): the event (title, dates), the clubs and teams
  of its entry list, and the **documents** on its notice board — title, kind (notice of
  race, sailing instructions, notice, other), date and the public download link. The
  file stays at Manage2Sail; the site links it. `--to <event id>` attaches it to an event
  that already exists here — the usual case, since the SAP import or an organizer created
  it.
- **Matching is by `ExternalId`, never by name.** A club is keyed by its **club code**
  (SAP's `shortName`, M2S's `ClubCode` — `HSC`, `NRV`), case-insensitive, since both
  systems spell the names differently. A club this site already has with that code as its
  short name is linked on the first run rather than duplicated; an unknown one is created.
  Events, races and documents are keyed by the source's UUID.
- **Repeatable:** a second run with unchanged data changes nothing and says so.
- **The race committee wins** (Domain decisions): a result already recorded here that
  differs from the source is kept and reported as a conflict, never overwritten.
- SAP's `carriedPoints` — points a team carries into the matchday — become the team's
  **matchday penalty** (Story WL-4), under the same rule.
- **Imported competitions start as drafts**, unless `--publish`: a past season appearing
  on the public site is a decision, not a side effect.
- **Staging imports on every build** (`api/Dockerfile`): on top of the seed, the seasons
  of the build argument `SAP_IMPORT_YEARS` — **`2025-2026` by default**, empty to skip —
  published, from `SAP_BASE_URL` (default `www.sapsailing.com`). A failed or empty import
  never fails the build. The public SAP server has no season after 2023, so the default
  imports nothing until the newer seasons' SAP instance is known and set. **The
  Junioren-Liga** follows (decided 2026-10-23): `JUNIOR_IMPORT_YEARS` (default `2026`)
  from `JUNIOR_SAP_BASE_URL` (default `hnv.sapsailing.com`), the same way.
- Each run is an `ImportRun` row and prints what it created, updated, left unchanged,
  and what conflicted or failed.
- Sailors are **not** imported: SAP carries none for the league (its "sailor" is the club),
  and Manage2Sail's public list has names but no id to match them by. That is VA-1's job,
  with the check-in report's World Sailing ids.

Open: show the imported documents on the matchday page (the notice board is still
placeholder content, `web/src/content/`, issue #14's question 5); SAP's attribution notice
under imported results (`docs/findings.md` §3).

Tests: `api/tests/stories/test_imports.py::TestSapImport`,
`api/tests/stories/test_imports.py::TestJuniorenImport`,
`api/tests/stories/test_imports.py::TestManage2SailImport`,
`api/tests/unit/test_import_parsing.py`

## The series and who sails in it

### A-6 ● Create series and select clubs
As **administration** I want to **create a series and select clubs in the process**, so that
**a new year is set in one step**.

Acceptance criteria:
- To create, **name and year** suffice; without its own abbreviation, the name applies.
- **Clubs can be selected immediately** — they become the teams. They then appear in this
  series on the public page.
- Participants can be changed later.
- A club under which races have already been **sailed in this series** cannot be removed:
  results depend on it.
- An unknown club is **named**, not silently skipped.
- Administration sees **all years**, not just the current — they plan ahead. Publicly only
  the current year remains visible.
- A **series' manager** (Story Z-2, journey J-4) edits their series in the same *Series*
  tab — its clubs, squad limits, description, publication — and sees only their own
  series there; creating a series stays the league office's, so the tab has no *New
  series* button for them. Until 2026-10-24 the tab showed them the editor's notice
  ("created by the business office only") although the API let them edit.

This is the opposite direction to [A-3](#a-3--assign-clubs-to-series): there you attach a
club to multiple series, here a series to multiple clubs. Both write the same `Team` rows.

Endpoints: `POST /api/admin/series`, `PATCH /api/admin/series/{id}`,
`PUT /api/admin/series/{id}/clubs`, `GET /api/admin/series`

Tests: `api/tests/stories/test_create_series.py`, `e2e/lifecycle.spec.ts`

Open: The interface for this is missing — only via API so far. Currently only `admin` has
access; editorial may also create clubs. Whether that should remain is to be decided.

### A-3 ● Assign clubs to series
As **administration or editorial** I want to **assign a club to one or more series**,
so that **it appears in the right competitions**.

There are multiple series side by side: 1st and 2nd German Sailing League, Juniors, Sailing
Champions League — each for a specific year. A club can compete in multiple at once.

Acceptance criteria:
- A newly created club does **not** appear on the public page as long as it is not assigned
  to a series.
- A club can be assigned to **one or multiple** series.
- **The year is in the series.** An assignment to "DSBL 2026" does not apply to "DSBL 2027" —
  there you must assign anew.
- An assignment under which races have already been sailed cannot be removed: results depend
  on it.
- Administration sees even **not yet assigned** clubs; otherwise, they could not be found.

Model: the assignment *is* `Team` — (club, series). No separate table is needed.

Endpoints: `PUT /api/admin/clubs/{id}/series`, `GET /api/admin/clubs`,
`GET /api/clubs?year=&series=`

Tests: `api/tests/stories/test_series_assignment.py`

### A-9 ● Accept or reject participation
As **administration** I want to **accept or reject applications**,
so that **only those who belong come to the field**.

Acceptance criteria:
- Administration sees all open applications per series.
- **So does the series' organizer, for their series** — the `manager` of the series (or of
  the event, for an application to one event), who decides them like administration does.
  They could already set the series' clubs directly (A-6), so deciding an application
  gives them nothing new; refusing it only sent them to the league office for a club
  they could have added themselves (found by Journey J-4, decided 2026-10-17). Listing
  without naming their series or event, or deciding someone else's, is refused (403).
- **Accepting** makes the club a participant — from then on everything applies as with a
  directly set assignment.
- **Rejecting** needs no reason but can have one: the club should learn why.
- Administration can **continue to assign directly**, without application. The path from above
  remains; the application is a convenience, not a requirement.
- An accepted participation under which races have already been sailed cannot be revoked — results
  depend on it.
- Every decision is logged: who, when, what.

Endpoints: `GET /api/admin/applications`, `POST /api/admin/applications/{team_id}/accept`,
`POST /api/admin/applications/{team_id}/reject`

Tests: `api/tests/stories/test_participation.py::TestDecidingOnApplications`

## Accounts and roles

### Z-2 ◐ Access is a relation tuple: user · relation · object
As an **administrator** I want to **say who is what to which thing** — manager of club
A and B, race officer of event C, admin of the site — so that **everyone can only do
what they are responsible for, and a club running its own regatta here never holds the
league's keys**.

Permissions are **relation tuples** in the Zanzibar/OpenFGA sense, at the size this site
needs and without the server: ``user:relation:object``. The model is written in
OpenFGA's DSL (`MODEL` in `app/models/auth.py`) and that string *is* the definition —
parsed at import, interpreted by `User.can(...)`. The tuples live in one table (`Grant`,
`access_grant`) whose object is one of four foreign keys, all NULL for the site: the
database cascades and joins, and a check needs no lookup.

The model — almost every relation is scoped by a club, a series or an event:
- `site`: `admin`, `editor`, `race_officer` — the league office and its race committee.
  The site's admin is admin of everything.
- `club`: `admin` decides who is **in** the club — members (V-8, V-9), organizers (A-8),
  the club's crest (V-3), club assignment (Z-3), the club's tuples among its members;
  `manager` decides who **sails** — squads (V-1), lineups (V-2), registrations (V-5,
  V-6); `treasurer` pays the costs of every event the club hosts (Story F-1). A club
  has no race committee of its own: the events it hosts get theirs from the event, the
  series or the site, or from the club's admin, who is admin of those events.
- `series`: `admin` (everything within the series, its events included, and its people),
  `manager` (participants, events, publication — a cup series run by someone other than
  the league office), `race_officer`, `jury`.
- `event`: `admin` (everything within the event: setup, results, and who holds what on
  it), `manager` (the organizer of the event-organizer stories: setup, clubs, boats,
  schedules, publication — not the people), `race_officer` (results, race control,
  trackers), `jury` (the protest committee; announcements, VA-11), `treasurer` (checks
  and pays the event's expense claims, F-1), `helper` (works the day — no power on the
  event, but a claim on its costs and their documents seen by its organizers, VA-12).
- `sailor`: `guardian` — a parent the child's club linked (V-13), who accepts the child's
  liability waiver online while the child is a minor (S-8). Nothing implies it and it
  implies nothing; a sailor has no admin, so it is written by the child's club through
  its own endpoints, or by the site's admin.

The rewrite rules (`or … from …` in the DSL) say what implies what: an object's `admin`
is each of its other relations; a series' admin, manager, race officer or jury is that of
every event in the series; the host club's admin, manager and treasurer are those of
every event it hosts; the site's editor and race committee are managers of every event — the
league's committee keeps the setup rights it always had, while a race officer appointed
for one event only runs its races. Nothing else inherits.

Acceptance criteria:
- A tuple is written and deleted **one at a time**; deleting one leaves every other
  tuple of the person in place. (The earlier "set roles" endpoint rebuilt the rows from
  a list of names and silently dropped every per-club grant on any edit.)
- One person holds as many tuples as they have responsibilities — manager of two clubs
  and race officer of two events is four rows.
- The **schema decides what can be written**: `manager` on the site or `admin` on a
  club is refused (`tuple-relation-invalid`); an object that does not exist is a 404
  (`tuple-object-missing`); a malformed object string a 422 (`tuple-object-invalid`);
  a duplicate a 409 (`tuple-exists`).
- **Who may see and write tuples on an object: its `admin`** — through the model, so the
  site's admin everywhere, a series' admin on its events, the host club's admin on the
  events it hosts. An event's manager sets it up but does not name its people. A club's
  admin names only **active members** of the club (`tuple-not-a-member`), as A-8 always
  said; the site's admin names anyone. Anyone else is refused (`tuple-forbidden`). Site
  tuples are the site admin's alone.
- A race officer of one event enters results there and is refused next door, cannot
  change that event's setup, and the admin event list shows only the events their
  tuples reach. The league office's gates (`require_site`) count site tuples only.
- Deleting one's own `admin` is refused (`tuple-self-lockout`); deleting a club's last
  `manager` follows A-8 (`last-organizer`).
- A deleted tuple takes effect immediately, not when the token expires.
- **Every refusal of a guard is a typed problem** (RFC 9457, `app/auth.py`), never a
  sentence the screen has to parse: no token is `not-signed-in`, an expired one
  `session-expired`, a forged one `token-invalid`, a blocked account `account-inactive`
  (all 401); a missing relation is `forbidden` (403) with the relations that would have
  passed as `required`; an unknown event or series in the path is `<thing>-not-found`
  (404) before any permission question. Every guarded route answers this way.
- Every write and delete is written to the audit log with relation and object.
- A blocked account cannot sign in.
- **Bootstrap:** an address listed in `SBL_ADMIN_EMAILS` becomes `admin` automatically on
  its first successful sign-in (any provider) — otherwise a fresh deployment has no one
  who can write the first tuple at all. Checked on every sign-in, not just account
  creation. See `docs/deploy.md`.

**Summary roles.** The navigation and the help page still speak of roles; those are
**derived** from the tuples (`User.roles`, `Role`): `admin`, `editor`, `race_officer`,
`jury`, `treasurer` and `helper` for the relation held anywhere, `club_admin` for `admin` of some club,
`team_manager`, `series_manager` and `event_manager` for `manager` **or** `admin` of some
club, series or event (an admin is a manager, says the model). Never a permission check —
that is `authz.check`.

**One facade** (`app/authz.py`, decided 2026-10-17): every permission question goes
through `check` (FGA's Check), `read` (is exactly this tuple written), `list_objects`
(FGA's ListObjects) and `ensure` (check or a typed 403), objects named as `ObjectRef`
(`club:3`); writes stay in `app/services/grants.py`. Its names are OpenFGA's so the
in-process interpreter could become an OpenFGA server with the callers unchanged. What
that switch would still need: the checks become async calls, an event's `series` and
`host_club` become tuples (today they are foreign keys the check reads off the row),
and `DELETE /api/auth/tuples/{id}` names the tuple instead of its row id. Before this,
hand-written shortcuts disagreed with the model: a club's admin could not create an
event their club hosts, and a series' or host club's manager could not open a waiver
scan of the event.

Club **membership** is the `member` tuple on the club, written by the club's admin (Story Z-5).

Screens: the **Accounts** tab of `/admin` lists each account's tuples — relation, then the
object — with a delete on each and a "＋" that asks object type, relation and object, in
that order, offering only what the model defines. Each object carries its own side,
"People": who holds what on this event, series or club, with add-by-email and remove —
on the event panel, the opened series row and the club screen's Members tab, for whoever
is that object's admin. A series' organizer reaches `/admin` with the Series and Events
tabs, narrowed to their series; an event's organizer or jury with the Events tab alone.

Endpoints (FGA's vocabulary): `GET /api/auth/model`, `GET /api/auth/tuples?object=event:3`
(read), `POST /api/auth/tuples` (write: `{user, relation, object}`, user by email),
`DELETE /api/auth/tuples/{id}`; `UserOut.tuples` lists a person's, `UserOut.roles` the
summary roles.

Open: the Accounts tab does not yet filter by relation or object.

Tests: `api/tests/stories/test_login_and_roles.py::TestRoles`,
`api/tests/unit/test_authz.py`,
`api/tests/stories/test_login_and_roles.py::TestTuples`,
`api/tests/stories/test_login_and_roles.py::TestOrganizers`,
`api/tests/stories/test_login_and_roles.py::TestAdminWhitelist`,
`api/tests/stories/test_guard_problems.py::TestGuardProblems`,
`e2e/lifecycle.spec.ts` ("Z-2: access is a relation tuple, written and deleted one at a time")

### A-8 ● Set up club organizer
As **administration** I want to **give a club an organizer**,
so that **the club manages itself from then on**.

A club has two organizer relations (Story Z-2): its **admin** decides who is *in* the
club — members, organizers, crest, the club's tuples — and its **manager** decides who
*sails* for it — squads, lineups, registrations. An admin is a manager too, says the
model. A person can organize several clubs independently, each tuple written and deleted
on its own. The club screen and the Accounts tab go through the same
`app/services/grants.py`, so the last-organizer rule below holds whichever screen is used.
"Organizer" below means either relation; `club_admin` and `team_manager` are the summary
roles.

Acceptance criteria:
- Administration creates the account (name, email) and makes it the club's **admin** —
  the first account of a club can only come from administration: who has no one cannot
  name anyone.
- **The club's admin names more organizers for their own club.** The People panel on
  the Members tab writes `admin`, `manager`, `race_officer` or `member` on this club for
  any account, by email — an organizer need not be a member. **A person may organize
  multiple clubs** — a second club no longer fails because they already organize a
  different one; it fails only if they already hold *this* relation on *this* one.
- Revoking for one club is allowed too — but **at least one organizer (admin or manager)
  must remain** for that specific club; the last one can't step down until someone else
  has taken over. Revoking one club never touches a person's organizer status at any other
  club, and the account stays either way.
- **And at least one admin must remain** (decided 2026-10-18): the admin is who decides
  who is *in* the club, so a club left with managers only could no longer add a member, a
  treasurer or another organizer — it would have to ask the league office for every
  change. Removing the club's last `admin` is refused with the same `last-organizer`
  code until someone else holds `admin` on it; a manager may still go while an admin
  remains, because the admin is a manager too.
- Every grant and revoke is written to the audit log.

Endpoints: the tuple endpoints of Story Z-2 — `GET /api/auth/tuples?object=club:<id>`,
`POST /api/auth/tuples`, `DELETE /api/auth/tuples/{id}`. `ClubMemberOut.relations` says
what each member is to the club.

Screen: the Members tab on `/me/club/:id` (Stories V-12, S-7), People panel; administration uses the
Accounts tab or the same panel.
Tests: `api/tests/stories/test_club_members.py::TestOrganizers`,
`api/tests/stories/test_login_and_roles.py::TestTuples`

### Z-6 ● Removing an account deactivates it
As **administration** I want **removing an account to leave the row in place**,
so that **audit entries, past decisions, and entered results still resolve by id**.

Acceptance criteria:
- `DELETE /api/auth/users/{id}` sets `is_active = False` — it never deletes the row.
- A deactivated account can't sign in, and a still-valid token stops working immediately
  (`is_active` is re-checked on every request).
- Administration can't remove its own account (self-lockout guard).
- Only administration can remove an account.

Endpoints: `DELETE /api/auth/users/{id}`

Tests: `api/tests/stories/test_login_and_roles.py::TestRemoveAccount`

## The admin screens

### A-10 ● The admin screens have to work on a phone
As an **organizer standing on a jetty with a phone**, I want **the admin screens to be
operable at 412 px**, so that I **can fix a date or publish an event without finding a
laptop**.

Found by `e2e/lifecycle.spec.ts` under the `mobile` project (Pixel 7): **every** click on a
control inside an admin row was refused, each test timing out with Playwright's
"…intercepts pointer events" and naming a different interceptor every retry — sometimes the
row's own title block, sometimes an input from the create form far above, sometimes the
header's language switcher. The same controls worked at desktop width.

**The cause was not the rows.** `/admin` overflowed horizontally, and mobile Chromium
answers horizontal overflow by *zooming the whole page out to fit it*: `window.innerWidth`
reported **754 px inside a 412 px viewport**, the page rendered at ~55%, and pointer
coordinates no longer matched what was under them. A shifting cast of interceptors is what
that looks like from the test's side; unreadably small text is what it looks like to a
person.

The overflow itself came from the `grid gap-*` idiom used to stack the admin sections and
their form rows. A grid's `auto` column is sized by its items' **min-content** width, so
one wide box — the boat-setup table in `admin/events/GeneralDataStep.tsx` — widened its column, and because
grid items stretch to the column, *every* sibling section grew with it. The fix is to make
those columns able to be narrower than their content — which is now what `Stack` and
`CardGrid` are for (`components/Layouts.tsx`), so it cannot be forgotten by writing the
class string out again. The wide table then scrolls inside the nearest scroll container
rather than widening the page.

Two related defects were fixed with it, both in `web/src/index.css`: `scroll-padding-top`
so a scroll-into-view does not park its target beneath the `sticky top-0` header, and
`scroll-behavior: smooth` moved behind `prefers-reduced-motion: no-preference`.

Acceptance criteria:
- Every control in an admin row — manage/close, save, draw, publish, start, the crest pen —
  is clickable at 412 px width.
- **The page is never zoomed out**: `window.innerWidth` equals the viewport width, and
  `document.documentElement.scrollWidth` does not exceed it. That is the rule — the
  *document* must not be wider than the viewport. **Which** box scrolls instead is a
  separate choice, and it is now the content panel (`.panel-scroll` on `<main>`) rather
  than a box around each table: a page with two wide tables had two independent
  horizontal scrollbars, each ending in mid-air where its own box did, and neither moving
  the headings that belong with the columns.
- The row header wraps: the title and badges on one line, the actions below, each with its
  own hit area.
- **A matchday's facts are three lines, not one run.** Which competition, where and when,
  and how far along — three kinds of fact, and as a single dot-separated string they were a
  hundred and forty characters that wrapped mid-phrase. The status badge sits on the first
  of them rather than on a row of its own: "which matchday is this, and where does it
  stand" is one question. Within a group the separator is a comma ("Kiel, Kieler Förde"),
  between groups a dot — so the dot always means "a different kind of fact".
- **Tables are dense.** One rule sets cell padding for every data table (`.data-table` in
  `index.css`), because a results screen is read by scanning down it and generous padding
  means fewer rows in view and more scrolling to compare two of them. A cell that needs
  something else still overrides it with a utility. The standings tables are sized by their
  content rather than stretched to the panel: a table stretched to its container hands the
  leftover width to whichever column has no explicit one, which was the club column — and
  it holds an abbreviation.
- `ClubSelector`'s two panes stack on a narrow screen without their scrollable lists
  covering what follows them.
- Verified by **removing** the `testIgnore` from the `mobile` project and having
  `lifecycle.spec.ts` pass there — done; the `mobile` project now runs every spec.
- The zoom-out cannot come back silently: `expectNoSidewaysScroll` in `e2e/layout.ts`
  asserts both numbers on every admin visit, and `e2e/visitor.spec.ts` runs it over every
  public page.

Tests: `e2e/lifecycle.spec.ts` under the `mobile` project (every test in the file)

### A-11 ● The admin screen in tabs
As an **organizer**, I want the admin screen **split into tabs by what I am configuring**,
so that I **reach the one thing I came for instead of scrolling past four other areas**.

`/admin` grew by section: clubs, then series, then events, then sailors, then accounts —
five independent tools stacked in one column. Each is short on its own; together they are a
page nobody reads top to bottom, and on a phone the events section — the one used on a
jetty — is several screens down.

Acceptance criteria:
- Five tabs, in the order the work happens: **Clubs**, **Series**, **Events**, **Sailors**,
  **Accounts**. That is the same order the sections had, and the order is not alphabetical
  for a reason: a series needs clubs, an event needs a series.
- **The tab lives in the URL** (`/admin?tab=events`), so it can be linked, survives a
  reload, and the browser's back button steps between tabs. An unknown or missing `tab`
  opens the first tab the signed-in user may see rather than erroring.
- **A tab a role may not use does not exist for it.** Accounts is `admin` only, exactly as
  the section was; an `editor` sees four tabs, not five with one refusing.
- **Only the selected tab's panel is mounted.** This is the part that pays for itself: the
  page used to issue every area's queries on load — clubs, series, events, readiness,
  sailors, accounts — and now issues one area's.
- **The tab strip never widens the page.** Five tabs do not fit across 412 px, so the strip
  scrolls sideways inside its own box. The alternative is the failure Story A-10 documents:
  a page wider than the viewport, which mobile Chromium answers by zooming everything out.
- Switching tabs loses no work in progress in the sense that matters: nothing on this
  screen is a multi-step wizard, and every form is a create-or-save that either happened or
  did not. A half-typed club name is discarded when the tab changes, and that is acceptable
  where re-typing costs one line.

Tests: `e2e/lifecycle.spec.ts::A-11: the admin screen is organized in tabs`

### A-13 ● One list mechanism, and every long list is paged

As **someone working through several hundred sailors or accounts**, I want **to page,
sort and search every list the same way**, so that **finding one row does not mean
scrolling past all of them**.

Every list screen had grown its own arrangement: a `<ul>` of rows here, a table there,
a search box on two of them and not the others, and each one fetching the whole table.
`GET /api/sailors` answered with up to 500 people in one response and the screen showed
all of them; `GET /api/auth/users` had no limit at all. The two habits reinforce each
other — a list with no paging needs no page control, and a screen with no page control
has no reason to ask for less than everything.

**Everything the server can do stays on the server.** Filtering, ordering and counting
are one query against an index; a page that downloads every row in order to sort it in
the browser has not solved the problem it appears to have solved, it has moved it to the
slowest machine involved.

Acceptance criteria:
- **One envelope for every list that can grow**: `Page[T]` — `items`, `total`, `limit`,
  `offset`. Not a bare array with headers: the count belongs to the body, where the
  generated client types it and the screen can say "26–50 of 180" without a second call.
- `limit` defaults to 25 and is capped (100); `offset` starts at 0. An `offset` past the
  end returns an **empty page**, never a 404 — a list that shrank between two clicks is
  not an error.
- `total` counts what the filter matched, not what the page returned. It is the number the
  paging control is built from, so counting the unfiltered table would make every search
  claim more results than it can show.
- **Sorting is a parameter**, one column name with a `-` prefix for descending. An unknown
  column is refused (422) rather than ignored: a sort that silently does nothing looks
  exactly like a sort that did not fire.
- **Lists bounded by their own subject keep a plain array** — an event's participants, its
  boats, the pairing catalog, a club's members. The concept is one mechanism applied where
  a list grows with the database, not one shape imposed on every endpoint; an event with
  18 participants has no page two, and inventing one would only cost every caller an
  `.items`.
- **The frontend has exactly one table component**, built on TanStack Table (headless — it
  owns sorting and the row model, we own every element and class, so the `.data-table`
  surface, the density and Story A-10's width rules all still apply).
- **Page, sort and search live in the URL** (`?page=3&sort=-last_name&q=mann`). A row
  someone found is then a link they can send, and a reload does not throw the work away.
- **The table is the same on a phone.** It scrolls inside the panel rather than widening
  the page (Story A-10), and the paging control stays reachable without horizontal
  scrolling.
- A column that is sorted says so to a screen reader (`aria-sort`), and the header is a
  real button, so sorting is reachable without a mouse.

**Where this stands.** The backend is done: `app/pagination.py` and every list that grows
with the database — and since every one of them is also **searchable**, a screen no longer
has to filter what it downloaded. `q` narrows the *statement* before `paginate` counts it
(`pagination.apply_search`, one function rather than the same eight lines per router), so
`total` is the number of matches and page two of a search is a search. What each list
searches: the public club list and the admin one by name, abbreviation and city; the
public calendar and the admin event list by title, venue and host club — one query, two
outer joins, no lookup per row; the series list by name and short name; sailors by first
name, last name and email; accounts by display name and email. Searching is
case-insensitive and matches anywhere in the field, a blank or whitespace-only term is
**no** search rather than a search for nothing, and on the public lists `q` only ever
narrows: an unregistered club and a draft event stay unfindable however exactly they are
named.

The frontend spends it the same way everywhere. **Page, sort and search live in the URL**
(`?page=3&sort=-last_name&q=mann`, `lib/listParams.ts`): the three belong together because
they interact — a new term invalidates the page someone was on — and in the query string a
found row is a link that can be sent and a reload does not throw the work away. The hook
writes only its own keys, so `?tab=` and `?view=` survive, and it replaces rather than
pushes: paging should not fill the Back button with every step on the way.

Two shapes, and the difference is the part worth remembering:

- **A table of values** uses `components/DataTable` — the one table, on TanStack Table v9,
  headless: the library owns the sorting state model and the row model, every element and
  class is ours, so Story A-10's width rules and the `.data-table` surface still apply. The
  server sorts (`manualSorting`), a column is sortable exactly where its endpoint can sort
  it, each such header is a real button, and the sorted one carries `aria-sort`. Accounts
  and sailors are tables now; both were `<ul>`s with their own arrangement.
- **A list whose rows are editors** keeps being a list and takes only `useListParams` and
  `Pager`: the admin event list, where a row opens readiness, clubs, the draw, publication
  and closing, and the club list, where a row *is* the crest editor. Forcing those into a
  table of values would be the shape imposed where it does not fit — the mistake this story
  warns about for endpoints.

The club and event lists now search on the **server**, so a search finds what it should
rather than what happened to be downloaded. What still asks for the whole list at once
(`WHOLE_LIST`, the server's cap of 100, read through `useAsyncRows`) are the **selectors** —
a dropdown must offer every club — and the two screens that *count* acts per series out of
the event list. Those are honest ceilings rather than hidden ones: past a hundred, a
selector needs a search of its own and the counts need the server to count them.

Tests: `api/tests/stories/test_pagination.py` — the envelope in
`api/tests/stories/test_pagination.py::TestEveryPagedListSpeaksTheSameShape`, and the
search in `api/tests/stories/test_pagination.py::TestEverySearchableListSearchesTheSameWay`
(one parametrized case per searchable list: nothing matched is an empty page, `total`
counts the matches and not the page, case is ignored, whitespace is not a search) plus
`api/tests/stories/test_pagination.py::TestSearchingTheClubList`,
`api/tests/stories/test_pagination.py::TestSearchingTheEventCalendar` and
`api/tests/stories/test_pagination.py::TestSearchingTheSeriesList` for the fields each one
reaches and for what a visitor must **not** find. The frontend is covered by
`e2e/lifecycle.spec.ts::A-13: every long list pages, sorts and searches — in the URL`,
which pages the sailor table, reloads on page two, sorts a column both ways, searches for
one person out of a couple of hundred and opens the whole state as a deep link. What is
still untested: the `Pager` arithmetic at its edges ("26–50 of 180", the disabled buttons)
has no test of its own.

### A-12 ● The account menu, and the page's name
As **someone who uses this site on a laptop and on a phone**, I want **the navigation where
I expect it**, so that **the screen is spent on what I came to read**.

**Superseded in part by Story B-13 (2026-10-11).** This story first put the navigation in a
column on the left on a wide screen, and behind a burger on a phone. The site structure of
issue #14 replaced both with **one row on top** — logo, the leagues, the account button —
on every device, because the leagues *are* the navigation now and three names fit a phone's
row. What is left of this story is the account menu and the page's name.

Acceptance criteria:
- **Neither the row nor the menu may widen the page** (Story A-10).
- **A guest gets no menu** (2026-10-18): top right sits the **language** — a dropdown
  (`Select`) drawn as an entry of the row, like the leagues beside it, not as a form
  field; each language named **in itself**, "English", "Deutsch", never translated:
  someone looking for their own language is looking for the word they would recognise —
  and **Sign in**. Those are the only two things about the reader a guest has, and a
  menu that opened to show two entries was a tap more than either needed. A dropdown, not
  an EN|DE pair, because a third language fits a dropdown and would not fit the pair.
- **Signed in, the account button opens a menu**, on every device, holding everything
  that is about the *reader* rather than the page: my space (with its badge), Profile,
  *Administration* for the roles that can use it, Help, and the language. Each of those is
  used rarely, and as separate items in the frame they competed with the navigation for
  room — Help was a main nav entry beside Series and Clubs, which is not what someone
  comes to the site for.
  - **The language is a flyout submenu** there. It opens beside the row — to the right,
    or to the left when there is no room there, decided from the row's own rectangle when
    it opens: the account menu is anchored to the top right of the window, so "to the
    right" is off-screen as often as not. The chosen language stays on the row itself, so
    the menu says what it is without being opened.
  - On a phone it sits **top right**, where a phone's account button belongs, and opens
    downward pinned to that edge.
  - Escape closes it, a click outside closes it, following a link in it closes it —
    the three rules `useDisclosure` gives every panel on this site.
- **The legal pages are in the footer, not in the menu** (2026-10-18). Both footers — the
  official pages' and the internal screens' — carry the legal notice and privacy on every
  page, which is what § 5 DDG asks; a second copy in the menu only repeated them.
- **The page states its name once, and that place is its `<h1>`.** On the pages outside
  the leagues (my space, administration, a club, a sailor) a breadcrumb under the row
  names the page. The breadcrumb's last
  crumb — where you are — is the heading element, small type and all. A page with no `h1`
  has no outline for anyone reading it with a screen reader, and moving the name into the
  breadcrumb must not cost that. `PageHeader` no longer
  renders an `<h1>` — it was the same words the breadcrumb above it had just said — nor a
  subtitle, most of which restated what the page then showed ("18 clubs" above a list of
  eighteen clubs). It keeps `title`, because that is what the breadcrumb reads, and a
  `right` slot for the one control that belongs to the page as a whole. Facts that live
  nowhere else — a matchday's venue and dates — stay on the page as their own line, which
  is what they always were.
- **Sections do not explain themselves.** `Section`'s `hint` is gone with them: a
  paragraph above every admin form describing what the form obviously does is read once
  and skipped forever after.
- `admin` still appears only for the roles that can use it, because a link that ends in a
  403 is worse than no link, and *My space* for anyone signed in (Story Z-8 — it replaced
  "My club" and "Reimbursements").

Tests: `e2e/visitor.spec.ts::A-12: the account menu and the page's name`
