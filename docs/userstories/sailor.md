# Sailor

Part of the [user stories](README.md); the format, the status marks and the
identifier rule are explained there.

A sailor is the person behind the name in a result: they create their own account, join
their club, sign the liability waiver once per competition and decide what their profile
shows. Nothing here is required to appear in a result — a name in a pairing list is
public whether or not its owner ever signs in.

## Account and club

### Z-4 ● Register yourself
As a **sailor** I want to **create an account for myself**, so that I **don't have to wait
for someone to register me**.

Acceptance criteria:
- Only **email address and name** are required.
- The address is initially just **claimed**; only when the one-time code is redeemed is it
  verified (`email_verified`). Anyone could type in someone else's address.
- The new account has **neither role nor club**. A club's admin can then make it a member
  ([Z-5](#z-5--membership-is-a-tuple-the-clubs-admin-writes)).
- The response is **identical** for known and unknown addresses — otherwise, it would be
  possible to query who has an account here.
- Registration with an existing address **overwrites nothing**.
- Can be disabled via `SBL_ALLOW_REGISTRATION`.

Endpoints: `POST /api/auth/register`, then `POST /api/auth/email/verify`

Tests: `api/tests/stories/test_registration.py::TestRegistering`

### Z-5 ● Membership is a tuple the club's admin writes
As a **registered person** I want to **be made a member of my club by its admin**, so that
I **can sail for them** — and to leave again on my own.

Membership is `user:member:club` (Story Z-2), nothing else: no request, no invitation,
no acceptance. The club's admin knows who is in the club and writes the tuple, the way a
club keeps its member list anyway. **Decision of 2026-09-24**, replacing the mutual
consent of the first version (person applies, club approves, or vice versa): two states
awaiting the other side, a rejection with a reason and a "both directions meet" rule were
a lot of machinery for a fact the club already knows.

Acceptance criteria:
- The club's `admin` (or the site's) writes `member` on the club for any account —
  `POST /api/auth/tuples` with `{user: <email>, relation: "member", object: "club:<id>"}`
  — from the People panel on the club's Members tab, by email. Nobody else can.
- A member **leaves** by deleting their own `member` tuple (`DELETE /api/auth/tuples/{id}`,
  the one write a person may make on themselves); the club's admin removes a member the
  same way. Everything else the person holds on the club stays.
- Being a member implies no other relation: a member is not a manager, an admin is not
  a member. My space lists both kinds (Z-8).
- Every write and delete is in the audit log, as for every tuple.

Screen: the club's Members tab on `/me/club/:id` (Stories V-12, S-7) — the People panel for the admin,
a "Leave" button for the member. The public club page offers no way in.
Tests: `api/tests/stories/test_club_members.py::TestMembers`

### V-10 ● See fellow club members
As an **active club member** I want to **see who else belongs to my club**, so that I
**know who I'm sailing with** — without needing the leadership's admin view.

Acceptance criteria:
- Everyone with a `member` tuple on the club, with what else they are to it (manager,
  admin, race officer) so the organizers are recognizable — display name only, no
  email: contact data stays the club admin's business (the People panel,
  [V-8](club.md#v-8--decide-who-is-in-the-club)).
- Open to a signed-in **member of that specific club**, to the club's admins and
  managers, and to the site's `admin` (until 2026-10-24 also the site's `editor`, who
  organizes nothing since). A stranger, or a member of a *different* club,
  gets 403; signed-out gets 401.
- **Not** the sporting roster: the squad and lineup (`ClubDetail.teams[].members`,
  `.events[].crew`) stay public with no login required, exactly as before — this is only
  about the account-level affiliation.
- **The account list is the league office's alone** (`GET /api/auth/users`, 2026-10-24):
  it carries every account's tuples — who is in which club — and was open to every
  club's organizer.

Endpoints: `GET /api/clubs/{id}/members`

Screen: the Members tab on `/me/club/:id` (Stories V-12, S-7); the roster stays on the public club
page for a signed-in member as well.
Tests: `api/tests/stories/test_club_members.py::TestMemberRoster`,
`api/tests/stories/test_club_members.py::TestOrganizers::test_a_clubs_organizer_lists_no_accounts`

### B-10 ○ My clubs beside the club search
As **someone who sails**, I want **the clubs I belong to at the top of the clubs page**,
so that I **reach my own club in one click instead of searching for it every time**.

Today `/clubs` is one flat, searchable list of every club. For a visitor that is right; for
the people who actually use this site every week it is wrong — they open the page to reach
*their* club, and they have to type its name to find it among eighteen others.

Acceptance criteria:
- **"My clubs"** comes first: every club the signed-in account belongs to. Plural
  deliberately — a person can be an active member of more than one club (Story V-7), and a
  `team_manager` can manage several, so this is a list, never a single club.
- What counts as "mine" is the `member` tuple on the club (Story Z-5). An account has no
  club field of its own, so there is nothing else this could read.
- The **club search** sits beside it on a wide screen and **below it** on a phone — the
  section that matters most has to be the one that is above the fold on the small screen.
  It searches every club, exactly as it does now.
- A **guest, or a signed-in account with no membership, sees no "My clubs" section at all**
  — not an empty box explaining what would go there. The search then simply is the page,
  which is what `/clubs` is today.
- A club in "My clubs" is marked with **what the account is there**: member, or organizer of
  it. That is the one place a person can check whether their manager rights actually
  arrived, without opening the admin area.
- Both sections lead to the same club page (Story B-11).

Endpoints: `GET /api/clubs` exists and stays the search's source. The account's own clubs
come from `GET /api/clubs/mine` (signed-in only) rather than making the frontend fan out
over `GET /api/clubs/{id}/members` for all eighteen clubs to find itself. **Built for Story
V-12**, which needed the same list to let a team manager reach their squad; this page is
still to be written.

Each entry carries the club, the account's two *independent* relationships to it, and the
club's series registrations:

- `is_member` — an **active** `ClubMember`. This is what "my clubs" means on this page.
- `may_manage` — `team_manager` for this club, or `admin`. Deliberately separate: the two
  do not imply each other. A club's organizer is often not in the sailing squad and need
  not be an accepted member at all, and most members manage nothing. An entry appears when
  **either** is true, so this page filters on `is_member` and V-12's screen on `may_manage`,
  from one request.
- `teams` — the club's series registrations (`team_id`, series, current squad size), which
  is what V-12 navigates by.

Tests: `api/tests/stories/test_my_clubs.py`

## Before the season: the waiver

### S-1 ● Submit the liability waiver for each competition I am entered in
As a **sailor** I want to **submit the liability waiver once per series — or per event, when
the event stands alone — from my own account**, so that I **don't have to repeat it before
every race and know at a glance where I am still missing**.

The rule: **one statement per competition.** A series confirmation covers every event of that
series; an event that belongs to no series needs its own. Which competitions a sailor has to
sign for follows from their squads: every series they are registered in, and every
stand-alone event they are entered in (`GET /api/waiver/me`).

Acceptance criteria:
- The account page lists each of my competitions with its status — cleared, missing,
  outdated version, or waiting on the guardian's signature — and says "add your date of
  birth first" when none is on file (`birth_date_known: false` on `GET /api/waiver/me`;
  the status stays *missing*, since nothing can be confirmed yet). The status
  `birth_date_unknown` is only for a confirmation already on file whose sailor's date of
  birth has since gone missing, so it cannot be judged.
  The status is computed exactly as the organizer's list computes it (`app/services/waivers.py`),
  never a second rule.
- **Adults confirm online.** The wording is shown in full, in the reader's language, and
  must be actively accepted (checkbox + button). What is recorded is who, when, which
  version, in which language, from which account — the same append-only row as S-3.
- **Minors** (under 18 on the reference date) cannot confirm by their own click. The page
  offers instead:
  1. **Download the form** (`GET /api/waiver/form?scope=…&scope_id=…&sailor_id=…&locale=…`)
     — a PDF with the wording in force, the sailor's name and date of birth, the
     competition, and signature lines for the guardian. Built with reportlab from the
     versioned text, so the paper always matches the version being confirmed.
  2. **Upload the signed scan** (`POST /api/series/{id}/waiver/scan`,
     `POST /api/events/{id}/waiver/scan`; multipart: `file`, `guardian_name`) — PDF, JPEG or
     PNG, at most 10 MB. This creates the `guardian` confirmation (or completes one whose
     name was recorded first) and clears the sailor; a second upload replaces the file and
     is logged as such.
  Uploading a scan for an adult is refused (`/errors/waiver-scan-not-needed`): an adult's
  own click is their statement, and the scan path stays what it is for — a signature the
  site cannot collect online.
- The date of birth decides the path. Unknown, the page says so and points at the profile
  form above it, where the sailor enters it themselves (S-2).
- **Where I meet it is the event, not a tab** (decided 2026-10-17). My page for a series
  or an event (S-7) has no waiver tab: while my waiver is not cleared, a **notice above
  the tabs** says so and holds the whole row — the wording to accept, or the form and the
  scan upload. An event of a series shows the **series'** notice, and every such event I
  sail in shows it: accepting once, on any of them, clears it on all (one statement per
  competition). Cleared, the notice is gone. The full list stays on my profile's
  *Waivers* tab, beside my children's (S-8).
- Whoever may record a confirmation (S-3) may also upload a scan and download a form for
  that sailor: the sailor's own account, `admin` (until 2026-10-24 also `editor`), and the manager of a club
  the sailor sails for (V-4; until 2026-10-25 any club whose squad held them). So a team manager can hand in the paper forms their
  club collected — and only those: until 2026-10-17 any club's manager could sign for any
  sailor on the site (found by Journey J-5).

**The scan is the most sensitive document in the whole project**: it contains data on a
minor and a signature. Therefore:

- **Stored** under `uploads/waivers/` with a random file name that only the confirmation
  row knows (`guardian_signature_ref = "upload:<uuid>.<ext>"`), served by exactly one
  endpoint, `GET /api/waiver/confirmations/{id}/scan`, which checks access on every
  request — the sailor themselves, `admin` (until 2026-10-24 also `editor`), the leadership of the sailor's club,
  and the organizer of the event (the host's `team_manager`, `race_officer`). Never a static
  path, never public, never guessable.
- **Every retrieval is logged** as an `AuditLog` row (`waiver_scan` / `viewed`, with the
  actor), as is every upload and replacement.
- **Deletion after the season** is not built yet — see Open.

Open: whether an authenticated online confirmation meets the insurer's and league's
requirements for adults (`docs/findings.md` §6). If not, the upload path is opened for
adults by dropping one check. The deletion deadline for scans after season end is
specified but not implemented; it needs the season's end date, which a series has and a
stand-alone event has, and a job that nobody has written.

Built on top of the versioned confirmation mechanism — see [S-3](#s-3--confirm-a-waiver-version-for-a-series-or-event).

Tests: `api/tests/stories/test_waiver.py::TestSelfService`,
`api/tests/stories/test_waiver.py::TestScans`, `e2e/waiver.spec.ts`,
`e2e/my-space.spec.ts` ("S-1/Z-8/V-14: an unsigned waiver is a notice with its button, a badge, and a line in the club's list")

### S-8 ● My parent accepts the waiver for me
As a **guardian** I want to **accept the liability waiver for my child online, from my own
account**, so that **my child is cleared without printing, signing and scanning a form**.

The club links the parent's account to the child first (Story V-13). From then on the
parent sees their children in their own space and can confirm there what S-1 would
otherwise send to paper.

Acceptance criteria:
- **Where**: the waiver tab of my space (`/me/profile?tab=waivers`) gains a section
  *My children* — for each linked child their competitions with the same status as
  their own page (S-1), computed by the same function. `GET /api/waiver/wards`.
- **Confirming**: the same text, in full, actively accepted (checkbox + button), through
  the same endpoints as S-1 (`POST /api/series/{id}/waiver`,
  `POST /api/events/{id}/waiver`, with the child's `sailor_id`). Recorded as method
  `guardian_online`: who (the guardian's account, `recorded_by_user_id`), their name as
  `guardian_name`, when, which version, in which language. It **clears the minor** like a
  signed scan does; the paper path stays for those without a linked account.
- **A parent who also runs the club is still the parent** (2026-10-19): in a small club
  the team manager is often a sailor's mother or father. Linked as guardian, their click
  from *My children* is a `guardian_online` acceptance; the club's paper path applies only
  when they send a guardian's name or a scan.
- **Only while the child is a minor** on the reference date: for an adult ward the guardian
  is refused (`waiver-ward-is-adult`, 422) — an adult's own click is their statement. A
  guardian may also print the form and upload a scan for the child, as the club may.
- My space says it: the *Me* card carries `ward_waiver` with the number of the children's
  competitions not cleared (Z-8).

Endpoints: `GET /api/waiver/wards`; confirmation as S-1.

Tests: `api/tests/stories/test_guardians.py::TestAGuardianConfirms`, `e2e/guardians.spec.ts`

### S-3 ● Confirm a waiver version for a series or event
As a **sailor** (or an admin/team manager acting for one) I want to **confirm one specific
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
- A sailor can confirm for **their own account** (matched by its **verified** email);
  the site's `admin` can record for anyone (until 2026-10-24 the site's `editor` too), a club's manager for the sailors in their
  club's squads (they collect the paper forms) — `waiver-confirmation-forbidden` for
  everyone else. "Their club's" is the club the sailor sails for (V-4), never a squad
  alone: a rejected registration's squad, or one a club filled with another club's
  people, signs for nobody.

**Minors** (under 18 on the reference date — the event start, or the series start / 1 Jan of
its year):
- An online self-confirmation is **not enough** (`/errors/guardian-confirmation-needed`).
- The confirmation is recorded as `guardian` with the guardian's **name** and a reference to
  the **signed statement** (`guardian_signature_ref` — an uploaded scan is
  `upload:<uuid>.<ext>` under `uploads/waivers/`, see S-1; a paper form kept elsewhere is a
  free note like "office folder #42"). The name may be recorded first and the
  scan reference attached later — until it is present the sailor is not cleared
  (`guardian_signature_missing`).
- If the sailor's **date of birth is unknown**, confirmation is refused
  (`/errors/waiver-birth-date-required`) — age can't be judged.

Endpoints: `GET /api/waiver`, `GET /api/admin/waiver/texts`, `POST /api/admin/waiver/texts`,
`POST /api/series/{series_id}/waiver`, `POST /api/events/{event_id}/waiver`,
`GET /api/admin/events/{event_id}/waivers`

Tests: `api/tests/stories/test_waiver.py`

Open: the reference version is the single one in force league-wide. A separate waiver text
per series (e.g. a juniors-specific wording) would add `Series.waiver_text_id`; not built
until it is actually needed.

## My profile

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
  (`GET`/`PATCH /api/sailors/me`) — previously only a team manager or admin could. Not
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
account connected to them — themselves, `admin` (until 2026-10-24 also `editor`), or a manager of a club they're
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

### S-4 ● Decide whether my own profile is public
As a **sailor** I want to **decide whether my profile page is public**,
so that I **can compete without having a page about me on the open internet**.

The site names whoever sails — the pairing list, the results and the standings all carry
the name, and a race cannot be published without them. A **profile page** is a different
thing: it collects a photo, every club and series someone has sailed for, and every
matchday they were in a lineup for, in one place, under one URL. That collection is the
part a person should be able to decline.

Acceptance criteria:
- One switch on the sailor's own profile (`PATCH /api/sailors/me`, a `profile_public`
  boolean on `Sailor`). **The sailor owns this choice**: a team manager or an
  `admin` can see the setting but cannot flip it for someone else — this is the one field
  on the sailor record that management does not maintain (contrast V-4, where they
  maintain all of it).
- **Off means the profile page is not public**: `GET /api/sailors/{id}` answers 404 for a
  guest, so the page does not confirm that the person exists to whoever guesses an id.
  Signed in it still opens for the people already connected to that record — the sailor
  themselves, `admin`, and a manager of a club they are registered with (until 2026-10-24
  the site's `editor` too; editorial organizes nothing since) — the
  same circle Story S-2 already uses for a minor's photo.
- **The name stays visible wherever they compete, and only the name.** In a squad, a
  lineup, a pairing list, a result row or a standings row, a hidden profile appears as
  plain text instead of a link to the page — never as "anonymous", never omitted. Hiding
  a name there would make the pairing list unusable for the race committee and the
  results unverifiable for everyone else, and the same name is on the notice board at the
  club anyway.
  - Correspondingly **no photo** travels with the name in those places while the profile
    is off, and no birth date or club history — the competition views carry the name and
    the sporting facts of that competition, nothing about the person.
- **The default follows age**, not a blanket choice: an adult's profile starts public
  (that is what B-8 is for and what the clubs want), a **minor's starts off**, matching
  S-2's existing rule that a minor's photo is not public. A sailor with no recorded
  birth date counts as an adult here, because `is_minor` returns `None` and guessing
  "minor" would hide most of the seed; the switch is theirs to turn off either way.
- Turning the switch back on is symmetric and immediate — no review step, no
  administration involved.

Open: whether a guardian can set this for a minor. Today only the sailor's own linked
account can, exactly as with the photo (S-2) — noted there as out of scope for the same
reason.

**How it is stored:** `Sailor.profile_public_choice` is the sailor's own answer and stays
empty until they give one; `Sailor.profile_public` reads the choice, else the age default.
So a minor who never touched the switch gets a public page on their eighteenth birthday by
itself, while one who decided keeps that decision. The squad and lineup outputs
(`MemberOut`) carry the effective `profile_public`, and the frontend's `SailorName` renders
the name as a link or as plain text from it. The photo follows the page: a hidden
profile's `GET /api/sailors/{id}/photo` answers the same 404 as a sailor without one, for
everyone outside the circle above (a minor's photo keeps S-2's 403 first).

Tests: `api/tests/stories/test_profile_visibility.py::TestProfileVisibility`

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
- `Grant` (the tuples) and `Identity` rows go with the account (already cascaded).
- The now-invalid token stops working immediately, same as any other removed account.

Endpoints: `DELETE /api/auth/me`

Tests: `api/tests/stories/test_login_and_roles.py::TestDeleteMyAccount`

### Z-8 ● My space: everything I am part of, on one page
Issue #10. **Being replaced by [Z-10](#z-10--the-workspace-where-i-am-what-i-can-do-here-what-waits-for-me)** (issue #28): the cards become
the context switcher, the notices the to-dos.

As a **signed-in person** I want **one page listing every club, series and event I am part
of, what I am to each, and what waits for me there**, so that **I see at a glance where I
belong and where I am needed — and reach each one in a tap**.

"Part of" is two things, and the page needs both. A **relation** I hold — any tuple of
Story Z-2 on a club, series or event (member, admin, manager, race officer, jury, helper,
treasurer). And **sailing** — a squad puts me in a series, a crew in an event (Stories V-1,
V-2) — which is no tuple at all, and so was invisible on the account page this replaces.
Site-wide relations are not "mine" in this sense: the league office's work stays on
`/admin`.

Acceptance criteria:
- `/me`, signed in. Groups in this order: **Me** (always one card: my own profile and
  papers), **Clubs**, **Series**, **Events** — events split into *upcoming* and *past*, the
  past folded away behind its count. A group with nothing in it is left out; with nothing
  at all, the page says how one joins a club (Story V-7).
- One card per club, series or event: its name, dates where it has them, and my relations
  as chips — *sailor* among them when I sail there. A person who is both member and
  manager sees both.
- A card says what **needs me** there, in words, only when something does:
  - a liability waiver of mine that is not cleared — on the series, and on each event of
    it I sail in, since that is where I meet it (S-1); on an event in no series, there;
  - claims waiting for my decision or payment (on the event when I hold the event, else
    on the club that pays);
  - as a club's organizer: a series squad below its minimum, an upcoming entry with no crew
    named (the matchday's crew, `EventCrew` — until 2026-10-17 this counted the squad on
    the entry instead, so a series matchday asked for a crew that was already named; found
    by Journey J-5), an upcoming matchday whose crew has a waiver not cleared (VA-5);
  - on *Me*: a document of mine that has expired.
- Tapping a card opens my page for it (Story S-7).
- **The account button carries a badge** with the number of things that need me —
  every card's, *Me* included, each thing once (a series' waiver asked again on its events
  is one signature; `total` on `GET /api/me/contexts`) — so I see from any page that
  something is to do, and *My space* in its menu repeats the number. No badge when
  nothing does.
- Sailing in an event is being **named in its crew** (`EventCrew`, Story V-2) or, for an
  event in no series, being in its entry's squad. Until 2026-10-17 only the entry's
  members counted — which a series matchday's entry never has — so a sailor named for a
  matchday did not find it here at all.
- One request: `GET /api/me/contexts`. It is the one answer to "which clubs, series and
  events are mine" — the account page, the club screen and the reimbursements page each
  had their own, and the three disagreed (a treasurer had no club, a helper no event).
- One way in: **My space** in the navigation and in the account menu. It replaces "My
  club(s)", "Reimbursements" and "Profile"; their old addresses lead to the new pages.

Screen: `/me`.
Tests: `api/tests/stories/test_my_space.py::TestMySpace`,
`e2e/my-space.spec.ts` ("Z-8/S-7: my space — one card per thing I am part of, and my page in it"),
`e2e/my-space.spec.ts` ("S-1/Z-8/V-14: an unsigned waiver is a notice with its button, a badge, and a line in the club's list")

### S-7 ● My page in a club, a series or an event
Issue #10. **Being replaced by [Z-10](#z-10--the-workspace-where-i-am-what-i-can-do-here-what-waits-for-me)** (issue #28): the tabs become
the section sidebar.

As a **signed-in person** I want **a page of my own for each club, series and event I am
part of, holding exactly what is mine to see and do there**, so that **I never hunt
through screens built for other roles**.

The page is assembled, not written per role: each section says which relations show it,
and the page shows the sections my relations allow — so a club treasurer who sails sees
both the money and their squad, and a helper sees only their claims. The sections are the
panels the separate screens had; this story moves them, it does not change what they do.

Acceptance criteria:
- `/me/profile` — **Me**: account and sign-in methods (Z-9), sailor profile (S-2),
  documents and licences (S-5), bank account (S-6), my waivers (S-1), deleting the account
  (Z-7).
- `/me/club/:id` — **members** (every member; adding, removing and access for the club's
  admin, Z-5, V-8, A-8), **matchdays** with their crews and **series** with their squads
  (V-1, V-2; editable for the club's organizer, read-only for a member), **my claims** to
  the club (member, F-2), **money** — claims to decide and pay, the club's bank account,
  payment runs and the books (manager, treasurer; F-3, F-4, F-7).
- `/me/series/:id` — **my squad** (sailor), the series' **events**, and for its organizer
  the way to the organizer screen.
- `/me/event/:id` — **my crew** (sailor), **my claims** for the event
  (anyone holding a relation on it, F-2), **claims to decide** (its manager, treasurer),
  **race control** (race officer), and for its organizer the way to the organizer screen.
- Tabs keep their selection in the URL (`?tab=`), like every tabbed screen. A tab that
  needs me says so on its label.
- An unsigned waiver of mine is no tab but a **notice above the tabs**, with the accept
  button in it (S-1).
- The tabs are the page's **sub-menu**, drawn like a matchday page's: in the header row
  beside the page's name (`My space › Me | Account · Documents · …`), staying under the
  top bar while the page scrolls. The breadcrumb is the way back to my space — there is
  no separate back link, which took a line of its own on every page.
- A page I am not part of answers *not found*, not an empty shell.
- The old addresses keep working: `/account` (signed in) → `/me/profile`, `/club?club=N`
  → `/me/club/N`, `/reimbursements` → `/me`; `/account` signed out stays the sign-in page.

Screen: `/me/profile`, `/me/club/:id`, `/me/series/:id`, `/me/event/:id`.
Tests: `e2e/my-space.spec.ts` ("Z-8/S-7: my space — one card per thing I am part of, and my page in it"),
`e2e/club.spec.ts`

### Z-10 ◐ The workspace: where I am, what I can do here, what waits for me
Issues #28 (parent), #29–#35. The plan, with every table: `docs/PLAN_NAVIGATION.md`.

As **anyone signed in** — a sailor, a parent, a team manager, an organizer, the race
committee, a treasurer, editorial, the league office — I want **to see on every page where
I am, reach every page of my work in a click or two, and find what waits for me first**,
so that **I never hunt for the page an action lives on**.

Z-8 and S-7 gave every club, series and event I am part of a page of mine; A-11 split the
administration into tabs. Both still left people lost (2026-10-25): *where are our club's
minors, where do I add a new person* — because the same club had two homes (`/me/club/…`
and `/admin`), tabs hid sections several clicks deep, and a page said where it was only in
a breadcrumb. Chosen in a TOAD over task-first navigation, a dashboard and today's pages
polished: a **context switcher** plus a **section sidebar**, with the to-do list built in.

Acceptance criteria:
- **All work happens in My space**, and only My space has a sidebar. The public site only
  shows — no sidebar on a public page, signed in or not; *My space* in its header, and
  *Work on this* on the public page of an object I work on.
- **Two levels, never a tree.** The **context switcher** in the header names the one
  context I am working in — *Me*, the *League office* (only with a site relation), a club,
  a series or an event — and lists mine: those `GET /api/me/contexts` returns, each with my
  relations as chips and its waiting count; events upcoming first, past folded; drafts
  after the current year. Objects I reach only through another (a series manager's events)
  are opened from inside it and then kept under **Recent**. The **section sidebar** lists
  the sections of that one context.
- **What I hold there decides what I see** — the model (Z-2), never a summary role; several
  relations add up into one list ordered by the work, never duplicated; a section I cannot
  use does not exist (not disabled); a group with one section shows without a heading.
  The sections per context and who has each are the tables of the plan's §3 — Me, Club
  (People · Racing · Money · Club), Series (Sailing · Series · Organize · Officials ·
  Editorial), Event (Sailing · Set up · Race day · Money · Editorial), League office.
- **Club and event, never "matchday"**: a matchday is an event's number in its series; the
  club's sections are *Squads* (one, with a picker for the registration or stand-alone
  event) and *Events & crews* (with a team picker when the club enters several teams).
- **Where am I, twice on every page**: the switcher names the context, the sidebar marks
  the section, and the breadcrumb joins them (`ASVW › Sailors › Minors & guardians`).
- **To do (built in)**: every to-do is a link to the section that clears it, computed and
  never stored, shown only to those who hold that section. *Me › Overview* is the landing
  page: **Live now** while an event I work on is live (the sections my relations give me
  there, Race control first for the race committee), then **To do** across all my
  contexts, then **Last visited**. Each context opens on its own *Overview*; the switcher
  and the sidebar carry the counts. The to-do codes, today's and the new ones, are the
  plan's §4 — all of them are built.
- **Every to-do is one row** (#33, the backend part built 2026-10-25): each need on
  `GET /api/me/contexts` — on *Me*, on a context, on the league office — carries its
  `code`, `count`, the **`section`** that clears it and a **`severity`**, and the answer
  adds **`todos`**, every one of them in one list, each with its `context`
  (`{kind, id}`; *Me* is `kind: "me"`, the league office `kind: "office"`, both without an
  id) — the row of the plan's §4. Ordered by severity, then by `due` (the date it is
  tied to, undated last).
  - **Severity** is a closed set: **`now`** — tied to a race day within 7 days, a live
    event (check-in, results), or a deadline (none is modelled yet); **`soon`** — tied to
    a race day within 30 days, or undated work someone is waiting on (a claim, a waiver,
    a minor without a guardian, an application); **`info`** — everything else (an open
    payment run waits on the bank; an event months away not ready yet).
  - **Section keys** — the same keys the sidebar declares (#30), kebab-case:
    *Me* `overview account waivers claims documents bank children`;
    club `overview members sailors minors waivers squads crews hosting my-claims
    decide-claims payment-runs bank-account club-page`;
    series `overview team events standings registrations dates scoring officials news`;
    event `overview crew general clubs boats pairing publication people check-in
    race-control results trackers notice-board my-claims decide-claims news`;
    league office `overview clubs series events sailors accounts news media imports`.
  - **Code → section**: `waiver` → series `team` / event `crew`; `ward_waiver` → Me
    `children`; `documents_expired` → Me `documents`; `claim_rejected` → Me `claims`, or
    `my-claims` on the event or club card it sits on; `claims` → club/event
    `decide-claims`; `squad_below_min` → club `squads`; `crew_missing` → club `crews`;
    `crew_waiver_missing` → club `waivers`.
  - **Only what I can act on**, decided by the model (Z-2) on an object already mine — a
    to-do appears for whoever holds the section it links to:
    - `minor_without_guardian` — club `minors`, the club's organizers: sailors of the club
      (`SailorClub`) who are minors today and have no guardian linked;
    - `sailor_without_birth_date` — club `sailors`, the club's organizers: no waiver can be
      confirmed for them (S-3);
    - `payment_run_open` — club `payment-runs`, organizers and `treasurer`: a run with a
      payment still `issued`, not booked (F-7); `info`;
    - `event_not_ready` — event `overview`, the event's organizers: a planned event's
      readiness reasons (VA-8), counted;
    - `event_unpublished` — event `publication` / series `dates`, organizers: dates set,
      still a draft;
    - `checkin_waivers_missing` — event `check-in`, organizers and `race_officer`: a race
      day within 7 days (or live) whose named crews have sailors not cleared (VA-5),
      counted per sailor; always `now`;
    - `results_missing` — event `results`, organizers and `race_officer` (§3's holders of
      *Results*): a live event's finished races with an entry lacking a result; always
      `now`;
    - `registrations_open` — series `registrations` (event `clubs` for an application to
      one event), the competition's `manager`: applications still `requested` (V-5,
      A-9).
  - **The league office** is no context of "mine" — `contexts` stays as Z-8 says — but
    with any site relation the answer carries **`office`** (my site relations, its needs),
    and only the site's `admin` gets: `clubs_without_league` (office `clubs` — a club
    enrolled in no series of a league, so the public site does not show it; `info`) and
    `imports_failed` (office `imports` — a source reference whose latest import run
    failed; `soon`).
  - A context's `relations` are a closed set (`ContextRelation`: member, sailor, admin,
    manager, editor, treasurer, race_officer, jury, helper — in that reading order), so
    the page compares against names the compiler knows.
  - A to-do of an event or series reached only *through* another object (a series
    manager's acts) is not listed: those are opened from inside, as the plan's §2 says.
- **One home per object**: an object's administration lives in its own context; `/admin`
  becomes **`/office`**, the league office's own work. Old addresses redirect.
- **Recent and last visited** are kept per browser — a convenience, never needed to work.
- **Laptop first, phone too**: sidebar 248 px; icons only between 768 and 1100 px; on a
  phone a bar of two buttons — context ▾ and section ▾ — instead of the sidebar. No page
  wider than the screen (A-10).
- The combinations of the plan's §5 (a sailor who also helps, a parent with no club, a
  series editor, the site admin, …) are this story's examples, and its tests walk them.

**The declaration** (#30): every context's groups and sections, and who has each, are
declared once in `web/src/lib/workspace.ts` — the sidebar, the guards and the help's
places read it; a section's key is also its URL segment and the `section` a to-do links
to. Unit-tested against the plan's §5 table in `web/tests/test_workspace.ts`.

**The shell** (#31): every page of My space is drawn by `WorkspaceFrame`
(`web/src/pages/me/Workspace.tsx`) — the switcher at the top of the sidebar (in the bar on
a phone), the sections of the context, the breadcrumb; each section at its own address
(`/me/club/:id/<section>`, `/me/profile/<section>`), `?tab=` redirecting. Today's panels
became sections unchanged; the icon rail for 768–1100 px waits for an icon set, and those
widths get the phone's bar.

Built in steps, each its own issue: the declaration of contexts and sections (#30), the
switcher and sidebar around today's pages (#31), the admin work moved into each context
and `/office` (#32), the to-dos and landing page (#33), the switcher's search (#34),
handbook and e2e (#35).

Tests: `api/tests/stories/test_my_space.py::TestTodos`

### S-5 ● Keep my documents, and show them to my organizers
As a **signed-in person** I want to **upload my licences and certificates once, each with
a label**, so that **an organizer who needs to see my boat licence finds it without asking
me for a scan before every event**.

Acceptance criteria:
- A document has a **label** from a fixed list — boat licence sea (*Sportbootführerschein
  See*), boat licence inland (*Binnen*), radio certificate (SRC/UBI), first aid,
  jury licence (judge, umpire), race officer licence, other — an optional title (required for
  *other*) and an optional **valid until** date. A fixed list, not free text, so an
  organizer can look for "boat licence" across people.
- PDF, JPEG or PNG by content, at most 10 MB, stored under a random name, any number per
  person. Uploaded and deleted by the owner only (`/api/me/documents`).
- **Who else sees them** (decision of 2026-10-07): the **organizers** of the person —
  whoever is `manager` (by the model) of an event the person holds a relation on directly
  (helper, jury, race officer, manager), and whoever is `manager` of a club the person is
  a member of. Nobody else: not another member, not another event's organizer. A look
  by anyone but the owner is written to the audit log.
- The organizer reaches them from the person's row — the event's access list, the club's
  member list (`GET /api/people/{user_id}/documents`).
- A document past its *valid until* date is shown as expired, not hidden: an organizer
  must see that the licence ran out, not that there is none.
- Deleting the account deletes the documents and their files.

Tests: `api/tests/stories/test_personal_space.py::TestMyDocuments`,
`api/tests/stories/test_personal_space.py::TestOrganizersSeeDocuments`

### S-6 ● Save my bank account once
As a **signed-in person** I want to **save the account my costs are paid back to**,
so that **I do not type an IBAN into every claim**.

Acceptance criteria:
- One account per person: account holder and IBAN, the BIC optional (`/api/me/bank-account`).
- The IBAN is normalised (spaces removed, upper case) and checked with `schwifty` —
  length and check digits per country, the bank code where the country publishes a
  register; a wrong one is refused (`iban-invalid`) before anything is saved. An empty
  BIC is filled in from the IBAN's bank code; a typed one is checked (`bic-invalid`).
- **Read by the owner alone.** It is its own table, not a column on the account, so no
  serializer of accounts can carry it. Whoever decides a claim sees the copy taken onto
  the claim at submission (Story F-2), never the profile.
- Changing it later changes no claim already submitted.
- Deleting the account deletes it.

Tests: `api/tests/stories/test_personal_space.py::TestBankAccount`

### B-18 ◐ The help for what I do
As **someone signed in** — a sailor, a team manager, an organizer, a race officer, a
treasurer, the league office — I want to **find the help for what I do, in my language**,
so that **I can get a task done without asking someone who has done it before**.

**The help is internal; the public site explains itself** (decided 2026-10-18). A visitor
who needs a manual to read a results table is a defect in the table, not a missing help
page — so there is no visitor help, and what a help author found unclear on a public page
is reported as a fix to that page.

Acceptance criteria:
- **`/help` is for signed-in accounts.** A guest at `/help` or `/help/<page>` sees only a
  prompt to sign in, never a page; the account menu offers *Help* only when signed in.
- `/help` opens **one tile per audience** — sailor, club, event organizer, race committee,
  treasurer, administration — each opening that audience's starting page. The audiences a
  person **has** come first and are marked, taken from the answer my space uses
  (`GET /api/me/contexts`, Story Z-8, plus the site roles). **Nothing is hidden from a
  signed-in person**: the audience only orders, so someone about to become a team manager
  can read what that means.
- Below the tiles: one card per **journey** page (the journeys in `docs/journeys/`, in the
  order they happen across people), then the reference pages — terms, roles, questions.
- A **search** box over titles, headings and search words finds a page in either language.
- **`/help/:page`** shows one page with its sections as a table of contents; it loads
  directly in a fresh tab, and `/help/roles#roles-matrix` scrolls to that section.
- **The roles page replaces the hand-written matrix** `/help` showed until now: who may do
  what, derived from the permission model (Story Z-2), and how one gets a role.
- Pages are written in English and fully translated into German, with the same sections and
  anchors in both; the language switcher changes the page in place.
- Screenshots come from the running site, per language, with a phone version for what is
  done on the water; a missing one shows a "screenshot pending" box, never a broken image.
- **Help for this page:** the account menu's *Help* entry opens the page that explains the
  current screen when there is one, `/help` otherwise.
- No page scrolls sideways on a phone (Story A-10); a wide table scrolls inside itself.
- **A click path is a link to the place it describes — for the reader who can use it.**
  "*Me* → *Waivers*" opens `/me/profile?tab=waivers`; "*Members*" on a club guide opens
  *my* club's page on its *Members* tab, one link per club when I organize several
  ("(NRV · KYC)"). A reader for whom that tab does not exist — a sailor reading the
  treasurer's guide — sees the same words as plain text: the path still explains the
  screen. The page names a **place** (`place:club.members`), never a URL, and one
  registry (`web/src/handbook/places.ts`) turns it into an address per reader, using the
  same declarations of who sees which tab that the screens themselves are built from.
  *Why names, not URLs:* routes and tab keys change, and a hundred hand-written
  addresses in two languages would drift silently; a place is one line to change, and
  `scripts/check-docs.py` refuses a place nobody declared and a raw address a place
  covers. *Why hidden, not refused:* a link that ends in a 403 or an empty page is worse
  than none (Story A-12's rule for the administration link) — and the help is read by
  people about to take on a role, who must not be led to doors that do not open for them.
- The pages are files in `web/src/handbook/`, built from the stories and journeys by the
  `handbook` skill; `scripts/check-docs.py` holds them to the stories, the journeys, the
  routes and each other (both languages present, anchors unique, links resolve, the
  structure no page may silently lose).

Not a secret: the pages ship in the site's JavaScript like every other text, so the
sign-in is about whom the help is written for, not about hiding it.

Frontend: `web/src/pages/Help.tsx`, `web/src/handbook/` (places: `places.ts`), `web/src/lib/workspace.ts`, `web/src/components/HelpLink.tsx`

Tests: `e2e/help.spec.ts::B-18: as a guest I am asked to sign in for the help`, `e2e/help.spec.ts::B-18: as anyone signed in I find the help for what I do`, `e2e/help.spec.ts::B-18: a click path in the help opens that place, for the reader who can use it`
