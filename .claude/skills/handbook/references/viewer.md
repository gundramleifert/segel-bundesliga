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
  router's `Link`, with `#anchor` resolves to `/help/<page>#anchor`, with `place:<id>`
  renders `PlaceLink` (§ Places, below); `blockquote` starting
  with **Note/Hinweis** or **Careful/Achtung** renders the site's info or warning style.
- Layout from `Stack`; tables in `TableFrame` so a wide table scrolls inside itself and
  never the page (Story A-10, `e2e/layout.ts::expectNoSidewaysScroll`).
- The page's `h1` is `PageHeader`; the markdown never renders an `h1`.

## Places — links resolved per reader

`[*Me* → *Waivers*](place:profile.waivers)` (`content-model.md` § Links to the site:
places). `urlTransform` lets `place:` through — react-markdown's default would empty an
unknown scheme — and the `a` renderer hands it to `PlaceLink` in `Help.tsx`, which asks
`usePlace(id)` (`web/src/handbook/places.ts`) for the reader's **targets**:

```
usePlace(id)
  unknown id                → { status: "unknown" }   (check-docs.py refuses it before a build)
  account or contexts load  → { status: "loading" }
  otherwise                 → { status: "ready", targets: resolvePlace(def, hasRole, contexts) }

resolvePlace
  /me, /me/profile          → one target: every signed-in reader
  /me/<kind>/:id + tab      → one per context of that kind in GET /api/me/contexts whose
                              relations give the section (hasSection(kind, section, relations))
  /admin (+ tab)            → one target if adminTabs(hasRole) has the tab (any tab, bare)
  /admin/<area>/new         → one target if mayCreateIn(area, hasRole)
```

| Targets | Rendered as |
|---|---|
| none, still loading, or unknown | the link's children as they are (emphasis kept), **no link** — `data-reachable="false"`, `"pending"` while loading. No layout jump to a link that may turn out wrong |
| one | the children as a router `Link` to it |
| several | the children, then one link per context named by it: "*Money* (NRV · KYC)" |

Every rendering carries `data-testid="help-place-<id>"` and `data-place`; with several
targets each link is `help-place-<id>-<kind>-<contextId>`. The contexts come from the same
query the audience tiles use, so a page full of places costs no extra request.

**Why the viewer never decides access itself:** `places.ts` imports the tab
declarations from `web/src/lib/workspace.ts`, which `pages/me/Contexts.tsx` and
`pages/Admin.tsx` are built from. A rule copied into the help would drift from the screen
and send a reader to a tab that is not there — a link that ends in a 403 or an empty page
is worse than none (Story A-12).

## The landing page `/help`

1. **"Help for …" tiles, one per audience** (`LinkCard`s in a `CardGrid`), opening
   `start-<audience>`. When signed in, the audiences the person **has** come first, marked
   — derived from `GET /api/me/contexts` (relations and `sailor`) and `User.roles` (site
   roles), the same answer my space uses (Story Z-8). A guest sees no tiles at all — only a prompt
   to sign in (Story B-18). **Nothing is hidden from a signed-in person**: the audience only orders and
   filters. The help contains nothing secret, and someone about to become a team manager
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

- the landing renders every audience tile and journey; a signed-in team manager sees
  theirs first (`e2e/session.ts::signIn`);
- `/help/roles` deep-loads in a fresh tab and scrolls to `#roles-matrix`;
- a cross-page anchor link opens the right page; an internal link navigates without reload;
- switching to German shows the German page with the same anchors;
- no sideways scroll on the widest page (`expectNoSidewaysScroll`);
- "help for this page" on `/me/club/:id` opens the team manager's guide;
- a place is a link to the reader's own screen and tab where they have it, and plain words
  (`data-reachable="false"`) where they do not — a sailor's `profile.waivers`, a club
  treasurer's and admin's `club.money`, a plain member's `club.money` (words) and
  `club.members` (link).

A unit test for the frontmatter parser and the anchor index lives beside the other web
unit tests, if the web project has them; otherwise the e2e tests carry it.
