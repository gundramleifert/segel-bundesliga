# User Stories

Here we collect what the system should be able to do — from the perspective of those who use it. Each story gets an identifier (`B-1`, `WL-3`, …); tests carry the same identifier in their docstring. This makes it possible to look in both directions: What is already covered by this story? And which story does this test belong to?

**Roles:** `B` Visitor/Fan · `WL` Race Committee · `V` Club Manager ·
`R` Editorial · `S` Sailor · `A` Administration · `L` Live and tracking (spectator, race
committee and the phone on the boat share these; the plan is `docs/PLAN_LIVE_IMPLEMENTATION.md`)

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

Tests: `api/tests/stories/test_visitor.py::TestSeriesTable`
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
- **The ranking comes first.** The matchdays used to sit above it as a grid of cards, with
  the series' free-text description above that and a paragraph explaining low-point
  scoring below — so the ranking, which is the one thing a league table is opened for,
  started below the fold. The description and the paragraph are gone for good.
- **Two named blocks: "Results", then "Events".** The matchday cards are back, but below
  the table. There they are the step a reader takes *after* the numbers rather than an
  obstacle in front of them, and the page states what each block is — the page's own name
  is the breadcrumb's (Story A-12), so these are `h2`s, not a second title.
- **Each act column heading also links to its matchday.** A reader looking at one column of
  positions wants that matchday, and the cards below answer a different question ("where
  and when"). The heading is narrow ("Act 2"), so the event's full name is its tooltip.
- The scoring rule is not explained on the page. A "did not sail" cell says so in its own
  tooltip, which is where the question is actually asked; a permanent paragraph restating
  it was read once and skipped thereafter.

Tests: `api/tests/stories/test_visitor.py::TestSeriesTable`,
`e2e/visitor.spec.ts::B-1: as a fan I see the series standings`

### B-2 ● Review matchday results
As a **fan** I want to **review how a matchday turned out**,
so that I **can understand the course of events**.

Acceptance criteria:
- Complete daily standings across 18 teams; each team sailed once in 16 flights.
- The points are broken down by race, and the sum gives the overall standings.
- A running matchday shows an interim standing, a planned one shows no results yet.

`EventStandingRow.points_by_race`/`discarded_races` (`api/app/schemas/public.py`) carried the
per-race breakdown from the start, but `web/src/pages/Matchday.tsx`'s daily standings only
rendered rank/team/net/total until now — the second acceptance criterion was met by the API but
not actually visible anywhere. The page now adds one column per flight (16, not 48 individual
races — clearer to read, still sums to the same total) showing that team's points for the
flight, "–" where not yet sailed, scrollable horizontally like the other result tables. It also
adds a clearly-marked, italic "≈ projected" total once any race in the matchday has been scored,
so a team that hasn't sailed yet no longer looks like it's provisionally winning outright with
`net = 0` — purely a display computation, never used for `rank` or sorting.

Tests: `api/tests/stories/test_visitor.py::TestMatchdayResult`. The new UI additions
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
- Every cell is centred under its heading. The grid is read by scanning a column for one's
  own abbreviation; left-aligned tokens in columns far wider than they are made that a
  ragged line to follow.
- A club is named by its abbreviation, carries its full name as a tooltip, and links to its
  page — the same treatment the standings tables give it. The abbreviation is what keeps the
  column narrow enough for six boats to fit side by side, and "which club is BYC (BE)?" was a
  question this table previously refused to answer.
- **The list is downloadable as a PDF** — the sheet that gets printed, pinned up at the
  clubhouse and handed to crews, who do not read a matchday off a phone at the dock. One page
  carries the whole grid; then one page per club, with that club's races marked and the teams
  it shares a shuttle with — the sheet a crew actually uses.
- Rendering is done by the **Java tool** (`reference/PairingList`), which owns the print
  layout, via a new entry point `PdfExport`: schedule configuration and pairing list in, one
  PDF out. `Optimizer` printed PDFs only as a by-product of a draw, and `ReuseSchedule` writes
  a whole event directory. A second layout in Python would be a second thing to keep in step
  with the first, and the printed list has looked like this for years.
- Our boats carry **any** color (Story VA-6 offers a color picker), and the color is handed
  over exactly as it is stored. The tool reads both a name it knows and the `#rrggbb` a
  picker produces; anything else it prints in the default color with a warning, because a
  sheet handed out on the morning of an event must not fail over a color name. That used to
  be ~35 lines of translation here, inventing `additional_colors` entries — **the knowledge
  belongs in the tool**, where a plain command-line run gets it too.
- The rendering is **cached by its own content**: the same list, boats and title yield the
  same file. Nothing has to be invalidated when a draw is replaced — a different draw is a
  different key. Without it every visitor starts a JVM.
- **A crew can print its own sheet alone** (`?team=`): the same page the full file holds for
  that club — its races marked, its shuttle partners named — and nothing else. Finding one's
  page among eighteen is what a crew would otherwise do at the dock, in the wind, on paper.
  A club picker sits next to the download; "all clubs" stays the default, because the notice
  board wants the whole thing. The file is named after the club, so eighteen downloads in one
  folder stay apart.
- **The teams printed are the ones that were drawn**, never the event's current entry list.
  The two can differ — a club entered after the draw has no seat in it — and naming a club
  the draw does not know would shift every index along it, putting whole flights on the wrong
  boat. This was a real 503 before it was a rule.
- **Print settings belong to the organizer** (`Event.print_settings`): font size, landscape,
  and whether the per-team pages are included. The organizer knows the venue, the printer and
  the paper; nobody else does. `factor_flight_race_width` and the per-team pages are unanimous
  across all 43 archived events, so they are not offered as choices.
- **An unset font size is not sent at all** — the tool picks it from the number of rows
  (`flights × races`): up to 42 rows 10pt, up to 56 8pt, up to 64 7pt, beyond that 6pt, a
  table read off those same 43 events, every one a sheet that was printed and sailed by. A
  league matchday still prints at 8pt, exactly as it always has. This was decided here once,
  which meant the tool's own default stayed a flat 10pt that does not fit 48 rows on a page:
  the site got a good sheet and everyone else got a bad one. It lives in
  `DisplayConfig.fontsize` now.
- A stored setting is **read back defensively**: anything unexpected in the column falls back
  to letting the tool decide. A sheet that will not print is worse than one printed at the
  wrong size.
- **The download appears only where the server can print.** The renderer is a separate
  program, and an installation may not carry it — the free test image had no JRE at all
  until one was added, so the button sat there answering 503. The pairing response says
  `pdf_available`, and the page leaves the picker and the link out when it is false: an
  offer that cannot be honoured is worse than no offer. The deployment now builds the tool
  from a pinned commit into its image (`api/Dockerfile`, `docs/deploy.md`), so the answer
  there is yes.

Endpoints: `GET /api/events/{id}/pairing` (JSON),
`GET /api/events/{id}/pairing.pdf[?team={team_id}]`.
The organizer sets the print settings through `POST`/`PATCH /api/admin/events/{id}`
(Story VA-6).

Tests: `api/tests/stories/test_visitor.py::TestPairingList`,
`api/tests/unit/test_pairing_pdf.py`,
`api/tests/stories/test_create_event.py::TestCreateEvent::test_the_organizer_decides_how_the_list_prints`,
`e2e/visitor.spec.ts::B-3: as a sailor I see when I am on which boat`

### B-12 ● See who sails for each team at a matchday
As a **visitor** I want to **see who sails for each team at one matchday**,
so that I **know which crew is on the water when I read a result**.

The lineup already exists — a club manager names it (Story V-2, `EventCrew`) and the club
page shows it from that one club's side (Story B-7). What was missing is the matchday's own
side of the same fact: standing at the notice board or watching from the shore, the question
is not "who does NRV field this season" but "who is sailing here today", across every team
at once. Answering it meant opening eighteen club pages.

Acceptance criteria:
- A third tab on the matchday page, beside the daily standings and the pairing list: one
  entry per team **entered in this event** (`Team.event_id` set, accepted), with the people
  lined up for it, helm first — the order a crew is announced, the same
  `MemberOut`/`_ROLE_ORDER` the club page and the squad already use.
- **A team with no lineup yet is listed with an empty crew, not omitted.** "Not named yet" is
  the answer to the question; a missing row reads as "this team is not sailing", which is
  false. The same reasoning as B-7's "if the lineup is not yet set, the page says so".
- **No login.** Participation is public — the pairing list, the results and the standings
  carry these names anyway, so putting the lineup behind a session would be theatre. The
  private thing is club *membership* (Story V-10), which this is not.
- Each name links to its sailor page; once Story S-4 exists, a sailor who has switched their
  profile off appears here as plain text under the same name, never hidden and never omitted.
- **No contact details**, exactly as in the squad: `MemberOut` carries id, name and role and
  nothing else.
- A draft matchday answers 404 here as it does everywhere public (Story VA-8).

Deliberately a **new public endpoint** rather than widening `EventDetail`: the standings are
what the matchday page opens with, and every visitor would then pay for a second table join
they mostly do not look at. It also keeps the tab honest — an unopened tab in `TabbedView`
issues no query at all.

Endpoints: `GET /api/events/{id}/crew`

Tests: `api/tests/stories/test_visitor.py::TestMatchdayCrew`. The tab itself
(`web/src/pages/Matchday.tsx`) has no automated test yet — same state as B-2's flight
columns; Playwright coverage for this page is a separate, not-yet-started task.

### B-5 ◐ Follow live updates
As a **spectator** I want to **see current results on the page**,
so that I **can follow along while racing**.

Three views that must be current simultaneously:

1. **Running race** — which race is running (WL-3 is what sets `started_at`), who is on
   which boat, and once results arrive, the finish.
2. **Live daily standings** — the standings of the running matchday, updated with each
   recorded race.
3. **Live season standings** — the league table including the running matchday.

Acceptance criteria:
- After the race committee enters a result, starts or recalls a race (WL-3), or changes the
  event's state (VA-8, VA-10 — **all six** transitions, publish and unpublish included,
  because they change who may see the event), every open page showing that event or its
  series is current within seconds, without anyone reloading.
- The page never starts empty: the last known standing is there immediately, updates come
  after.
- If the connection drops, the page says so and continues showing the last standing, rather
  than silently presenting stale data as current. This is a **badge**, not an empty page —
  the table stays on screen while the connection is re-established.
- After repeated failed reconnects the page falls back to **polling** every ~20 s and says
  so; a proxy that buffers streams must degrade the experience, never break it.
- If there is no matchday now, `/live` leads to the next date instead of showing an empty
  view (`GET /api/live/now` answers with the running event, else the next one).
- A draft event has no live stream: the stream answers 404 by the same predicate the public
  router uses everywhere (`Event.published` **and** the series not a draft), never a
  restated copy of it.

How it works (decisions 1–4 in `docs/PLAN_LIVE_IMPLEMENTATION.md` §3; the earlier text here
said "WebSocket with SSE as fallback" and is corrected):

- **Server-Sent Events, not WebSocket.** Traffic is one-directional, `EventSource`
  reconnects by itself, rides the plain HTTP path through every proxy, and needs no bearer
  token — which it *cannot* send, and live spectator data is public anyway (B-6). The
  fallback is polling, not a second transport.
- **The stream carries a version token, not the payload.** `change {topic, version}` makes
  the browser invalidate the TanStack Query keys it was given and refetch through the
  generated client. Shipping standings down the stream would be a second serialization of
  the same table that can disagree with the first and bypasses every error, i18n and cache
  path the pages already have. Positions (L-1) are the one exception: six boats at 1 Hz is
  where a refetch per tick would be absurd, so they travel inline.
- **Publish after commit, never inside the transaction.** A subscriber that refetches while
  the writer's transaction is still open reads the *old* standings and stays stale until the
  next race. This is the one trap in the feature.
- **Fan-out in-process** (`api/app/live.py`), the same stated cost as `app/jobs.py`: one
  uvicorn process. Bounded queues, a slow subscriber loses the oldest frames rather than
  stalling the writer; a heartbeat comment every ~15 s keeps proxies from closing an idle
  stream. Never one poller per visitor against the data source.
- **Live is an event.** The only topic is `event:{id}`: a series is never live, it has an
  event that is, and a result changes the series table *because* it changes that event.
  The series page therefore listens on its running event — or the next planned one, so it
  hears the start — and refetches its own table.

What's done: the transport. `GET /api/live?topic=event:{id}` streams `change` frames
(`api/app/live.py`, `routers/public.py`); a result, the draw and all six event transitions
publish after their commit; `web/src/api/useLive.ts` opens the stream, invalidates the
page's queries on each frame, and falls back to polling; `LiveBadge` shows the state on the
matchday and the series page; `/live` redirects via `GET /api/live/now`. Still open: the
"running race" view itself (it needs WL-3's `started_at`), and the production check that
the static site's `/api/*` rewrite does not buffer the stream.

Tests: `api/tests/unit/test_live_hub.py`,
`api/tests/stories/test_live_updates.py`,
`e2e/live.spec.ts::B-5: as a spectator I follow live updates`

### B-4 ◐ Find clubs and dates
As a **visitor** I want to **find the participating clubs and dates**.

Open: club profile with squad and past results.

Tests: `api/tests/stories/test_visitor.py::TestClubs`

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

Tests: `api/tests/stories/test_club_page.py::TestClubPage`

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
- What counts as "mine" is **active membership** (`ClubMember` with an accepted status), not
  `User.club_id`. That field means "the club this account represents" and is a different,
  narrower idea; a pending membership request does not put a club in this list either.
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

### B-11 ○ Club page in tabs
As a **visitor** I want the club page **split into Info, Team and Competition**,
so that I **find what I came for instead of scrolling past everything else**.

Story B-7 built this page as one column: crest and description, then the teams, then each
team's squad, then each team's matchdays. That is everything a club has, in one scroll, and
on a phone the competition data — the part that changes weekly — sits furthest from the top.

Acceptance criteria:
- Three tabs, in this order: **Info**, **Team**, **Competition**.
  - **Info** — crest, name, location, website, description. The club as an organisation.
  - **Team** — two lists that must not be conflated, because they are visible to
    different people (see the visibility rule below): the **squads** per series team —
    the ten registered sailors, helm first, each linking to their sailor page (Story
    B-8) — and, for a member, the club's **member roster** (Story V-10).
  - **Competition** — the **series** the club is enrolled in and the **events** it enters,
    including standalone events it hosts. This is the tab that answers "when do they sail
    next" and "how did they do", so it carries the club's placing per event where one
    exists.
- The tab lives in the **URL** (`/clubs/:id/team`, or a query parameter — the existing
  matchday tabs in `web/src/pages/Matchday.tsx` are the pattern to follow), so a tab can be
  linked and survives a reload. `/clubs/:id` opens Info.
- **Everyone sees all three tabs** without signing in — but the Team tab's two lists differ:
  **participation is public, affiliation is not.** Whoever a club registers for a series or
  enters into an event is publicly named, because they appear on every pairing list, result
  and standings row anyway; simply *belonging* to the club is shown only to the club's own
  active members (and `admin`/`editor` staff), exactly as Story V-10 already enforces on
  `GET /api/clubs/{id}/members`.
  - So a guest sees the squads and, where the roster would be, nothing at all — not a
    locked box and not a sign-in prompt. The tab never advertises what it is withholding.
  - Consequence worth naming: a member who is in no squad is **not** publicly listed
    anywhere on this page, which is the point of the split.
  - Still no contact details and no birth dates for anyone, member or not, the same rule
    as B-7 — the roster adds display name and organizer status, nothing more.
- A tab with nothing in it says so plainly rather than rendering an empty table — a club
  with no series enrollment keeps a working page (B-7 already requires this).

Tests: none yet

### B-8 ● View sailor page
As a **visitor** I want to **see who someone registers for and where they sail**.

Two levels that must not be confused:

- **Registration for a series** — a club's squad for that series (`TeamMembership`, ten
  people), which is a `Team` row with no `event_id`.
- **Lineup for a matchday** — who actually sails one event (`EventCrew`, four people).

Someone in the squad does not necessarily sail every matchday. The page shows both
separately.

There is no "season" on this page, and the wording must not invent one. The site has no
season field — a `Series` carries its own year in its name, and a sailor can be registered
for several series at once (1. Liga and DSL-Pokal, say). "Registrations for the season"
named a thing that does not exist and implied a single one; the heading is **Series
registrations**.

Acceptance criteria:
- Name, the club and series of each registration with role, the matchdays with role.
- A substitute is registered but not placed anywhere — the page says so.
- No contact details, no birth year.
- Accessible without login — **unless the sailor has switched their profile off**
  (Story S-4), in which case this page is theirs and their club's, and the rest of the
  site shows their name without a link to it.

Tests: `api/tests/stories/test_club_page.py::TestSailorPage`

### B-9 ◐ Find legal notice and privacy policy
As a **visitor** I want to **reach the legal notice and the privacy policy from every page**,
so that I **can see who runs this site and what happens to my data**.

Acceptance criteria:
- **The account menu links to both, on every page, without login** (Story A-12). They sat
  in a footer until that menu existed; a footer that carried two links and one line of
  copy was a strip of chrome on every page for the sake of something used twice a year,
  and the menu is on every page too. What § 5 DDG asks for is reachability, not a
  particular corner of the screen.
- Routes `/legal-notice` and `/privacy`. Deliberately **no** German aliases: every route
  on this site is English, and German is a language the site is translated into, never a
  second set of identifiers. The page titles and all their text do read German through the
  language switcher, which is what a German visitor actually needs.
- Both pages read fully in German and English through the language switcher (`legal`
  namespace); no key exists in one language only.
- The legal notice carries the § 5 DDG provider information and the person responsible
  for editorial content under § 18 Abs. 2 MStV. It names **no** EU online dispute
  resolution platform — that platform was shut down in July 2025.
- The privacy policy follows Art. 13 DSGVO and describes what this application actually
  stores: accounts without passwords, OIDC identities, sailor profiles with birth dates
  and photos including the minors rule, waivers, club membership. No cookie-consent
  section, because the app sets no cookies and runs no analytics.
- Values nobody has yet — register court, association register number — appear as visibly
  marked pending values, never invented. Points still undecided — retention periods, the
  deletion concept for position data — appear as marked open questions, and the privacy
  page carries a draft banner until it has been reviewed.
- Because a club can run **its own** Event here, the privacy page states as its most
  prominent open question that it is undetermined whether the association is sole
  controller (Art. 4(7) DSGVO), processor for that club (Art. 28) or joint controller
  (Art. 26) — each answer requires different agreements, and the draft picks none.

Frontend: `web/src/pages/LegalNotice.tsx`, `web/src/pages/Privacy.tsx`,
`web/src/components/LegalText.tsx`

Tests: none yet.

Open: The legal review by the association's board, and the placeholder values, are still
missing — see the open questions rendered on the pages themselves.

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

Tests: `api/tests/stories/test_login_and_roles.py::TestSigningIn`

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

Tests: `api/tests/stories/test_login_and_roles.py::TestRoles`,
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

Tests: `api/tests/stories/test_login_and_roles.py::TestAssigningAClub`

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

Tests: `api/tests/stories/test_registration.py::TestRegistering`

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

Tests: `api/tests/stories/test_registration.py::TestRequestingClubMembership`,
`api/tests/stories/test_club_membership.py::TestPersonApplies`

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
- Output as printable PDF that can be distributed to teams — done, as the download on the
  public pairing list ([B-3](#b-3--view-pairing-list)); the organizer needs no separate one.

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
- **How the pairing list prints** is part of the setup too, and the panel offers it next to
  the draw: font size, landscape, per-team pages (`print_settings`). Empty means the sheet
  is printed the way its configuration implies — see [B-3](#b-3--view-pairing-list), which
  owns the reasoning.

Endpoints: `POST /api/admin/events`

Tests: `api/tests/stories/test_create_event.py::TestCreateEvent`

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
`api/tests/stories/test_create_event.py::TestPairingFromCatalog`

### VA-8 ● Save a draft, publish it, start it
As an **event organizer** I want to **save an event that isn't finished yet, publish it when
it is worth showing, and start it when it is valid**, so that I **can work in the order the
season actually happens — and so that nothing moves under a race that is already sailing**.

Acceptance criteria:
- **Saving never depends on validity.** Title alone is enough; no date, no host, no boats, the
  wrong number of clubs — all savable. That is the normal early state, not an error.
- **Publication is a separate flag, not a status.** `Event.published` and `Series.published`
  decide *who can see it*; `Event.status` (`planned` → `live` → `final`, or `cancelled`)
  says where it stands sportingly. The two are orthogonal: a published event can be
  `planned`, and a started one can stay unpublished.
- **Publishing locks nothing.** A published event stays fully editable, and it does not have
  to be complete — the calendar entry is often what makes people ask about the missing
  pieces. Unpublishing takes it back to a draft; results and pairing list are untouched.
- **A draft does not exist publicly.** Every public endpoint (series list and standings
  table, event list and detail, pairing list, club and sailor pages, the club list and the
  event-logo fallback) shows published data only, and answers **404** rather than 403 — a
  draft's existence is itself not public. A published event of an *unpublished* series stays
  hidden, or one matchday would give the draft series away. `/api/admin/…` shows everything.
- **Validity is computed, never stored**, and it answers with a **list of reasons**, not a
  flag: the organizer has to be told what is missing. Each reason is a stable code plus the
  numbers involved (`registered`/`configured`, `teams`/`boats`/`flights`/`available`, …),
  translated by the client — never an English sentence from the server. The rules:
  registered teams ≠ `team_count`, boats set up ≠ `boat_count`, no catalog entry for
  `team_count`/`boat_count`/`flight_count`, and no date.
- **Validity gates the draw and the start**, and reports the same reasons in the same shape.
  A single cause keeps its own code and status, so `pairing-team-count-mismatch` (409) and
  `pairing-catalog-missing` (404) read exactly as before; several causes arrive together as
  `event-not-ready` (409) carrying `reasons`. The catalog reason is exempt where it makes no
  sense: the optimizer job, an imported draw, and the start of an event whose list already
  exists.
- **Starting is a decision, not a date passing.** `POST …/start` requires readiness and a
  pairing list (`event-without-pairing-list`) and moves the event to `live`. A matchday
  postponed by fog must not start itself. Calling it twice is not an error.
- **After the first race, the configuration freezes.** The trigger is precise and does not
  depend on `status`: any race of the event that has left `scheduled` (running, finished,
  abandoned) **or** any result recorded. Frozen are the dimensions (`team_count`,
  `boat_count`, `flight_count`), the series and matchday, the entered clubs, the boats and
  the pairing list — `event-configuration-frozen` (409), carrying `races_started` and
  `results_recorded`. A redraw *before* the first start still works, which is the point of
  drawing twice while the fleet is at the dock.
- **Results are never frozen.** Entering, correcting and re-correcting results is the whole
  purpose of the race-committee screens, and a protest decision must stay possible months
  later (see [WL-2](#wl-2--enter-and-edit-results-easily) and "Points are derived, not
  entered" in `docs/concepts.md`). Title, dates, venue, host, logo, status and publication
  also stay editable while racing: a typo has to be fixable on a race day too.

- **Drafts are listed where they are finished.** `GET /api/admin/events` lists every event,
  drafts included, ordered dateless-first then newest-first. The public `GET /api/events`
  shows published events only — the right list for a calendar and exactly the wrong one for
  the screen that publishes, where it would hide the single event being worked on.

Endpoints: `GET /api/admin/events`, `GET /api/admin/events/{id}/readiness`,
`POST /api/admin/events/{id}/publish`, `POST /api/admin/events/{id}/unpublish`,
`POST /api/admin/events/{id}/start`, `POST /api/admin/series/{id}/publish`,
`POST /api/admin/series/{id}/unpublish`; `published` also on `POST /api/admin/events`,
`PATCH /api/admin/events/{id}`, `POST /api/admin/series`, `PATCH /api/admin/series/{id}`.
Computed in `api/app/services/event_readiness.py`. The admin screen is
`web/src/pages/AdminEvents.tsx` — a create form that gates almost nothing, and a manage
panel per event carrying the readiness reasons, the date, the entered clubs, the draw,
publication and the start.

Tests: `api/tests/stories/test_event_lifecycle.py::TestSavingAnIncompleteEvent`,
`::TestPublication`, `::TestStarting`, `::TestFreezeAfterTheFirstRace`,
`api/tests/stories/test_complete_lifecycle.py::TestTheAdminEventList`

---

### VA-9 ● Run one event from end to end

As the **association** I want **one test that walks the whole way — clubs, series, event,
boats, clubs entered, draw, start, all races sailed, standings, freeze, protest** — so that
**the steps are proven to fit together in the order they actually happen**.

Acceptance criteria:
- Every individual step is already covered by its own story test. What this adds is the
  **sequence**: each step's output really is the next step's input, through the HTTP API
  only, with nothing reached around into the database.
- It runs the catalog's **smallest** configuration (12 clubs, 6 boats, 8 flights = 16
  races), not the league's 48 — small enough to sail to the end in a test, large enough to
  be a real pairing list rather than a hand-made fixture.
- Deliberately **one long test**, not several: a step that only makes sense after the
  previous one has happened cannot be a test that runs on its own.
- It asserts the things that are wrong only *in sequence*: that a draw refuses while the
  clubs are still being added, that an event saves with no date because the date is agreed
  later, that a series' registrations gate who may enter its events, that the whole fleet's
  points add up to what 16 races hand out, and that a protest decision still lands after
  the configuration has frozen.

Tests: `api/tests/stories/test_complete_lifecycle.py::TestTheCompleteLifecycle`

### VA-10 ● Close an event, or call it off

As an **event organizer** I want to **declare that racing is over, or that it never
happened**, so that **the calendar, the series table and everyone reading them stop treating
a finished day as if it were still running**.

`EventStatus` has carried `final` and `cancelled` from the beginning, and
`app/services/standings.py` already scores `live` and `final` alike — but nothing ever set
either. The only transition that existed was `start` (`planned` → `live`), so every event
that had ever begun stayed "live" forever, including seasons that ended months ago.

Acceptance criteria:
- **Finishing** (`POST …/finish`) moves a **live** event to `final`. It is a declaration by
  the people on site, never a consequence of a date passing or of all races being sailed —
  a matchday that loses its last three flights to dying wind is still over when the race
  committee says it is.
- **Finishing does not require complete results**, and deliberately so: requiring all 48
  races would disable the button exactly on the days it is needed. A day where *nothing*
  was sailed is a cancellation, not a finish.
- **Finishing freezes nothing.** The configuration was already frozen by the first race
  (VA-8), and results stay editable forever — a protest heard weeks later is the entire
  point of the race-committee screens, and it must still land on a `final` event.
- **Cancelling** (`POST …/cancel`) is available from `planned` **and** from `live`: a day
  can be called off before anyone leaves the dock, or abandoned halfway through. It
  **deletes nothing** — pairing list and any results recorded stay exactly as they are, so
  a cancellation that turns out to be premature costs no data.
- **A cancelled event scores nothing, and costs nobody anything.** It drops out of
  `scored_events`, so the "who misses an event gets participants + 1" rule does **not**
  fire for it — being at a regatta that was called off must never be worse than staying
  home.
- **Both are reversible** (`POST …/reopen`), because both are human judgements made in a
  hurry: `final` → `live`, `cancelled` → `planned`. Nothing else about the event changes.
- Every transition is **idempotent** — finishing a `final` event answers 200, the same way
  starting a `live` one already does. A second tap on a button in a rocking boat is not an
  error.
- Refusals are typed and say which state the event is actually in: finishing something that
  never started is `event-not-started`, and reopening something that was never closed is
  `event-not-closed`.
- **Publication stays orthogonal.** Finishing does not publish, cancelling does not
  withdraw — `published` remains the only thing that decides who can see the event
  (VA-8).
- Permissions are the same as for starting: `admin`, `editor`, `race_officer`.

In the interface, the three transitions live in their own block at the bottom of the manage
panel — after publication and the start, because that is the order an organizer does them
in. The block shows **only the transitions that apply right now**: an open event offers
Finish and Call off, a closed one offers a single Reopen and nothing else. That is
deliberate — a permanently visible, permanently disabled "Reopen" on every planned event
would be four-fifths noise on a screen that has to work at 412 px (Story A-10).

Neither closing asks for confirmation. Both are one tap to undo and neither deletes
anything, so a confirmation dialog would buy nothing and cost a tap on a boat.

Tests: `api/tests/stories/test_event_closing.py`,
`e2e/lifecycle.spec.ts::VA-10: closing an event, and taking it back`

---

## Administration

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
one wide box — the boat-setup table in `AdminEvents.tsx` — widened its column, and because
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

### A-12 ● Navigation beside the page, not above it
As **someone who uses this site on a laptop and on a phone**, I want **the navigation where
that device puts it**, so that **the screen is spent on what I came to read**.

One horizontal bar served both and served neither well. On a laptop it wasted the full
width of a wide screen on six links and left no room to say where you are; the site grew
two more entries (Story V-12's "Our club", the admin area) and the row started competing
for space with the language switcher and the account button. On a phone the same row had
to scroll sideways, which is a navigation nobody discovers.

Acceptance criteria:
- **Wide screens (`lg` and up) put the navigation in a column on the left.** It holds the
  logo, the links, the language switcher and the account button — everything that is about
  the site rather than about the page.
- **The top bar then carries a breadcrumb and nothing else**, small: `Series`, or
  `Series › 1. Segel-Bundesliga 2026`. It answers "where am I" in the place the eye
  already goes, and it is the only thing in the header, so it can stay quiet.
  - The first crumb comes from the route and links to that section. The second is the
    page's own title, which every page already declares through `PageHeader` — so a page
    contributes its crumb by existing, and none of them needed changing.
  - A section's own landing page shows one crumb, not the same word twice.
- **Narrow screens keep a top bar**, in the arrangement a phone user expects: **burger on
  the left, logo in the middle, account on the right**. The burger opens the same links as
  a panel.
  - The panel closes when a link in it is followed, and on `Escape`. A menu that stays open
    over the page it just navigated to reads as a broken link.
  - While it is open it is the only thing the tab key reaches, and the burger says so
    (`aria-expanded`).
- **Neither layout may widen the page** (Story A-10). The sidebar is a fixed column that
  does not shrink and the content column may be narrower than its content; on a phone the
  panel is an overlay, so it adds no width at all.
- **The account button opens a menu**, in both arrangements, holding everything that is
  about the *reader* rather than the page: the language, Profile, Help, and the two legal
  pages. Each of those is used rarely, and as separate items in the frame they
  competed with the navigation for room — Help was a main nav entry beside Series and
  Clubs, which is not what someone comes to the site for.
  - **The language is a flyout submenu**, not a pair of toggle buttons. It opens beside
    the row — to the right, or to the left when there is no room there, decided from the
    row's own rectangle when it opens: the account menu is anchored to the top right of
    the window, so "to the right" is off-screen as often as not. The chosen language stays
    on the row itself, so the menu says what it is without being opened. Two languages fitted an
    EN|DE segmented control; a third would not, and the control read as a widget wedged
    into a list of links rather than as one of its entries. The row says what the language
    currently is and opens to the choices, which is the same shape as everything else in
    the menu and does not change when a language is added. Each language is named **in
    itself** — "English", "Deutsch", never translated: someone looking for their own
    language is looking for the word they would recognise, which is not the word for it in
    a language they cannot read.
  - It opens for a guest as well. The language and the legal pages belong to a visitor as
    much as to anybody; only the avatar changes, from initials to a plain account icon.
  - On a phone it sits **top right**, where a phone's account button belongs, and opens
    downward pinned to that edge.
  - Escape closes it, a click outside closes it, following a link in it closes it —
    the same three rules as the burger panel, which is why both use `useDisclosure`.
  - The legal pages are **only** here. The footer that used to carry them is gone: it was
    a strip of chrome on every page holding two links and one line of copy. § 5 DDG wants
    them reachable from every page, and this menu is on every page — so the requirement is
    met by the menu, which is why the footer could go at all.
- **No hairlines, and no footer.** The frame is white and the page is a tinted panel
  inside it, so the regions are told apart by colour rather than by 1px borders — and the
  panel's **top-left corner is rounded**, at the point where the navigation, the
  breadcrumb and the page meet, so the frame reads as wrapping around the page rather
  than being ruled off from it. On a phone there is no sidebar, so both top corners are
  rounded.
- **The page states its name once, and that place is its `<h1>`.** The breadcrumb's last
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
- The navigation entries themselves do not change: `admin` and `Our club` still appear only
  for the roles that can use them, because a link that ends in a 403 is worse than no link.

Tests: `e2e/visitor.spec.ts::A-12: the navigation moves with the viewport`


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

Tests: `api/tests/stories/test_master_data.py::TestCreatingAMatchday`

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

Tests: `api/tests/stories/test_series_assignment.py`

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

Tests: `api/tests/stories/test_series_assignment.py::TestSeriesNaming`

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

Tests: `api/tests/stories/test_scoring_storage.py::TestSeriesStanding`

### B-6 ● Read as guest without login
As a **visitor without an account** I want to **see public pages**,
so that I **can follow results without signing in**.

Acceptance criteria:
- Tables, dates, matchdays, clubs, and pairing lists are accessible without login.
- An **expired or invalid** token does not make the public page unusable — the caller is then
  treated as a guest (`app/auth.py::optional_user`).
- Protected areas respond with 401 instead of partial data.

Tests: `api/tests/stories/test_series_assignment.py::TestGuestAccess`

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

Tests: `api/tests/stories/test_create_series.py`

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

Tests: `api/tests/stories/test_series_assignment.py::TestClubCreationAndAssignment`

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

Tests: `api/tests/stories/test_club_membership.py::TestOrganizerRole`

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

Tests: `api/tests/stories/test_sailors_and_squads.py::TestCreatingSailors`

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

Tests: `api/tests/stories/test_participation.py::TestApplying`

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

Tests: `api/tests/stories/test_participation.py::TestDecidingOnApplications`

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

Tests: `api/tests/stories/test_club_membership.py::TestPersonApplies`

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

Tests: `api/tests/stories/test_club_membership.py::TestClubInvites`,
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

Tests: `api/tests/stories/test_club_membership.py::TestMemberRoster`

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
- **Ten is a target the screen shows, never a rule it enforces.** "7 of 10 registered" with
  the usual size coming from the series, and nothing is blocked at eleven or at three. The
  same goes for having exactly one helm: the screen says when there is none or more than
  one, and saves anyway. Illness and late registration have to get through, which is why
  this is guidance and not validation — and saying so on screen is what stops it from
  looking like an oversight.
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

Open: **Is it always exactly ten, or is ten a ceiling?** The number is deliberately not enforced
— illness and late registration would not get through otherwise. Also open: until when the
squad can be changed (see "Deadlines remain out for now").

Endpoints: `GET /api/admin/teams/{team_id}/members`,
`PUT /api/admin/teams/{team_id}/members`

Tests: `api/tests/stories/test_sailors_and_squads.py::TestRegisteringASquad`,
`api/tests/stories/test_sailors_and_squads.py::TestSquadRefusalsAreTyped`

### V-12 ● Reach our own squad without the admin screen
As a **club manager** I want **my club's squad to be somewhere I can get to**,
so that **I can register who may sail without asking an administrator to do it for me**.

Story V-1 has said since it was written that "registration may be done by the leadership of
their **own** club", and the endpoint has enforced exactly that from the start. The screen
never did: the only squad panel lives under `/admin`, which refuses anyone who is not
`admin` or `editor`, and it finds a team by first listing every series through
`GET /api/admin/series` — an admin-only route. So a club manager had the permission, the
data and no door. This story is the door.

Acceptance criteria:
- **`/club` is the club manager's screen.** It shows the clubs the signed-in account may
  act for (`GET /api/clubs/mine`, Story B-10), and for each of them that club's series
  registrations. One club is the normal case and opens straight away; several are listed,
  because a person can manage more than one.
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

Tests: `api/tests/stories/test_my_clubs.py`,
`e2e/lifecycle.spec.ts::V-12: a club manager manages their own squad`

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

Tests: `api/tests/stories/test_waiver.py`

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

Tests: `api/tests/stories/test_waiver.py::TestMinors` (check-in list)

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

Tests: `api/tests/stories/test_lineup.py`

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

---

## Race Committee

### WL-1 ○ Run races
As **race committee** I want to **have a simple app with which I run the races**,
so that I **work quickly and accurately on the water**.

The screen itself — which race is next, who is on which boat, start, recall, finish, the
progress through the day — is Story **WL-3**. What stays here is the part WL-3 deliberately
leaves open:

Acceptance criteria:
- It works **without network**: every tap is stored locally and reconciled when the
  connection returns, with the same "later entry wins, the overridden state is logged"
  rule as WL-2. WL-3's `localStorage` mirror of the finish order is *not* this: it survives a
  reload, not a morning without coverage.
- Usable with wet hands on a rocking boat: large areas, no fiddling (WL-3 states the sizes).

Tests: none yet

### WL-3 ◐ Start, recall and finish races from one screen
As **race committee** I want **one full-screen page that shows the current race and lets me
start it, recall it, abandon it or record its finish with a few large taps**,
so that **on the water I handle one race at a time and never hunt through three tables**.

Today `RaceStatus.RUNNING` and `Race.started_at` exist and are **never set**: a race goes
from `scheduled` straight to `finished` when a result is saved, and nothing in the system
knows a race is *underway*. B-5's "which race is running" and everything in L-1…L-3 read
`started_at`/`finished_at`, so this story comes first. Plan: `docs/PLAN_LIVE_IMPLEMENTATION.md`
§7 (decision 14).

Acceptance criteria:
- **A page, not a Matchday tab:** `/events/:id/race-control`, gated to `admin` and
  `race_officer`, linked from the manage screen and the results tab. The results tab stays
  the *correction* screen — a protest heard weeks later belongs there, not here.
- **One race on screen, the current one:** the first race that is neither `finished` nor
  `abandoned` — the rule the results tab already uses to find the open race. Header names
  the race and its flight, a progress bar shows races done over the event's total. Arrows
  reach the previous race (to correct) and the next (to preview), nothing further.
- **Everything is sized by the event** — `Event.boat_count` chips, `ceil(team_count /
  boat_count)` races per flight, `flight_count` flights. A guest club's four-boat event works
  exactly like a league day; no "six" and no "48" in the code.
- **Scheduled:** the event's boats in their colours, each with the team the pairing list puts
  on it. Buttons **Start** (the gun went now) and **Start sequence** (5-4-1-0 minutes per
  RRS 26, fires Start at 0), and **AP** (see *Signals*).
- **Running:** elapsed clock; one chip per boat as a finish pad — tap in finish order, tap
  again to undo; codes (OCS, DNF, DSQ, RDG …) one tap below. Buttons **X** (individual
  recall), **General recall** (First Substitute, back to `scheduled`), **Abandon → resail**
  (N, the same reset), **Abandon → no resail** (`abandoned`, scores nothing), **Shorten**
  (S), **Finish** — enabled once every boat has a position or a code.
- **Signals are what the committee actually does on the water, so the screen speaks in
  flags.** Two kinds, deliberately kept apart:
  - **Transitions** are signals that change the race's status and are the endpoints above:
    First Substitute is the recall, N is the abandonment (with or without resail), the gun
    is the start. Nothing new.
  - **Displayed signals** stay hoisted for a while and mean something to the boats and to
    the spectators (B-5's running-race view shows them): **AP** (postponed — cancels a
    running start sequence, the race stays `scheduled`; hauling it down means the warning
    signal follows one minute later, which the screen counts), **X** (individual recall,
    with the boats over the line), **S** (shortened course, the finish is at the next mark).
    The one currently displayed is stored on the race (`Race.signal`, nullable) and cleared
    when hauled down — a flag on the mast is state, its hoist is an audit row like every
    other action here. `POST …/races/{race_id}/signal` with `{signal: "AP" | "X" | "S" |
    null}`; AP is allowed only while `scheduled`, X and S only while `running`.
  - **The preparatory flag decides the penalty.** The start sequence asks for it once —
    **P** (default), **I**, **Z**, **U**, **black** — and stores it (`Race.preparatory`).
    Tapping a boat under **X** gives it the code that flag prescribes: `OCS` under P and I
    (the boat may return and start correctly, and the committee then clears the code with
    one tap), `ZFP` under Z, `UFD` under U, `BFD` under black — codes that stay. `UFD` and
    `BFD` are not in `ResultCode` today and are added here, scored like `OCS` (RRS A5.2:
    starters + 1, discardable unless the sailing instructions say otherwise). An OCS mark
    is nothing but a result code recorded early, so the finish pad already knows how to
    show, change and clear it; no second per-boat state is invented.
  - **AP over A**, **N over A** (no more racing today) and **AP over H**, **N over H** (back
    to the harbour) are not race signals but the day's: they map to VA-10's finish or to
    plain postponement, and the screen offers them where the event's own transitions are.
- **Finished:** the result, read-only, then the next race slides in; **Correct** leads to
  that row in the results tab.
- **Races run strictly one at a time.** Starting a race while another is `running` is
  refused with `race-already-running`; recalling or abandoning a race that is not running
  with `race-not-running`; anything while the event is not `live` with `event-not-live`.
  The event's own gate is reused: a `planned` event shows one button, **Start matchday**
  (the existing `POST …/start`, VA-8 readiness applies); `final` or `cancelled` shows the
  state and a link to VA-10's reopen. The page invents no state of its own.
- **One service owns the transitions.** `app/services/race_state.py` implements start,
  recall, abandon (both kinds) and finish — and the result PUT goes through it too. Until
  now `put_race_result` set `finished` with no check at all, and neither the standings
  service nor the scoring reads `Race.status`: a race is scored the moment its entries carry
  codes, whatever its status says. Left as is, this state machine would be advisory — race
  18 finished from the results tab while race 17 runs, an abandoned race still scoring. So:
  the PUT refuses to finish a race while another one is running, and refuses an `abandoned`
  race; **recall and abandon clear the race's entries** (code, position, redress) before
  recomputing, which is what makes "scores nothing" true; a `finished` race stays editable
  forever, which is the protest case.
- **A recalled first race leaves the event frozen.** The configuration freeze (VA-8) counts
  races no longer `scheduled` and recorded codes — both of which a general recall of race 1
  undoes, un-freezing the event with the fleet on the water. Every transition writes an
  `AuditLog` row anyway; the freeze predicate counts those too, so a race that has started
  *once* keeps the event frozen.
- **Start** sets `started_at` and stamps the race with the event's active course if one is
  laid (L-2); **Finish** sets `finished_at`; recall clears `started_at`. Every transition is
  idempotent (a second tap in a rocking boat is not an error) and publishes on the live
  stream (B-5).
- **Wet hands:** chips at least 64 px, no dropdowns on the main path. The finish order is
  mirrored to `localStorage` per race so a reload or a dropped connection does not lose the
  taps — not WL-1's offline sync, but it removes the likeliest way to lose a race.
- The tap-to-finish chips leave `RaceResultRow` for a shared `FinishOrderPad` component, so
  the results tab and this page cannot drift apart.

Endpoints: `POST /api/admin/events/{event_id}/races/{race_id}/start`, `…/recall`,
`…/abandon?resail=`, `…/signal`; finish is the existing `PUT …/result`.

What's done: the state machine (`app/services/race_state.py`) with the guarded PUT, the
cleared entries, the audit-row freeze, `started_at`/`finished_at`, `Race.signal` and
`Race.preparatory`, `UFD`/`BFD`; the page `/events/:id/race-control` with the start
sequence, the signals, the two-tap abandon, the finish pad kept on the device until
"Finish", and the codes below it; `FinishOrderPad`/`useFinishOrder` shared with the results
tab. Still open: `Race.course_id` (there is no `Course` table until L-2), the detected
finish order as a suggestion (L-2), and the day's signals AP/N over A or H, which map to
VA-10 and are reached from the manage screen for now.

Tests: `api/tests/stories/test_race_control.py`,
`api/tests/unit/test_scoring.py::test_non_finishers_score_starters_plus_one`,
`e2e/race-control.spec.ts::WL-3: as race committee I run one race at a time`

### WL-2 ◐ Enter and edit results easily
As **race committee** I want to **enter and correct results easily**,
so that **a mis-entry is not a disaster**.

Acceptance criteria:
- Finish line is recorded by tapping in order, not by typing position numbers.
- Penalty codes (DNF, DSQ, OCS, ZFP, RDG …) are readily accessible.
- Every entry can be undone and changed later.
- **A boat with no result yet is a normal state, not an error.** A race begins with six of
  them and is entered one boat at a time, so "no result recorded" has to be something the
  screen can *send*, not merely something it starts out with. `code: null` for a boat
  clears that boat's result — code, position and redress alike — and undoing a tap uses
  exactly that. Without it, the screen had to report a boat whose position had not been
  typed yet as `FINISHED` with no position, which the endpoint correctly refused: a red
  "Enter a finish position for boat 4" appeared under the race on the way to every
  hand-entered result and cleared itself a keystroke later. The refusal itself stays — it
  still catches a *code* that needs a position arriving without one.
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
dropped. `web/src/pages/Matchday.tsx`'s results-entry tab (`RaceResultRow`) now makes the
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

Tests: `api/tests/stories/test_result_entry.py::TestEnteringResults`

---

## Live and Tracking

The plan behind these four stories — make or buy against SAP Sailing Analytics, the
module layout, the phases and their proofs — is `docs/PLAN_LIVE_IMPLEMENTATION.md`. The
result in one line: results and positions are ours to build (a day's work each on top of
B-5); the analytics that rank boats on the water are a small port of one-design ideas, not a
self-hosted SAP instance; SAP is used **once, offline, as an oracle** to check our
detectors against theirs on a recorded dataset. Decision numbers below refer to §3 of the
plan.

Data comes in three stages, and every story is built against the first: **emulated**
tracks posted through the real ingest endpoint (the emulator knows its own ground truth —
when it rounds, when it finishes — so it is the contract test for every detector), then
SAP's recorded Mövenstein dataset, then our own phones on our own boats.

### L-1 ○ See the boats move
As a **spectator** I want to **see the boats of the running race move on a map**,
so that I **follow the race from the shore, the club house or the sofa**.

Acceptance criteria:
- `/events/:id/live` shows a map with one marker per boat of the event, in the boat's colour
  and carrying the team's name that the pairing list puts on it for the running race, a
  short trail behind each, and a follow mode that keeps the fleet in view.
- Markers move as fixes arrive, over B-5's stream, inline (`positions` frame) — the one
  payload that does not go through a refetch.
- **The tracker belongs to the boat, not the team** (decision 5). One phone per boat of the
  event, `Event.boat_count` of them; who sails boat 3 in race 17 is what `RaceEntry` already
  says. This is the largest simplification against SAP's competitor↔device mapping, and it is
  available only because the pairing list is ours.
- **The committee boat is a tracker too** (decision 6): its phone position *is* the boat end
  of the start and finish lines. Nobody types coordinates on the water.
- Ingest (`POST /api/track/fixes`) takes a device token issued from the race-control screen
  and a batch of fixes; a fix is `(tracker, t, lat, lon, sog, cog)`, unique per tracker and
  time, so a retried batch is idempotent. A wrong or expired token is refused.
- A spectator gets positions for a published event only; a draft event **and a published
  event in a draft series** answer 404 — the public router's predicate, reused (B-5).
- **Where fixes live is decided in this story, not deferred.** The free test instance bakes
  its SQLite file into the image and resets on every sleep and redeploy, so fixes written
  there are gone before a replay (L-3) is watched; SQLite's default journal mode takes an
  exclusive lock per ingest commit and would block the committee's result PUT. So: WAL and a
  busy timeout in `app/db.py`; for a deployment meant to keep a matchday, a persistent disk
  or Postgres plus an export of the day (`GET /api/races/{id}/track`), so a day never lives
  only in a container's filesystem. On the test instance fixes are **ephemeral by design**
  and the page says so.

Tests: none yet

### L-2 ○ Course, mark passings and a live ranking on the water
As a **spectator** I want to **see which leg each boat is on and who is ahead**, and as
**race committee** I want to **lay the course on the map with a few taps**,
so that **the live page tells a story rather than showing six dots**.

Acceptance criteria:
- **One course family first: windward/leeward with a leeward gate** (decision 7). Waypoints
  in order: `START` (line between committee boat and pin, **pin to port of the committee
  boat**), `WINDWARD` (one mark, rounded to port), `GATE` (two marks, either one), repeated
  per lap, `FINISH` (line between committee boat and pin, pin **left or right** — one flag).
  Parameters: `laps`, finish upwind or downwind. Nothing else is modelled until real data
  asks for it.
- The race committee lays the course on the map: the committee boat follows its tracker
  (L-1), the pin and the marks are set by holding a phone next to them or by tapping the
  map. A re-lay creates a new course; races already started keep the one they were started
  with (WL-3 stamps it).
- The live page shows, per boat, the current leg, the gap to the boat ahead, and a rank;
  after a race the detected finish order prefills the race-control pad (WL-3) as a
  suggestion the committee confirms with one tap — the committee's word stays the result.
- **Geometry lives in a local tangent plane** (decision 8): one projection turns lat/lon
  into metres around the course centre and everything downstream is flat 2-D.
- **Distance to go is the projection onto the course axis** (decision 9): for a boat at `p`
  heading for waypoint `w` along unit vector `a`, `to_go = (w − p) · a`. Two boats on
  opposite tacks at the same height rank equal — the "distance to windward" a commentator
  means — and on a W/L course the axis from gate centre to windward mark *is* the wind axis,
  so no wind estimate is needed.
- **Ranking by time to go from a polar** (decision 10): remaining distance per leg divided
  by the polar's best VMG at the wind speed, summed. An upwind and a downwind boat become
  comparable in one number. Ranking depends on the polar's *shape*, not its speeds: scaling
  the polar by 1.2 must change no rank (unit test). The first polar is the ORC J/70 data in
  `api/tests/fixtures/polars/j70.csv`, in SAP's CSV shape so one loader reads their 49er and
  505 files too; the optimum angles and their speeds come from the `beat …`/`jibe …` rows —
  they must, because the beat angles lie below the table's first column.
- **Interfaces only where a second implementation is already known** (decision 11): a
  `Projection`, a `LegDistance` (axis projection, straight line; later wind- or
  polar-based), a `PassingDetector` (sequential course order; later the SAP candidate-graph
  port), a `Ranker` (time to go; leg then distance), a `WindSource` (course axis; manual;
  later estimated from tracks) and a `FixSource` (emulated, recorded, live). Pure functions
  over immutable inputs, no session, no ORM, so every one of them runs on a recorded track
  without a server. `RaceAnalysis` plus `default_pipeline()` is the one place concrete
  classes are named. Ingest, the hub and the map get **no** interface: one implementation
  each.
- **Mark passings need no candidate graph on this course family.** A line or gate is
  passed when the track segment crosses it in the leg's direction; the windward mark when
  the distance has a local minimum below about three boat lengths *and* the bearing from
  mark to boat sweeps through a port rounding's arc. A passing counts only if it is the
  **next expected waypoint** — the course order does the disambiguation SAP's Dijkstra does
  for arbitrary courses. If real data breaks this, the port of SAP's `CandidateFinder` /
  `CandidateChooser` (about a thousand lines of Python) is the fallback, not the start.
- **Derived, never stored** (decision 12): leg per boat, passing times, distance and time
  to go, rank. The same rule as points.
- **Contract test for every implementation:** against the emulator's ground truth, passings
  within ±3 s and a rank order that does not change when the boats' start order is permuted.
  A new implementation is admitted when it passes the same suite; `compare.py` runs several
  against one recorded track so an algorithm change is decided on data, not argued.

Tests: none yet

### L-3 ○ Replay a race
As a **spectator** I want to **scrub through a race that is over**,
so that I **can see how the leader got there**.

Acceptance criteria:
- A slider over the stored fixes of a race; the same map, markers and side panel as L-1 and
  L-2, fed from `GET /api/races/{id}/track` instead of the stream. Nothing new on the
  server.
- Scrubbing to a passing time puts the boat at the mark (e2e).
- On the test instance the replay says the day's fixes are ephemeral (L-1).

Tests: none yet

### L-4 ○ The phone on the boat is the tracker
As the **crew of boat 3** I want to **open one page on the phone in the cockpit and forget
about it**,
so that **the boat is on the map all day without any app to install**.

Acceptance criteria:
- `/track/:token` — the token is issued per boat from the race-control screen and shown as
  a QR code; the page requests a wake lock, watches the position, buffers fixes and posts a
  batch every ~5 s to the ingest endpoint (L-1), retrying while there is no coverage.
- It shows the boat's colour and name, the last fix's age, and the buffer size, so a crew
  can tell at a glance it is working.
- **The one open question is answered on the water, not on paper:** whether a browser page
  keeps delivering positions with a locked screen in a pocket. One morning with two phones
  decides whether a web page suffices or the boats need a native shell; L-2's shape may
  change with that result, which is why this story comes before L-3.
- The emulator (`python -m app.tracking.emulate`) is a client of the same endpoint
  (decision 13): it exercises the path real phones use, tacks with the polar's angles and
  speeds, picks a gate side at random, adds ±5 m of GPS noise, and is deterministic by seed.

Tests: none yet

---

## Still to Write

Sensible next areas:

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
