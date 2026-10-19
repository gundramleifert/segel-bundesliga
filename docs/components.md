# The frontend's building blocks

Every screen here is assembled from the same small set of pieces. This file is the list —
read it before writing a page, and add to it rather than beside it.

The reason is not tidiness. Each entry below replaced something that had been written out
by hand three times or more, and in every case the copies had already drifted: two of them
used a different gap, one had lost its empty state, one had lost the rule that keeps the
page from zooming out on a phone. A pattern that has to be remembered is a pattern that
will eventually be remembered wrong.

## Where things live

Everything shared lives in `web/src/components/`. A component never imports from
`web/src/pages/` — that direction is what tells you something is in the wrong file.

| File | Holds |
|---|---|
| `Async.tsx` | `Async` — one request, rendered |
| `Blocks.tsx` | `Loading`, `ErrorMessage`, `Empty`, `PageHeader`, `Badge`, `StatusBadge`, `LiveBadge`, `TableFrame`, `MatchdayCard` |
| `Layouts.tsx` | `Stack`, `CardGrid` |
| `LinkCard.tsx` | `LinkCard` |
| `Tip.tsx` | `Tip` — the tooltip, in place of `title` |
| `Form.tsx` | `Section`, `Field`, `Message` |
| `TransferList.tsx` | `TransferList` — the two-pane "move it across" picker |
| `ClubSelector.tsx` | `ClubSelector` — `TransferList` for clubs |
| `LineupPanel.tsx` | `LineupPanel` — a matchday's crew from the squad, with roles (Story V-2) |
| `Tabs.tsx` | `TabbedView` |
| `Steps.tsx` | `Steps` — where you are in a short, ordered sequence (Story VA-6) |
| `AddButton.tsx` | `AddButton` — the "＋" top-right of every admin list, leading to its `/admin/<area>/new` page |
| `FinishOrderPad.tsx` | `useFinishOrder`, `FinishChip`, `FinishOrderPad` — a race's result as taps (Stories WL-2, WL-3) |
| `SquadPanel.tsx` | registering a squad (Story V-1), used by `/admin` and the club's page in my space (`/me/club/:id`) |
| `Select.tsx` | `Select` — **the** dropdown: a native `<select>` that sets its own colours, sized `field` / `inline` / `row` / `touch`; `oxlint` refuses a bare `<select>` |
| `RoleSelect.tsx` | `RoleSelect` — helm / crew / substitute beside a name on the right pane of `SquadPanel` and `LineupPanel`; their shared draft is `useRosterDraft` (`lib/useRosterDraft.ts`) |
| `SailorName.tsx` | `SailorName` — a sailor's name in a squad or lineup: a link to their page, or plain text when they switched it off (Story S-4). Never hand-write a link to `/sailors/:id` |
| `PersonDocuments.tsx` | `PersonDocuments` — a person's licences on demand, for their organizers, on a person's row (Story S-5); hides itself on `documents-forbidden`. `ExpiredBadge` |
| `FileDropzone.tsx` | `FileDropzone` — a file field you drop a file onto or tap to choose; checks the type on drop, keeps a hidden `<input type="file">` carrying the `testId` for `setInputFiles` |
| `Crest.tsx` | `Crest` — a club's crest or an event's logo, `sm` / `md` / `lg`, the abbreviation standing in when there is none (Story V-3). Never a bare `<img src={…logo_url}>` |
| `MediaPicker.tsx` | `MediaPicker` — the picture library where a picture is wanted (the editor, a post's own picture): pick, upload, fetch from a web address, drop; hands the library entry to `onPick` (Story R-2) |
| `MediaContextSelect.tsx` | `MediaContextSelect` — an event or a series (or none) for a picture, series with their events under them |
| `ConfirmButton.tsx` | `ConfirmButton` — an action that cannot be taken back asks once more, in place: prompt, the real button, a way out |
| `CrestEditor.tsx` | `CrestEditor` — a club's crest, edited from the crest itself (Story V-3); the admin club list and the club's page in my space |
| `ClaimParts.tsx` | `ClaimStatusBadge`, `ClaimSummary`, `ClaimItems`, `ClaimReceipts` — one expense claim as both the claimant and the decider see it, in my space (`/me/…`) (Stories F-2 to F-6) |
| `HelpLink.tsx` | `HelpLink` — the "?" beside a heading that opens the help on that one thing, by handbook anchor (Story B-18) |
| `Layout.tsx`, `Breadcrumb.tsx` | the frame around every page (Story A-12) |

## The pieces

### `Async` — one request, rendered

```tsx
const clubs = useAsync(useListClubs());

<Async state={clubs} testId="clubs" loadingText={t("loading")} empty={t("empty")}>
  {(data) => <CardGrid>…</CardGrid>}
</Async>
```

Loading, error, empty, content. `children` is a *function*, so it runs only when there is
data and `data` inside it needs no null check. The testids follow from `testId`:
`clubs-loading`, `clubs-error`, `clubs-empty` — which was already the convention in twelve
hand-written copies, so nothing about the tests changed when they were replaced.

Omit `empty` when a page draws its own empty state inside a frame it wants to keep (a
search box above an empty result list, for instance).

### `Stack` — things down the page

```tsx
<Stack gap={6}>…</Stack>
```

`grid-cols-[minmax(0,1fr)]`, never a bare `grid`. This is Story A-10 in a component: a
grid's `auto` column is sized by its items' *min-content* width and its items stretch to
the column, so one wide table anywhere inside pushes the whole stack past the viewport —
and mobile Chromium answers that by zooming the entire page out. 412 px of viewport
rendered as 754, every tap landing next to what it aimed at, and nothing looking broken.

`Stack` means **always one column**. A responsive grid that starts at one column and
becomes two (`sm:grid-cols-2`) is a different thing and keeps its class string.

### `CardGrid` — a list of cards

```tsx
<CardGrid columns={3} testId="clubs-list">
  {clubs.map((club) => <li key={club.id}><LinkCard … /></li>)}
</CardGrid>
```

One column on a phone, two from `sm`, three from `lg` when asked. A `<ul>` by default,
because a list of cards is a list.

### `LinkCard` — a card that is a link

```tsx
<LinkCard to={`/clubs/${club.id}`} testId={`club-card-${club.id}`}
          title={club.name} description={club.city} lead={<Crest />} aside={<StatusBadge …/>}>
  optional body
</LinkCard>
```

`lead` is the crest or logo on the left, `aside` the badge on the right. The title
truncates rather than pushing the badge out of the card.

### `Section`, `Field`, `Message` — forms

`Section` is a titled card with a hint. `Field` is a label bound to its control by `htmlFor`
— deliberately not by wrapping it, because wrapping a `<input type="date">` makes every
click re-toggle the native picker. `Message` renders a save's success or failure.

Plain `<input>` elements rather than HeroUI inputs: these forms are a tool, and a plain
input behaves more predictably inside one than a component with its own state.

### `Tip` — a tooltip

```tsx
<Tip text={club.name}>
  <Link to={`/clubs/${club.id}`}>{club.short_name}</Link>
</Tip>
```

Replaces the browser's `title` attribute, which is free and ugly: a system rectangle in
the OS font, appearing after a delay nobody can change, and invisible on a touch screen.

It **clones** its child rather than wrapping it, because half of these sit on a `<th>` or
`<td>` that may not have a `<span>` between it and its row — so it adds handlers, not an
element. The bubble is rendered through a portal and positioned `fixed`, because a CSS
`::after` bubble is clipped by every ancestor that hides overflow, and the two places that
most need a tooltip here are a `truncate`d name and a cell inside the horizontally
scrolling panel. Empty `text` renders the child alone, so a caller may pass a value that is
sometimes absent.

The bubble opens above its trigger, or **below it when there is no room above** — measured
after mount in a layout effect, because the bubble's height depends on how its text wraps
and a fixed threshold is wrong for exactly the long strings that need a tooltip. It ran off
the top of the window on the breadcrumb before that.

In an iterator, the `key` belongs on the `Tip`, not on the child — it is the outer element
now.

### `HelpLink` — the "?" that opens the help on this

```tsx
<h2>{t("roles.title")} <HelpLink anchor="roles-matrix" /></h2>
```

A small "?" with a tooltip, linking to `/help/<page>#<anchor>`. It takes a handbook
**anchor**, never a path: which page owns an anchor is `web/src/handbook/index.ts`'s
business, and anchors are what the help promises to keep (the structure lock in
`scripts/check-docs.py`), while pages may be split or renamed around them. An anchor no
page has renders nothing, so a link is never a "?" that lands on an empty page. The
testid is `help-link-<anchor>`. For "help for the whole screen" use `helpFor(pathname)`
from the same module, as the account menu does — never write a `/help/…` path by hand.

### `Badge` — a small label in a tone

```tsx
<Badge tone="danger" testId={`doc-expired-${doc.id}`}>{t("documents.expired")}</Badge>
<Badge tone="success" pulse>{statusText("live")}</Badge>
```

The rounded pill every status, role and warning label is: `StatusBadge`, `LiveBadge`,
`ClaimStatusBadge`, `ExpiredBadge`, a member's relations, the "minor" mark. Tones are
named by meaning — `neutral`, `muted`, `success`, `warning`, `caution`, `danger`,
`brand` — so a status map reads as a decision ("cancelled is danger") rather than as a
palette, and six hand-written copies of the same class string no longer drift apart in
padding and shade. `pulse` adds the green "happening now" dot; any other attribute
(`role`, `data-state`) is passed through to the `<span>`.

### `LiveBadge` and `useLive` — the page hears about changes

```tsx
const live = useLive(event.published ? `event:${id}` : null, [
  getGetEventQueryKey(id),
  `/api/events/${id}/`,
]);
…
{event.status === "live" && <LiveBadge state={live} testId="matchday-live-badge" />}
```

`useLive` (`web/src/api/useLive.ts`, Story B-5) opens one Server-Sent-Events stream on an
event and, on every `change` frame, invalidates the targets it was given — the same
generated keys and path prefixes `useInvalidate` takes after a mutation, so the page
refetches through the client it always used and nothing arrives by a second path. It
reports `"live"`, `"reconnecting"` or `"off"`; in the last state it polls every twenty
seconds and retries the stream after a minute. Pass `null` as the topic for a draft: the
server answers a draft's stream with 404, and the hook would otherwise poll for nothing.

`LiveBadge` renders that state and nothing else. The rule it exists for: a lost connection
is a **badge, never an empty page** — TanStack keeps the last table on screen, the badge
says whether it is current. Show it only while something is actually live; a finished day
with a "Live" badge is a lie, and a planned one has nothing to stream yet. The hook itself
may stay mounted regardless, so the page hears the start.

### `useFinishOrder`, `FinishChip`, `FinishOrderPad` — a race's result as taps

```tsx
const order = useFinishOrder(race, standings, { onChange: (body) => save.mutate({ … data: body }) });
<FinishChip boat={boat} teamName={team} row={order.rows[boat.number]} onTap={() => order.tap(boat.number)} />
```

Two screens record results — the results tab (WL-2, the correction screen) and the
race-control page (WL-3, the one used on the water) — and they must not drift apart on
what a tap means, which position comes next, or what is sent. The state is one hook; the
chip is one component, compact in a table cell or large on the pad. The pure rules (codes,
"complete", the redress suggestion) are `lib/results.ts`.

The screens differ in *when* they write, and that is the one option: the results tab passes
`onChange` and writes through on every change; the race-control page passes a `mirrorKey`
instead, keeps taps in `localStorage` until "Finish", and so a mis-tap on the last boat does
not end the race by itself. With flag X up, `tap(boat, overEarlyCode)` marks the boat over
the line with the code the preparatory flag prescribes instead of giving it a place.

### `TabbedView` — tabs, with the selection in the URL

```tsx
<TabbedView tabs={tabs} param="view" testIdPrefix="matchday" label={t("viewLabel")} />
```

Each tab's `render` is a function, so only the selected panel mounts and an unopened tab
issues none of its queries. The selection lives in a query parameter, so a tab can be
linked, survives a reload, and the Back button steps between tabs. It owns the roving
tabindex, the arrow keys, and the horizontal scroll guard — the parts that get dropped
when a strip is copied.

**Who sees which tab of my space and of the administration is declared in
`lib/spaceTabs.ts`**, not in the page: `PROFILE_TABS`, `CLUB_TABS`, `SERIES_TABS`,
`EVENT_TABS` (each tab's key and the relations that show it, spread into a section with
`tabRule`) and `adminTabs(hasRole)`. The help's places (`handbook/places.ts`, Story B-18)
read the same declarations to decide whether a reader gets a link to a tab or plain
words — so a new tab there, or a changed `for`, is declared in that file first, never
only in the screen.

### `Steps` — where you are in a short, ordered sequence

```tsx
<Steps testId="admin-events-steps" current={step} steps={[t("stepGeneral"), t("stepClubs"), t("stepPairing")]} />
```

The marker row above a wizard: done steps carry a check, the current one is filled, the
rest are outlined. `current` is 1-based, and a value past the last step means "all done".
Not `TabbedView`: tabs let the reader jump anywhere and keep the choice in the URL, and
neither is wanted where each step needs what the one before it produced — a half-created
event is not a place to link to. Each step is `${testId}-${n}` with
`data-state="done" | "current" | "upcoming"`, which is what a spec asserts on.

### `AddButton` — the "＋" top-right of a list

```tsx
<Section title={t("title")} action={
  <AddButton label={t("newButton")} to="/admin/series/new" testId="admin-series-new-button" />
}>
  …the list…
</Section>
```

`Section`'s `action` slot sits beside the title. The tab is the list; creating is a page of
its own — `/admin/<area>/new`, built on `pages/AdminNewPage.tsx` (`NewEntryPage` for the
access rule, breadcrumb and card; `AfterCreate` for "Back to the list" and "Create
another"; `CancelButton`). A form embedded above the list put the thing being worked on
below the fold, asked for input before showing what was already there, and could not be
linked to or returned to with the back button. Same corner, same sign on every admin list,
so nobody has to find out where a screen hides its "new".

### `Pager` — one page of a long list

```tsx
const [offset, setOffset] = useState(0);
const query = useListEvents({ limit: PAGE_SIZE, offset },   // PAGE_SIZE from api/useApi
  { query: { placeholderData: keepPreviousData } });
...
<Pager page={query.data} onOffset={setOffset} testId="events" />
```

The other half of Story A-13's envelope: the backend answers a growing list as
`{ items, total, limit, offset }`, and this turns the last three numbers into "26–50 of
180" plus the two buttons. It renders **nothing** while everything fits on one page.

Two things it cannot do for you, both easy to forget:

* **`placeholderData: keepPreviousData`** on the hook. The offset belongs in the query key,
  so every step is a different query — without the placeholder, `data` empties and the
  table is replaced by a spinner between pages.
* **Reset the offset when a filter or search term changes.** Page 4 of the previous search
  says nothing about this one, and an offset past the end answers empty.

A screen that does *not* page — a client-side filter over the list, or a count taken from
it — asks for `WHOLE_LIST` rows and reads them with `useAsyncRows`
(`api/useApi.ts`), which hands back the rows and hides the envelope.

### `DataTable` — the one table

```tsx
const list = useListParams();
const query = useListSailors(
  { ...list.request, q: list.q || undefined, sort: list.sort ?? undefined },
  { query: { placeholderData: keepPreviousData } },
);
const columns = useMemo(() => helper.columns([...]), [t]);

<DataTable columns={columns} page={query.data} params={list}
           testId="admin-sailors" empty={t("sailors.emptyText")}
           rowTestId={(sailor) => sailor.id} />
```

Story A-13's table, on TanStack Table v9 (headless: the library owns the sorting state and
the row model, every element and class below is ours). It draws the header row, the body
and the `Pager`, puts `aria-sort` on the sorted column and makes each sortable header a
real button.

- **The server sorts.** `manualSorting` tells the table so; without it the rows of *one
  page* would be re-sorted among themselves, which looks like sorting and is not.
- **Mark a column `enableSorting` only where the endpoint can sort it** — its `sortable`
  map in the router. A header that promises more answers 422.
- Columns are built with `createColumnHelper<typeof TABLE_FEATURES, Row>()` from
  `lib/table.ts`, and **memoised**: a new array each render rebuilds the table.
- There is no `rowPaginationFeature`: paging is the URL's and the server's.

A screen whose rows are *editors* rather than values — the admin event list, where every
row opens readiness, clubs, the draw and publication — stays a list and takes only
`useListParams` + `Pager`.

### `useListParams` — page, sort and search in the URL

```tsx
const list = useListParams();     // ?page=3&sort=-last_name&q=mann
list.request                      // { limit, offset } — spread into the generated hook
list.setQuery(value)              // also resets to page 1
```

The three live together (`lib/listParams.ts`) because they interact: a new search term
invalidates the page someone was on. Keeping them in the query string is what makes a found
row a link you can send, and what stops a reload from throwing the work away. It writes only
its own keys, so `?view=pairing` and `?tab=events` survive, and it uses `replace` — paging
should not fill the Back button with every step on the way.

### `RichText` and `RichTextEditor` — formatted text, shown and written

`RichText` shows the HTML of a post (Story R-1) as it is — safe **only** because the
server cleaned it on write (`api/app/services/rich_text.py`); never pass it anything else.
`RichTextEditor` is the TipTap editor editorial writes it in, a toolbar of HeroUI buttons
with `Tip`s. Both style the text with `.rich-text` (`index.css`), so the editor shows what
the page will. The editor is the module's default export, loaded with `React.lazy`:
TipTap is a few hundred kilobytes no reader needs. A toolbar control added there needs its
element added to the server's allowlist, or it is dropped on save.

## Adding to this

Two rules, both from `CLAUDE.md`:

- **The second time you write something, notice. The third time, extract it** — and put
  the reasoning inside the extracted thing, where the next person will read it.
- **Put the new piece in `components/` and add a row above.** A shared component nobody
  knows about is a component that gets written again.

## The site frame (issue #14, Stories B-13–B-16)

The public site's pages draw their own frame from `web/src/components/site/`; everything
else sits in `Layout`, which uses the same top row.

- **`TopBar`** — the one row: logo, the leagues (`GET /api/leagues`), the account menu. On
  an official page's picture (`overlay`), solid and sticky on the internal screens.
  **`Bars`** is it with the sub-menu (`LeagueSubBar`, or a matchday's `SubBar`) in the
  rows' shade; **`BARS`** their height, for scrolling and `sticky`.
- **`ChapterScroller`** — a league's (or the association's) page: chapters at their own
  height over one fixed `photo`, the dots on the right, each chapter ending in its own
  page. Only the first chapter's title is an `h1`.
- **`DepthPage`** — the frame of a page behind a chapter: its picture fixed behind it, the
  rows, the kicker and title (the page's `h1`), the content in cards. `Block` and
  `Expand` are its section heading and its row that opens in place.
- **`PageLoading`** — what an official page shows while its data is on the way: the same
  dark frame, never a white page.
- **`Cards.tsx`** — the official pages' building blocks, taken from the chapter page
  (2026-10-18): **`Card`** (a box, a link with `to`), **`MediaCard`** (picture first, then
  kicker, title, text — news, videos, photos, people), **`Panel`** (room for what is
  read closely: a full table, an article, the matchday's tables — over a picture a card
  whose `.on-glass` scope in `index.css` maps the light colours of the tables shared with
  the internal screens to the glass's), **`CardRow`** and **`Columns`** (the grid),
  **`PillSwitch`** (one of a few, as pills — a matchday's division, the language). All
  are frosted glass with white type, because every official page lies on its picture;
  **`tone`** gives the type, line and pill classes for anything else on the glass, and
  `GLASS`, `BAR_SHADE`, `SHADE_ACROSS`, `SHADE_DOWN` and `PAGE_TITLE` the look's other
  pieces — written here once.
  How dark and blurred the glass is, how far the picture is darkened and how strong the
  secondary text is are CSS variables (`--site-card-alpha`, `--site-card-blur`,
  `--site-shade`, `--site-text` in `index.css`), tuned live with the DEV switch's sliders.
  **`TextCard`** puts a text of its own (an introduction, a note) on a card: over a
  picture no small text lies bare. Write a page's content once with these, never with `bg-white/10` or `text-slate-600`
  by hand: that is what made each page look different. On a page deeper, the
  sub-menu's pages and the matchday's tabs come from **`SubBar`** / **`LeagueSubBar`**.
- **One column, one grid** (2026-10-18). The width belongs to the frame, never to the
  content: a chapter, and a page deeper, has one column (`data-column`), and every block in
  it spans that column — content sets no `max-w-*` (text *inside* a card may keep a
  readable measure). Tiles and splits sit on one 12-column grid with one gap:
  **`CardRow`** (1, 2, 3, 4 or 6 equal tiles; fewer tiles than columns share the row, so
  it never ends in a gap) and **`Columns`** (`halves`, or `twoToOne` — which breaks where a
  row of three does). A block that only stacks others says so with `data-flow`, so they
  are measured too — the frames' business (`ChapterScroller`, `DepthPage`, `Block`, the
  footer), not a page's; one meant to be as wide as its content (a pill switch, the
  "more" link) is `inline-*` and left out. `e2e/visitor.spec.ts` › *one column, one grid* measures every
  official page and names the block that breaks the rule — a hand-written `grid-cols-*`
  or `max-w-*` in a chapter fails it.
- **`GlassFooter`** (`Footer.tsx`) — the official pages' footer, the last band on the
  picture in the same column and grid; **`Footer`** the internal screens' light one.
- **`Picture`** — a page's one big picture as photo, fade, slide or muted video
  (`settings.ts`).
- **`useActTitle`**, **`useCurrentActs`** (`acts.ts`) — "Act 2 · Kiel"; each league's
  act now or next, kept for minutes, for the footer and the association's home.
- **`DevSwitch`** — the open variants, mounted by `SiteShell` wherever `DEV_TOOLS` is.
- Content without a backend comes from **`web/src/content/`**, through hooks that return
  an `AsyncState` like a generated query — render it with `Async`, and the page does not
  change when the endpoint arrives.

## `StandingsTable`

A series' standings as a table — rank, club, points, a column per act (a missed act in
italics, the rule in its tooltip). One table for a series' own page (`/series/:id`) and
each division on a league's standings page, where `marks` (the league's promotion,
relegation and requalification ranks) colour the row's edge and add a legend. `actHref`
says where an act's heading leads; `testId` prefixes every testid.

## `Select` — one dropdown, both surfaces

A native `<select>` paints its own field and option list but takes its **text colour from
the page**. On paper that is fine; on the official pages' glass (`.on-glass`) the text is
white while the browser still draws white — the pairing list's "all clubs" picker was white
on white. `Select` names `bg-white text-slate-900` itself, which `.on-glass` maps to glass,
and `index.css` gives a select on glass `color-scheme: dark` and dark options, so the open
list is dark too. Every dropdown is this component; `.oxlintrc.json` forbids `<select>`
anywhere else.

- **`size` says where it stands:** `field` (a labelled form control, full width, in
  `Field`), `inline` (a toolbar, as wide as its options), `row` (beside a name in a list,
  `RoleSelect`), `touch` (a thumb target on the water, `RaceControl`).
- **`tone="bar"`** is an entry of the top row rather than a field: no box, the row's own
  text, its pill shape and hover, a chevron of its own — the guest's language (Story
  A-12). `dark` gives its open list the dark scheme when the row is on a picture.
- **`invalid`** draws the red border and sets `aria-invalid`.
- **`className` is for layout only** — `flex-1`, `w-32`. A colour or padding there wins or
  loses by its place in Tailwind's stylesheet, not by its place in the list (docs/gotchas).
