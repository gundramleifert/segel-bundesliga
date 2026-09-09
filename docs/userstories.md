# User Stories

Here we collect what the system should be able to do — from the perspective of those who use it. Each story gets an identifier (`B-1`, `WL-3`, …); tests carry the same identifier in their docstring. This makes it possible to look in both directions: What is already covered by this story? And which story does this test belong to?

**Roles:** `B` Visitor/Fan · `WL` Race Committee · `V` Club Manager ·
`R` Editorial · `S` Sailor · `A` Administration

**Status:** ○ open · ◐ partial · ● implemented and tested

Format:

```
### B-1 ● View league standings
As a **fan** I want to **see the current league standings**,
so that I **know where my team stands**.

Acceptance criteria:
- All 18 teams, places 1–18, fewer points rank higher.
- For each matchday, the position achieved there is visible.
- A not yet sailed matchday does not count.

Tests: `api/tests/stories/test_visitor.py::TestLigatabelle`
```

---

## Visitor and Fans

### B-1 ● View league standings
As a **fan** I want to **see the current league standings**,
so that I **know where my team stands**.

Acceptance criteria:
- All 18 teams, places 1–18, fewer points rank higher.
- For each matchday, the position achieved there is visible.
- A not yet sailed matchday does not count.

Tests: `api/tests/stories/test_visitor.py::TestLigatabelle`

### B-2 ● Review matchday results
As a **fan** I want to **review how a matchday turned out**,
so that I **can understand the course of events**.

Acceptance criteria:
- Complete daily standings across 18 teams; each team sailed once in 16 flights.
- The points are broken down by race, and the sum gives the overall standings.
- A running matchday shows an interim standing, a planned one shows no results yet.

`EventStandingRow.points_by_race`/`discarded_races` (`api/app/schemas/public.py`) carried the
per-race breakdown from the start, but `web/src/pages/Spieltag.tsx`'s daily standings only
rendered rank/team/net/total until now — the second acceptance criterion was met by the API but
not actually visible anywhere. The page now adds one column per flight (16, not 48 individual
races — clearer to read, still sums to the same total) showing that team's points for the
flight, "–" where not yet sailed, scrollable horizontally like the other result tables. It also
adds a clearly-marked, italic "≈ projected" total once any race in the matchday has been scored,
so a team that hasn't sailed yet no longer looks like it's provisionally winning outright with
`net = 0` — purely a display computation, never used for `rank` or sorting.

Tests: `api/tests/stories/test_visitor.py::TestSpieltagsergebnis`. The new UI additions
(flight columns, projected total) have no additional automated test — verified via
`pnpm typecheck`/`pnpm build` and against seeded data; Playwright e2e coverage for this page is
a separate, not-yet-started task.

### B-3 ● View pairing list
As a **sailor** I want to **know before the matchday which boat I'm on**,
so that I **can prepare**.

Acceptance criteria:
- All 48 races, boats identified by their color.
- In each race, each boat is crewed exactly once.
- In each flight, each team sails exactly once.
- Accessible before the matchday begins.

Tests: `api/tests/stories/test_visitor.py::TestPairingListe`

### B-5 ○ Follow live updates
As a **spectator** I want to **see current results on the page**,
so that I **can follow along while racing**.

Three views that must be current simultaneously:

1. **Running race** — which race is running, who is on which boat, and once results arrive,
   the finish.
2. **Live daily standings** — the standings of the running matchday, updated with each
   recorded race.
3. **Live season standings** — the league table including the running matchday.

Acceptance criteria:
- After the race committee enters results, all three views are current within seconds, without
  anyone reloading.
- The page never starts empty: the last known standing is there immediately, updates come
  after.
- If the connection drops, the page says so and continues showing the last standing, rather
  than silently presenting stale data as current.
- If there is no matchday now, the page leads to the next date instead of showing an empty view.

Technical: one poller **per event** on the server that distributes to all spectators —
never one request per visitor to the data source. WebSocket with SSE as fallback, because
WebSockets reliably fail on mobile networks and behind corporate proxies.

Tests: none yet

### B-4 ◐ Find clubs and dates
As a **visitor** I want to **find the participating clubs and dates**.

Open: club profile with squad and past results.

Tests: `api/tests/stories/test_visitor.py::TestVereine`

### B-7 ● View club page
As a **visitor** I want to **see a club's page**,
so that I **know who sails there**.

Acceptance criteria:
- Name, crest, location, and a **short description**; without a crest the club abbreviation
  takes its place.
- The **teams in the season** — a club can compete in multiple leagues, so a list. Each
  carries the league name with year.
- For each team, the **squad**: ten registered, helmsman first.
- For each team, the **matchdays of its league**, nested under the team — including those
  where the club sails. If the lineup is not yet set, the page says so.
- Events **without a series** cannot be nested under a team; they stand separately, assigned
  via the host club.
- **No contact details.** Names appear on every result list anyway; email and birth year have
  no place on a public page.
- The cards on `/vereine` lead to the club page.
- Without a league assignment, the page remains accessible and says so.

Tests: `api/tests/stories/test_vereinsseite.py::TestVereinsseite`

### B-8 ● View sailor page
As a **visitor** I want to **see who someone registers for and where they sail**.

Two levels that must not be confused:

- **Registration for the season** — a league's squad (`TeamMembership`, ten people).
- **Lineup for a matchday** — who actually sails (`EventCrew`, four people).

Someone in the squad does not necessarily sail every matchday. The page shows both
separately.

Acceptance criteria:
- Name, the clubs and leagues of the season with role, the matchdays with role.
- A substitute is registered but not placed anywhere — the page says so.
- No contact details, no birth year.
- Accessible without login.

Tests: `api/tests/stories/test_vereinsseite.py::TestSeglerseite`

---

## Access

### Z-1 ● Sign in without password
As a **user** I want to **use an identity provider of my choice** (Google, Microsoft,
or email), so that **the operator does not have to manage identities**.

Acceptance criteria:
- Google and Microsoft via verification of their ID token; email via a one-time code.
- The code is valid for ten minutes, can be used only once, and is locked after five failed
  attempts.
- It is stored only as a hash in the database.
- All paths lead to the **same** account, linked via the verified email address.
- The response does not reveal whether an account exists for an address.
- Accounts are created by creation, import, or **explicit registration** ([Z-4](#z-4--register-yourself)) — not silently when signing in with an unknown address.

Tests: `api/tests/stories/test_login_and_roles.py::TestAnmeldung`

### Z-2 ● Assign roles
As a **administrator** I want to **assign and revoke roles**, so that **everyone can only do
what they are responsible for**.

Acceptance criteria:
- Roles: `admin`, `editor`, `race_officer`, `club_manager`; multiple per account possible.
- A revoked role takes effect immediately, not when the token expires.
- The administrator's own role cannot be self-revoked.
- A blocked account cannot sign in.
- **Bootstrap:** an address listed in `SBL_ADMIN_EMAILS` becomes `admin` automatically on
  its first successful sign-in (any provider) — otherwise a fresh deployment has no one
  who can grant the first role at all. Checked on every sign-in, not just account
  creation. See `docs/deploy.md`.

Tests: `api/tests/stories/test_login_and_roles.py::TestRollen`,
`api/tests/stories/test_login_and_roles.py::TestAdminWhitelist`

### Z-3 ● Assign user to club
As a **club manager** I want to **assign a user to a club**,
so that **registrations, posts, and check-in go to the right club**.

Acceptance criteria:
- The assignment is tied to the account, not the matchday — it applies **across matchdays**.
- A club manager assigns only a club **they organize** (Story A-8 — that can now be more
  than one) and moves only people who are not yet assigned or already assigned to one of
  those clubs. Otherwise, other teams could be taken over.
- Administration is exempt and can set and remove any assignment.
- People are discoverable by name and email so the assignment is practical.
- Every change is logged: who, when, from which club to which.

Tests: `api/tests/stories/test_login_and_roles.py::TestVereinszuordnung`

### Z-4 ● Register yourself
As a **sailor** I want to **create an account for myself**, so that I **don't have to wait
for someone to register me**.

Acceptance criteria:
- Only **email address and name** are required.
- The address is initially just **claimed**; only when the one-time code is redeemed is it
  verified (`email_verified`). Anyone could type in someone else's address.
- The new account has **neither role nor club**. It can do exactly one thing: request club
  membership ([Z-5](#z-5--request-club-membership)).
- The response is **identical** for known and unknown addresses — otherwise, it would be
  possible to query who has an account here.
- Registration with an existing address **overwrites nothing**.
- Can be disabled via `SBL_ALLOW_REGISTRATION`.

Endpoints: `POST /api/auth/register`, then `POST /api/auth/email/verify`

Tests: `api/tests/stories/test_registrierung.py::TestRegistrierung`

### Z-5 ● Request club membership
As a **registered person** I want to **request membership in a club**, so that I **can sail
for them**.

Acceptance criteria:
- The request visibly awaits **the club's decision** (`pending_club`).
- A request does not yet make someone a member — that is precisely what it is about.
- Without a verified address it is not possible; otherwise, someone could flood clubs with
  requests using foreign addresses.
- As long as open, the request can be withdrawn.
- After rejection, a new attempt is possible; the person learns the reason.

Endpoints: `POST /api/club-memberships`, `GET /api/club-memberships`,
`DELETE /api/club-memberships/{id}`

Tests: `api/tests/stories/test_registrierung.py::TestAufnahmeAntrag`,
`api/tests/stories/test_vereinsmitgliedschaft.py::TestPersonFragtAn`

Open: More roles will be needed later.

---

## Event Organizer

### VA-1 ○ Import registrations from manage2sail
As an **event organizer** I want to **import registrations from manage2sail**,
so that I **don't have to type them in**.

Acceptance criteria:
- Import via M2S access **and** alternatively via file upload, so a missing token does not block.
- Assignment to existing clubs and teams via `ExternalId`, never by name comparison.
- The import is repeatable: a second run with unchanged data changes nothing.
- After the run, it is clear what was created, changed, skipped, and what could not be
  assigned.

Open question: Scope and access of the M2S export — to be asked at the league office
(see `docs/findings.md`, section 4).

Tests: none yet

### VA-2 ○ Self check-in with liability waiver
As an **event organizer** I want **teams to check themselves in at the event and confirm
the liability waiver**, so that I **have little work on event day**.

Acceptance criteria:
- **Check-in happens in advance, not on event day.** The link/QR opens a set number of days
  before the event (reuse the deadline pattern from V-2) and closes at event start. On event
  day the organizer only reads the status list — nothing legal is signed on the dock.
- A team checks in by itself (QR code or link), without any involvement from the organizer.
- During check-in, the crew is confirmed or corrected.
- The liability waiver is displayed in full text and must be actively confirmed.
- The confirmation is **documented proof**: who (authenticated account, not a typed-in name),
  when, which version of the text. The text version is tracked — a text changed later must
  not retroactively alter an old confirmation.
- The organizer sees at a glance which teams have checked in and which are missing.

Overlaps with story S-1: If the liability waiver is already available for the season, only
attendance needs to be confirmed at check-in. Check-in thus becomes much shorter.

Note: This is the legally most sensitive part of the project. Legal landscape and the two
constraints that actually bind (insurer's required form, guardian consent for minors) are
written up in `docs/findings.md` section 6. Before building, the league and its insurer must
confirm whether an authenticated online confirmation is accepted for adults; if not, everyone
takes the scan-upload path from S-1.

Tests: none yet

### VA-3 ○ Calculate and publish pairing list in the interface
As an **event organizer** I want to **calculate and publish the pairing list via the
interface**, so that I **don't have to operate command-line tools**.

Acceptance criteria:
- Team count, boat count, and flight count are set in the interface; calculation runs on the
  server, not in the browser.
- Calculation takes noticeably longer than a click — it needs a progress indicator and the
  ability to leave the page in between.
- **Before publishing, quality is displayed**: boat distribution per team, encounter frequency,
  boat changes between flights. The organizer decides rather than blindly trusting the result.
- The draw is **reproducible**: same input and same seed produce the same list. A draw must
  be provable in case of dispute.
- Generate multiple suggestions side by side and select the best.
- Publishing makes the list publicly visible (Story B-3) and can be undone as long as no
  races have been sailed.
- An already sailed race must not be overwritten by recalculation.
- Output as printable PDF that can be distributed to teams.

**Open decision:** This story elevates the generator from fallback to main function. Three
approaches are available — enhance the Python generator, call the existing Java tool from
the backend, or extend the Java tool with an interface. See `docs/findings.md`, section 2.

Implemented in the backend is the chain: start job, query progress, read quality report,
publish — `POST /api/admin/events/{slug}/pairing/jobs`, `GET /api/admin/jobs/{id}`,
`POST /api/admin/events/{slug}/pairing/publish`. Calculation is done with the Java tool.
The interface is missing.

Tests: `api/tests/unit/test_pairing_generator_jar.py`, `api/tests/unit/test_pairing_generator.py`

### VA-4 ○ Participants write posts on the homepage
As an **event organizer** I want to **enable participants to easily publish posts on the
homepage**, so that **the page lives without me writing everything myself**.

Acceptance criteria:
- A participant writes a post with text and images, without needing to know editorial tools.
- The post appears under the name of the club or person, not anonymously.
- Images are resized on upload; mobile format works.
- A draft can be saved and continued later.

**Decided (29.08.2026): Club account with editorial approval.**

- **One account per club**, not per sailor — 18 accounts instead of hundreds, and far fewer
  personal data under GDPR.
- A post arrives as a **draft** and is approved by editorial. An official league page is liable
  for what appears on it; unmoderated publishing would be a risk without benefit.
- **Image rights:** Photos of people need their consent, foreign photos need a license. Both
  must be confirmed on upload.
- There needs to be a way to quickly take down an approved post.

Tests: none yet

### VA-6 ● Create event with its configuration
As an **event organizer** I want to **create an event with name, date, and configuration**,
so that **everything else follows from it**.

Acceptance criteria:
- Only **name and date** are required. Everything else has sensible defaults.
- The configuration consists of **number of teams, number of boats, and number of flights**. From
  it the number of races per flight is calculated — no constants in code.
- **Boats** can be specified with **color and name**; on the water they are referred to by name,
  not number. Without specification, `boat_count` boats are created in league colors; with
  specification, their count determines `boat_count`.
- Boats belong to the **event**, not the draw: a new pairing list changes the assignment,
  not the boats at the dock.
- Each boat row defaults to a color from the league colors, in order (`WHITE` beyond that, or
  once a custom field is left empty — "no color" is not a choice), and a name of
  **"Boat 1".."Boat N"** by position — a clearer starting point than an empty required field,
  freely renamed afterwards. **Three controls, always shown together**: a plain named select, a
  native color picker, and a free-text field — the color itself is only actually visible in the
  picker. Choosing a named color in the select copies it into the picker/text; editing either
  the picker or the text switches the select to "Custom", so a hand-picked color is never left
  sitting silently under a named option it no longer matches.
- In addition to administration, editorial, and race committee, also the **leadership of the
  host club** can create — not for a foreign host.

Endpoints: `POST /api/admin/events`

Tests: `api/tests/stories/test_veranstaltung_anlegen.py::TestVeranstaltungAnlegen`

### VA-7 ● Take finished pairing list from catalog
As an **event organizer** I want to **have the draw immediately**, so that I **don't wait
ten minutes for an optimization run**.

Acceptance criteria:
- A pairing list depends only on **teams, boats, and flights**. For the usual configurations,
  it lies **pre-calculated** in the catalog.
- **Exactly one file per configuration** is stored — the `out.yml` of the Java tool. It carries
  all information; the configuration is read from its content, not from the filename. An
  official draw can be deposited unchanged.
- A **seed value** shuffles the starting positions. That takes milliseconds.
- **Shuffling does not change quality**: boat distribution, encounters, and boat changes depend
  on the structure of the list, not on which name is at which starting position.
- The same seed produces the **same** draw — recoverable in case of dispute.
- If no entry fits the configuration, the response says which ones are available; the way via
  the calculation job ([VA-3](#va-3--calculate-and-publish-pairing-list-in-the-interface))
  remains.
- **Event creation applies this automatically:** the event-creation form (VA-6) takes a seed
  (default `1240`, reproducible) and calls this endpoint right after the event is created, so a
  new event has its pairing list immediately, without a separate manual step. A failed draw
  (e.g. no teams registered yet) is reported as its own notice — the event exists either way.

Endpoints: `GET /api/admin/pairing/catalog`,
`POST /api/admin/events/{id}/pairing/from-catalog`

Extend catalog: `uv run python -m app.pairing.catalog --teams 18 --boats 6 --flights 16`

Tests: `api/tests/unit/test_pairing_catalog.py`,
`api/tests/stories/test_veranstaltung_anlegen.py::TestPairingAusDemKatalog`

---

## Administration

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

Tests: `api/tests/stories/test_stammdaten.py::TestVereineAnlegen`

### A-2 ● Create matchday
As an **event organizer** I want to **create a matchday with name, date, and host**,
so that **the date is set before details are finalized**.

Acceptance criteria:
- Access is available to **administration, editorial, and race committee** — all three
  contribute an event.
- Name, date, league, and season are sufficient. The **host** is selected from created clubs
  (A-1).
- Without an end date, the matchday is single-day; an end before the start is rejected.
- The **venue remains open** and can be added later — it often is not yet determined when
  creating. The interface names the host instead of leaving a gap.
- An **own logo** is possible; without one, the host's crest applies.
- The matchday number increments if not specified; a taken number is rejected.
- Club accounts may not create matchdays.

Endpoints: `POST /api/admin/events`, `PATCH /api/admin/events/{slug}`

Tests: `api/tests/stories/test_stammdaten.py::TestSpieltagAnlegen`

Open: The interface for this is still missing — only via API so far.

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

Tests: `api/tests/stories/test_serienzuordnung.py`

### A-4 ● Series includes its year
As a **user** I want to **see the year from the name**,
so that **"1st Sailing League" is not ambiguous**.

Acceptance criteria:
- A series is named "1st Sailing League 2026" — **one** name, not two. League and season are
  merged into one term.
- `Series.year` serves sorting and finding the current year, not naming.
- A **future year** does not switch the public page: "DSBL 2027" is created in 2026 so you
  can assign to it.

The **number of the act** belongs to the event, not the series: `Event.matchday`. An event
without a series has none.

Tests: `api/tests/stories/test_serienzuordnung.py::TestSerienname`

### A-5 ● Series standings with substitute score
As a **fan** I want to **see a series table that is correct even with missing clubs**.

Normally, the same clubs compete in all acts. But a club can participate in Act 1 and not
in Act 2.

Acceptance criteria:
- The series table adds up the placings of the acts; fewer is better.
- **Who is missing an act gets participant count + 1.** Same logic as a not-sailed race: not
  participating must never be better than participating and placing last.
- The table shows which acts a team was missing — otherwise its points would be inexplicable.
- A not-yet-sailed act does not count.

Tests: `api/tests/stories/test_scoring_storage.py::TestSerienwertung`

### B-6 ● Read as guest without login
As a **visitor without an account** I want to **see public pages**,
so that I **can follow results without signing in**.

Acceptance criteria:
- Tables, dates, matchdays, clubs, and pairing lists are accessible without login.
- An **expired or invalid** token does not make the public page unusable — the caller is then
  treated as a guest (`app/auth.py::optional_user`).
- Protected areas respond with 401 instead of partial data.

Tests: `api/tests/stories/test_serienzuordnung.py::TestGastzugriff`

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

This is the opposite direction to [A-3](#a-3--assign-clubs-to-series): there you attach a
club to multiple series, here a series to multiple clubs. Both write the same `Team` rows.

Endpoints: `POST /api/admin/series`, `PATCH /api/admin/series/{id}`,
`PUT /api/admin/series/{id}/clubs`, `GET /api/admin/series`

Tests: `api/tests/stories/test_serie_anlegen.py`

Open: The interface for this is missing — only via API so far. Currently only `admin` has
access; editorial may also create clubs. Whether that should remain is to be decided.

### A-7 ● Club can exist without competition
As **administration** I want to **create a club that does not yet participate in any competition**,
so that **master data and participation remain separate**.

Already built that way (see [A-1](#a-1--create-clubs) and
[A-3](#a-3--assign-clubs-to-series)) and recorded here because it is easily forgotten:

- A club is created with its **name**, nothing else.
- It can maintain its page, have organizers and sailors, without belonging to a series.
- Publicly, it only appears with its first **accepted** participation.

Tests: `api/tests/stories/test_serienzuordnung.py::TestVereinAnlegenUndZuordnen`

### A-8 ● Set up club organizer
As **administration** I want to **give a club an organizer**,
so that **the club manages itself from then on**.

The organizer is the account with the `club_manager` role for that club. `club_manager` is
a **per-club** grant (`UserRole.club_id`) — a person can organize several clubs
independently, each grant and revoke handled on its own. They maintain squads, lineups, and
posts — and apply for participation (V-5).

Acceptance criteria:
- Administration creates the account (name, email) and binds it to the club — the first
  account of a club can only come from administration: who has no one cannot name anyone.
- **An existing organizer may name more organizers for their own club.** Grant adds
  `club_manager`, scoped to this club, to an **active member** of the club. **A person may
  organize multiple clubs** — granting a second club no longer fails because they already
  organize a different one; it fails only if they already organize *this* one.
- Revoking `club_manager` for one club is allowed too — but **at least one organizer must
  remain** for that specific club; the last one can't step down until someone else has
  taken over. Revoking one club never touches a person's organizer status at any other
  club, and the account stays either way.
- Every grant and revoke is written to the audit log.
- `User.club_id` keeps its separate meaning — "the club this account represents" (e.g. a
  shared club account, Story VA-4) — and is no longer what defines or limits organizer
  scope. Granting someone's first club populates it as a sensible default if it was unset.

Endpoints: `POST /api/admin/clubs/{club_id}/members/{user_id}/organizer`,
`DELETE /api/admin/clubs/{club_id}/members/{user_id}/organizer` (an organizer of that club,
or administration). `MembershipOut.organizer` reports the current state.

Tests: `api/tests/stories/test_vereinsmitgliedschaft.py::TestOrganizerRole`

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

### Z-7 ● Delete my own account

As a **signed-in person** I want to **delete my own account outright**,
so that **cleaning up a test account doesn't need administration**.

Deliberately different from Z-6: this is a **testing-phase convenience**, not the
permanent answer. While accounts are still mostly test data, self-service cleanup matters
more than an audit trail — a real delete is safe because nothing in season history points
at a `User` by foreign key today (`Sailor` is linked only by email). **Once accounts are
reachable from real registrations, results, or waiver confirmations other people rely on,
this stops being safe** and should become a deactivation too, or gain a precondition —
revisit before real seasons depend on this data.

Acceptance criteria:
- `DELETE /api/auth/me` removes the account row itself, not just `is_active`.
- Administrative rows that point at the account by id and have no ORM cascade are cleaned
  up explicitly: club memberships (`ClubMember`) are deleted; a waiver confirmation the
  account recorded for someone else keeps its row, with the reference cleared.
- `UserRole` and `Identity` rows go with the account (already cascaded).
- The now-invalid token stops working immediately, same as any other removed account.

Endpoints: `DELETE /api/auth/me`

Tests: `api/tests/stories/test_login_and_roles.py::TestDeleteMyAccount`

### V-4 ● Create sailors
As a **club manager** I want to **create sailors in my club**,
so that I **can register them in the squad**.

Acceptance criteria:
- First name, last name, and **email are all required** — someone created through this form
  must be reachable: the address is the bridge to the account, through which the person
  signs in and submits their liability waiver (V-1, S-1). (A future manage2sail import may
  still write a sailor without one, bypassing this form.)
- Birth date is captured as a **complete date**, not just a year — age-category eligibility
  (e.g. a youth series) needs the exact date. It stays optional and is never shown publicly.
- An organizer creates only people from their **own** club.
- If the address is already known, the **existing person is offered** instead of creating a
  second. Two records for the same person would be a mistake that is hard to fix later.
- **A person may sail for multiple clubs.** They can be registered for one in the first
  series and for another in the juniors — that is not an exception, it happens.
- **Within a series or event, they appear only once.** Otherwise, they would start against
  themselves. This is the rule that must be enforced — not the number of clubs.
- Addresses are stored **lowercase**: "Jan@…" and "jan@…" would otherwise be two people and
  later two accounts.
- People are discoverable by **name and address** — without search, a list of 360 names is
  unusable.
- A name can be corrected; a typo should not force a second person.

**Done: `User.club_id` is the club an account represents** — not membership. That is in
`ClubMember` and can be multiple ([V-9](#v-9--invite-someone-to-club)). This resolves the
contradiction: a person sails for two clubs but always handles only one.

Still open: The **account** is not created automatically with the person. Those who should be
able to sign in register ([Z-4](#z-4--register-yourself)) or are created. Both are connected
via the address.

Endpoints: `GET /api/admin/sailors`, `POST /api/admin/sailors`,
`PATCH /api/admin/sailors/{id}`

Tests: `api/tests/stories/test_segler_und_kader.py::TestSeglerAnlegen`

---

## Request and Accept Participation

Previously, administration assigns clubs to series ([A-3](#a-3--assign-clubs-to-series),
[A-6](#a-6--create-series-and-select-clubs)). The club itself cannot register. The
following two stories add the path from below — **without** replacing the one from above.

### V-5 ● Request participation
As a **club manager** I want to **register my club for a series or event**,
so that I **don't have to call the league office**.

Acceptance criteria:
- An organizer applies only for their **own** club.
- The application is then visible to them, with its status: **requested, accepted, rejected**.
- An applied-for club does **not** appear publicly in the series and does **not count** in
  standings — only acceptance makes it a participant.
- An application can be withdrawn as long as it is not accepted.
- A second application for the same series is rejected, not duplicated.
- After rejection, a new attempt is possible.

Endpoints: `POST /api/applications`, `GET /api/applications`,
`DELETE /api/applications/{team_id}`

Tests: `api/tests/stories/test_teilnahme.py::TestAntragStellen`

### A-9 ● Accept or reject participation
As **administration** I want to **accept or reject applications**,
so that **only those who belong come to the field**.

Acceptance criteria:
- Administration sees all open applications per series.
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

Tests: `api/tests/stories/test_teilnahme.py::TestEntscheidung`

### V-6 ● Request participation in an event
As a **club manager** I want to **register my club for a single event**,
so that **we can also participate in a cup that belongs to no series**.

Acceptance criteria:
- The application names **either** a series **or** an event, never both.
- If the event belongs to a series, the club must be **registered** there — otherwise it would
  be in the daily standings but in no series table.
- An applied-for club is **not drawn** and **not scored**.
- **Only the club leadership registers participants.** A regular member cannot, nor can the
  race committee — they run the races, registration is with the club. Administration can
  because they can assign directly anyway.
- Administration assigns **unilaterally**: a confirmation from above needs no club consent and
  supersedes an open application. Only the opposite direction needs consent.
- When creating an act, **the same clubs** are preset as in the series.

Endpoints: `POST /api/applications` (with `event_id`),
`GET /api/admin/events/{id}/clubs`, `PUT /api/admin/events/{id}/clubs`

Tests: `api/tests/stories/test_teilnahme.py::TestTeilnahmeAnEinerVeranstaltung`,
`::TestNurDieVereinsleitungMeldet`

### How participation is modeled now

**Done: the status is a field on `Team`** (`requested | accepted | rejected`). An accepted
participation is exactly what `Team` was before; all public queries and scoring additionally
filter on it. Both paths — direct assignment and application — end in the same row.

**Done: participation in an event.** `Team` now depends on a series **and/or** an event:

| `series_id` | `event_id` | Meaning |
|---|---|---|
| set | empty | **Registration for the series.** The squad depends on it, it determines public visibility. |
| set | set | **Entry in an act.** Pairing list, results, and lineup depend on it. |
| empty | set | **Entry in a standalone event** without series. |
| empty | empty | forbidden (database constraint). |

Who enters an event that belongs to a series is thus **also registered for the series** — the
row carries both identifiers, and the endpoint checks that the series registration really
exists. The reverse is not true: being registered for the series does not mean entering every
act. Who is missing gets participant count + 1
([A-5](#a-5--series-standings-with-substitute-score)).

This determines the assignment of dependent data:

- `RaceEntry`, `EventCrew`, and daily standings point to the **entry**.
- `TeamMembership` (squad) and series table point to the **series registration**.
- The series table translates between both via the club.

**Deadlines remain out for now.** Series and event each have a **time range** (`starts_on`,
`ends_on`); from this a deadline concept can be derived later if needed. A fixed deadline
concept would be advised now.

---

## Clubs and Sailors

These stories are connected: who joins a club can join its squad; the club registers a season
squad, the registered sailors sign once for the season, the organizer checks them off, and
before each matchday the club names the four who actually sail.

### V-8 ● Decide on membership requests
As a **club manager** I want to **decide on requests**, so that **not everyone can join
our club**.

Acceptance criteria:
- The club sees its open requests with the requester.
- **Accepting** makes the person a member; **rejecting** can include a reason the person will
  see.
- Only the **requested club** decides on a request — who requested cannot accept themselves,
  and a different club does not decide.
- Every decision is logged.

Endpoints: `GET /api/admin/clubs/{id}/members`,
`POST /api/club-memberships/{id}/accept`, `POST /api/club-memberships/{id}/reject`

Tests: `api/tests/stories/test_vereinsmitgliedschaft.py::TestPersonFragtAn`

### V-9 ● Invite someone to club
As a **club manager** I want to **invite someone**, so that I **can register our sailors
myself, instead of waiting for their request**.

Acceptance criteria:
- Contact is via **email address** — the identifier a person knows about themselves. An
  account must exist for it; those without one register first ([Z-4](#z-4--register-yourself)).
- The invitation visibly awaits **the person's decision** (`pending_user`).
- **The club cannot accept for them.** Otherwise, it could claim members who don't know about it.
- The person can refuse.
- If both sides want the same — request meets invitation — the matter is decided without a
  third step.
- A person may be in **multiple clubs**; the constraint "only once" applies first per series
  and event, not for membership.

Endpoints: `POST /api/admin/clubs/{id}/members`

Tests: `api/tests/stories/test_vereinsmitgliedschaft.py::TestVereinLaedtEin`,
`::TestBeideRichtungenTreffenSich`

**Difference from competition participation.** Here two equal sides face each other: **both**
must consent, in whatever direction it begins. With series and event it is different — there
administration also assigns **unilaterally**, because it runs the competition, and only the
opposite direction (club applies) needs their consent. See [V-6](#v-6--request-participation-in-an-event).

### V-10 ● See fellow club members
As an **active club member** I want to **see who else belongs to my club**, so that I
**know who I'm sailing with** — without needing the leadership's admin view.

Acceptance criteria:
- Only **active** memberships are shown — pending requests and invitations stay the
  leadership's business ([V-8](#v-8--decide-on-membership-requests)).
- No email address and no decision notes: that stays reserved for the club's own
  leadership and admin ([V-8](#v-8--decide-on-membership-requests)). Display name and
  organizer status only.
- Open to a signed-in **active member of that specific club**, or `admin`/`editor` staff.
  A stranger, or a member of a *different* club, gets 403; signed-out gets 401.
- **Not** the sporting roster: the squad and lineup (`ClubDetail.teams[].members`,
  `.events[].crew`) stay public with no login required, exactly as before — this is only
  about `ClubMember`, the account-level affiliation.

Endpoints: `GET /api/clubs/{id}/members`

Tests: `api/tests/stories/test_vereinsmitgliedschaft.py::TestMemberRoster`

### V-1 ● Register season squad
As a **club manager** I want to **register the people who are allowed to sail for us**,
so that **it is clear who can be lined up**.

Acceptance criteria:
- The squad depends on the **registration for the series**, not entry in a single act. Lineup
  is drawn from it per matchday ([V-2](#v-2--select-sailors-for-matchday)).
- A registration replaces the previous one **completely** — it is the squad, not a supplement.
- **The same person may be registered in multiple clubs**, but **within a series only once** —
  otherwise they would start against themselves.
- No one appears twice in the same squad.
- **Who is lined up for a matchday does not fall out of the squad.** Otherwise, a lineup would
  exist with no squad. Change the lineup first, then the squad.
- Registration may be done by the leadership of their **own** club; administration everywhere.

Open: **Is it always exactly ten, or is ten a ceiling?** The number is deliberately not enforced
yet — illness and late registration would not get through otherwise. Also open: until when the
squad can be changed (see "Deadlines remain out for now").

Endpoints: `GET /api/admin/teams/{team_id}/members`,
`PUT /api/admin/teams/{team_id}/members`

Tests: `api/tests/stories/test_segler_und_kader.py::TestKaderMelden`

### S-1 ○ Submit liability waiver online for the season
As a **sailor** I want to **submit the liability waiver once online for the whole season**,
so that I **don't have to repeat it before every race**.

Acceptance criteria:
- Submission online, in time before the event. **A fixed deadline is not yet set** — series
  and event each have a time range, from which it can be derived later.
- A statement applies for the **entire season**, not per matchday.
- The wording is shown and **version-tracked**: who confirmed which text version when must be
  provable later. Changed text must not retroactively alter an old confirmation.
- The person sees their own status and is reminded while missing.

**Minors:** The statement needs the signature of a guardian. Since that is not given digitally,
there is an **upload for the scan** of the signed statement (image or PDF). Only with the scan
present is the statement considered submitted; it is then confirmed like everyone else via
VA-5.

The scan is the **most sensitive document in the whole project**: it contains data on a minor
and a signature. Therefore:

- visible only to the person affected, their club, and the organizer — never public, never
  retrievable via a guessable address;
- deletion deadline after season end, established and implemented, not just promised;
- every retrieval is logged.

Open: Does digital confirmation for adults meet the insurer's and league's requirements? If
not, everyone needs the scan path.

Built on top of the versioned confirmation mechanism — see [S-3](#s-3--confirm-a-waiver-version-for-a-series-or-event).

Tests: none yet

### S-3 ● Confirm a waiver version for a series or event
As a **sailor** (or an admin/club manager acting for one) I want to **confirm one specific
version of the liability waiver**, so that **participation is covered and provable**.

Acceptance criteria:
- The waiver text is **versioned and frozen**. `POST /api/admin/waiver/texts` adds the next
  version; the highest one is in force. An existing version is never edited — a wording
  change is a new version.
- A confirmation records **who, when, which version, in which language** — and never moves
  when a new version is published. It is append-only.
- **Scope is a series or a single event.** A **series** confirmation covers **every event**
  of that series; an event confirmation covers only that event.
- Publishing a new version does not rewrite old confirmations; it means the sailor is **no
  longer cleared** until they confirm the new one (status `version_outdated`).
- Confirming the same version for the same scope twice is rejected
  (`/errors/waiver-already-confirmed`).
- A sailor can confirm for **their own account** (matched by email); `admin`, `editor`, and
  `club_manager` can record for anyone (they collect the paper forms).

**Minors** (under 18 on the reference date — the event start, or the series start / 1 Jan of
its year):
- An online self-confirmation is **not enough** (`/errors/guardian-confirmation-needed`).
- The confirmation is recorded as `guardian` with the guardian's **name** and a reference to
  the **signed statement** (`guardian_signature_ref` — a URL, an object key, or a note;
  file storage itself is still open, see below). The name may be recorded first and the
  scan reference attached later — until it is present the sailor is not cleared
  (`guardian_signature_missing`).
- If the sailor's **date of birth is unknown**, confirmation is refused
  (`/errors/waiver-birth-date-required`) — age can't be judged.

Endpoints: `GET /api/waiver`, `GET /api/admin/waiver/texts`, `POST /api/admin/waiver/texts`,
`POST /api/series/{series_id}/waiver`, `POST /api/events/{event_id}/waiver`,
`GET /api/admin/events/{event_id}/waivers`

Tests: `api/tests/stories/test_haftungsausschluss.py`

Open: the reference version is the single one in force league-wide. A separate waiver text
per series (e.g. a juniors-specific wording) would add `Series.waiver_text_id`; not built
until it is actually needed.

### VA-5 ◐ Confirm liability waivers
As a **race organizer** I want to **only check off submitted liability waivers**,
so that I **don't have to collect anything on event day**.

Acceptance criteria:
- List of all people in the participating squads with their status: cleared, missing,
  outdated version, or (for a minor) waiting on the guardian's signature. **Built** —
  `GET /api/admin/events/{event_id}/waivers` (see [S-3](#s-3--confirm-a-waiver-version-for-a-series-or-event)).
- Who is not cleared cannot be registered for a matchday — the lock applies in Story V-2,
  not on the water. **Not yet wired** into the V-2 lineup check.
- Every confirmation is logged: who, when. **Built** — the confirmation row records it.

Access: the event's host-club leadership, plus `admin`, `editor`, `race_officer`. No fifth
role was added — the on-site organizer is a `race_officer` or the host `club_manager`.

Tests: `api/tests/stories/test_haftungsausschluss.py::TestMinors` (check-in list)

### V-2 ● Select sailors for matchday
As a **club manager** I want to **name the four sailors for a matchday in advance**,
so that **the registration is timely**.

The core rule: **A club registers X people for the league; for a matchday they choose from
them.** Who is not registered cannot be lined up — checked at the endpoint, not just in the
interface.

Acceptance criteria:
- Lineup is drawn **only from the season squad** of the same team (V-1).
- The **number is free.** `Event.crew_size` says how many the matchday is usually sailed with
  (four), and the interface orientates itself to it — it is not enforced. Illness, late
  registration, and different formats would not get through otherwise.
- No one appears twice in a lineup, and no one sails a matchday for two teams.
- A club manager lines up only their **own** team; administration and race committee can
  intervene anywhere — on event day someone must be able to change quickly.
- An empty list removes the lineup.
- An event **without a series** has no squad and thus no lineup.

Endpoints: `PUT /api/admin/events/{slug}/crew`, `GET /api/admin/events/{slug}/crew/{team_id}`

Tests: `api/tests/stories/test_aufstellung.py`

Open: coupling to confirmed liability waiver (S-1, VA-5).

### S-2 ◐ Upload own photo, edit own name and birthdate
As a **sailor** I want to **optionally upload a photo of myself and correct my own name
or birthdate**, so that **people see who sails for the club, and my data is right**.

Acceptance criteria:
- Voluntary. Without a photo everything remains usable; the frontend renders a neutral
  placeholder itself (`GET /api/sailors/{id}/photo` only serves the file — a missing one
  is a plain 404, not this endpoint's job).
- The person uploads it themselves (`POST /api/sailors/me/photo`) and can remove it
  anytime (`DELETE /api/sailors/me/photo` — removing an absent photo is a no-op, not an
  error).
- Cropped and scaled down; mobile format works: every upload is EXIF-rotated upright,
  center-cropped to a square, and downsized to a fixed 512×512 JPEG regardless of the
  source aspect ratio or camera format. Rejected with a typed error if it's not a
  readable image, or over ~5&nbsp;MB.
- The sailor can also view and correct their own `first_name`/`last_name`/`birth_date`
  (`GET`/`PATCH /api/sailors/me`) — previously only a club manager or admin could. Not
  `email`: that's account identity, out of scope here. Resolved via the account's
  **verified** email matching `Sailor.email` — the same link Story S-1's waiver
  confirmation already relies on — so there is no id parameter to point at anyone else's
  record. An account with no matching sailor row (e.g. an admin-only account) gets a
  clear 404, not a crash.

**Storage** (resolves the "not yet decided" note below, for this story only): a
deterministic local path, `api/uploads/sailors/{sailor_id}.jpg` — the file's existence
*is* the "has a photo" state, so no database column was needed. Not versioned (see
`.gitignore`); an S3-compatible store remains a later option once this needs to survive
redeploys of the API's disk, or multiple instances.

**Resolved — visibility:** public **unless** the sailor is a minor (under 18 as of
today) *and* has a `birth_date` on record: their photo is then shown only to a signed-in
account connected to them — themselves, `admin`/`editor`, or a manager of a club they're
registered with — matching how Story S-1 already treats minors' data with extra care.
An adult's, or a sailor with no recorded birthdate, is public — "so that people see who
sails for the club" is the point of the story, and there's no reason to gate it absent
the minors concern. No separate rights-confirmation checkbox was added: the upload is
already restricted to the sailor's own account, which is a stronger guarantee than a
click-through checkbox would be — open if a future review wants it anyway (e.g. for a
guardian uploading on a minor's behalf, which is out of scope for now: today only the
sailor's own linked account can upload their photo, same as a minor's waiver still needs
the *guardian's* signature recorded separately in S-1).

Tests: `api/tests/stories/test_sailor_profile.py`

### V-3 ◐ Upload club crest
As a **club manager** I want to **upload our club's crest**,
so that **we are recognizable on the page**.

Acceptance criteria:
- The `club_manager` uploads it for their **own** club — the same restriction as club
  assignment (Z-3). `admin` and `editor` may do it for any club, as with the rest of club
  master data (A-1). The check is `User.manages_club(club_id)`: `club_manager` is granted
  per club, so someone who organizes two clubs can maintain both crests, and merely
  *representing* a club (`User.club_id`) grants nothing.
- Replacing and removing are possible (`POST` again replaces; `DELETE` on a club without
  an uploaded crest is a no-op, not an error).
- Appears in table, club overview, and matchday view; without crest the abbreviation field
  remains — no placeholder is invented by the API, a club without a crest simply has no
  file (`GET /api/clubs/{id}/logo` → 404).
- **Transparency survives.** Deliberately *not* the sailor-photo pipeline (S-2), which
  flattens to RGB and re-encodes as JPEG: a crest is a logo drawn over colored surfaces
  (the home-page hero, the event cards), so flattening its alpha channel would put a
  visible white box around the emblem. PNG, JPEG and WebP are accepted as input; the store
  is always PNG, RGBA when the source carried transparency in any form (including a
  palette image's transparency index). There is also **no square crop** — a pennant is not
  square — only the longest edge is bounded at 512 px, and an already-smaller crest is
  left at its own resolution. Rejected with a typed error if it is not a readable image
  (`/errors/club-crest-invalid-type`, `/errors/club-crest-invalid`) or over 2 MB
  (`/errors/club-crest-too-large`).

**Storage**, as in S-2: a deterministic local path, `api/uploads/clubs/{club_id}.png` —
the file's existence *is* the "has a crest" state, so no database column was added. Not
versioned (see `.gitignore`); an S3-compatible store remains the same later option.

**Resolved — how the upload reaches consumers:** `Club.logo_url` keeps its single meaning,
*an externally hosted emblem*, and the two sources are resolved **on read** in one place
(`ClubOut._prefer_uploaded_crest`, `api/app/schemas/public.py`): an uploaded file wins,
otherwise the column is used. The alternative — writing the file's URL into the column on
upload — was rejected because it makes two places able to disagree about one fact and
destroys a pasted URL that the club may still want. Consequences: everything that already
reads `logo_url` (club list, club page, admin list, and the event-logo fallback
`event.logo_url or host_club.logo_url` in `public.py::_event_out`) shows an uploaded crest
with no change on its side and none in the frontend, and removing the upload falls back to
the external URL instead of leaving the club blank. The served URL carries a `?v=<mtime>`
cache stamp, because the path itself is stable across replacements.

Open: the admin/club-manager **UI** for the upload — the API is complete, the form is not
built yet.

Endpoints: `POST /api/admin/clubs/{club_id}/logo`, `DELETE /api/admin/clubs/{club_id}/logo`,
`GET /api/clubs/{club_id}/logo`

Tests: `api/tests/stories/test_club_crest.py`

---

## Race Committee

### WL-1 ○ Run races
As **race committee** I want to **have a simple app with which I run the races**,
so that I **work quickly and accurately on the water**.

Acceptance criteria:
- The app shows which race is next and who is on which boat.
- It works **without network**: everything is stored locally and reconciled later.
- Usable with wet hands on a rocking boat: large areas, no fiddling.
- Progress through 16 flights is visible at any time.

Tests: none yet

### WL-2 ◐ Enter and edit results easily
As **race committee** I want to **enter and correct results easily**,
so that **a mis-entry is not a disaster**.

Acceptance criteria:
- Finish line is recorded by tapping in order, not by typing position numbers.
- Penalty codes (DNF, DSQ, OCS, ZFP, RDG …) are readily accessible.
- Every entry can be undone and changed later.
- A correction overrides import from foreign systems, never the other way.
- With simultaneous changes on two devices, the later entry wins; the overridden status is
  not lost but logged and displayed.

Open: full offline capture is Story WL-1 (offline sync) territory and stays open here. The
overridden state on a stale-`version` submission is written to `AuditLog`
(`app/services/standings.py`) but not yet surfaced anywhere in the UI — displaying that history
remains open.
What's done: `PUT /api/admin/events/{event_id}/races/{race_id}/result` records
`code`/`finish_position`/`redress_points` per boat (`admin`, `race_officer`), rejects an
invalid ranking (two boats claiming the same place), and recomputes points/standings
immediately, so a protest decision is a one-row correction, never a data migration. With a
stale `version`, the later submission still wins (a rocking boat is no place for a hard
conflict error), but the state it replaces is written to `AuditLog` first, not silently
dropped. `web/src/pages/Spieltag.tsx`'s results-entry tab (`RaceResultRow`) now makes the
finish line the primary, fast path: tapping a boat's colored chip in finish order assigns it
`FINISHED` + the next unused position (a normal 6-boat race is 6 taps), the chip shows the
assigned rank as a badge, tapping again undoes just that boat, and a "reset race" action clears
all taps at once. The existing per-boat code `<select>` and manual position/redress `<input>`s
stay available underneath for the exceptions (DNF, DSQ, OCS, RDG, …) and always reflect the same
component state as the tap flow, so the two can never drift apart. Every result code now carries
a tooltip spelling out its exact point consequence (from `api/app/scoring/low_point.py`), and
picking `RDG` prefills the redress points with a suggested RRS A10 average of the team's other
scored races in the event — clearly labelled as a suggestion, never enforced. Duplicate finish
positions from the manual inputs (tap-assignment cannot produce one by construction) are flagged
in the UI and block Save immediately, ahead of the existing
`/errors/race-result-duplicate-position` server-side check.

Tests: `api/tests/stories/test_ergebniserfassung.py::TestErgebniserfassung`

---

## Still to Write

Sensible next areas:

- **B-…** Live: follow running race, see boats on map.
- **S-…** Tracking: register mobile as tracker and record.
- **A-…** Administration: set up seasons and leagues, maintain venues.
- **File storage — decided for S-2 and V-3, still open for S-1.** Three stories need
  uploads: the scan of the consent (S-1), member photo (S-2), and club crest (V-3). S-2
  and V-3 now use a local directory (`api/uploads/sailors/{id}.jpg`,
  `api/uploads/clubs/{id}.png`; deterministic path, no database column, access control per
  request in `app/routers/sailors.py` and `app/routers/clubs.py`) — see their sections
  above for the reasoning, including why a crest keeps its alpha channel where a photo does
  not. Still to be decided before S-1 is built, since a
  consent scan is far more sensitive than a photo: local directory or S3-compatible
  storage, size and type limits, virus scanning, and retention. **Access control differs
  per story** — a crest and most photos are public, the scan from S-1 on no account —
  which already rules out one shared static path for all three.
- **Deadlines:** deliberately left out for now. Series and event each have a **time range**
  (`starts_on`, `ends_on`); a deadline concept is derived from this if it becomes clear what
  is needed.
- **R-…** Editorial: publish post, create gallery.
