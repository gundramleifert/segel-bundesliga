---
title: The content store — layout, frontmatter, audiences, anchors, structure lock
description: File layout of the handbook store under web/, the frontmatter that ties a page to its audience, stories, journey and route, the page types, the reserved pages, markdown conventions and the structure lock.
---

# The content store

```
web/src/handbook/
├── start-sailor.en.md          start-sailor.de.md
├── squad-and-lineup.en.md      squad-and-lineup.de.md
├── journey-lifecycle.en.md     journey-lifecycle.de.md
├── roles.en.md                 roles.de.md
├── …
└── .baseline/                  ← snapshot of the released structure, committed
web/public/handbook/screenshots/<shot-id>_<locale>[_phone].png
```

**Why under `web/src/`**: Vite's `import.meta.glob` reaches only the project root, and the
web build (Render, `docs/deploy.md`) builds `web/`. Screenshots in `web/public/` are copied
into the bundle as they are.

One flat directory; structure comes from frontmatter, not folders.

## File naming

`<id>.<locale>.md`. `id` is kebab-case, English, describes the **reader's task**
(`squad-and-lineup`, not `team-members-put`), and is **permanent** — it is in URLs and in
support mails. `locale` is `en` or `de`; both exist for every id.

## Frontmatter

Flat `key: value` lines, `[a, b]` lists, `true`/`false`, `null`. No nesting, no comments,
quote a `title` containing `:`. **Every field except `title` is identical in both files.**

```yaml
---
id: squad-and-lineup
type: guide
order: 20
audience: [club]
stories: [V-1, V-2, V-12]
journey: null
route: /me/club/:id
tags: [crew, squad, matchday, kader, aufstellung]
title: "Register the squad and name the crew"
---
```

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | equals the file name's id |
| `type` | yes | `start`, `guide`, `journey`, `doc`, `faq` |
| `order` | yes | position within its type, **steps of 10**, never renumbered |
| `audience` | yes | one or more of `sailor`, `club`, `event-organizer`, `race-committee`, `treasurer`, `administration`; a `guide` has **exactly one** |
| `stories` | yes | the story IDs this page documents — the link the checks and the update mode follow. `[]` only for `start` pages |
| `journey` | `journey` pages | the journey ID (`J-1`); `null` elsewhere |
| `route` | no | the route this page explains, as written in `App.tsx`; feeds "help for this page". At most one page per route. `null` if none |
| `tags` | no | search words the prose does not use — include the German domain word in **both** locales (`kader`), so a German speaker finds the English page too |
| `title` | yes | the only field that differs between locales |

## Types — from what the reader is doing

| `type` | The reader … | Holds |
|---|---|---|
| `start` | just learned they have this role | one per audience: what this person does on the site, in the order of a season, linking each task to its guide. ≤ 250 words |
| `guide` | wants to get one thing done | numbered steps from a stated starting state to a stated result, for one audience |
| `journey` | wants to see how the pieces fit, across people | the journey's steps in order, who acts, links into each person's guide |
| `doc` | looks something up | terms (Series, Event, Act, Squad, Lineup, Host club, Venue …), scoring, states of an event, the roles page |
| `faq` | is stuck or surprised | a refusal they met, a boundary ("why can't I …"), what is deliberately not possible |

A first pass typically has 7 `start` pages, 10–20 guides, one `journey` page per ◐/●
journey, 2–4 docs and 1–3 FAQ pages. Extend a page before adding a thin one.

## Reserved pages

Other code links to these; their `id`, `type` and anchors are fixed.

| `id` | `type` | Anchors | Purpose |
|---|---|---|---|
| `roles` | `doc` | `roles-list`, `roles-matrix`, `roles-getting` | which roles exist, who may do what, how one gets a role (`writing-guide.md` § The roles page). Replaces `Help.tsx`'s matrix. |
| `terms` | `doc` | `terms-competition`, `terms-people`, `terms-event-states` | the glossary every other page reuses |
| `start-<audience>` | `start` | — | one per audience; the viewer's audience tiles open these |

## Body markdown

GFM, rendered with `react-markdown` + `remark-gfm` (`viewer.md`).

- The first `##` is the page title (no anchor — the page id is its anchor). Only `##`,
  `###`, `####`; the page's `h1` is the app's `PageHeader` (a second `h1` is a known trap,
  see docs/gotchas).
- Every `###` carries an explicit, permanent anchor: `### Name the crew {#squad-and-lineup-crew}`,
  prefixed with the page id, unique in the store.
- **No numbers in headings**; position comes from `order`.
- Hard-wrap at ~90 columns, like the rest of the docs.
- **No raw HTML.**

Four conventions, all plain markdown so GitHub renders the files readably too:

| What | Syntax | Rendered as |
|---|---|---|
| Screenshot | `![Caption saying what to look at](shot:lineup-panel)` on its own line | the PNG for the current locale (and `_phone` on narrow screens if it exists); a missing PNG renders a "screenshot pending" box |
| Callout | a blockquote starting `> **Note:**` / `> **Careful:**` (de: `**Hinweis:**` / `**Achtung:**`) | the site's warning/info style; at most one per page; *Careful* only for the irreversible |
| Link to a place of the site | `[*Me* → *Waivers*](place:profile.waivers)` | a link to that screen and tab **for this reader**, or the plain words when it is not there for them — § Links to the site: places |
| Link into the site | `[Sign in](/account)` | router link, no reload. Only for a route no place covers (the sign-in page, a public page); `check-docs.py` refuses a raw path a place covers |
| Link to another page | `[squad size](#squad-and-lineup-size)` | opens the page owning the anchor. Never a file path |

## Links to the site: places

A page **names a place, never a URL**. The link text stays the click path a reader
follows by hand — it is still read on a screenshot, in a mail, on someone else's phone —
and the target is a place id:

```markdown
In my space: [*Me* → *Account*](place:profile.account) → *Sign-in methods*.
Your club's page in [*My space*, tab *Money*](place:club.money).
[*Administration*, tab *Clubs*](place:admin.clubs): [*New club*](place:admin.new-club) ①.
[Open my space](place:space)
```

Put the link around the part that **opens a screen or a tab**; what is done inside it
(*Sign-in methods*, *Leave the club*, a button) stays plain text after it.

**Why ids, not URLs.** Routes and tab keys change (`/club` became `/me/club/:id`, the
claims screen became a tab); a hundred hand-written addresses in two languages would
drift without a sound. A place is one line in the registry. And an address is not even
the same for two readers: *my* club is NRV for one and KYC for another.

**Why hidden, not refused.** Each reader gets a link only where that screen or tab is
there for them; for anyone else the same words render as plain text. A link that ends in
a 403 or an empty page is worse than none (Story A-12), and the help is read by people
about to take on a role. The rule lives in one place — see "Who may use it" below.

### The families

The registry is `web/src/handbook/places.ts` (`PLACES`):

| Place | Leads to | A link for |
|---|---|---|
| `space` | `/me` | every signed-in reader (the help is only for them) |
| `profile.<tab>` — `account`, `documents`, `bank`, `waivers`, `claims` | `/me/profile?tab=<tab>` | every signed-in reader |
| `club.<tab>` — `members`, `events` (*Matchdays*), `series` (*Series & squads*), `waivers`, `claims` (*My claims*), `money` | `/me/club/<id>?tab=<tab>` | each club in the reader's space where that tab is there for their relations — one link per club |
| `series.<tab>` — `team`, `events`, `organize` | `/me/series/<id>?tab=<tab>` | likewise, per series |
| `event.<tab>` — `crew`, `claims`, `decide`, `race`, `organize` | `/me/event/<id>?tab=<tab>` | likewise, per event |
| `admin`, `admin.<tab>` — `clubs`, `series`, `events`, `sailors`, `accounts` | `/admin`, `/admin?tab=<tab>` | a reader who has that administration tab |
| `admin.new-club`, `admin.new-series`, `admin.new-event` | `/admin/<area>/new` | a reader who has the tab that page is reached from (`new-series`: the site's admin alone) |

The tab keys are the screens' own (`?tab=` values), not the labels: *Matchdays* is
`club.events`, *Series & squads* is `club.series`, *Claims to decide* is `event.decide`,
*Race control* is `event.race`. When the label in a page and the key disagree, the key
in `lib/workspace.ts` is right.

### Who may use it

**Not decided in `places.ts`.** The screens build their tabs from the declarations in
`web/src/lib/workspace.ts` — `PROFILE_TABS`, `CLUB_TABS`, `SERIES_TABS`, `EVENT_TABS`
(each tab's `for`: the relations that show it) and `adminTabs(hasRole)`,
`mayCreateIn(area, hasRole)` for the administration. A place only points at one of
them, and the viewer asks the same declarations with the reader's relations from
`GET /api/me/contexts`. A change to who sees a tab is therefore one edit, and the help
follows it without being touched.

### Adding a place

Only when a page names it (plus the obvious tab siblings):

1. The tab exists in `lib/workspace.ts` (the screen declares it there; a new screen tab
   is declared there first, never only in the page).
2. One line in `PLACES`: `"club.money": { path: "/me/club/:id", tab: "money" },` —
   literal, one entry per line: `check-docs.py` reads the keys and paths with a regex.
   `PlaceDef` types the `tab` by the path, so a tab the screen does not declare does not
   compile.
3. A new **family** (another route) also needs a branch in `resolvePlace` — who may use
   it, from the screen's own rule — and a row in the table above.
4. Use it in both locales — the same places, in the same order (`check-docs.py`).

## Structure lock

Pages are read, bookmarked and linked from mails. A change may **add** pages and sections
and **rewrite prose** freely; it may not silently restructure. `scripts/check-docs.py`
compares the store with `web/src/handbook/.baseline/` (`checks.md`):

| Violation | Meaning |
|---|---|
| `removed-page` | an id is gone (a rename is a removal plus an addition — reuse the id) |
| `reorder` | `order` changed |
| `retype` | `type` changed |
| `lost-anchor` | an anchor disappeared |
| `lost-locale` | one locale of a page is gone |
| `audience-dropped` | an audience was removed from a page (adding one is fine) |

Not locked: prose, `title`, `tags`, `stories` (it must follow the facts), `route`, new
anchors, new pages.

**Retiring a page** when a feature goes: (1) repurpose it to what replaced the feature,
keeping id and anchors; (2) *default* — keep it, saying what is gone and what to do
instead; (3) delete both files only on the user's explicit word, then re-snapshot and say
in the report which page was removed.
