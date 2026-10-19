import { Role } from "../api/types";

/** Who sees which tab — of my profile, of my page in a club, a series or an event, and of
 *  the administration.
 *
 * **Declared once, read twice.** The screens (`pages/me/Contexts.tsx`, `pages/Admin.tsx`)
 * build their tabs from these declarations, and the handbook's places
 * (`handbook/places.ts`, Story B-18) decide from the very same ones whether a reader gets
 * a link to a tab or plain words. A second copy of these rules in the help would drift,
 * and a help link that ends on a tab the reader does not have is worse than none — Story
 * A-12's rule. Here only the *keys* and the *relations*; labels and panels stay with the
 * screens.
 */

/** A tab of a context page: shown when I hold one of `for` there (`sailor` included —
 *  sailing there, Story Z-8); without `for`, always. */
export type TabRule = { readonly for?: readonly string[] };

/** The organizers of a club, a series or an event: its `admin` and its `manager`. */
export const ORGANIZERS = ["admin", "manager"] as const;

/** Whether a tab with this rule is there for someone holding `relations`. */
export function tabVisible(rule: TabRule, relations: readonly string[]): boolean {
  return !rule.for || rule.for.some((r) => relations.includes(r));
}

/** `/me/profile` — mine alone, so every tab is there for every signed-in person. */
export const PROFILE_TABS = {
  account: {},
  documents: {},
  bank: {},
  waivers: {},
  claims: {},
} as const satisfies Record<string, TabRule>;

/** `/me/club/:id`. The club's own tabs are for whoever is *in* it — a member or one of its
 *  organizers (`GET /api/clubs/mine` answers the same: member or manager, an admin being
 *  both); a treasurer who is neither gets the money only (Story V-12). */
export const CLUB_TABS = {
  members: { for: ["member", ...ORGANIZERS] },
  events: { for: ["member", ...ORGANIZERS] },
  series: { for: ["member", ...ORGANIZERS] },
  waivers: { for: ORGANIZERS },
  claims: { for: ["member"] },
  money: { for: [...ORGANIZERS, "treasurer"] },
} as const satisfies Record<string, TabRule>;

/** `/me/series/:id`. */
export const SERIES_TABS = {
  team: { for: ["sailor"] },
  events: {},
  organize: { for: ORGANIZERS },
} as const satisfies Record<string, TabRule>;

/** `/me/event/:id`. Those who work the event file claims on it (Story F-2); sailing is not
 *  work. */
export const EVENT_TABS = {
  crew: { for: ["sailor"] },
  claims: { for: ["admin", "manager", "treasurer", "race_officer", "jury", "helper"] },
  decide: { for: [...ORGANIZERS, "treasurer"] },
  race: { for: [...ORGANIZERS, "race_officer"] },
  organize: { for: ORGANIZERS },
} as const satisfies Record<string, TabRule>;

export const CONTEXT_TABS = { club: CLUB_TABS, series: SERIES_TABS, event: EVENT_TABS } as const;

export type ContextKind = keyof typeof CONTEXT_TABS;
export type ProfileTab = keyof typeof PROFILE_TABS;
export type ClubTab = keyof typeof CLUB_TABS;
export type SeriesTab = keyof typeof SERIES_TABS;
export type EventTab = keyof typeof EVENT_TABS;

/** `{ key, for }` of one tab, for a screen to spread into its section. */
export function tabRule<T extends Record<string, TabRule>, K extends keyof T & string>(
  tabs: T,
  key: K,
): { key: K; for?: readonly string[] } {
  return { key, for: tabs[key].for };
}

// ---------------------------------------------------------------- administration

/** The areas of the administration. Also the values `?tab=` accepts — an unknown one falls
 *  back to the first tab rather than erroring (Story A-11). */
export type AdminTab = "clubs" | "series" | "events" | "sailors" | "news" | "media" | "accounts";

export type HasRole = (...roles: Role[]) => boolean;

/** The summary roles the administration has something for (Story A-12). Read by the
 *  account menu (whether to offer the link), by the administration's own guard (whether to
 *  let someone in) and by the help's places: copies would drift, and a link that ends in a
 *  403 is worse than no link. */
export const ADMIN_ROLES: readonly Role[] = [
  Role.admin,
  Role.editor,
  Role.series_manager,
  Role.event_manager,
  Role.jury,
];

/** The administration's tabs this person has, in the order the work happens (Story A-11).
 *  The league office sees every area; a series' organizer its series and events; the
 *  organizer or jury of one event the events tab alone — a tab a role may not use does not
 *  exist for it. *News* and *Media* are editorial's (Stories R-1, R-2), *Accounts* the admin's alone. Nobody
 *  outside `ADMIN_ROLES` has any. */
export function adminTabs(hasRole: HasRole): AdminTab[] {
  if (!hasRole(...ADMIN_ROLES)) return [];
  const tabs: AdminTab[] = hasRole(Role.admin, Role.editor)
    ? ["clubs", "series", "events", "sailors", "news", "media"]
    : hasRole(Role.series_manager)
      ? ["series", "events"]
      : ["events"];
  if (hasRole(Role.admin)) tabs.push("accounts");
  return tabs;
}

/** `/admin/<area>/new` — reached from its area's tab, and the series page for the site's
 *  `admin` alone (Stories A-4, A-6: an editor's *Series* tab only explains who creates
 *  one). */
export const ADMIN_NEW_PAGES = {
  clubs: { tab: "clubs", adminOnly: false },
  series: { tab: "series", adminOnly: true },
  events: { tab: "events", adminOnly: false },
  sailors: { tab: "sailors", adminOnly: false },
  news: { tab: "news", adminOnly: false },
} as const satisfies Record<string, { tab: AdminTab; adminOnly: boolean }>;

export type AdminArea = keyof typeof ADMIN_NEW_PAGES;

/** Whether this person can use `/admin/<area>/new`: its tab is theirs, and an admin-only
 *  page needs the admin. */
export function mayCreateIn(area: AdminArea, hasRole: HasRole): boolean {
  const page = ADMIN_NEW_PAGES[area];
  return adminTabs(hasRole).includes(page.tab) && (!page.adminOnly || hasRole(Role.admin));
}
