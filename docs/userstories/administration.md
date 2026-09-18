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

This is the opposite direction to [A-3](#a-3--assign-clubs-to-series): there you attach a
club to multiple series, here a series to multiple clubs. Both write the same `Team` rows.

Endpoints: `POST /api/admin/series`, `PATCH /api/admin/series/{id}`,
`PUT /api/admin/series/{id}/clubs`, `GET /api/admin/series`

Tests: `api/tests/stories/test_create_series.py`

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

Screen: the Members tab on `/club` (Story V-12) — an organizer makes a member an
organizer or revokes it; administration uses the same endpoints.
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
two more entries (Story V-12's "My club", the admin area) and the row started competing
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
- The navigation entries themselves do not change: `admin` and `My club` still appear only
  for the roles that can use them, because a link that ends in a 403 is worse than no link.

Tests: `e2e/visitor.spec.ts::A-12: the navigation moves with the viewport`
