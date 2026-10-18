import { EventStatus, type EventSummary, type LeagueSeason } from "../api/types";

/** The site's URL scheme (`docs/site-structure.md`, Stories B-13–B-16). Route words are
 *  English; the league's slug is data. One place, so a link cannot drift from its route. */
export const href = {
  home: () => "/",
  about: (league?: string) => (league ? `/${league}/about` : "/about"),
  league: (league: string) => `/${league}`,
  standings: (league: string, year?: number) => (year ? `/${league}/${year}/standings` : `/${league}/standings`),
  season: (league: string, year?: number) => (year ? `/${league}/${year}/season` : `/${league}/season`),
  noticeBoard: (league: string) => `/${league}/notice-board`,
  clubs: (league: string) => `/${league}/clubs`,
  news: (league: string) => `/${league}/news`,
  article: (league: string, slug: string) => `/${league}/news/${slug}`,
  media: (league: string) => `/${league}/media`,
  press: (league: string) => `/${league}/press`,
  live: (league: string) => `/${league}/live`,
  results: (league: string) => `/${league}/results`,
  act: (league: string, year: number, act: string, tab?: string) =>
    `/${league}/${year}/${act}${tab ? `/${tab}` : ""}`,
  /** An event in no league keeps its own page (Story B-15). */
  event: (id: number, tab?: string) => `/events/${id}${tab ? `/${tab}` : ""}`,
  club: (id: number) => `/clubs/${id}`,
};

/** Where an act stands, from its events' states: one live makes it live, all closed make
 *  it done. `next` is the first act still ahead — there is only ever one. */
export type ActState = "live" | "done" | "next" | "planned" | "cancelled";

/** One act of a league's year: the events of its series that share a matchday — the 1.
 *  and the 2. Liga sail the same weekend at the same venue, and that is one page. */
export type Act = {
  slug: string;
  matchday: number | null;
  events: EventSummary[];
  state: ActState;
  first: EventSummary;
};

/** The acts of a league's year, in date order. An event without a matchday stands as an
 *  act of its own (`event-<id>`), so nothing the league published goes missing. */
export function actsOf(season: LeagueSeason): Act[] {
  const groups = new Map<string, EventSummary[]>();
  for (const event of season.events) {
    const key = actSlug(event);
    groups.set(key, [...(groups.get(key) ?? []), event]);
  }
  // Each act's events in the order of the year's series: the top division first.
  const order = new Map(season.series.map((s, i) => [s.id, i]));
  const acts = [...groups.entries()].map(([slug, events]) => {
    events.sort((a, b) => (order.get(a.series?.id ?? -1) ?? 99) - (order.get(b.series?.id ?? -1) ?? 99));
    const first = events[0];
    return { slug, matchday: first.matchday ?? null, events, first, state: stateOf(events) };
  });
  acts.sort((a, b) => (a.first.starts_on ?? "9999").localeCompare(b.first.starts_on ?? "9999"));
  const next = acts.find((act) => act.state === "planned");
  if (next) next.state = "next";
  return acts;
}

/** The act an event belongs to, as its address names it: `act-<matchday>`, or
 *  `event-<id>` for one without a matchday — a cup's one weekend has one page, not two. */
export const actSlug = (event: EventSummary) => (event.matchday != null ? `act-${event.matchday}` : `event-${event.id}`);

/** Where the events of an act stand together. */
export function stateOf(events: EventSummary[]): ActState {
  if (events.some((e) => e.status === EventStatus.live)) return "live";
  if (events.every((e) => e.status === EventStatus.cancelled)) return "cancelled";
  if (events.every((e) => e.status === EventStatus.final || e.status === EventStatus.cancelled)) return "done";
  return "planned";
}

/** The act that is running, else the next one, else the last. */
export const currentAct = (acts: Act[]) =>
  acts.find((a) => a.state === "live") ?? acts.find((a) => a.state === "next") ?? acts[acts.length - 1] ?? null;

/** The last act with results. */
export const lastSailed = (acts: Act[]) => [...acts].reverse().find((a) => a.state === "done") ?? null;

/** Whether racing has begun — the matchday page then opens on its results. */
export const hasResults = (act: Act) => act.state === "live" || act.state === "done";
