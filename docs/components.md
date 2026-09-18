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
| `Blocks.tsx` | `Loading`, `ErrorMessage`, `Empty`, `PageHeader`, `StatusBadge`, `LiveBadge`, `TableFrame`, `MatchdayCard` |
| `Layouts.tsx` | `Stack`, `CardGrid` |
| `LinkCard.tsx` | `LinkCard` |
| `Tip.tsx` | `Tip` — the tooltip, in place of `title` |
| `Form.tsx` | `Section`, `Field`, `Message` |
| `TransferList.tsx` | `TransferList` — the two-pane "move it across" picker |
| `ClubSelector.tsx` | `ClubSelector` — `TransferList` for clubs |
| `LineupPanel.tsx` | `LineupPanel` — a matchday's crew from the squad, with roles (Story V-2) |
| `Tabs.tsx` | `TabbedView` |
| `Steps.tsx` | `Steps` — where you are in a short, ordered sequence (Story VA-6) |
| `AddButton.tsx` | `AddButton` — the "＋" after every admin list that opens its create form |
| `FinishOrderPad.tsx` | `useFinishOrder`, `FinishChip`, `FinishOrderPad` — a race's result as taps (Stories WL-2, WL-3) |
| `SquadPanel.tsx` | registering a squad (Story V-1), used by `/admin` and `/club` |
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

### `AddButton` — the "＋" after a list

```tsx
{creating ? <CreateForm onClose={() => setCreating(false)} /> : (
  <AddButton label={t("newButton")} onPress={() => setCreating(true)} testId="admin-series-new-button" />
)}
```

What exists comes first, then the plus, and the create form takes the space below the
list only while something is being created. A screen that opened on an empty form put the
thing being worked on below the fold and asked for input before showing what was already
there. Same place, same sign on every admin list, so nobody has to find out where a screen
hides its "new".

### `Pager` — one page of a long list

```tsx
const [offset, setOffset] = useState(0);
const query = useListEvents({ limit: PAGE_SIZE, offset },
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

## Adding to this

Two rules, both from `CLAUDE.md`:

- **The second time you write something, notice. The third time, extract it** — and put
  the reasoning inside the extracted thing, where the next person will read it.
- **Put the new piece in `components/` and add a row above.** A shared component nobody
  knows about is a component that gets written again.
