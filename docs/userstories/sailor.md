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
  a member. "My clubs" on the account page lists both kinds (Z-8).
- Every write and delete is in the audit log, as for every tuple.

Screen: the club's Members tab on `/club` (Story V-12) — the People panel for the admin,
a "Leave" button for the member. The public club page offers no way in.
Tests: `api/tests/stories/test_club_members.py::TestMembers`

### V-10 ● See fellow club members
As an **active club member** I want to **see who else belongs to my club**, so that I
**know who I'm sailing with** — without needing the leadership's admin view.

Acceptance criteria:
- Everyone with a `member` tuple on the club, with what else they are to it (manager,
  admin, race officer) so the organizers are recognizable — display name only, no
  email: contact data stays the club admin's business (the People panel,
  [V-8](club-manager.md#v-8--decide-who-is-in-the-club)).
- Open to a signed-in **member of that specific club**, to the club's admins and
  managers, and to `admin`/`editor` staff. A stranger, or a member of a *different* club,
  gets 403; signed-out gets 401.
- **Not** the sporting roster: the squad and lineup (`ClubDetail.teams[].members`,
  `.events[].crew`) stay public with no login required, exactly as before — this is only
  about the account-level affiliation.

Endpoints: `GET /api/clubs/{id}/members`

Screen: the Members tab on `/club` (Story V-12); the roster stays on the public club
page for a signed-in member as well.
Tests: `api/tests/stories/test_club_members.py::TestMemberRoster`

### B-10 ○ My clubs beside the club search
As **someone who sails**, I want **the clubs I belong to at the top of the clubs page**,
so that I **reach my own club in one click instead of searching for it every time**.

Today `/clubs` is one flat, searchable list of every club. For a visitor that is right; for
the people who actually use this site every week it is wrong — they open the page to reach
*their* club, and they have to type its name to find it among eighteen others.

Acceptance criteria:
- **"My clubs"** comes first: every club the signed-in account belongs to. Plural
  deliberately — a person can be an active member of more than one club (Story V-7), and a
  `club_manager` can manage several, so this is a list, never a single club.
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
V-12**, which needed the same list to let a club manager reach their squad; this page is
still to be written.

Each entry carries the club, the account's two *independent* relationships to it, and the
club's series registrations:

- `is_member` — an **active** `ClubMember`. This is what "my clubs" means on this page.
- `may_manage` — `club_manager` for this club, or `admin`. Deliberately separate: the two
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
  outdated version, waiting on the guardian's signature, or "add your date of birth first".
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
- Whoever may record a confirmation (S-3) may also upload a scan and download a form for
  that sailor: the sailor's own account, `admin`, `editor`, `club_manager`. So a club
  manager can hand in the paper forms their club collected.

**The scan is the most sensitive document in the whole project**: it contains data on a
minor and a signature. Therefore:

- **Stored** under `uploads/waivers/` with a random file name that only the confirmation
  row knows (`guardian_signature_ref = "upload:<uuid>.<ext>"`), served by exactly one
  endpoint, `GET /api/waiver/confirmations/{id}/scan`, which checks access on every
  request — the sailor themselves, `admin`, `editor`, the leadership of the sailor's club,
  and the organizer of the event (the host's `club_manager`, `race_officer`). Never a static
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
`api/tests/stories/test_waiver.py::TestScans`, `e2e/waiver.spec.ts`

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

### S-4 ○ Decide whether my own profile is public
As a **sailor** I want to **decide whether my profile page is public**,
so that I **can compete without having a page about me on the open internet**.

The site names whoever sails — the pairing list, the results and the standings all carry
the name, and a race cannot be published without them. A **profile page** is a different
thing: it collects a photo, every club and series someone has sailed for, and every
matchday they were in a lineup for, in one place, under one URL. That collection is the
part a person should be able to decline.

Acceptance criteria:
- One switch on the sailor's own profile (`PATCH /api/sailors/me`, a `profile_public`
  boolean on `Sailor`). **The sailor owns this choice**: a club manager, an `editor` or an
  `admin` can see the setting but cannot flip it for someone else — this is the one field
  on the sailor record that management does not maintain (contrast V-4, where they
  maintain all of it).
- **Off means the profile page is not public**: `GET /api/sailors/{id}` answers 404 for a
  guest, so the page does not confirm that the person exists to whoever guesses an id.
  Signed in it still opens for the people already connected to that record — the sailor
  themselves, `admin`/`editor`, and a manager of a club they are registered with — the
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

Tests: none yet

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

### Z-8 ● My clubs, my series, my events on the account page

As a **signed-in person** I want **my account page to list the clubs, series and events
I have something to do with, and what I am to each**, so that **I see at a glance where I
belong and where I am responsible — and reach each one in a click**.

The tuples of Story Z-2 make this a projection, not a new record: every club, series or
event the account holds a relation on, plus the clubs it is a member of (`ClubMember`,
which is deliberately not a tuple). Site-wide relations are not "mine" in this sense;
they stay in the permissions card.

Acceptance criteria:
- Three sections in that order — **My clubs**, **My series**, **My events** — each on
  every account page, each saying so when it is empty rather than disappearing.
- A club line names the club and what I am to it: *member* from the membership, and
  *admin*, *manager* or *race officer* from the tuples; a person who is both member and
  manager sees both. The name links to the club's page.
- A series line names the series and my relations on it (admin, manager, race officer,
  jury), linking to the series' standings; an event line the same, linking to the event.
- The data is what `/api/auth/me` and `/api/clubs/mine` already return — no new endpoint.

Screen: `/account`, below the account and permissions cards.
Tests: `e2e/lifecycle.spec.ts` ("Z-8: the account page lists my clubs, series and events")
