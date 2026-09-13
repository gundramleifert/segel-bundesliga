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
| `Blocks.tsx` | `Loading`, `ErrorMessage`, `Empty`, `PageHeader`, `StatusBadge`, `TableFrame`, `MatchdayCard` |
| `Layouts.tsx` | `Stack`, `CardGrid` |
| `LinkCard.tsx` | `LinkCard` |
| `Tip.tsx` | `Tip` — the tooltip, in place of `title` |
| `Form.tsx` | `Section`, `Field`, `Message` |
| `ClubSelector.tsx` | the two-pane club picker |
| `Tabs.tsx` | `TabbedView` |
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

In an iterator, the `key` belongs on the `Tip`, not on the child — it is the outer element
now.

### `TabbedView` — tabs, with the selection in the URL

```tsx
<TabbedView tabs={tabs} param="view" testIdPrefix="matchday" label={t("viewLabel")} />
```

Each tab's `render` is a function, so only the selected panel mounts and an unopened tab
issues none of its queries. The selection lives in a query parameter, so a tab can be
linked, survives a reload, and the Back button steps between tabs. It owns the roving
tabindex, the arrow keys, and the horizontal scroll guard — the parts that get dropped
when a strip is copied.

## Adding to this

Two rules, both from `CLAUDE.md`:

- **The second time you write something, notice. The third time, extract it** — and put
  the reasoning inside the extracted thing, where the next person will read it.
- **Put the new piece in `components/` and add a row above.** A shared component nobody
  knows about is a component that gets written again.
