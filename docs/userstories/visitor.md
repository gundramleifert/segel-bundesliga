# Visitor and Fans

Part of the [user stories](README.md); the format, the status marks and the
identifier rule are explained there.

Most readers never sign in. Standings, results, pairing lists, club and sailor pages are
public, and the site is read mostly on a phone at the harbour.

## Standings and results

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

## The matchday

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

## Clubs and sailors

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

## The site

### B-6 ● Read as guest without login
As a **visitor without an account** I want to **see public pages**,
so that I **can follow results without signing in**.

Acceptance criteria:
- Tables, dates, matchdays, clubs, and pairing lists are accessible without login.
- An **expired or invalid** token does not make the public page unusable — the caller is then
  treated as a guest (`app/auth.py::optional_user`).
- Protected areas respond with 401 instead of partial data.

Tests: `api/tests/stories/test_series_assignment.py::TestGuestAccess`

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
- Accounts are created by creation, import, or **explicit registration** ([Z-4](sailor.md#z-4--register-yourself)) — not silently when signing in with an unknown address.

Tests: `api/tests/stories/test_login_and_roles.py::TestSigningIn`

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
