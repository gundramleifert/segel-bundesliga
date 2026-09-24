# Club Manager

Part of the [user stories](README.md); the format, the status marks and the
identifier rule are explained there.

These stories are connected: who joins a club can join its squad; the club registers a season
squad, the registered sailors sign once for the season, the organizer checks them off, and
before each matchday the club names the four who actually sail.

Two people stand behind "the club" here (Story Z-2): the club's **admin** decides who is
*in* the club — memberships, invitations, organizers, the crest — and the club's
**manager** decides who *sails* — squads, lineups, registrations. Where a story below
says `club_manager`, read the manager for sport and the admin for membership; an admin
is a manager too.

The path into a competition goes both ways. Administration assigns clubs to series
([A-3](administration.md#a-3--assign-clubs-to-series), [A-6](administration.md#a-6--create-series-and-select-clubs)); V-5
and V-6 add the club's own application from below — **without** replacing the path from
above — and [A-9](administration.md#a-9--accept-or-reject-participation) is administration's answer to it.

## Members

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

Tests: `api/tests/stories/test_login_and_roles.py::TestAssigningAClub`

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

Screen: the Members tab on `/club` (Story V-12) — requests waiting for the club with
accept / reject, should any arrive through the API; the invited person decides on the
public club page.
Tests: `api/tests/stories/test_club_membership.py::TestPersonApplies`

### V-9 ● Invite someone to club
As a **club manager** I want to **invite someone**, so that I **can register our sailors
myself, instead of waiting for their request**.

Acceptance criteria:
- Contact is via **email address** — the identifier a person knows about themselves. An
  account must exist for it; those without one register first ([Z-4](sailor.md#z-4--register-yourself)).
- The invitation visibly awaits **the person's decision** (`pending_user`).
- **The club cannot accept for them.** Otherwise, it could claim members who don't know about it.
- The person can refuse.
- If both sides want the same — request meets invitation — the matter is decided without a
  third step.
- A person may be in **multiple clubs**; the constraint "only once" applies first per series
  and event, not for membership.

Endpoints: `POST /api/admin/clubs/{id}/members`

Tests: `api/tests/stories/test_club_membership.py::TestClubInvites`,
`::TestBeideRichtungenTreffenSich`

**Difference from competition participation.** Here two equal sides face each other: **both**
must consent, in whatever direction it begins. With series and event it is different — there
administration also assigns **unilaterally**, because it runs the competition, and only the
opposite direction (club applies) needs their consent. See [V-6](#v-6--request-participation-in-an-event).

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
able to sign in register ([Z-4](sailor.md#z-4--register-yourself)) or are created. Both are connected
via the address.

Endpoints: `GET /api/admin/sailors`, `POST /api/admin/sailors`,
`PATCH /api/admin/sailors/{id}`

Tests: `api/tests/stories/test_sailors_and_squads.py::TestCreatingSailors`

## Entering competitions

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

Tests: `api/tests/stories/test_participation.py::TestApplying`

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

Tests: `api/tests/stories/test_participation.py::TestEnteringAnEvent`,
`::TestOnlyTheClubOrganizerRegisters`

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
([A-5](visitor.md#a-5--series-standings-with-substitute-score)).

This determines the assignment of dependent data:

- `RaceEntry`, `EventCrew`, and daily standings point to the **entry**.
- `TeamMembership` (squad) and series table point to the **series registration**.
- The series table translates between both via the club.

**Deadlines remain out for now.** Series and event each have a **time range** (`starts_on`,
`ends_on`); from this a deadline concept can be derived later if needed. A fixed deadline
concept would be advised now.

## Squad and lineup

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

- **Every refusal is a typed problem** (`app/problems.py`), not a sentence built in the
  router: the squad screen has to say *which* rule was broken, and it has to say it in the
  reader's language. A club manager who adds someone who already sails for another club in
  the same series gets that sentence, with both names in it — not a 422 whose body is an
  English string chosen by the backend.
  - `squad-duplicate-sailor` — the same person twice in one submission.
  - `squad-sailor-in-another-club` — already registered for this series elsewhere, and by
    whom.
  - `squad-member-is-lined-up` — cannot be dropped while lined up for a matchday, and for
    which one.
  - `squad-needs-series-registration` — this `Team` is an event entry, not a series
    registration, so it carries no squad.
- **The squad's size is set per series — or per event, when the event stands alone**
  (`Series.squad_min` / `squad_max`, `Event.squad_min` / `squad_max`; defaults 4 and 10).
  The **maximum is enforced** when the squad is saved (`squad-too-large`, naming the
  limit) and the screen offers nobody once it is reached; the **minimum is guidance**
  ("3 of 4–10 registered", said in amber), because a squad is built up over weeks and a
  club must be able to save two names in March. A minimum above the maximum is refused
  (`squad-limits-invalid`). The same goes for having exactly one helm: the screen says
  when there is none or more than one, and saves anyway. The limits are edited on the
  series' admin panel and, for a stand-alone event, on the event's; the squad panel
  reads them off the squad itself (`SquadOut.squad_min/max`), never off a constant.
- Somebody is added **in the role they will sail**, not always as crew to be corrected
  afterwards.
- **The list to pick from says where each person already sails.** A name on its own does
  not identify anybody: eighteen people in this data share a surname, and a person is
  legitimately registered in **several clubs at once** — one `TeamMembership` row per
  series registration — so "3 registrations" as a bare number answers neither "is this the
  right Nanisberg" nor "can I add them". Each candidate therefore carries their
  registrations as club **and** series.
- **Somebody already registered for *this* series is offered as unavailable, naming the
  club they sail for**, instead of being addable and refused on save. The rule is the
  oldest one in this story — once per series, whichever club — and it is the one a club
  manager is most likely to walk into, because the person is genuinely a member of their
  club too. The endpoint keeps refusing it (`squad-sailor-in-another-club`): the list is
  a courtesy, not the enforcement.

Open: until when the squad can be changed (see "Deadlines remain out for now"). Whether
the minimum should also block something — a matchday start, say — is not decided; today it
is a warning on the club screen only.

Endpoints: `GET /api/admin/teams/{team_id}/members`,
`PUT /api/admin/teams/{team_id}/members`

Tests: `api/tests/stories/test_sailors_and_squads.py::TestRegisteringASquad`,
`api/tests/stories/test_sailors_and_squads.py::TestSquadRefusalsAreTyped`

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

Screen: `/club` lists the club's matchdays and opens the lineup under each one
(`LineupPanel`, Story V-12); administration and race officers use the same endpoint.

Tests: `api/tests/stories/test_lineup.py`, `e2e/club.spec.ts`

Open: coupling to confirmed liability waiver (S-1, VA-5).

### V-12 ● My club: one screen for members, matchdays and squads
As a **club manager** I want **my club's squad to be somewhere I can get to**,
so that **I can register who may sail without asking an administrator to do it for me**.

Story V-1 has said since it was written that "registration may be done by the leadership of
their **own** club", and the endpoint has enforced exactly that from the start. The screen
never did: the only squad panel lives under `/admin`, which refuses anyone who is not
`admin` or `editor`, and it finds a team by first listing every series through
`GET /api/admin/series` — an admin-only route. So a club manager had the permission, the
data and no door. This story is the door.

Acceptance criteria:
- **`/club` is the club's own screen, for everyone who belongs to it.** "My club" — "My
  clubs" for a person in several, the private view beside the public "Clubs" list — is in
  the navigation for anyone who is a member of a club or organizes one (`GET
  /api/clubs/mine`, Story B-10) — not only for `club_manager`, since a member has things
  to see there too. The screen has **three tabs**: **Members**, **Matchdays** and
  **Series** (`?tab=members|events|series`; Members opens first).
  - *Members*: the roster (Story V-10). For the club's organizer additionally the
    requests waiting for a decision with accept/reject (V-8), the invitations sent and
    an invite-by-email form (Z-5), and per member "make organizer" / "revoke" (A-8) and
    "remove". A plain member sees the roster and can leave the club. Until here every one
    of those endpoints existed without a page — the help text said so.
  - *Matchdays*: the club's event entries with the lineup under each (Story V-2).
  - *Series*: the series registrations, each with its squad (Story V-1).
- **Several clubs choose themselves in the navigation, not on the page.** "My club" opens
  the club the account acts for. With more than one club, a **dropdown** beneath the
  entry (`layout-nav-myClub-select`) picks another — a dropdown rather than one link per
  club, because ten links would swallow the navigation; picking one opens that club and
  **remembers it on the account** (`User.club_id`, `PATCH
  /api/auth/me`, only a club the account belongs to or organizes —
  `/errors/active-club-not-mine`). With nothing remembered, a club the person organizes
  wins over one they merely belong to. One club is the normal case and has no sub-entries.
  The account page does not repeat the choice — the navigation is the one place it is
  made; what the account page lists is every club, series and event the person has
  something to do with (Story Z-8).
- **Joining starts with the club's invitation, never with a stranger's click.** The
  public club page (`/clubs/{id}`) shows a signed-in visitor only what already exists
  between them and the club: an invitation the club sent (accept / decline), a request
  on file (with withdraw), or "you are a member" with the way to "My club". There is
  deliberately **no open "ask to join"** on the public page; the request endpoint of
  Story Z-5 stays, unused by the interface.
- **Nothing on the way in is admin-only.** The route reaches the squad through
  `/api/clubs/mine` and `/api/admin/teams/{team_id}/members`, both of which a
  `club_manager` may call for their own club. Needing an admin-only list to find your own
  team was the actual defect, and it would come straight back if this screen borrowed the
  admin page's queries.
- **The squad panel is the same component in both places.** `SquadPanel` is used by `/club`
  and by the admin screen; two copies would drift, and the rules it displays — the ten, the
  one helm, the typed refusals — are the ones that took the longest to get right.
- **The screen never offers what the account may not do.** A member who is not an organizer
  of that club sees the squad and cannot change it; the buttons are absent, not disabled
  and refused on click.
- **A signed-in account with no club does not get an empty screen.** `/club` says so in a
  sentence and links to the clubs page, which is where joining one starts (Story V-7).
- Administration keeps its own way in unchanged: `/admin?tab=sailors` still reaches every
  club's squad through the series, which is the right shape for someone whose job is all
  eighteen of them.
- A person can be a member of several clubs and organize several — the two relationships
  are per club (`ClubMember`, a `manager` tuple on the club) and independent. `User.club_id` has
  meant "the club this account acts for" since the model was written and had no way to be
  set; the navigation's sub-entries are that way now. `?club=` in the URL names the club
  being shown, so a link to one club keeps working and the sub-entry can show which is
  open.
- **The Matchdays tab** (Story V-2's door).
  `GET /api/clubs/mine` lists each club's **event entries** alongside its series
  registrations: every matchday of a series the club is registered in, and every
  stand-alone event it is entered in — with the event's dates and status, the entry's
  `team_id`, and the `squad_team_id` the lineup draws from (the series registration, or
  the entry itself for a stand-alone event). An organizer opens a matchday and names the
  crew from the squad, with roles; a member sees who is named. The endpoint is the one
  Story V-2 always had, `PUT /api/admin/events/{event_id}/crew`, which lets a
  `club_manager` line up their own club — the screen was the missing part, exactly as it
  was for the squad.
- A stand-alone event's squad hangs off the entry itself (`squad_team`), so the same
  `SquadPanel` is shown for it under the matchday — otherwise a club running its own cup
  here could enter it and never register anyone.

Tests: `api/tests/stories/test_my_clubs.py`,
`api/tests/stories/test_login_and_roles.py::TestActiveClub`,
`e2e/lifecycle.spec.ts::V-12: a club manager manages their own squad`,
`e2e/club.spec.ts`

## The club's page

### V-11 ○ Manage our own club page
As a **club organizer** I want to **edit our club page where it is shown**,
so that I **do not have to ask administration to fix our description or our crest**.

A `club_manager` can already upload the crest (Story V-3) and maintain sailors (V-4) — but
through the admin area, which is a different page from the one the public reads. The club
page is where a manager notices that the description is out of date, and it is where they
should be able to fix it.

Acceptance criteria:
- On the club page (Story B-11), a manager of **this** club — and `admin`/`editor` for any
  club — sees the page's own editing affordances. Everyone else sees the page exactly as it
  is today, with no disabled buttons and no hint that an editing mode exists.
- The check is `User.manages_club(club_id)`, never `acting.club_id == club_id`:
  `club_manager` is granted per club, so someone who organizes two clubs can maintain both,
  and merely *representing* a club grants nothing (same rule as V-3).
- **Info tab**: description, website and location are editable in place. Name and
  abbreviation are **not** — the abbreviation is in the URL and in every external-id
  mapping, so renaming a club stays an administration action.
- **The crest is edited from the crest.** Hovering the crest shows a pen overlay when the
  viewer may change it, and clicking it opens the file chooser — no separate "upload" button
  beside it. Without the right, there is no overlay and the crest is just an image.
- **Team tab**: a manager reaches the squad registration for their teams from here rather
  than only from the admin area. The rules do not change — a squad hangs off the series
  registration (V-1), and someone in a lineup cannot be dropped (V-2). The member roster
  on this tab is the members-only one (V-10); a manager additionally sees the pending
  requests they have to decide on (V-8), which no other member does.
- **Competition tab** stays read-only for a manager: which series a club is enrolled in is
  an administration decision (A-3), and entering an event goes through a request that
  administration accepts (V-6, A-9). A manager sees the state of those requests here.
- Every change is a normal API call against the endpoints that already enforce these rules;
  no new permission path is invented in the frontend.

Tests: none yet

### V-3 ◐ Upload club crest
As a **club manager** I want to **upload our club's crest**,
so that **we are recognizable on the page**.

Acceptance criteria:
- The club's **admin** uploads it for their **own** club — the crest is the club's
  identity, like its members (Z-3). `admin` and `editor` may do it for any club, as with
  the rest of club master data (A-1). The check is `User.administers_club(club_id)`: the
  relation is held per club, so someone who administers two clubs can maintain both
  crests, and merely *representing* a club (`User.club_id`) grants nothing.
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

**The UI** is the club list in `web/src/pages/Admin.tsx` (`ClubRow`). The crest is edited
**from the crest**: hovering (or keyboard-focusing) the thumbnail reveals a pen over it, and
activating it opens the file chooser — there is deliberately no separate "upload"/"replace"
button, which said the same thing twice and put the action a row's width away from the thing
it acts on. It is a real `<button>`, so the pen appears on focus as well as on hover; one
that only showed under a mouse pointer would tell a keyboard user nothing. Removing keeps its
own control, because removing is not replacing, and it appears only when there is something
to remove. The thumbnail sits on a checkerboard, because a crest whose transparency was
deliberately preserved has to *read* as transparent rather than as a white rectangle that
happens to match the page.

Endpoints: `POST /api/admin/clubs/{club_id}/logo`, `DELETE /api/admin/clubs/{club_id}/logo`,
`GET /api/clubs/{club_id}/logo`

Tests: `api/tests/stories/test_club_crest.py`
