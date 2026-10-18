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
- **Since issue #14 a series in a league has its table on the league's standings page**
  (Story B-14), one division under the other — the same table as here, a column per act
  leading to that act's results (`components/StandingsTable.tsx`). A series in no league
  keeps this page at `/series/:id`. For a few hours after the rebuild the league page
  showed each division as a list whose rows opened to their places per act, as the
  prototype did; a list is not a league table, and the table came back.
- The scoring rule is not explained on the page. A "did not sail" cell says so in its own
  tooltip, which is where the question is actually asked; a permanent paragraph restating
  it was read once and skipped thereafter.

Tests: `api/tests/stories/test_visitor.py::TestSeriesTable`,
`e2e/visitor.spec.ts::B-1/B-14: as a fan I see the series standings`

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
- The **points per flight** come from the server (`EventStandingRow.points_by_flight`, keyed
  by flight number, summed from each race's own flight), and the event says how many races
  a flight has (`EventOut.races_per_flight`). The page used to rebuild flights from race
  sequence numbers and an assumed flight length — which breaks the day a flight is
  re-sailed or a race renumbered. Only the projection stays display math in the browser.

`EventStandingRow.points_by_race`/`discarded_races` (`api/app/schemas/public.py`) carried the
per-race breakdown from the start, but the daily standings (now `web/src/pages/league/act/Standings.tsx`) only
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

### B-17 ○ Club crests and a partner mark on the results
As a **fan** I want to **see each club's crest next to its result and know where the data
comes from**, so that **the table is recognisable at a glance and the partners are credited**.

Acceptance criteria:
- **A club crest sits beside the club name in every results table** — the league/series
  `StandingsTable` (Stories B-1, B-14) and the matchday daily standings (`league/act/Standings.tsx`,
  Story B-2). Same emblem the club page already shows (B-7), at a small, fixed row height so
  no row grows and the table still fits a phone (Story A-10).
- **The crest is our own, not hot-linked.** It is `Club.logo_url` / the club crest already in
  our model. SAP and Manage2Sail both expose crest URLs (SAP on the league's S3 bucket,
  `docs/findings.md` §3a) — those are a **source to import a missing crest from once**, with
  reuse cleared, never a URL the public page fetches live.
- **A missing crest never breaks the layout** — a club with no emblem shows a neutral
  placeholder (e.g. its short code), never a broken image.
- **Accessibility:** the crest's alt text is the club name; it adds nothing a screen reader
  must read twice beside the name already in the row.
- **A "powered by SAP Sailing Analytics" mark appears on the results page**, linking to SAP.
  - **The data shown here is our own** computed standings (Domain decisions: points are
    derived here), so SAP's **attribution/branding clause does not yet compel it**
    (`docs/findings.md` §3 "Legal Requirements") — it is a **partner acknowledgment** now,
    and it is already in place for when a table *is* fed from SAP, where the clause *does*
    compel it. The page must not imply the numbers are SAP's while they are ours.
  - The mark is one shared, reusable piece (a component, not copy pasted per page), so the
    day a table becomes SAP-sourced the obligation is met in one place.
- **No new backend and no SAP call** for this story — it is the visuals on data we already
  serve. Pulling results *from* SAP is a separate, larger story (see `docs/findings.md` §3a).

Open question for the league office before build: written clearance to display the club
crests (they are the clubs' marks, held in the league's media bucket) and the exact SAP
attribution lockup/wording required.

Tests: _(none yet — story recorded first; a test and the code follow per CLAUDE.md "From
issue to merge")._

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
`e2e/visitor.spec.ts::B-3: as a sailor I see when I am on which boat`

### B-12 ● See who sails for each team at a matchday
As a **visitor** I want to **see who sails for each team at one matchday**,
so that I **know which crew is on the water when I read a result**.

The lineup already exists — a team manager names it (Story V-2, `EventCrew`) and the club
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
(`web/src/pages/league/act/Crew.tsx`) has no automated test yet — same state as B-2's flight
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
- **The start sequence is on the live page too** (WL-3): while the committee runs one, the
  spectator sees which flags are up, what comes next and the countdown to it — and after a
  general recall, that the First Substitute is up. The committee's screen stores the
  sequence on the race (`Race.start_sequence`, `PUT …/races/{id}/sequence`) whenever it
  changes; the live page derives flags and countdown from it with the very code the
  committee's screen uses (`web/src/lib/startSequence.ts`). Times are the committee
  phone's clock: a spectator's phone that is off by a second shows the countdown off by a
  second. The start clears it.

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

## The leagues

The site's structure is option E of issue #14, recorded in `docs/site-structure.md`:
**chapters on top, depth behind**. These stories are what was built from it.

### B-13 ◐ One row of navigation, the leagues in it
As a **visitor** I want **one row at the top that names the association's competitions**,
so that **I am one tap from the league I follow, whatever page I am on**.

Acceptance criteria:
- Every page has the same row, and only one: the **logo** and ***Association*** (*Verein*,
  both the association's home, `/`), **the leagues** in the order the league office set
  (`League.position`) — *1. Liga · 2. Liga · Junioren · DSL-Pokal* in the seed, the way
  deutsche-segelbundesliga.de names its competitions — and the **account button** at the
  right: *Sign in* for a guest, *My space* when signed in. Topics such as results or
  press are not in it — each is a chapter of the league's page. (Changed 2026-10-16: the
  1. and 2. Liga were one entry, *DSBL*, and the association had only the logo.)
- **The leagues are data** (`GET /api/leagues`), never a list in the code: the row names
  whatever leagues exist. A site with one league shows one.
- On every official page the row lies on the page's picture, **and it keeps naming the
  association and every league**, the current one marked — it no longer turns into a
  league switch. The league's own pages are the sub-menu under it (below); on a matchday
  page its tabs are (Story B-15).
- **At most two rows of navigation, ever.** The second exists only on a matchday page
  (Story B-15).
- **On a phone the entries are a menu**: one button names where you are (*☰ 1. Liga*) and
  opens the association and the leagues as a list; following a link closes it. Five
  entries beside the logo and the account button do not fit a phone's width.
- **A new page opens at its top.** The router keeps the window's scroll position, so a
  footer link opened the next page at its footer, past its picture and title. Back and
  forward keep their place; a matchday's tabs scroll on purpose (Story B-15).
- **Every page has a skip link** to its content, the chapter and depth pages included —
  they draw their own frame, and the link used to live only in the frame they left.
- The fixed dev switches keep clear of the footer, where the legal links are.
- The account button keeps its menu (Story A-12): language, profile, help, legal pages —
  and *Administration* for whoever can use it.
- What is still open (`docs/site-structure.md`) is switched by the **DEV** button
  (not tested in the browser suite, whose build leaves the dev tools out — the setting it
  writes is), bottom left, wherever the role switcher is built in (`DEV_TOOLS`): the
  picture as photo, fade, slide or video, and the glass over it. The choice is remembered
  in this browser. (Until 2026-10-18 it also switched a classic layout, chapters snapping
  into place, and three depth frames A–C; the layout below was chosen and the rest went.)
- **The layout with a sub-menu** (2026-10-18): the public site is built like my space. The
  top row is solid everywhere, and under it a **sub-menu row sticks** — where you are on
  the left (*1. Liga*; on a matchday *1. Liga › Season › Act 2 · Kiel*), the pages beside
  it on the right: the league's pages (*Standings · Season · Notice
  board · Clubs · News · Media · Press · About*), the association's on its own pages, a
  matchday's tabs on a matchday page — as **pills**, like the top row's leagues. Still at
  most two rows: on a matchday page the matchday's tabs *are* the sub-menu, the league's
  pages a step up its crumbs. **The overview has no sub-menu** (changed 2026-10-18; it
  had one, with the chapter on screen marked in it): the chapters are the overview's
  contents and each leads to its page, which has the sub-menu. Both rows have **one
  background everywhere** — the picture through a dark, blurred shade.
- **The picture stands still and only the text scrolls**: a chapter page
  has one picture behind all its chapters (photo, fade, slide or video, as before), a depth
  page **has its own picture behind the whole page** too (changed 2026-10-18 — a white page
  after the chapters read as a break in style): the rows and the title lie on it in white,
  the content in cards that scroll over it, and each page has a different picture.
- **One design over every official page** (2026-10-18): the chapter page's cards are the
  pieces every page is built from — frosted glass on the picture for teasers, lists and
  facts, and also for what is read closely (a full table, an article, a matchday's
  results, pairing list and crews). The media page's videos and photos are the chapter's
  video cards. **The DEV switch tunes the glass** live — card darkness and blur, how far
  the picture is darkened, the strength of secondary text — with a reset to the defaults.
  **No small text lies on a picture bare**: introductions, notes, the season's list, the
  running act, club names and links are cards or glass pills, and the glass really blurs
  what is behind it.
- **One column, one grid** (2026-10-18): one chapter's cards never end where the next
  one's go on. Every block spans its page's column, and tiles and columns share one
  12-column grid, so their edges line up from chapter to chapter (`docs/components.md`).
- **The footer is the last band on the picture** (2026-10-18): the rows' shade, the same column and grid — a card per league (its act now or next, standings,
  season, notice board, press), the association beside the account (sign in or my space,
  the language), and the legal notice and privacy on every page. On a chapter page the
  dots step aside while the footer is on screen. The internal screens keep the light
  footer.
- **The league's name in the sub-menu is its overview** — there is no entry *Overview*
  beside it (it said the same twice).
- **A chapter is as tall as its content** and the page scrolls freely: chapters that
  each filled the screen and clicked into place left half a screen of empty picture
  between two (removed 2026-10-18).
- **No white page while one loads**: a page whose data is still on the way shows the same
  dark frame, its rows in their place — a white one flashed on every change of league.

Tests: `e2e/visitor.spec.ts::B-13: one row of navigation names the leagues`

### B-14 ● A league's page in chapters, each leading to its own page
As a **fan** I want **the league's page to show me what is happening now, and lead me
deeper from there**, so that **the first screen answers the common question and every
other one is a tap away**.

Acceptance criteria:
- `/:league` (`/1-liga`) is one page of chapters over one picture, with dots on
  the right to jump between them: **Standings, Results, News, Media, About, Archive**.
  Each is a preview that ends in a link to its own page. (Changed 2026-10-16, from *Now,
  Standings, Season, Clubs, News, Media, Press, About*.)
- **A chapter's title is its name** — *Standings*, *News* — the same word as its dot.
  The slogans it replaced ("Where everyone stands.") did not say what the chapter is;
  the association's home follows the same rule.
- ***Standings* opens the page**: the top five of the year's table, leading to the full
  standings. ***Results* is there only while a matchday is live** — the act, its venue and
  host, links to its live map, results and notice board; between matchdays the season's
  page holds the calendar. ***About*** carries the league's text, its clubs and the link
  to the press centre. ***Archive*** lists the earlier years, each leading to that year's
  standings; with no earlier year it is left out.
- **The league's page shows its current year**: the newest year of *its* series that is
  not in the future (Story A-4's rule, asked per league — the DSBL publishing next year's
  series must not empty the Junioren-Liga's page). `GET /api/leagues/{slug}` answers with
  the year, the years in the archive, the year's series and their events. Published only.
  **Each series carries its clubs** (its accepted registrations), and the season the clubs
  of all its series once — the *About* chapter, `/:league/clubs` and the association's
  member list read them there instead of fetching every series' full table for its names.
- **The 1. and the 2. Liga are two leagues** (`/1-liga`, `/2-liga`), each with one
  series a year. They sail the same weekends at the same venues, but each has its own
  page, its own standings and its own matchday pages; promotion and relegation are named
  on each table's edge. A league with several series in a year still shows each of them,
  and an **act** is still the events of the year's series sharing a matchday number.
- **The dots on the right are a control of their own size**, fixed on a phone (2026-10-12):
  - only the dots take touch — the chapter names appear over the chapter while a thumb
    slides, and take no room. Reserving their room had made the column an invisible strip
    a third of the screen wide, and a swipe that started there, where a right thumb
    scrolls, jumped chapters instead of scrolling the page;
  - a sliding thumb is followed by its **height**, so drifting off the column sideways no
    longer freezes the slide;
  - a tap scrolls to the chapter and leaves the address and the history alone (it used to
    add `#season` to both, so Back walked the chapters);
  - the marked dot is the chapter crossing the **middle of the screen**. "At least 55%
    visible" could never be true of a chapter taller than about 1.8 screens.
- **The chapter page scrolls from the keyboard.** It is its own scrolling box (so the
  picture behind stands still), and the document behind has nothing to scroll — so the box takes the
  focus when the page opens, and Space, Page Down and the arrows move it.
- The depth pages: `/:league/standings` (each division's full table, a column per act; promotion,
  relegation and requalification marked on the row's edge and named in a legend, where
  the league's rules say so; the archive by year at `/:league/:year/standings`), `/:league/season`
  (every act, expanding to its venue, host and links into its tabs), `/:league/clubs`,
  `/:league/notice-board`, `/:league/news`, `/:league/media`, `/:league/press`,
  `/:league/about`, and `/about` for the association.
- **News, press, media, documents and the about texts are static content for now**,
  behind hooks shaped like the API calls that will replace them
  (`web/src/content/`), so a page does not change when its data becomes dynamic.
- **Placeholder content that could read as official says it is an example**: the season's
  documents and a matchday's notice board (invented jury decisions on a real matchday
  were the problem). A document carries no download mark until there is a file.
- The association's home `/` is a chapter page too: *Now* (every league's current act),
  *Leagues*, *News*, *For clubs*, *About* — titled with those names, except the first,
  whose title is the page's heading: *Deutsche Segel-Liga e.V.* *Now* and *Leagues* are one
  chapter (2026-10-18 — both showed the same four competitions): a card per league with
  the act it is sailing or sails next, its state, its tagline and its introduction.
- **Old addresses of the DSBL** (`/dsbl`, `/dsbl/…`) go to the 1. Liga's same page
  (Story B-16).
- **The chapters are filled** (2026-10-18): *Standings* also lists the year's matchdays with their
  state, each leading to its page; *Results* how many races are sailed; *News* the newest
  three as cards with picture and teaser and three more headlines; *Media* the videos as
  stills; *About* the league's facts. On the association's home: figures, the service for
  clubs as six tiles, the history.
- **Every article has its own page** (`/:league/news/:slug`): the lead, the byline, the
  text, a quote where there is one, and the league's next three articles. An invented
  article says it is an example — it names real clubs.

Tests: `api/tests/stories/test_league_pages.py::TestLeagueSeason`,
`e2e/visitor.spec.ts::B-14: a league's page in chapters`

### B-15 ● The matchday page, its tabs in the URL
As a **fan** I want **one page per act with everything it has**, so that **results,
pairing list and crews of both divisions are where I expect them**.

Acceptance criteria:
- `/:league/:year/act-:n`, for example `/dsbl/2026/act-2`; the tab is the last path segment
  (`…/act-2/results`), so every tab has its own URL. Without a tab the page opens on
  *Results* once racing has begun, and on *Notice board* before that.
- Tabs: **Notice board · Results · Pairing list · Crews · Live · Media**, and for the race
  committee **Enter results**. They sit in the second row, which names the act and sticks
  under the top bar.
- An act with several divisions offers a switch between them inside the tab; each
  division is its own event underneath.
- An event that belongs to no league — a club's own regatta — keeps its page at
  `/events/:id`, in the same frame and with the same tabs.
- **The page follows the stream** (Story B-5): when the race committee starts or finishes
  the event, the live badge and the act's state change without a reload — the league's
  year is refetched with the event.

Tests: `e2e/visitor.spec.ts::B-15: the matchday page`

### B-16 ● Old addresses lead to the new pages
As **someone with a bookmark** I want **yesterday's address to still work**, so that **a
shared link does not end on the home page**.

Acceptance criteria:
- `/series/:id` of a series in a league goes to `/:league/:year/standings`, and
  `/events/:id` of an event in a league to its act page, keeping the tab — an event
  without a matchday to `…/event-<id>`, the address its league's season links to, so it
  has one page and not two. If the leagues cannot be loaded, the event's own page shows
  rather than a spinner that never ends. A series or
  event in no league stays at its own page.
- `/:league/live` goes to the running act's *Live* tab, else the next act's;
  `/:league/results` to the last act sailed.
- **`/dsbl` and everything under it go to the same page of the 1. Liga** (`/dsbl/standings`
  → `/1-liga/standings`, `/dsbl/2026/act-2/live` → `/1-liga/2026/act-2/live`): the DSBL
  was one league until 2026-10-16 (Story B-14), and its addresses were shared.
- Short paths are redirects, never copies.

Tests: `e2e/visitor.spec.ts::B-16: old addresses lead to the new pages`

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
  matchday tabs in `web/src/pages/league/act/` are the pattern to follow), so a tab can be
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

### Z-1 ● Sign in with Google, Microsoft or a one-time code
As a **user** I want to **use an identity provider of my choice** (Google, Microsoft,
or email), so that **the operator does not have to manage identities**.

Acceptance criteria:
- Google and Microsoft via verification of their ID token; email via a one-time code.
- The code is valid for ten minutes, can be used only once, and is locked after five failed
  attempts.
- It is stored only as a hash in the database.
- All paths lead to the **same** account, linked via the verified email address — a
  password ([Z-9](#z-9--sign-in-with-a-password)) is one more path to it.
- The response does not reveal whether an account exists for an address.
- Accounts are created by creation, import, or **explicit registration** ([Z-4](sailor.md#z-4--register-yourself)) — not silently when signing in with an unknown address.

Tests: `api/tests/stories/test_login_and_roles.py::TestSigningIn`

### Z-9 ● Sign in with a password
As a **sailor** I want to **sign in with a password I set myself**, so that **I am not
waiting for a code by email on a pontoon, and need no Google or Microsoft account**.

This reverses an earlier decision ("we store no passwords", 2026-10-05). The one-time
code stays: it is how an address is proven, and it is the reset — "forgot password" means
signing in with a code and setting a new one, so there is no reset-token table.

Acceptance criteria:
- **Only a verified address gets a password** (`User.email_verified`). Setting one never
  creates an account; accounts still come from creation, import or registration.
- **Length is the only rule:** 12 to 128 characters, no "one digit, one symbol". The text
  is Unicode-normalized (NFKC) first, so an umlaut typed on a Mac and on a phone is the
  same password.
- **Argon2id** (`argon2-cffi`). A hash made with older parameters is re-hashed on the
  next successful sign-in.
- **Every wrong combination answers the same:** unknown address, no password set, wrong
  password, a locked or suspended account — one 401 problem, `login-failed`, with the
  same body. An unknown address still verifies against a dummy hash, so timing does not
  tell either.
- **After 5 failures the account locks**, for 1, then 5, then 15 minutes. A wrong current
  password when changing it counts too. A successful sign-in by password or by code
  clears the count.
- **Changing** a password requires the current one; **removing** it leaves the one-time
  code as the way in — which is why removing is never refused as "the last way in": the
  code is always one.
- The site's **admin can clear** someone's password; the person then signs
  in by code and sets a new one.
- Setting, changing, removing, clearing and locking each write an `AuditLog` row. The
  password is never logged or echoed, and the hash never appears in any response — it
  lives in its own table, `PasswordCredential`, which no account serializer reads.
- A password is an `Identity` (`provider = "password"`), so the account page lists it
  beside Google, Microsoft and email.
- `SBL_ALLOW_PASSWORD_LOGIN` (default on) closes the path; `GET /api/auth/providers`
  says whether it is open, and the sign-in card only offers the tab then.

Later, when there is a reason: an **OpenID Connect verifier driven by configuration**
(issuer + client id per entry, `PyJWKClient` already a dependency), so a DSV, a club's
Keycloak or Apple is one setting instead of code; **passkeys** (py_webauthn) as a
`PasskeyCredential` beside `PasswordCredential`; rejecting known-breached passwords
(HIBP range API, never live in tests); per-IP limits if deployment shows the need.
Manage2Sail sign-in: see `docs/findings.md` §4.

Tests: `api/tests/stories/test_password_login.py`

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
  stores: accounts, OIDC identities, password hashes (Z-9), sailor profiles with birth dates
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
