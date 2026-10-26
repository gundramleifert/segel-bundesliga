# One person, many clubs — merging members and sailors

Decided 2026-10-25 (the user, after the pros and cons of separate vs merged lists):
**merge them and link them.** After this change there is no difference between a member
and a sailor: a **person** exists once in the instance, may have an account to sign in
with, and may be a member of several clubs.

## 1. What is wrong today

Two records describe the same human, joined only by an email address:

| | today's member | today's sailor |
|---|---|---|
| record | an account (`User`) holding `user:member:club` (Z-5) | a `Sailor` row with `SailorClub` rows (V-4) |
| created by | the club's admin, by an account's email | the club's organizer, *+ New person* |
| link to the other | none — `Sailor.email == User.email`, compared where needed | |

So a club keeps two lists of mostly the same people (*Members*, *Sailors*), a sailor who
signs in is two things to the system, and "is Anna in our club?" has two answers.

## 2. The model after the change

- **`Person`** (today's `Sailor`, renamed everywhere — model, table, API `/api/people`,
  UI words; public `/sailors/:id` redirects to `/people/:id`): name, date of birth,
  contact email, federation id, the profile switch (S-4). It is what squads, crews,
  waivers, results and guardians point at, as `Sailor` is today.
- **`Person.user_id`** — the account a person signs in with: optional, unique. **Every
  account has exactly one person**: created with the account (registration, enrollment,
  first sign-in), or the existing person with that **verified** address is linked to it.
  A person without an account is normal (children, other clubs' sailors, imports).
- **`ClubMembership`** (today's `SailorClub`, plus a status) is **the** membership:
  `person · club · status` with status `active`, `invited` (the club asked, the person has
  not answered) or `requested` (the person asked, the club has not answered). The
  `member` tuple on a club goes away; being a member is an `active` row.
- **Roles stay tuples on accounts** — `admin`, `manager`, `treasurer` on a club and every
  series, event and site relation: a role is exercised by signing in, so it needs an
  account. A role does not make anyone a member, and a member needs no role (as today).
- **The permission model**: `type sailor` becomes `type person` (`admin from site`,
  `manager from club`, `guardian: [user]`), its `club` edge the person's **active**
  memberships. `club#member` is answered from the membership of the asking account's
  person — one rule in `app/authz.py`, not a tuple. Everything that asks "is this account
  a member of that club" keeps asking `check(user, member, club)`.

## 3. Joining a club

| Who joins | How | Why |
|---|---|---|
| a **new** person (in no club, no account) | the club's organizer creates them — a member at once (V-4 today) | the club knows who is in it (decision of 2026-09-24) |
| an **existing** person in **no club** (an account, e.g. the new treasurer) | the club's admin adds them by email — a member at once (Z-5 today) | nobody else has a claim on them |
| a person **already in another club** | **consent, either way round**: the club's admin invites → `invited`, the person accepts in *Me*; or the person asks → `requested`, the club's admin accepts in the club | a second club's organizers get to see and change the person (birth date, guardians, documents), so the person — or the club — must agree; no club can simply take anyone (V-4's reason) |
| a person in another club **without an account** | the league office (nobody could accept) | as V-4 today |

Leaving: the person ends their own membership (as Z-5's *Leave the club*); the club's admin
removes one. Declining an invitation or a request deletes the row. Invitations and
requests are to-dos: `membership_invited` on *Me* (section `clubs`), `membership_requested`
on the club (section `people`).

This **revises** the decision of 2026-09-24 ("no request, no invitation") for the one case
it did not foresee — a person who already belongs to someone else.

## 4. Screens

- **Club › People** replaces *Members* and *Sailors*: one `DataTable`, narrowed on the
  server (`PersonFilter`, A-13) — search over name and email; filters *Role*, *Account*
  (yes/no), *Minor*, *No date of birth*, *In a squad* (this year), *Status* (active,
  invited, requested); sort by name, date of birth. Columns: name, roles (chips with ✕ for
  the club's admin), account, date of birth/age. *＋ Person* top-right (`AddDialog`):
  create a new person, or add an existing one by email (directly, or as an invitation
  when they are in another club). Row actions by what the reader may do — the club's
  admin roles and membership, the organizers the person's details.
- **A plain member** sees a read-only roster: names and roles of the active members, no
  dates of birth, no people without the member's own reason to see them (V-10 stays).
- *Minors & guardians* and *Waivers* stay sections for now; each is also reachable as a
  filter of *People*.
- **Me**: *My clubs* — my memberships, invitations to accept or decline, *Ask to join*
  a club (also from the public club page, signed in).
- The workspace's club sections (`PLAN_NAVIGATION.md` §3): *People* group = **People**,
  Minors & guardians, Waivers.

## 5. Steps (sub-issues, in order)

1. **Story and plan** — this file; stories V-4, V-8, V-9, V-10, Z-3, Z-5 rewritten into
   the person model; CLAUDE.md's domain decisions and `docs/concepts.md` updated.
2. **Rename** `Sailor` → `Person`, `SailorClub` → `ClubMembership` — model, table, API,
   generated client, i18n, tests, redirects. No behaviour change; alone, because it
   touches everything.
3. **Link** — `Person.user_id`, a person for every account (registration, enrollment,
   sign-in; linking by verified email), the `member` tuple replaced by active
   memberships, `club#member` from the person, seed rebuilt. Backend and its tests.
4. **Consent** — `invited`/`requested`, accept/decline both ways, the to-dos, *Me › My
   clubs*, *Ask to join*.
5. **Club › People** — `PersonFilter`, the table, the dialog, the read-only roster;
   *Members* and *Sailors* sections go (old addresses redirect).
6. **Handbook, journeys, e2e** — the help pages, J-3 (member) and the §5 walk.

Steps 2–3 are one database change for the initial migration (CLAUDE.md, Migrations).

## Status

Built 2026-10-26: steps 1–6 — #41 (stories), #42 (rename), #43 (link, membership not a
tuple), #44 (consent, V-15), #45 (*Club › People*), #46 (help pages, J-3, the §5 walk).
