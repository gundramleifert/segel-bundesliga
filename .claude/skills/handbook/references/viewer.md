---
title: The viewer — /help in web/
description: How the site renders the handbook store — loading it with import.meta.glob, rendering with react-markdown, the audience filter fed by /api/me/contexts, help for the current page, absorbing today's Help.tsx, test ids and tests.
---

# The viewer

There is no handbook package here; the site renders its own, from the pieces in
`web/src/components/` (`docs/components.md` — read it first). The viewer agent owns these
files and nothing else:

| File | Holds |
|---|---|
| `web/src/handbook/index.ts` | loads the store, parses frontmatter, builds the anchor → page index and the route → page map |
| `web/src/pages/Help.tsx` | the `/help` page (replaces today's hand-written roles matrix) |
| `web/src/components/HelpLink.tsx` | the "?" beside a heading that opens one anchor — a component, so pages can use it |
| `web/src/i18n/locales/{en,de}/help.json` | the viewer's own chrome (the namespace exists; its matrix keys go once the `roles` page has the content) |
| `App.tsx` | the routes `help`, `help/:page` |

## Loading the store

```ts
// web/src/handbook/index.ts
const files = import.meta.glob("./*.md", { query: "?raw", import: "default", eager: true });
```

A literal glob, eager: the store is small text, and a lazy one fetches each page over HTTP
in dev (the `vertical-docs` trap: works in one mode, empty in the other). Parse the
restricted frontmatter by hand (`content-model.md` § Frontmatter) — no YAML dependency.
Pick the file for `i18n.resolvedLanguage`, falling back to `en`.

## Rendering

- `react-markdown` is already a dependency; tables need **`remark-gfm`** — the one
  dependency the viewer may add (pnpm, in `web/`). Nothing else.
- Custom renderers: `h2`/`h3` strip `{#anchor}` from the text and set it as `id`; `img`
  with a `shot:` src resolves to `/handbook/screenshots/<id>_<locale>.png` (the `_phone`
  variant under the `md` breakpoint when it exists) with the alt text as caption, and a
  "screenshot pending" box when it does not load; `a` with an internal path renders the
  router's `Link`, with `#anchor` resolves to `/help/<page>#anchor`; `blockquote` starting
  with **Note/Hinweis** or **Careful/Achtung** renders the site's info or warning style.
- Layout from `Stack`; tables in `TableFrame` so a wide table scrolls inside itself and
  never the page (Story A-10, `e2e/layout.ts::expectNoSidewaysScroll`).
- The page's `h1` is `PageHeader`; the markdown never renders an `h1`.

## The landing page `/help`

1. **"Help for …" tiles, one per audience** (`LinkCard`s in a `CardGrid`), opening
   `start-<audience>`. When signed in, the audiences the person **has** come first, marked
   — derived from `GET /api/me/contexts` (relations and `sailor`) and `User.roles` (site
   roles), the same answer my space uses (Story Z-8). A guest sees `visitor` first.
   **Nothing is hidden**: every page is readable by everyone; the audience only orders and
   filters. The help contains nothing secret, and someone about to become a club manager
   should be able to read what that means.
2. **Journeys** — one `LinkCard` per `journey` page.
3. **Look up** — `terms`, `roles`, the FAQ.
4. A search box over titles, headings and `tags`, client-side (the store is small).

`/help/:page` shows one page, with its `###` as a table of contents and, at the foot, the
other audiences' pages that share a story ("The organizer's side of this: …").

## Help for this page

`web/src/handbook/index.ts` exports `helpFor(pathname)`: the page whose `route` matches the
current path (`matchPath` against each `route`). The navigation shows a "Help" entry that
opens it when there is one, and `/help` otherwise. Hardcode no handbook path outside
`index.ts` and `App.tsx`.

## Absorbing today's `Help.tsx`

Its matrix becomes the `roles` page's content (re-derived from the model, `sources.md`),
its route stays `/help`, and `/help/roles` is the address the account and club screens link
to with `HelpLink`. Keys of `help.json` the new page no longer uses are removed in both
locales.

## Test ids and tests

`data-testid` on: `help-audience-<audience>`, `help-journey-<id>`, `help-page-<id>`,
`help-search`, `help-for-this-page`, `help-shot-<shot-id>`.

Tests, under the story the first pass wrote (`describeStory("B-n: …")`, both projects,
`chromium` and `mobile`):

- the landing renders every audience tile and journey; a signed-in club manager sees
  theirs first (`e2e/session.ts::signIn`);
- `/help/roles` deep-loads in a fresh tab and scrolls to `#roles-matrix`;
- a cross-page anchor link opens the right page; an internal link navigates without reload;
- switching to German shows the German page with the same anchors;
- no sideways scroll on the widest page (`expectNoSidewaysScroll`);
- "help for this page" on `/me/club/:id` opens the club manager's guide.

A unit test for the frontmatter parser and the anchor index lives beside the other web
unit tests, if the web project has them; otherwise the e2e tests carry it.
