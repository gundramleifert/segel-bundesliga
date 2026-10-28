# Club: its admin and its team manager

Part of the [user stories](README.md); the format, the status marks and the
identifier rule are explained there.

These stories are connected: who joins a club can join its squad; the club registers a season
squad, the registered sailors sign once for the season, the organizer checks them off, and
before each matchday the club names the four who actually sail.

Two people stand behind "the club" here (Story Z-2): the club's **admin** decides who is
*in* the club — members, organizers, the crest — and the club's **manager** decides who
*sails* — squads, lineups, registrations; the site calls them the **team manager**. Where a story below says `team_manager`, read
the manager for sport and the admin for membership; an admin is a manager too.
Membership itself is a tuple, `user:member:club`, written by the admin (Z-5) — **until
#40** (decided 2026-10-25, [`docs/PLAN_PEOPLE.md`](../PLAN_PEOPLE.md)): then members and
sailors are one **person**, and being in a club is one `ClubMembership` row
(person · club · status `active`, `invited` or `requested`) that replaces both the `member`
tuple and `SailorClub`. A person may have an account (`Person.user_id`); roles stay tuples
on accounts. The criteria below say where they change, under **After #40**.

The path into a competition goes both ways. Administration assigns clubs to series
([A-3](administration.md#a-3--assign-clubs-to-series), [A-6](administration.md#a-6--create-series-and-select-clubs)); V-5
and V-6 add the club's own application from below — **without** replacing the path from
above — and [A-9](administration.md#a-9--accept-or-reject-participation) is administration's answer to it.

## Members

### Z-3 ● Assign user to club
As a **club admin** I want to **make an account a member of my club**,
so that **registrations, posts, and check-in go to the right club**.

This *is* adding a person to the club (Story Z-5): an account has **no club
of its own** — no "assigned" or "acting" club, no `User.club_id` (removed 2026-09-25).
What ties a person to a club is their membership and what their account holds on it —
`manager`, `admin` (Story Z-2) — each per club, any number of clubs. Which of several clubs a screen shows
is the URL's business (`/me/club/:id`, Story S-7), not the account's.

Acceptance criteria:
- A club's admin adds people only to a club they administer; the site's admin to any.
- There is no account-level club field to set, by anyone; the account list does not show
  one. Every change to who is in a club is logged.
- Since #43 it is an `active` `ClubMembership` of a **person**, not a tuple. An account
  is linked to exactly one person (`Person.user_id`), so making an account a member makes
  *its person* one. A person already in another club joins only with consent
  ([V-15](#v-15--join-a-second-club-with-consent-either-way-round)).

Tests: `api/tests/stories/test_club_members.py::TestMembers`

### V-8 ● Decide who is in the club
As a **club admin** I want to **decide who is in our club**, so that **not everyone can
join** — and so that nobody has to wait for a decision.

Acceptance criteria:
- The club's people are **one list**, the *People* section (`/me/club/:id/people`, #45),
  where *Members* and *Sailors* were two — everyone with a `ClubMembership` on the club,
  and for the organizers also whoever's account holds a role there without being a
  member (organizers often never sail), with their roles, whether they have an account,
  and their date of birth. Narrowed on the server (`ClubPersonFilter`, A-13): search over
  name and email; filters role, account yes/no, minor, no date of birth, in a squad this
  year, status (active, invited, requested); sorted by name or date of birth; a page at a
  time, every filter in the address. The old addresses redirect.
- *＋ Person* (top right, a dialog) is the **club's admin's**: a new person for the
  club, or someone on record by email, with roles at once (V-9). A new person is a
  member, and who is in the club is the admin's to decide (decided 2026-10-28).
- **Membership is no role.** It has its own column (member, invited, asks to join, or
  none for an organizer who is not a member), and the roles stand beside it as plain
  marks.
- **Every change to a row sits behind the row's "⋯"**, the club's admin's alone: accept or
  decline a request, withdraw an invitation, give or remove a role (the roles are
  separate tuples on the account, so only someone with an account holds one, and each goes
  on its own), end a membership. One's own membership is not ended there. That
  is *Leave*, with its confirmation. Someone already in another club is invited, not
  taken ([V-15](#v-15--join-a-second-club-with-consent-either-way-round)).
- A manager (team manager) sees the whole list and completes dates of birth, but adds
  nobody and changes nobody's membership: the team manager decides who *sails*, the admin
  who is *in* (decided 2026-10-28; until then a manager created new people, each a member
  at once). A plain member reads the roster (V-10).
- Every change is logged.

Endpoints: `GET /api/clubs/{id}/people`, `POST`/`DELETE /api/clubs/{id}/members`,
`POST /api/clubs/{id}/members/{person_id}/accept`, `POST /api/auth/tuples` and
`DELETE /api/auth/tuples/{id}` for the roles (Story Z-2)

Screen: the *People* section of the club's page in my space, `/me/club/:id/people`
(Stories V-12, S-7, Z-10); `…/members` and `…/sailors` lead there.

Tests: `api/tests/stories/test_club_people.py::TestClubPeople`, `api/tests/stories/test_club_members.py::TestMembers`, `e2e/club.spec.ts`

### V-9 ● Add someone by email
As a **club admin** I want to **add a person by their email address**, so that I **can
register our sailors myself**.

Acceptance criteria:
- Contact is via **email address** — the identifier a person knows about themselves. An
  account must exist for it; those without one register first ([Z-4](sailor.md#z-4--register-yourself)),
  and the panel says so (404).
- The person is a member at once — no acceptance step (Z-5). They can leave again.
- A person may be in **multiple clubs**; the constraint "only once" applies first per series
  and event, not for membership.

Endpoints: `POST /api/auth/tuples`

**After #40** (not built yet):
- The email finds a **person**, not only an account: the person with that address, or
  the one linked to the account with it. No account is needed any more — a person
  without one is normal (a child, a crew member who never signs in).
- A person in **no club** becomes an `active` member at once, as today. A person
  **already in another club** gets an invitation instead (`invited`), which they accept
  in *Me › My clubs* ([V-15](#v-15--join-a-second-club-with-consent-either-way-round));
  without an account nobody could accept, so that case stays the league office's.

Tests: `api/tests/stories/test_club_members.py::TestMembers`

### V-4 ● Create sailors
As a **club admin** I want to **create sailors in my club**,
so that **our team manager can register them in the squad**.

**Who is in the club is the club admin's; who sails, the team manager's** (decided
2026-10-28). A person created for a club is a member at once, so creating one is the
admin's — until then this story was the team manager's, which let the team manager add
members through the back door. The team manager still finds everyone, completes and
corrects the club's people (a date of birth, a spelling) and puts **members** in squads.

Acceptance criteria:
- First name, last name, and **email are all required** — someone created through this form
  must be reachable: the address is the bridge to the account, through which the person
  signs in and submits their liability waiver (V-1, S-1). (A future manage2sail import may
  still write a sailor without one, bypassing this form.)
- Birth date is captured as a **complete date**, not just a year — age-category eligibility
  (e.g. a youth series) needs the exact date. It stays optional and is never shown publicly.
- **A person sails for clubs, and that is in the permission model** (decided 2026-10-25):
  `ClubMembership` rows (`SailorClub` until #42) are the `club` edge of a person, and a sailor's `manager` is
  `manager from club` (`app/models/auth.py`). Whoever is that `manager` puts the person in
  a squad, changes them, signs their waiver forms (S-1, S-3) and links their parents
  (V-13). Until 2026-10-25 putting someone in a squad was what made them a club's — and
  any club could put anyone in its squad, so it could then sign for another club's
  sailor and link itself as a child's guardian.
  - **The club's admin creates people for their own club** — `club_id` is required of
    them (`person-needs-club`, 422), and must be a club they are admin of
    (`person-club-not-yours`, 403 — a team manager gets it too). The league office may
    create someone who sails for no club yet (an import does too).
  - **A squad takes only its own club's members.** Someone in another club is
    `squad-person-of-another-club`, someone in no club `squad-person-not-a-member` (403,
    naming them — until 2026-10-28 the squad took them into the club); the squad screen
    greys both out with the reason, and offers *New person* to the club's admin only.
  - **A second club only through the league office** (decided 2026-10-25): a club's
    organizer manages the sailors of their own club and nobody else's. The league office
    adds someone to a second club by putting them in its squad. (For a day an endpoint
    let the club a person sails for connect them to another; removed — no club decides
    for another.) A club's admin lets someone go with `DELETE …/people/{id}/clubs/{club_id}` —
    its own connection only, never its team manager (2026-10-28); the squads they are in stay, and the person sails for no
    club then, so a new club can take them.
  - **Any club's organizer still finds everyone** — that is how they see who sails
    elsewhere, and finding the existing record beats creating a second. **Changing** a
    person: the organizer of a club they sail for, any club's while they sail for none;
    the site's `admin` always (until 2026-10-24 editorial too — sailors as master data
    are the admin's alone since, A-1). Anyone else gets `sailor-not-yours` (403); until
    2026-10-17 any club's organizer could edit anyone (found by Journey J-3).
- If the address is already known, the **existing person is offered** instead of creating a
  second. Two records for the same person would be a mistake that is hard to fix later.
- **A person may sail for multiple clubs.** They can be registered for one in the first
  series and for another in the juniors — that is not an exception, it happens. The
  league office connects them to the second club (above).
- **Within a series or event, they appear only once.** Otherwise, they would start against
  themselves. This is the rule that must be enforced — not the number of clubs.
- Addresses are stored **lowercase**: "Jan@…" and "jan@…" would otherwise be two people and
  later two accounts.
- People are discoverable by **name and address** — without search, a list of 360 names is
  unusable.
- A name can be corrected; a typo should not force a second person.

**Done: an account has no club of its own** — only tuples on clubs. That is in
the memberships and can be multiple ([V-9](#v-9--add-someone-by-email)). This resolves the
contradiction: a person sails for two clubs but always handles only one.

Still open: The **account** is not created automatically with the person. Those who should be
able to sign in register ([Z-4](sailor.md#z-4--register-yourself)) or are created. Both are connected
via the address.

**The address, once set, is the league office's to change** (`sailor-email-locked`,
2026-10-24): it is what links the record to an account. A club's organizer gives an
address to a person who has none; changing one would hand the person's waivers and profile
to another account.

**Screen** (Story Z-10, #45): the club's *People* section, `/me/club/:id/people`, for its
organizers — everyone in the club, *＋ Person* creating someone for this club (the admin
only), and the date of birth set right on the row of a person who has none (the club's
`person_without_birth_date` to-do lands on the list filtered to them). The squad screen
keeps its own *New person* for the squad it is on — for the club's admin and the league
office, absent for a team manager.

Endpoints: `GET /api/admin/people`, `POST /api/admin/people`,
`PATCH /api/admin/people/{id}`, `DELETE /api/admin/people/{id}/clubs/{club_id}`

**Since #40** (built in #42–#45):
- A sailor is a **person** (`Sailor` → `Person`, `/api/people`, public `/sailors/:id`
  redirects to `/people/:id`), and "sails for a club" is an `active` `ClubMembership` —
  the same row that makes them a member. The permission edges stay: a person's `manager`
  is `manager from club`, over their active memberships only.
- Creating a person for the club makes them an `active` member at once (a new person is
  in no club). The account link is `Person.user_id`, not the email: an account is linked
  to the person with its **verified** address, or gets a new person when it is created
  (registration, enrollment, first sign-in) — so the "still open" above is closed.
- **A second club is consent, no longer only the league office**: the club's admin
  invites, or the person asks, and the other side accepts
  ([V-15](#v-15--join-a-second-club-with-consent-either-way-round)). A person in another
  club without an account still goes through the league office — nobody could accept.
- The squad rule stays: a squad takes only people with an active membership in its club.
- The *Sailors* section went; its work is in *People* (V-8), filtered by *No date of
  birth* for the `person_without_birth_date` to-do.

Tests: `api/tests/stories/test_sailors_and_squads.py::TestCreatingSailors`,
`api/tests/stories/test_sailors_and_squads.py::TestASailorSailsForTheirClub`,
`e2e/lifecycle.spec.ts::V-12/V-4/VA-6: a team manager manages their own squad`

### V-15 ● Join a second club, with consent either way round
As a **person already in one club** I want **a second club to take me in only when I
agree** — and as a **club admin** I want **to take in someone from another club only when
they agree**, so that **no club can simply take anyone**.

Issue #44 (step 4 of #40, [`docs/PLAN_PEOPLE.md`](../PLAN_PEOPLE.md) §3). Joining a
second club hands that club's organizers a person's birth date, guardians and documents,
so either the person or the club must say yes. This revises the decision of 2026-09-24
(Z-5: no request, no invitation) for the one case it did not foresee — someone who
already belongs to another club. A person in no club still joins at once (V-4, V-9).

Acceptance criteria:
- **The club invites**: the club's admin adds, by email, a person who is active in
  another club → a `ClubMembership` with status `invited`. The person sees it as the to-do
  `membership_invited` in *Me › My clubs* (section `clubs`) and accepts (→ `active`) or
  declines (the row is deleted).
- **The person asks**: signed in, from *Me › My clubs* or the public club page, *Ask to
  join* → status `requested`. The club's admin sees it as the to-do `membership_requested`
  in the club's *People* section, filtered by status, and accepts (→ `active`) or
  declines (deleted). A person in no club asking is accepted the same way.
- An `invited` or `requested` row grants nothing: the person is not a member, not in the
  club's `manager from club` edge, not in a squad, and does not see the roster.
- A person in another club **without an account** cannot be invited (nobody could
  accept); the league office adds them, as before.
- Every change of a membership — invite, ask, accept, decline, leave, remove — is in the
  audit log.
- *Me › My clubs* lists my memberships with their status, the invitations to answer and
  my open requests, and *Leave* for each active one.

Endpoints: `POST /api/clubs/{id}/members` (invites), `POST
/api/clubs/{id}/members/{person_id}/accept`, `GET`/`POST /api/me/memberships`, `POST
/api/me/memberships/{club_id}/accept`, `DELETE /api/me/memberships/{club_id}`, and
`DELETE /api/clubs/{id}/members/{person_id}` for the club's side. The club's requests
wait in its *People* section; the to-do lands on it filtered by status.

Tests: `api/tests/stories/test_join_with_consent.py::TestTheClubInvites`,
`api/tests/stories/test_join_with_consent.py::TestThePersonAsks`,
`api/tests/stories/test_join_with_consent.py::TestEveryChangeIsLogged`,
`api/tests/stories/test_club_members.py::TestMembers::test_someone_in_another_club_is_invited_or_added_by_the_league_office`,
`e2e/join-consent.spec.ts`

### V-16 ○ Invite someone to an account
As a **club admin** I want to **send a person of our club an invitation by email**, so
that **they get their account from it** — without registering on their own first and
without knowing that they have to.

Today a club adds a new sailor in two halves that nothing joins: the club creates the
person with their address (V-4, V-8), and the person has to find the site, register
with **that same** address (Z-4) and redeem the code — only then does the account land
on the record the club made (`people.person_for`). Signing in with a code instead is
refused (`login-account-unknown`, `allow_self_signup` off), and the club admin adding
someone by email before they registered gets a 404 (V-9, Journey J-3.1). Nobody on the
site tells the person any of this; the club says it on the pontoon. Found drawing the
onboarding into Journey J-3 (2026-10-28).

Acceptance criteria:
- The club's `admin` sends an invitation to a person **of the club** — an `active`
  member — who has an address on record and **no account**: from the row's "⋯" in the
  *People* section, and offered right after *＋ Person* created someone. **Not the
  team manager** (decided 2026-10-28): the admin decides who is *in* the club and the
  team manager who *sails* — squads and crews, nothing about membership or accounts.
- The site mails a link to that address, naming the club and who invited, and ending
  with the footer every mail of the site carries (`app/mail.py::with_footer`: the
  association, why the mail came — here "your club … invited you" —, whom to write to,
  privacy and legal notice; decided 2026-10-28). The link is built on `SBL_SITE_URL`. The token in
  it is random, stored only hashed, valid for **14 days** (decided 2026-10-28 — a sailor does not
  read mail daily off-season, and the link is single-use and resent at will) and for
  **one** use;
  sending again replaces the earlier one.
- Opening the link shows the person's name as the club entered it; the person confirms
  it (or corrects it) and gets an account: the address **verified** by the link — it
  reached them — linked to **this** person (`Person.user_id`), so the membership and
  anything the club already entered are theirs at once. They are signed in, and may set
  a password then (Z-9).
- It works with registration closed and `allow_self_signup` off: the invitation is the
  explicit enrollment the club asks for, not a sign-up.
- Refused: a person who already has an account (`invitation-has-account`, 409 — they
  sign in), a person without an address, a person not in the club, anyone but the club's
  admin (and the site's) — a team manager gets `invitation-forbidden` (403). An expired or used link says so and points to the club.
- Every invitation sent and redeemed is in the audit log; the row in *People* shows
  "invited" until it is redeemed.

The mail is **German** by default, like every mail of the site (`app/mail.py`,
`MAIL_LOCALE`, decided 2026-10-28); English when the reader's language is known.

Tests: none yet

## Entering competitions

### V-5 ● Request participation
As a **team manager** I want to **register my club for a series or event**,
so that I **don't have to call the league office**.

Acceptance criteria:
- An organizer applies only for their **own** club.
- The application is then visible to them, with its status: **requested, accepted, rejected**.
- An applied-for club does **not** appear publicly in the series and does **not count** in
  standings — only acceptance makes it a participant.
- An application can be withdrawn as long as it is not accepted.
- A second application for the same series is rejected, not duplicated.
- After rejection, a new attempt is possible.

- On screen (#39): the club's *Squads* section, for its organizers — *Apply for a
  series* offers the published series of this year and next the club is not in yet, and
  lists the waiting and rejected applications (with the reason) to withdraw.

Endpoints: `POST /api/applications`, `GET /api/applications`,
`DELETE /api/applications/{team_id}`

Tests: `api/tests/stories/test_participation.py::TestApplying`, `e2e/workspace-club.spec.ts`

### V-6 ● Request participation in an event
As a **team manager** I want to **register my club for a single event**,
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
As a **team manager** I want to **register the people who are allowed to sail for us**,
so that **it is clear who can be lined up**.

Acceptance criteria:
- The squad depends on the **registration for the series**, not entry in a single act. Lineup
  is drawn from it per matchday ([V-2](#v-2--select-sailors-for-matchday)).
- A registration replaces the previous one **completely** — it is the squad, not a supplement.
- **The same person may be registered in multiple clubs**, but **within a series only once** —
  otherwise they would start against themselves. A squad takes only the club's active
  members (V-4): `squad-person-of-another-club`, or `squad-person-not-a-member` for
  someone in no club — the club's admin adds them first (decided 2026-10-28).
- No one appears twice in the same squad.
- **Who is lined up for a matchday does not fall out of the squad.** Otherwise, a lineup would
  exist with no squad. Change the lineup first, then the squad. So the squad says it up
  front: under each member, one line naming the matchdays they are lined up for here
  (`lineups` of `GET /api/admin/teams/{id}/members`), as the search side names where
  someone sails.
- Registration may be done by the leadership of their **own** club; administration everywhere.

- **Every refusal is a typed problem** (`app/problems.py`), not a sentence built in the
  router: the squad screen has to say *which* rule was broken, and it has to say it in the
  reader's language. A team manager who adds someone who already sails for another club in
  the same series gets that sentence, with both names in it — not a 422 whose body is an
  English string chosen by the backend.
  - `squad-duplicate-person` — the same person twice in one submission.
  - `squad-person-in-another-club` — already registered for this series elsewhere, and by
    whom.
  - `squad-member-is-lined-up` — cannot be dropped while lined up for a matchday, and for
    which one.
  - `squad-needs-series-registration` — this `Team` is the entry in an event that belongs
    to a series, whose squad is the club's series registration. **A stand-alone event's
    entry does carry the squad** (V-12) and is saved like a series registration, within
    the event's own limits; until 2026-10-17 it was refused too, which left a club's own
    cup without a squad, a crew or a waiver (found by Journey J-5, step J-5.4).
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
  club too. The endpoint keeps refusing it (`squad-person-in-another-club`): the list is
  a courtesy, not the enforcement.
- **A rejected registration takes no squad** (`squad-registration-rejected`) and holds
  nobody; at an event outside a series the squad is the club's **first** team's
  (`squad-on-first-team`), the one every team of the club is lined up from.

Open: until when the squad can be changed (see "Deadlines remain out for now"). Whether
the minimum should also block something — a matchday start, say — is not decided; today it
is a warning on the club screen only.

Screen: the club's *Squads* section, `/me/club/:id/squads` (Story Z-10) — one row per
series registration and per stand-alone event the club is entered in, each opening its
squad (`SquadPanel`); the series' *Squad size & scoring* section sets the limits.

Endpoints: `GET /api/admin/teams/{team_id}/members`,
`PUT /api/admin/teams/{team_id}/members`

Tests: `api/tests/stories/test_sailors_and_squads.py::TestRegisteringASquad`,
`api/tests/stories/test_sailors_and_squads.py::TestSquadRefusalsAreTyped`

### V-2 ● Select sailors for matchday
As a **team manager** I want to **name the four sailors for a matchday in advance**,
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
- A team manager lines up only their **own** team; administration and race committee can
  intervene anywhere — on event day someone must be able to change quickly.
- An empty list removes the lineup.
- An event **without a series** has no squad and thus no lineup.

Endpoints: `PUT /api/admin/events/{slug}/crew`, `GET /api/admin/events/{slug}/crew/{team_id}`

Screen: the *Events & crews* section of `/me/club/:id` (`/crews`, Story Z-10; the Matchdays
tab before #32) lists the club's events and opens the lineup under each one — one row per
team when the club enters several (VA-13) — (`LineupPanel`, Story V-12); administration and
race officers use the same endpoint.

Tests: `api/tests/stories/test_lineup.py`, `e2e/club.spec.ts`

Open: coupling to confirmed liability waiver (S-1, VA-5).

### V-12 ● My club: one screen for members, matchdays and squads
As a **team manager** I want **my club's squad to be somewhere I can get to**,
so that **I can register who may sail without asking an administrator to do it for me**.

Story V-1 has said since it was written that "registration may be done by the leadership of
their **own** club", and the endpoint has enforced exactly that from the start. The screen
never did: the only squad panel lives under `/admin`, which refuses anyone who is not
`admin` or `editor`, and it finds a team by first listing every series through
`GET /api/admin/series` — an admin-only route. So a team manager had the permission, the
data and no door. This story is the door.

Acceptance criteria:
- **The club's page in my space is the club's own screen, for everyone who belongs to
  it** — `/me/club/:id` (Story S-7; it was `/club` until Issue #10, and that address
  redirects). Every club a person is a member of or organizes is a card in *My space*
  (Story Z-8), not only for `team_manager`, since a member has things to see there too.
  The club screen's part of it is **three tabs**: **Members**, **Matchdays** and
  **Series & squads** (`?tab=members|events|series`; Members opens first), beside the
  person's claims and, for its organizer or treasurer, the club's money (S-7).
  - *Members*: the roster (Story V-10). For the club's admin additionally the People
    panel — every tuple on the club, add by email as member, manager, admin or race
    officer, remove (V-8, V-9, A-8). A plain member sees the roster and can leave the
    club (Z-5). Until here every one
    of those endpoints existed without a page — the help text said so.
  - *Matchdays*: the club's event entries with the lineup under each (Story V-2).
  - *Series*: the series registrations, each with its squad (Story V-1).
- **Several clubs are several cards, not a choice in the navigation.** Each club is its
  own card in my space, saying what the person is to it before it is opened, and the URL
  names the club shown; the account remembers nothing — it has no club of its own (Z-3).
  Until Issue #10 the navigation carried a "My club" entry with a dropdown of clubs and
  the browser remembered the last one; a card per club replaced both, because a dropdown
  could not say which club was the person's to organize and which merely theirs to sail
  for.
- **Joining is the club's doing, never a stranger's click.** The public club page
  (`/clubs/{id}`) offers no way in: the club's admin adds the person (Z-5).
  A signed-in member sees the roster there; their own way in is *My space*.
- **Nothing on the way in is admin-only.** The route reaches the squad through
  `/api/clubs/mine` and `/api/admin/teams/{team_id}/members`, both of which a
  `team_manager` may call for their own club. Needing an admin-only list to find your own
  team was the actual defect, and it would come straight back if this screen borrowed the
  admin page's queries.
- **The squad panel is the same component in both places.** `SquadPanel` is used by the club's
  page in my space and by the admin screen; two copies would drift, and the rules it displays — the ten, the
  one helm, the typed refusals — are the ones that took the longest to get right.
- **The screen never offers what the account may not do.** A member who is not an organizer
  of that club sees the squad and cannot change it; the buttons are absent, not disabled
  and refused on click.
- **A signed-in account with no club does not get an empty screen.** My space says so in a
  sentence and links to the clubs page, which is where joining one starts (Stories V-7,
  Z-8).
- Administration keeps its own way in unchanged: `/admin?tab=sailors` still reaches every
  club's squad through the series, which is the right shape for someone whose job is all
  eighteen of them.
- A person can be a member of several clubs and organize several — the relations
  (`member`, `manager`, `admin`) are per club and independent. The URL (`/me/club/:id`)
  names the club being shown, so a link to one club keeps working.
- **The Matchdays tab** (Story V-2's door).
  `GET /api/clubs/mine` lists each club's **event entries** alongside its series
  registrations: every matchday of a series the club is registered in, and every
  stand-alone event it is entered in — with the event's dates and status, the entry's
  `team_id`, and the `squad_team_id` the lineup draws from (the series registration, or
  the entry itself for a stand-alone event). An organizer opens a matchday and names the
  crew from the squad, with roles; a member sees who is named. The endpoint is the one
  Story V-2 always had, `PUT /api/admin/events/{event_id}/crew`, which lets a
  `team_manager` line up their own club — the screen was the missing part, exactly as it
  was for the squad.
- A stand-alone event's squad hangs off the entry itself (`squad_team`), so the same
  `SquadPanel` is shown for it under the matchday — otherwise a club running its own cup
  here could enter it and never register anyone.

**Since #32 the tabs are sections** of the club's context (Story Z-10): *Members* (the
roster, leaving, the People panel), *Squads* (every series registration **and** every
stand-alone event's squad, one row each) and *Events & crews* (the former Matchdays) —
beside *Sailors*, *Minors & guardians*, *Waivers*, *Hosting*, the money's three sections and
the *Club page*. The crest and the guardians left the Members tab for sections of their
own. Squads and crews come from `GET /api/clubs/mine`, which answers "mine": a club the
league office opens without being in it has every other section, and those two are left
out rather than drawn empty.

**Since #45**: *Members* and *Sailors* are one **People** section (V-8), the *People*
group being People, Minors & guardians and Waivers. Joining stays the
club's doing for a person in no club; a person **already in another club**, signed in,
may *Ask to join* from the public club page or *Me › My clubs*, and the club's admin
accepts ([V-15](#v-15--join-a-second-club-with-consent-either-way-round)) — the one way
in that starts from the person.

Tests: `api/tests/stories/test_my_clubs.py`,
`e2e/lifecycle.spec.ts::V-12/V-4/VA-6: a team manager manages their own squad`,
`e2e/club.spec.ts`

## The club's page

### V-13 ● Link a parent to a minor sailor
As a **team manager** I want to **link a parent's account to a young sailor of our club**,
so that **the parent can accept the liability waiver for their child online** — without
a printed form, a pen and a scan (Story S-8).

A minor's waiver needs their guardian (S-1). Until now the only way was paper: print the
form, have it signed, upload the scan. The club knows its young sailors' parents, so the
club says who is whose guardian — decided 2026-10-17: **only the club's manager or admin
connects an adult's account to a child**, never the parent themselves (anyone could claim
any child) and never the child.

Acceptance criteria:
- Guardianship is a relation tuple, `user:guardian:sailor` (Story Z-2) — a new object
  type `sailor` with the one relation `guardian`. A child can have several guardians, a
  parent several children.
- **Who may link and unlink**: the manager or admin of a club the child sails for — the
  model's `manager` on the sailor (V-4) — and the site's admin. Anyone else gets
  `guardian-link-forbidden` (403). Until 2026-10-25 a squad or an entry holding the child
  was enough, and any club could put any child in its squad.
- **The guardian need not belong to the club** — only the child does. A parent is often
  no member, sailor or organizer anywhere; the link asks nothing of them but an account.
- The parent is named by the **email of an existing account**, as on the People panel
  (V-9): no account → `guardian-account-missing` (404), register first (Z-4). Linking
  the same account twice is `tuple-exists` (409); a child cannot be their own guardian
  (`guardian-is-the-sailor`, 422).
- Every link and unlink is in the audit log, as every tuple.
- The screen is the club's **Minors & guardians** section (`/me/club/:id/minors`, under
  *People*, Story Z-10 — it was part of the Members tab until #32), for the club's
  organizer: the club's sailors, minors first, with their guardians, add by email, remove.
  A minor with no guardian linked is a to-do there (`minor_without_guardian`).

**After #40** (not built yet): the object type is `person` (`user:guardian:person`), and
"a club the child sails for" is an `active` `ClubMembership`. The guardian is still named
by an **account** — accepting a waiver online is signing in — and that account's person
need not be in any club. *Minors & guardians* stays a section and is also *People*
filtered by *Minor*.

Endpoints: `GET /api/clubs/{club_id}/guardians`, `POST /api/people/{person_id}/guardians`,
`DELETE /api/people/{person_id}/guardians/{tuple_id}`

Tests: `api/tests/stories/test_guardians.py::TestLinkingAGuardian`, `e2e/guardians.spec.ts`

### V-14 ● See whose waivers are in
As a **team manager** I want to **see which of our sailors have signed the liability
waiver and which have not**, so that **I can chase the missing ones before the matchday
instead of finding out at check-in**.

The organizer's check-in list (VA-2, VA-5) answers this for one event and every club in
it; the team manager needs it for their own club and every competition it is in.

Acceptance criteria:
- A **Waivers** section on the club's page in my space (`/me/club/:id/waivers`, under
  *People*, Z-10), for the club's organizer (`manager` or `admin` on it); it says how many
  matchdays need it (`crew_waiver_missing`, Z-8).
- One block per competition the club is in and has not finished: each **series squad**
  (one waiver covers all its matchdays) and each **entry in an event that belongs to no
  series** (planned or live). Each block says *n of m cleared*, and lists the sailors —
  those still missing first — with their status: cleared, missing, outdated version,
  waiting on the guardian's signature, date of birth unknown.
- The status is the one the sailor's own page and the check-in list compute
  (`app/services/waivers.py`) — never a second rule.
- Anyone else gets `club-waivers-forbidden` (403); an unknown club 404.

Endpoint: `GET /api/clubs/{club_id}/waivers`

Tests: `api/tests/stories/test_waiver.py::TestClubOverview`,
`e2e/my-space.spec.ts` ("S-1/Z-8/V-14: an unsigned waiver is a notice with its button, a badge, and a line in the club's list")

### V-11 ○ Manage our own club page
As a **club organizer** I want to **edit our club page where it is shown**,
so that I **do not have to ask administration to fix our description or our crest**.

A `team_manager` can already upload the crest (Story V-3) and maintain sailors (V-4) — but
through the admin area, which is a different page from the one the public reads. The club
page is where a manager notices that the description is out of date, and it is where they
should be able to fix it.

Acceptance criteria:
- On the club page (Story B-11), a manager of **this** club — and the site's `admin` for
  any club (until 2026-10-24 also `editor`) — sees the page's own editing affordances. Everyone else sees the page exactly as it
  is today, with no disabled buttons and no hint that an editing mode exists.
- The check is `authz.check(acting, MANAGER, on=club)`, never `acting.club_id == club_id`:
  the relation is held per club, so someone who organizes two clubs can maintain both,
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
As a **team manager** I want to **upload our club's crest**,
so that **we are recognizable on the page**.

Acceptance criteria:
- The club's **admin** uploads it for their **own** club — the crest is the club's
  identity, like its members (Z-3). The site's `admin` may do it for any club, as with
  the rest of club master data (A-1); until 2026-10-24 the site's `editor` could too. The check is `authz.check(acting, ADMIN, on=club)`:
  the relation is held per club, so someone who administers two clubs can maintain both
  crests.
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
versioned (see `.gitignore`); with `SBL_STORAGE=s3` the same key lives in a bucket
(`app/storage.py`).

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

**The club's admin edits it on their club's page in my space** — the *Club page* section,
`/me/club/:id/club-page` (Story Z-10, #32; it stood on the Members tab before), with the
club's name, short name, city and website shown beside it — those the league office
changes. Only the club's `admin` has the section. Until 2026-10-17 the only control was the admin screen's club list, which a
club's admin cannot open, so the endpoint let them upload and no screen did (found by
Journey J-2). Both places use one component, `CrestEditor`.

**The UI** in both places — the admin screen's club list (`ClubRow` in
`web/src/pages/Admin.tsx`) and the club's page — is `web/src/components/CrestEditor.tsx`. The crest is edited
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
