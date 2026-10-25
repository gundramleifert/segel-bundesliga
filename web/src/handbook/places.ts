import { useMyContexts } from "../api/generated/sbl";
import type { MyContext } from "../api/types";
import { useAccount } from "../api/useApi";
import {
  adminTabs,
  hasSection,
  mayCreateIn,
  sectionPath,
  type AdminArea,
  type AdminTab,
  type HasRole,
  type Section,
} from "../lib/workspace";

/** Story B-18: the places of the site a handbook page can link to.
 *
 * **A page names a place, never a URL** — `[*Me* → *Waivers*](place:profile.waivers)`.
 * The visible words stay the click path a reader follows by hand; this registry turns the
 * name into an address *for the reader*: their own profile, *their* club's page (one per
 * club they have), the administration's tab if they have it. Routes and tab keys change,
 * and a hundred hand-written addresses in two languages would drift without a sound; a
 * place is one line here.
 *
 * **Who may use a place is not decided here.** The tab declarations in
 * `lib/workspace.ts` are what the screens are built from; a place only says which of them
 * it points at. A reader for whom the tab does not exist gets the words, not a link — a
 * link ending in a 403 or an empty page is worse than none (Story A-12).
 *
 * `scripts/check-docs.py` reads the keys and paths of `PLACES` below (keep them literal,
 * one entry per line): every `place:<id>` in the store must be one, and a raw link to a
 * path a place covers is refused. Add a place only when a page names it.
 */

/** One place: the route as `App.tsx` writes it, and the tab — typed by the route, so a tab
 *  the screen does not declare does not compile. */
export type PlaceDef =
  | { path: "/me" }
  | { path: "/me/profile"; section: Section<"me"> }
  | { path: "/me/club/:id"; section: Section<"club"> }
  | { path: "/me/series/:id"; section: Section<"series"> }
  | { path: "/me/event/:id"; section: Section<"event"> }
  | { path: "/admin"; tab?: AdminTab }
  | { path: `/admin/${AdminArea}/new` };

export const PLACES = {
  // My space and my own profile — any signed-in person (the help is only for them).
  "space": { path: "/me" },
  "profile.account": { path: "/me/profile", section: "account" },
  "profile.documents": { path: "/me/profile", section: "documents" },
  "profile.bank": { path: "/me/profile", section: "bank" },
  "profile.waivers": { path: "/me/profile", section: "waivers" },
  "profile.claims": { path: "/me/profile", section: "claims" },
  // My page in a club, a series, an event — one target per such context in my space.
  "club.members": { path: "/me/club/:id", section: "members" },
  "club.events": { path: "/me/club/:id", section: "crews" },
  "club.series": { path: "/me/club/:id", section: "squads" },
  "club.waivers": { path: "/me/club/:id", section: "waivers" },
  "club.claims": { path: "/me/club/:id", section: "my-claims" },
  "club.money": { path: "/me/club/:id", section: "decide-claims" },
  "series.team": { path: "/me/series/:id", section: "team" },
  "series.events": { path: "/me/series/:id", section: "events" },
  "series.organize": { path: "/me/series/:id", section: "registrations" },
  "event.crew": { path: "/me/event/:id", section: "crew" },
  "event.claims": { path: "/me/event/:id", section: "my-claims" },
  "event.decide": { path: "/me/event/:id", section: "decide-claims" },
  "event.race": { path: "/me/event/:id", section: "race-control" },
  "event.organize": { path: "/me/event/:id", section: "general" },
  // The administration — a tab the reader has, a creation page they can use.
  "admin": { path: "/admin" },
  "admin.clubs": { path: "/admin", tab: "clubs" },
  "admin.series": { path: "/admin", tab: "series" },
  "admin.events": { path: "/admin", tab: "events" },
  "admin.sailors": { path: "/admin", tab: "sailors" },
  "admin.news": { path: "/admin", tab: "news" },
  "admin.media": { path: "/admin", tab: "media" },
  "admin.accounts": { path: "/admin", tab: "accounts" },
  "admin.new-club": { path: "/admin/clubs/new" },
  "admin.new-series": { path: "/admin/series/new" },
  "admin.new-event": { path: "/admin/events/new" },
} as const satisfies Record<string, PlaceDef>;

export type PlaceId = keyof typeof PLACES;

/** Where a place leads this reader: the address, and — when there are several, one per
 *  club, series or event — the context's name to tell them apart. */
export type PlaceTarget = { to: string; name?: string; key: string };

/** `loading` while the reader's contexts are still on their way — render the words then,
 *  never a link that may turn out wrong; `unknown` for an id no place has. */
export type PlaceState =
  | { status: "loading" }
  | { status: "unknown" }
  | { status: "ready"; targets: PlaceTarget[] };

/** The targets of one place for a reader — pure, so the rule reads in one piece. A section
 *  of a club, series or event is there for each of mine where the workspace's declaration
 *  gives the reader that section (`lib/workspace.ts`, Story Z-10). */
export function resolvePlace(def: PlaceDef, hasRole: HasRole, contexts: readonly MyContext[]): PlaceTarget[] {
  const path = def.path;
  if (path === "/me") return [{ key: path, to: path }];
  if (path === "/me/profile") return [{ key: path, to: sectionPath({ kind: "me" }, def.section) }];
  if (path === "/admin") {
    const tab = "tab" in def ? def.tab : undefined;
    const tabs = adminTabs(hasRole);
    if (!tabs.length || (tab && !tabs.includes(tab))) return [];
    return [{ key: path, to: tab ? `${path}?tab=${tab}` : path }];
  }
  const creation = /^\/admin\/(\w+)\/new$/.exec(path);
  if (creation) return mayCreateIn(creation[1] as AdminArea, hasRole) ? [{ key: path, to: path }] : [];

  const kind = /^\/me\/(club|series|event)\/:id$/.exec(path)?.[1] as "club" | "series" | "event";
  const section = (def as { section: string }).section;
  return contexts
    .filter((c) => c.kind === kind && hasSection(kind, section, c.relations))
    .map((c) => ({ key: `${kind}-${c.id}`, to: sectionPath({ kind, id: c.id }, section), name: c.name }));
}

export function isPlaceId(id: string): id is PlaceId {
  return Object.hasOwn(PLACES, id);
}

/** A place's targets for the signed-in reader, from the same answer my space uses
 *  (`GET /api/me/contexts`, Story Z-8) and the account's roles. */
export function usePlace(id: string): PlaceState {
  const { account, loading, hasRole } = useAccount();
  const known = isPlaceId(id);
  const def: PlaceDef | undefined = known ? PLACES[id] : undefined;
  const needsContexts = Boolean(def && /^\/me\/\w+\/:id$/.test(def.path));
  const contexts = useMyContexts({
    query: { enabled: Boolean(account) && needsContexts, staleTime: 5 * 60_000, refetchOnWindowFocus: false },
  });
  if (!def) return { status: "unknown" };
  if (loading || !account) return { status: "loading" };
  // A failed request leaves the words: nothing is known to be there for the reader.
  if (needsContexts && !contexts.data) return contexts.isError ? { status: "ready", targets: [] } : { status: "loading" };
  return { status: "ready", targets: resolvePlace(def, hasRole, contexts.data?.contexts ?? []) };
}
