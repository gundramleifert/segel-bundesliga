import { useMyContexts } from "../api/generated/sbl";
import type { MyContext } from "../api/types";
import { useAccount } from "../api/useApi";
import {
  hasSection,
  mayCreate,
  sectionPath,
  type HasRole,
  type OfficeArea,
  type Section,
} from "../lib/workspace";

/** Story B-18: the places of the site a handbook page can link to.
 *
 * **A page names a place, never a URL** — `[*Me* → *Waivers*](place:profile.waivers)`.
 * The visible words stay the click path a reader follows by hand; this registry turns the
 * name into an address *for the reader*: their own profile, *their* club's page (one per
 * club they have), the league office's section if they have it. Routes and tab keys change,
 * and a hundred hand-written addresses in two languages would drift without a sound; a
 * place is one line here.
 *
 * **Who may use a place is not decided here.** The section declarations in
 * `lib/workspace.ts` are what the screens are built from; a place only says which of them
 * it points at. A reader for whom the section does not exist gets the words, not a link — a
 * link ending in a 403 or an empty page is worse than none (Story A-12).
 *
 * `scripts/check-docs.py` reads the keys and paths of `PLACES` below (keep them literal,
 * one entry per line): every `place:<id>` in the store must be one, and a raw link to a
 * path a place covers is refused. Add a place only when a page names it.
 */

/** One place: the route as `App.tsx` writes it, and the section — typed by the route, so
 *  a section the context does not declare does not compile. */
export type PlaceDef =
  | { path: "/me" }
  | { path: "/me/profile"; section: Section<"me"> }
  | { path: "/me/club/:id"; section: Section<"club"> }
  | { path: "/me/series/:id"; section: Section<"series"> }
  | { path: "/me/event/:id"; section: Section<"event"> }
  | { path: "/office"; section?: Section<"office"> }
  | { path: `/office/${OfficeArea}/new` };

export const PLACES = {
  // My space and my own profile — any signed-in person (the help is only for them).
  "space": { path: "/me" },
  "profile.account": { path: "/me/profile", section: "account" },
  "profile.documents": { path: "/me/profile", section: "documents" },
  "profile.bank": { path: "/me/profile", section: "bank" },
  "profile.waivers": { path: "/me/profile", section: "waivers" },
  "profile.claims": { path: "/me/profile", section: "claims" },
  "profile.clubs": { path: "/me/profile", section: "clubs" },
  // My page in a club, a series, an event — one target per such context in my space.
  "club.people": { path: "/me/club/:id", section: "people" },
  "club.events": { path: "/me/club/:id", section: "crews" },
  "club.series": { path: "/me/club/:id", section: "squads" },
  "club.waivers": { path: "/me/club/:id", section: "waivers" },
  "club.claims": { path: "/me/club/:id", section: "my-claims" },
  "club.money": { path: "/me/club/:id", section: "decide-claims" },
  "club.minors": { path: "/me/club/:id", section: "minors" },
  "club.hosting": { path: "/me/club/:id", section: "hosting" },
  "club.payment-runs": { path: "/me/club/:id", section: "payment-runs" },
  "club.bank-account": { path: "/me/club/:id", section: "bank-account" },
  "club.page": { path: "/me/club/:id", section: "club-page" },
  "series.team": { path: "/me/series/:id", section: "team" },
  "series.events": { path: "/me/series/:id", section: "events" },
  "series.organize": { path: "/me/series/:id", section: "registrations" },
  "series.dates": { path: "/me/series/:id", section: "dates" },
  "series.scoring": { path: "/me/series/:id", section: "scoring" },
  "series.officials": { path: "/me/series/:id", section: "officials" },
  "event.crew": { path: "/me/event/:id", section: "crew" },
  "event.claims": { path: "/me/event/:id", section: "my-claims" },
  "event.decide": { path: "/me/event/:id", section: "decide-claims" },
  "event.race": { path: "/me/event/:id", section: "race-control" },
  "event.organize": { path: "/me/event/:id", section: "general" },
  "event.overview": { path: "/me/event/:id", section: "overview" },
  "event.clubs": { path: "/me/event/:id", section: "clubs" },
  "event.boats": { path: "/me/event/:id", section: "boats" },
  "event.pairing": { path: "/me/event/:id", section: "pairing" },
  "event.publication": { path: "/me/event/:id", section: "publication" },
  "event.people": { path: "/me/event/:id", section: "people" },
  "event.checkin": { path: "/me/event/:id", section: "check-in" },
  "event.results": { path: "/me/event/:id", section: "results" },
  "event.notice-board": { path: "/me/event/:id", section: "notice-board" },
  // The league office (Story A-11) — a section the reader has, a creation page they can
  // use. The ids keep their `admin.` from before #32: the handbook's pages name them.
  "admin": { path: "/office" },
  "admin.clubs": { path: "/office", section: "clubs" },
  "admin.series": { path: "/office", section: "series" },
  "admin.events": { path: "/office", section: "events" },
  "admin.sailors": { path: "/office", section: "people" },
  "admin.news": { path: "/office", section: "news" },
  "admin.media": { path: "/office", section: "media" },
  "admin.accounts": { path: "/office", section: "accounts" },
  "admin.new-club": { path: "/office/clubs/new" },
  "admin.new-series": { path: "/office/series/new" },
  "admin.new-event": { path: "/office/events/new" },
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
 *  gives the reader that section (`lib/workspace.ts`, Story Z-10); a section of the league
 *  office where the reader's site relations (`office`, empty without one) give it. Creating
 *  an event or a post is also theirs who create without an office (`CREATE_OUTSIDE_OFFICE`)
 *  — the office's address passes them on to theirs. */
export function resolvePlace(
  def: PlaceDef,
  hasRole: HasRole,
  contexts: readonly MyContext[],
  office: readonly string[] = [],
): PlaceTarget[] {
  const path = def.path;
  if (path === "/me") return [{ key: path, to: path }];
  if (path === "/me/profile") return [{ key: path, to: sectionPath({ kind: "me" }, def.section) }];
  if (path === "/office") {
    const section = "section" in def ? def.section : undefined;
    if (!office.length || (section && !hasSection("office", section, office))) return [];
    return [{ key: path, to: sectionPath({ kind: "office" }, section) }];
  }
  const creation = /^\/office\/(\w+)\/new$/.exec(path);
  if (creation) {
    const area = creation[1] as OfficeArea;
    return mayCreate(area, office, hasRole) ? [{ key: path, to: path }] : [];
  }

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
 *  (`GET /api/me/contexts`, Story Z-8 — its contexts and its `office`) and the account's
 *  roles. */
export function usePlace(id: string): PlaceState {
  const { account, loading, hasRole } = useAccount();
  const known = isPlaceId(id);
  const def: PlaceDef | undefined = known ? PLACES[id] : undefined;
  const needsContexts = Boolean(def && /^\/me\/\w+\/:id$|^\/office/.test(def.path));
  const contexts = useMyContexts({
    query: { enabled: Boolean(account) && needsContexts, staleTime: 5 * 60_000, refetchOnWindowFocus: false },
  });
  if (!def) return { status: "unknown" };
  if (loading || !account) return { status: "loading" };
  // A failed request leaves the words: nothing is known to be there for the reader.
  if (needsContexts && !contexts.data) return contexts.isError ? { status: "ready", targets: [] } : { status: "loading" };
  return { status: "ready", targets: resolvePlace(def, hasRole, contexts.data?.contexts ?? [], contexts.data?.office?.relations ?? []) };
}
