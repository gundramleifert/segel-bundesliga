import { ContextRelation, Relation, Role, type MyContext, type Todo } from "../api/types";

/** Story Z-10: the signed-in workspace — its contexts, their groups and sections, and who
 *  has each (`docs/PLAN_NAVIGATION.md` §2–§3, issue #30).
 *
 * **Declared once, read three times.** The sidebar builds itself from these declarations,
 * the routes' guards ask the same question before showing a section, and the handbook's
 * places (`handbook/places.ts`, Story B-18) decide from the very same ones whether a reader
 * gets a link or plain words. A second copy of these rules would drift, and a link that
 * ends on a section the reader does not have is worse than none (Story A-12's rule). Here
 * only the *keys* and the *relations*; labels, icons and panels stay with the screens.
 *
 * **The model decides, never a role.** A section is there when I hold one of its `for`
 * relations on the object — `relations` as `GET /api/me/contexts` reports them for a
 * context of mine (`sailor` included), or as `GET /api/events/{id}/access` answers for one
 * reached through another (a series manager's event). A section's key is also its URL
 * segment (`/me/club/7/minors`) and the `section` a to-do links to (#33), so it never
 * changes once built on.
 */

/** Sailing there — a squad, a crew. No tuple says it, so it is no `Relation`; the API
 *  reports it among a context's relations (`ContextRelation`, Story Z-8). */
export const SAILOR = ContextRelation.sailor;

/** What someone can hold on an object: what the API reports for a context
 *  (`ContextRelation`), or `guardian` — held on a sailor, never a context's. */
export type Holding = ContextRelation | typeof Relation.guardian;

/** A section: there when I hold one of `for`; without `for`, for everyone who has the
 *  context at all. */
export type SectionRule = { readonly for?: readonly Holding[] };

/** A group of sections; `null` is the ungrouped head of the list — the *Overview*. */
export type GroupDecl = { readonly key: string | null; readonly sections: Readonly<Record<string, SectionRule>> };

/** The organizers of a club, a series or an event: its `admin` and its `manager` (for an
 *  event the model adds the series', the host club's and the site's race committee —
 *  they arrive here already as `manager`). */
export const ORGANIZERS = [Relation.admin, Relation.manager] as const satisfies readonly Holding[];

const ME_GROUPS = [
  { key: null, sections: { overview: {} } },
  { key: "me", sections: { account: {}, clubs: {}, waivers: {}, claims: {}, documents: {}, bank: {} } },
  { key: "children", sections: { children: { for: [Relation.guardian] } } },
  // Every post and picture of every regatta I write about (Story R-1, decided 2026-10-25).
  { key: "editorial", sections: { news: { for: [Relation.editor] }, media: { for: [Relation.editor] } } },
] as const satisfies readonly GroupDecl[];

const CLUB_MONEY: readonly Holding[] = [...ORGANIZERS, Relation.treasurer];
const CLUB_GROUPS = [
  { key: null, sections: { overview: {} } },
  {
    key: "people",
    sections: {
      members: { for: [Relation.member, ...ORGANIZERS] },
      sailors: { for: ORGANIZERS },
      minors: { for: ORGANIZERS },
      waivers: { for: ORGANIZERS },
    },
  },
  {
    key: "racing",
    sections: {
      squads: { for: [Relation.member, ...ORGANIZERS] },
      crews: { for: [Relation.member, ...ORGANIZERS] },
      hosting: { for: ORGANIZERS },
    },
  },
  {
    key: "money",
    sections: {
      "my-claims": { for: [Relation.member] },
      "decide-claims": { for: CLUB_MONEY },
      "payment-runs": { for: CLUB_MONEY },
      "bank-account": { for: CLUB_MONEY },
    },
  },
  { key: "club", sections: { "club-page": { for: [Relation.admin] } } },
] as const satisfies readonly GroupDecl[];

const SERIES_GROUPS = [
  { key: null, sections: { overview: {} } },
  { key: "sailing", sections: { team: { for: [SAILOR] } } },
  { key: "series", sections: { events: {}, standings: {} } },
  { key: "organize", sections: { registrations: { for: ORGANIZERS }, dates: { for: ORGANIZERS }, scoring: { for: ORGANIZERS } } },
  { key: "officials", sections: { officials: { for: ORGANIZERS } } },
  { key: "editorial", sections: { news: { for: [Relation.editor] } } },
] as const satisfies readonly GroupDecl[];

const RACE_DAY: readonly Holding[] = [...ORGANIZERS, Relation.race_officer];
const EVENT_GROUPS = [
  { key: null, sections: { overview: {} } },
  { key: "sailing", sections: { crew: { for: [SAILOR] } } },
  {
    key: "setup",
    sections: {
      general: { for: ORGANIZERS },
      clubs: { for: ORGANIZERS },
      boats: { for: ORGANIZERS },
      pairing: { for: ORGANIZERS },
      publication: { for: ORGANIZERS },
      people: { for: ORGANIZERS },
    },
  },
  {
    key: "raceday",
    sections: {
      "check-in": { for: RACE_DAY },
      "race-control": { for: RACE_DAY },
      results: { for: RACE_DAY },
      trackers: { for: RACE_DAY },
      "notice-board": { for: [...RACE_DAY, Relation.jury] },
    },
  },
  {
    key: "money",
    sections: {
      // Those who work the event file claims on it (Story F-2); sailing is not work.
      "my-claims": { for: [Relation.manager, Relation.race_officer, Relation.jury, Relation.helper, Relation.treasurer] },
      "decide-claims": { for: [...ORGANIZERS, Relation.treasurer] },
    },
  },
  { key: "editorial", sections: { news: { for: [Relation.editor] } } },
] as const satisfies readonly GroupDecl[];

/** The league office: the site's own work, by the site's relations (Story Z-10, §3). */
const OFFICE_GROUPS = [
  { key: null, sections: { overview: {} } },
  {
    key: "office",
    sections: {
      clubs: { for: [Relation.admin] },
      series: { for: [Relation.admin] },
      events: { for: [Relation.admin, Relation.race_officer] },
      people: { for: [Relation.admin] },
      accounts: { for: [Relation.admin] },
      news: { for: [Relation.admin, Relation.editor] },
      media: { for: [Relation.admin, Relation.editor] },
      imports: { for: [Relation.admin] },
    },
  },
] as const satisfies readonly GroupDecl[];

export const WORKSPACE = {
  me: ME_GROUPS,
  office: OFFICE_GROUPS,
  club: CLUB_GROUPS,
  series: SERIES_GROUPS,
  event: EVENT_GROUPS,
} as const;

export type WorkspaceKind = keyof typeof WORKSPACE;

/** Every section the league office declares, overview included — App.tsx spells out a
 *  route for each. */
export const OFFICE_SECTIONS: readonly string[] = OFFICE_GROUPS.flatMap((g) => Object.keys(g.sections));
type SectionsOf<G> = G extends readonly (infer D)[] ? (D extends { sections: infer S } ? keyof S & string : never) : never;
/** The section keys of one context — `Section<"club">` is `"overview" | "members" | …`. */
export type Section<K extends WorkspaceKind> = SectionsOf<(typeof WORKSPACE)[K]>;

/** Whether a section with this rule is there for someone holding `relations`. */
export function sectionVisible(rule: SectionRule, relations: readonly string[]): boolean {
  return !rule.for || rule.for.some((r) => relations.includes(r));
}

/** One group as the sidebar draws it: its sections I have, and whether it carries a
 *  heading — a group with one section shows as that section alone (§1, rule 5). */
export type SidebarGroup = { key: string | null; sections: string[]; heading: boolean; folded: boolean };

/** The sidebar of one context for someone holding `relations` there: absent, never
 *  disabled — a section I cannot use is not listed, a group left empty disappears. Several
 *  relations add up, each section once, in the order of the work.
 *
 *  `only` limits it to the sections a screen has built so far — a declared section without
 *  a panel yet is not a link to nothing.
 *
 *  An event that has started (`started`: a race no longer scheduled, VA-8) puts *Race day*
 *  before *Set up* and folds *Set up* — it is frozen anyway; before, the reverse. */
export function sidebar(
  kind: WorkspaceKind,
  relations: readonly string[],
  options: { started?: boolean; only?: readonly string[] } = {},
): SidebarGroup[] {
  const groups: SidebarGroup[] = (WORKSPACE[kind] as readonly GroupDecl[])
    .map((g) => {
      const sections = Object.entries(g.sections)
        .filter(([key, rule]) => sectionVisible(rule, relations) && (!options.only || options.only.includes(key)))
        .map(([key]) => key);
      return { key: g.key, sections, heading: g.key !== null && sections.length > 1, folded: false };
    })
    .filter((g) => g.sections.length > 0);
  if (kind !== "event") return groups;
  const setup = groups.find((g) => g.key === "setup");
  const raceday = groups.find((g) => g.key === "raceday");
  if (!setup || !raceday) return groups;
  const first = options.started ? raceday : setup;
  const second = options.started ? setup : raceday;
  second.folded = true;
  const rest = groups.filter((g) => g !== setup && g !== raceday);
  const at = groups.indexOf(setup) < groups.indexOf(raceday) ? groups.indexOf(setup) : groups.indexOf(raceday);
  return [...rest.slice(0, at), first, second, ...rest.slice(at)];
}

/** The section keys of a context I have, flat — for the routes' guards. */
export function sectionsFor(kind: WorkspaceKind, relations: readonly string[]): string[] {
  return sidebar(kind, relations).flatMap((g) => g.sections);
}

/** Whether this person has `section` in this context — the guard's question. */
export function hasSection(kind: WorkspaceKind, section: string, relations: readonly string[]): boolean {
  return sectionsFor(kind, relations).includes(section);
}

// ---------------------------------------------------------------- the switcher

/** A context, named by kind and id — `{ kind: "club", id: 7 }`; *Me* and the league
 *  office have no id. */
export type ContextRef = { kind: "me" | "office" } | { kind: "club" | "series" | "event"; id: number };

/** One line of the context switcher. */
export type SwitcherEntry = {
  ref: ContextRef;
  /** The relations as chips, in `RELATION_ORDER` (the API's order); empty for *Me*. */
  relations: readonly string[];
  /** The waiting count — the sum of the context's to-dos. */
  waiting: number;
  /** A past event, folded under *Earlier*. */
  past: boolean;
  context?: MyContext;
};

/** The groups of the switcher, in its order (§2): Me, the league office, clubs, series,
 *  events, then Recent. */
export type Switcher = {
  head: SwitcherEntry[];
  clubs: SwitcherEntry[];
  series: SwitcherEntry[];
  events: SwitcherEntry[];
  recent: RecentRef[];
};

/** What the switcher is built from: the answer of `GET /api/me/contexts`, the site
 *  relations (the league office is there only with one), what waits for me on *Me*
 *  itself, and the contexts this browser opened last. */
export type SwitcherInput = {
  contexts: readonly MyContext[];
  site?: readonly string[];
  meWaiting?: number;
  recent?: readonly RecentRef[];
  /** Today, `YYYY-MM-DD` — injected so a test can pin it. */
  today: string;
};

const waitingOf = (c: MyContext) => c.needs.reduce((sum, n) => sum + n.count, 0);

/** The switcher's entries — exactly mine (Story Z-8's answer), never every event of every
 *  series I manage: those are reached inside and then kept under Recent.
 *
 *  Clubs by name; series of the current year first, newer and older after, drafts last;
 *  events upcoming by date (the next first), then past ones, latest first and folded. */
export function switcherEntries(input: SwitcherInput): Switcher {
  const entry = (c: MyContext, past = false): SwitcherEntry => ({
    ref: { kind: c.kind, id: c.id },
    relations: c.relations,
    waiting: waitingOf(c),
    past,
    context: c,
  });
  const head: SwitcherEntry[] = [{ ref: { kind: "me" }, relations: [], waiting: input.meWaiting ?? 0, past: false }];
  if (input.site?.length) head.push({ ref: { kind: "office" }, relations: input.site, waiting: 0, past: false });

  const byName = (a: MyContext, b: MyContext) => a.name.localeCompare(b.name);
  const of = (kind: MyContext["kind"]) => input.contexts.filter((c) => c.kind === kind);

  const clubs = of("club").sort(byName).map((c) => entry(c));

  const year = Number(input.today.slice(0, 4));
  const seriesRank = (c: MyContext) => [c.published === false ? 1 : 0, c.year === year ? 0 : 1, -(c.year ?? 0)];
  const series = of("series")
    .sort((a, b) => compareTuples(seriesRank(a), seriesRank(b)) || byName(a, b))
    .map((c) => entry(c));

  const isPast = (c: MyContext) => (c.ends_on ?? c.starts_on ?? "9999") < input.today;
  const upcoming = of("event")
    .filter((c) => !isPast(c))
    .sort((a, b) => (a.starts_on ?? "9999").localeCompare(b.starts_on ?? "9999") || byName(a, b));
  const past = of("event")
    .filter(isPast)
    .sort((a, b) => (b.starts_on ?? "").localeCompare(a.starts_on ?? "") || byName(a, b));
  const events = [...upcoming.map((c) => entry(c)), ...past.map((c) => entry(c, true))];

  const listed = new Set([...clubs, ...series, ...events, ...head].map((e) => refKey(e.ref)));
  const recent = (input.recent ?? []).filter((r) => !listed.has(refKey(r)));
  return { head, clubs, series, events, recent };
}

function compareTuples(a: number[], b: number[]): number {
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return a[i] - b[i];
  return 0;
}

/** Where a section of a context lives (§7): `/me` is *Me › Overview*, my own sections are
 *  under `/me/profile/`, a club's, series' or event's under `/me/<kind>/:id/`, its
 *  overview being the bare address; the league office's under `/office/`. */
export function sectionPath(ref: ContextRef, section = "overview"): string {
  if (!("id" in ref)) {
    if (ref.kind === "office") return section === "overview" ? "/office" : `/office/${section}`;
    return section === "overview" ? "/me" : `/me/profile/${section}`;
  }
  const base = `/me/${ref.kind}/${ref.id}`;
  return section === "overview" ? base : `${base}/${section}`;
}

/** `club:7`, `me` — a context as one string, for a set or a React key. */
export function refKey(ref: ContextRef): string {
  return "id" in ref ? `${ref.kind}:${ref.id}` : ref.kind;
}

// ---------------------------------------------------------------- the switcher's search

/** From how many entries the switcher shows its search; with a site relation it is always
 *  there — the league office finds every object by it, not by a list (§2, #34). */
export const SEARCH_FROM = 8;

/** Whether the switcher shows its search box. */
export function showsSearch(switcher: Switcher, hasOffice: boolean): boolean {
  const count = switcher.head.length + switcher.clubs.length + switcher.series.length + switcher.events.length + switcher.recent.length;
  return hasOffice || count >= SEARCH_FROM;
}

/** Lower case, accents dropped, `ß` as `ss` — so *minderjahrige* finds *Minderjährige* and
 *  *Warnemunde* finds *Warnemünde*. */
export function fold(text: string): string {
  return text.normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase().replace(/ß/g, "ss");
}

function words(query: string): string[] {
  return fold(query).split(/\s+/).filter(Boolean);
}

/** A section of one of my contexts that matches: the entry it belongs to, its key, its
 *  label as shown. */
export type SectionHit = { entry: SwitcherEntry; section: string; label: string };

export type WorkspaceSearch = { contexts: SwitcherEntry[]; sections: SectionHit[] };

/** Story Z-10, #34: what the switcher offers for `query` among my own entries — the
 *  contexts whose name matches, and the sections of them whose label does.
 *
 *  Every word must appear (case and accents ignored), in the context's name or the
 *  section's label, and a section needs at least one word in its own label: otherwise
 *  typing *asvw* would list every section of ASVW. Only sections the person has
 *  (`sectionsFor` — the sidebar's own answer), never the *Overview*, which is the context
 *  hit itself. `nameOf` names an entry (*Me*, *League office* have no context name),
 *  `labelOf` a section in the language on screen. */
export function searchWorkspace(
  query: string,
  entries: readonly SwitcherEntry[],
  labelOf: (kind: WorkspaceKind, section: string) => string,
  nameOf: (entry: SwitcherEntry) => string,
): WorkspaceSearch {
  const terms = words(query);
  if (terms.length === 0) return { contexts: [], sections: [] };
  const contexts: SwitcherEntry[] = [];
  const sections: SectionHit[] = [];
  for (const entry of entries) {
    const name = fold([nameOf(entry), entry.context?.short_name ?? ""].join(" "));
    if (terms.every((w) => name.includes(w))) contexts.push(entry);
    const kind = entry.ref.kind;
    for (const section of sectionsFor(kind, entry.relations)) {
      if (section === "overview") continue;
      const label = labelOf(kind, section);
      const folded = fold(label);
      if (!terms.some((w) => folded.includes(w))) continue;
      if (terms.every((w) => folded.includes(w) || name.includes(w))) sections.push({ entry, section, label });
    }
  }
  return { contexts, sections };
}

// ---------------------------------------------------------------- recent, per browser

/** How many contexts Recent keeps, and how many sections Last visited. */
export const RECENT_MAX = 5;

/** A context in Recent, with the name it had when it was opened. */
export type RecentRef = ContextRef & { name?: string };

/** `ref` put first in `list`, once, the list cut to `max` — pure, the storage below only
 *  keeps it. */
export function pushRecent<T>(list: readonly T[], item: T, key: (t: T) => string, max = RECENT_MAX): T[] {
  return [item, ...list.filter((x) => key(x) !== key(item))].slice(0, max);
}

const RECENT_KEY = "sbl.workspace.recent";

/** The contexts this browser opened last (§2: per browser, decided) — a convenience, never
 *  needed to work: storage that is blocked or empty reads as nothing. */
export function readRecent(storage: Pick<Storage, "getItem"> | undefined = safeStorage()): RecentRef[] {
  try {
    const parsed: unknown = JSON.parse(storage?.getItem(RECENT_KEY) ?? "[]");
    return Array.isArray(parsed) ? parsed.filter(isRef).slice(0, RECENT_MAX) : [];
  } catch {
    return [];
  }
}

/** Remember that this browser opened `ref`, and what it was called then — Recent lists
 *  contexts no request of the switcher names. */
export function rememberRecent(
  ref: ContextRef,
  storage: Pick<Storage, "getItem" | "setItem"> | undefined = safeStorage(),
  name?: string,
): void {
  try {
    const entry = name ? { ...ref, name } : ref;
    storage?.setItem(RECENT_KEY, JSON.stringify(pushRecent(readRecent(storage), entry, refKey)));
  } catch {
    // A private window or blocked site data: Recent stays as it was.
  }
}

function safeStorage(): Storage | undefined {
  try {
    return typeof localStorage === "undefined" ? undefined : localStorage;
  } catch {
    return undefined;
  }
}

function isRef(x: unknown): x is ContextRef {
  if (!x || typeof x !== "object") return false;
  const r = x as { kind?: unknown; id?: unknown };
  if (r.kind === "me" || r.kind === "office") return true;
  return (r.kind === "club" || r.kind === "series" || r.kind === "event") && typeof r.id === "number";
}

// ---------------------------------------------------------------- to do (§4)

/** Whether an event of mine is live for the landing page: running (`live`), or a race day
 *  today while still planned — the day does not start with a search (§4, decided). */
export function isLive(c: MyContext, today: string): boolean {
  if (c.kind !== "event" || c.status === "cancelled" || c.status === "final") return false;
  if (c.status === "live") return true;
  return c.starts_on != null && c.starts_on <= today && today <= (c.ends_on ?? c.starts_on);
}

/** What *Live now* offers per relation, in the order the day needs them (§4's table). */
const LIVE_OFFER: readonly [readonly Holding[], readonly string[]][] = [
  [[Relation.admin, Relation.manager, Relation.race_officer], ["race-control", "results", "check-in", "notice-board"]],
  [[Relation.jury], ["notice-board", "results"]],
  [[Relation.helper], ["overview", "my-claims"]],
  [[SAILOR], ["crew"]],
  [[Relation.editor], ["news"]],
];

/** One block of *Live now*: the event, the sections my relations give me there (race
 *  control first for the race committee), and whether the public live view is offered —
 *  to those who sail or write. */
export type LiveBlock = { context: MyContext; sections: string[]; publicLive: boolean };

export function liveNow(contexts: readonly MyContext[], today: string): LiveBlock[] {
  return contexts
    .filter((c) => isLive(c, today))
    .map((c) => {
      const sections: string[] = [];
      for (const [holders, offer] of LIVE_OFFER) {
        if (!holders.some((h) => c.relations.includes(h as ContextRelation))) continue;
        for (const s of offer) if (!sections.includes(s) && hasSection("event", s, c.relations)) sections.push(s);
      }
      const publicLive = c.relations.includes(SAILOR) || c.relations.includes(Relation.editor);
      return { context: c, sections, publicLive };
    });
}

/** The to-dos grouped by the context they belong to, each group in the order its most
 *  urgent to-do came — the API sends them by severity, then date (§4). */
export type TodoGroup = { ref: ContextRef; todos: Todo[] };

export function groupTodos(todos: readonly Todo[]): TodoGroup[] {
  const groups = new Map<string, TodoGroup>();
  for (const todo of todos) {
    const ref: ContextRef =
      todo.context.kind === "me" || todo.context.kind === "office" || todo.context.id == null
        ? { kind: todo.context.kind === "office" ? "office" : "me" }
        : { kind: todo.context.kind, id: todo.context.id };
    const key = refKey(ref);
    if (!groups.has(key)) groups.set(key, { ref, todos: [] });
    groups.get(key)!.todos.push(todo);
  }
  return [...groups.values()];
}

/** A section this browser opened — for *Last visited*, straight to the section. Its words
 *  are kept as they were shown, so the list needs no request. */
export type Visit = { ref: ContextRef; section: string; name: string; label: string };

const VISITS_KEY = "sbl.workspace.visits";
const visitKey = (v: Visit) => `${refKey(v.ref)}/${v.section}`;

export function readVisits(storage: Pick<Storage, "getItem"> | undefined = safeStorage()): Visit[] {
  try {
    const parsed: unknown = JSON.parse(storage?.getItem(VISITS_KEY) ?? "[]");
    return Array.isArray(parsed)
      ? parsed
          .filter((v): v is Visit => !!v && isRef(v.ref) && typeof v.section === "string" && typeof v.name === "string" && typeof v.label === "string")
          .slice(0, RECENT_MAX)
      : [];
  } catch {
    return [];
  }
}

export function rememberVisit(visit: Visit, storage: Pick<Storage, "getItem" | "setItem"> | undefined = safeStorage()): void {
  try {
    storage?.setItem(VISITS_KEY, JSON.stringify(pushRecent(readVisits(storage), visit, visitKey)));
  } catch {
    // Blocked storage: nothing is remembered, nothing breaks.
  }
}

// ---------------------------------------------------------------- the old addresses

/** Which section each tab of the pages before #31 became — `/me/club/7?tab=money` was a
 *  real address, in bookmarks and mails, and now redirects to `/me/club/7/decide-claims`.
 *  A tab that split into several sections goes to the first. */
export const LEGACY_TAB_SECTION = {
  profile: { account: "account", documents: "documents", bank: "bank", waivers: "waivers", claims: "claims" },
  club: {
    members: "members",
    events: "crews",
    series: "squads",
    waivers: "waivers",
    claims: "my-claims",
    money: "decide-claims",
    hosting: "hosting",
  },
  series: { team: "team", events: "events", organize: "registrations" },
  event: { crew: "crew", claims: "my-claims", decide: "decide-claims", race: "race-control", organize: "general" },
} as const satisfies {
  profile: Record<string, Section<"me">>;
  club: Record<string, Section<"club">>;
  series: Record<string, Section<"series">>;
  event: Record<string, Section<"event">>;
};

// ---------------------------------------------------------------- the league office

/** A section of the league office — `Section<"office">`. */
export type OfficeSection = Section<"office">;

export type HasRole = (...roles: Role[]) => boolean;

/** `/office/<area>/new` — each reached from the "＋" of its section and leading back to
 *  it; there for someone who has that section (Story A-11, issue #32). */
export const OFFICE_NEW_PAGES = {
  clubs: "clubs",
  series: "series",
  events: "events",
  people: "people",
  news: "news",
} as const satisfies Record<string, OfficeSection>;

export type OfficeArea = keyof typeof OFFICE_NEW_PAGES;

/** Whether someone holding `office` — the site relations, `office.relations` of
 *  `GET /api/me/contexts`, empty without one — can use `/office/<area>/new`: its section
 *  is theirs. */
export function mayCreateIn(area: OfficeArea, office: readonly string[]): boolean {
  return office.length > 0 && hasSection("office", OFFICE_NEW_PAGES[area], office);
}

/** Who creates outside the office, by summary role, and where (`/me/<kind>/new`):
 *
 * - **an event** — a series' manager its acts, a club's organizer a stand-alone event
 *   their club hosts (Stories VA-6, A-6);
 * - **a post** — the editor of a series or an event, about that regatta (Story R-1,
 *   decided 2026-10-24).
 *
 * A summary role only says *somewhere*; which series, host or regatta may be picked is the
 * server's answer (`GET /api/events/create-options`, the post form's regattas) — the page
 * only needs to know the door is theirs. They have no office to go back to, so their page
 * leads back to My space. */
export const CREATE_OUTSIDE_OFFICE = {
  events: { roles: [Role.series_manager, Role.team_manager], path: "/me/event/new" },
  news: { roles: [Role.editor], path: "/me/news/new" },
} as const satisfies Partial<Record<OfficeArea, { roles: readonly Role[]; path: string }>>;

/** Whether this person can create in `area` outside the office (`CREATE_OUTSIDE_OFFICE`). */
export function mayCreateOutside(area: OfficeArea, hasRole: HasRole): boolean {
  const door = (CREATE_OUTSIDE_OFFICE as Partial<Record<OfficeArea, { roles: readonly Role[] }>>)[area];
  return Boolean(door && hasRole(...door.roles));
}

/** Whether this person can create in `area` at all — from the office, or outside it. */
export function mayCreate(area: OfficeArea, office: readonly string[], hasRole: HasRole): boolean {
  return mayCreateIn(area, office) || mayCreateOutside(area, hasRole);
}

/** Where an address of the administration before #32 lives now — `/admin` became
 *  `/office`: `/admin?tab=<section>` → `/office/<section>` (an unknown tab → `/office`),
 *  `/admin/<area>/new` → `/office/<area>/new`, `/admin/news/:id` → `/office/news/:id`;
 *  every other query parameter (`sort`, `q`, `page`) kept. `rest` is what followed
 *  `/admin/`, `search` the query string with or without its `?`. */
export function officeAddress(rest: string, search: string): string {
  const params = new URLSearchParams(search);
  // `sailors` became `people` with #42 — one person, whether they sail or not.
  const renamed = (area: string) => (area === "sailors" ? "people" : area);
  const segments = rest.split("/").filter(Boolean).map(renamed);
  if (params.get("tab")) params.set("tab", renamed(params.get("tab")!));
  let path = "/office";
  if (segments.length === 0) {
    const tab = params.get("tab");
    params.delete("tab");
    if (tab && tab !== "overview" && (OFFICE_SECTIONS as readonly string[]).includes(tab)) path = `/office/${tab}`;
  } else if (segments.length === 2 && segments[0] in OFFICE_NEW_PAGES && segments[1] === "new") {
    path = `/office/${segments[0]}/new`;
  } else if (segments.length === 2 && segments[0] === "news") {
    path = `/office/news/${segments[1]}`;
  }
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}
