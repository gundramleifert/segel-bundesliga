// The site's editorial content — news, press, media, documents, the about texts.
//
// **News and press releases come from the API** — editorial writes them on the site
// (Story R-1). The rest is **static for now, shaped for an API later** (Story B-14):
// whether documents are the official notice board is an open question of issue #14. So
// every page reads its content through a hook that returns what a generated query returns
// — `{ data, error, loading }` — and renders it through `Async`; the day an endpoint
// exists, the hook's body becomes a generated query and no page changes.
//
// Content is data, not interface copy: an article stays in the language it was written
// in. The texts that describe the leagues and the association are given in both
// languages, because they stand where interface copy would.

import { keepPreviousData, useQueries, type QueryKey, type UseQueryOptions } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  getListLeagueMediaQueryOptions,
  getListPostsQueryOptions,
  useGetPost,
} from "../api/generated/sbl";
import type { PagePostSummary } from "../api/generated/model/pagePostSummary";
import type { PagePublicPicture } from "../api/generated/model/pagePublicPicture";
import type { PublicPicture } from "../api/generated/model/publicPicture";
import type { ApiError } from "../api/http";
import { PostKind, type Post, type PostSummary } from "../api/types";
import { errorText, useAsync, type AsyncState } from "../api/useApi";
import { DSBL_PHOTOS, OWN_PHOTOS, type Photo } from "./photos";

export type { Photo } from "./photos";
export { DSBL_PHOTOS, OWN_PHOTOS, SLIDES } from "./photos";

/** A text in both of the site's languages. */
export type Localized = { en: string; de: string };

/** The text in the reader's language, falling back to English. */
export function useLocalized() {
  const { i18n } = useTranslation();
  const german = i18n.language?.startsWith("de");
  return (text: Localized) => (german ? text.de : text.en);
}

const ready = <T,>(data: T): AsyncState<T> => ({ data, error: null, loading: false });

// ---------------------------------------------------------------- the association

export const BOARD = [
  { name: "Peter Weichsel", role: { en: "Chair", de: "Vorsitzender" }, photo: OWN_PHOTOS.chair },
  { name: "Markus Westerwalbesloh", role: { en: "Vice chair", de: "Stellv. Vorsitzender" }, photo: OWN_PHOTOS.viceChair },
  { name: "Tom Lukas Voigt", role: { en: "Treasurer", de: "Schatzmeister" }, photo: OWN_PHOTOS.treasurer },
];

// From deutsche-segelliga.de — the user's own site, so these texts are reused freely.
const ASSOCIATION = {
  founded: { en: "15 March 2014, Hamburg", de: "15. März 2014, Hamburg" },
  history: {
    en: "The Deutsche Segel-Bundesliga was started on 7 April 2013 by 17 founding clubs; the association followed on 15 March 2014 and has run the league on behalf of the Deutscher Segler-Verband since May 2014. It unites all 36 clubs of the 1. and 2. Liga.",
    de: "Die Deutsche Segel-Bundesliga wurde am 7. April 2013 von 17 Gründungsvereinen ins Leben gerufen; der Verein folgte am 15. März 2014 und richtet die Liga seit Mai 2014 im Auftrag des Deutschen Segler-Verbands aus. Er vereint alle 36 Vereine der 1. und 2. Liga.",
  },
  record: {
    en: "Record champion: Norddeutscher Regatta Verein, eight titles (2013, 2014, 2017, 2018, 2020, 2022, 2023, 2025).",
    de: "Rekordmeister: Norddeutscher Regatta Verein, acht Titel (2013, 2014, 2017, 2018, 2020, 2022, 2023, 2025).",
  },
  service: {
    en: "Pairing lists, results, live tracking, waivers and expense claims — the association's service for every club that runs its own regatta.",
    de: "Pairing-Listen, Ergebnisse, Live-Tracking, Haftungsausschlüsse und Auslagen — der Service des Vereins für jeden Club, der seine eigene Regatta ausrichtet.",
  },
};

export function useAssociation() {
  return ready(ASSOCIATION);
}

// ---------------------------------------------------------------- the leagues

export type LeagueAbout = { intro: Localized; facts: Localized[]; photo: Photo };

/** What a league is and what is at stake — condensed from deutsche-segelliga.de/wettbewerbe.
 *  Keyed by the league's slug; a league without an entry simply has no about text yet. */
const LEAGUE_ABOUT: Record<string, LeagueAbout> = {
  "1-liga": {
    photo: DSBL_PHOTOS.race,
    intro: {
      en: "The top of German club sailing since 2013: the best sailors of 18 clubs — Olympians, seasoned professionals and rising talents — race side by side for their club, on J/70s the league provides and rotates after every race.",
      de: "Die Spitze des deutschen Vereinssegelns seit 2013: Die besten Seglerinnen und Segler aus 18 Vereinen — Olympioniken, erfahrene Profis und junge Talente — segeln Seite an Seite für ihren Club, auf J/70, die die Liga stellt und nach jeder Wettfahrt tauscht.",
    },
    facts: [
      { en: "18 clubs, 6 matchdays, the German championship plate and SAILING Champions League places.", de: "18 Vereine, 6 Spieltage, die Meisterschale und Startplätze in der SAILING Champions League." },
      { en: "The last four go down to the 2. Liga.", de: "Die letzten vier steigen in die 2. Liga ab." },
    ],
  },
  "2-liga": {
    photo: DSBL_PHOTOS.aerial,
    intro: {
      en: "The second division of German club sailing: 18 clubs race the league's format — J/70, fleet race — at the same venues and weekends as the 1. Liga, for four places in it.",
      de: "Die zweite Liga des deutschen Vereinssegelns: 18 Vereine segeln im Format der Liga — J/70, Fleet Race — an denselben Orten und Wochenenden wie die 1. Liga, um vier Plätze in ihr.",
    },
    facts: [
      { en: "18 clubs, 5 matchdays, sailed alongside the 1. Liga's events.", de: "18 Vereine, 5 Spieltage, gesegelt bei den Events der 1. Liga." },
      { en: "The first four go up to the 1. Liga.", de: "Die ersten vier steigen in die 1. Liga auf." },
      { en: "Places 13–18 must requalify at the DSL-Pokal.", de: "Die Plätze 13–18 müssen sich beim DSL-Pokal neu qualifizieren." },
    ],
  },
  "junioren-liga": {
    photo: DSBL_PHOTOS.swimmer,
    intro: {
      en: "The talent school of German club sailing since 2016: sailors aged AK16 to AK21 race the league's format — J/70, fleet race — with a real path upwards. Under the patronage of the Deutsche Segel-Liga e.V.; the Heinz Nixdorf Verein provides the boats.",
      de: "Die Talentschmiede des deutschen Vereinssegelns seit 2016: Seglerinnen und Segler der AK16 bis AK21 segeln im Format der Liga — J/70, Fleet Race — mit einem echten Weg nach oben. Unter der Schirmherrschaft der Deutschen Segel-Liga e.V.; die Boote stellt der Heinz Nixdorf Verein.",
    },
    facts: [
      { en: "Open to youth teams of every German sailing club.", de: "Offen für Jugendteams aller deutschen Segelvereine." },
      { en: "The best teams qualify for the DSL-Pokal and the Youth SAILING Champions League.", de: "Die besten Teams qualifizieren sich für den DSL-Pokal und die Youth SAILING Champions League." },
      { en: "Each act is organised by the club that hosts it.", de: "Jeder Act wird vom ausrichtenden Verein organisiert." },
    ],
  },
  "dsl-pokal": {
    photo: DSBL_PHOTOS.aerial,
    intro: {
      en: "Where amateur meets professional, since 2017: one compact weekend in autumn, after the league season, in which clubs from every level race each other — and the way into the 2. Liga.",
      de: "Wo Amateure auf Profis treffen, seit 2017: ein kompaktes Wochenende im Herbst, nach der Ligasaison, an dem Vereine aller Ebenen gegeneinander segeln — und der Weg in die 2. Liga.",
    },
    facts: [
      { en: "Who starts: the best of the 1. Liga, the top and the threatened of the 2. Liga, the best junior teams, and clubs that qualify by pre-entry.", de: "Am Start: die Besten der 1. Liga, die Spitze und die Gefährdeten der 2. Liga, die besten Juniorenteams und Vereine aus der Vorqualifikation." },
      { en: "The best teams not yet in a Bundesliga earn a place in next season's 2. Liga.", de: "Die besten Teams, die noch in keiner Bundesliga segeln, erhalten einen Platz in der 2. Liga der nächsten Saison." },
      { en: "A trophy of its own — coveted by established league teams too.", de: "Ein eigener Pokal — begehrt auch bei etablierten Ligateams." },
    ],
  },
};

export function useLeagueAbout(league: string) {
  return ready(LEAGUE_ABOUT[league] ?? null);
}

/** The picture a league's pages fall back to. */
/** The same, outside a component — for a list of leagues. */
export const leagueAbout = (league: string) => LEAGUE_ABOUT[league] ?? null;

export const leaguePhoto = (league: string) => LEAGUE_ABOUT[league]?.photo ?? DSBL_PHOTOS.race;

/** Where a table marks promotion, relegation and requalification — the league's rules,
 *  per division (`Series.level`). Content for now; it belongs to the series' rules
 *  (`Series.scoring`) once someone needs to change it without a release. */
export type TableMarks = { promotion?: number; relegation?: number; requalify?: [number, number] };

const TABLE_MARKS: Record<string, Record<number, TableMarks>> = {
  // deutsche-segelliga.de/wettbewerbe: four down, four up, 13–18 of the 2. Liga requalify.
  "1-liga": { 1: { relegation: 4 } },
  "2-liga": { 2: { promotion: 4, requalify: [13, 18] } },
};

export const tableMarks = (league: string, level: number | null | undefined): TableMarks =>
  (level != null && TABLE_MARKS[league]?.[level]) || {};

// ---------------------------------------------------------------- news and press

/** An article as a list shows it — a card or a line. Written by editorial on the site
 *  (Story R-1) — the hooks below read `GET /api/posts` and turn a post into this shape.
 *  The text is not here: a list does not carry it, the article's own page reads it. */
export type ArticleSummary = {
  slug: string;
  title: string;
  date: string;
  /** The league's slug, or null for the association's own news (shown in every league). */
  league: string | null;
  teaser: string;
  photo: Photo;
  /** Written to fill the page, not real news — the article says so (Story B-14). */
  example?: boolean;
};

/** An article as its own page shows it. */
export type Article = ArticleSummary & {
  /** HTML from the editor, cleaned by the server on every write — shown as it is. */
  body: string;
  author?: string;
  quote?: { text: string; by: string };
};

/** A post's own picture, or its league's when it has none. */
function postPhoto(post: PostSummary): Photo {
  if (!post.photo_url) return leaguePhoto(post.league ?? MEMBER_LEAGUES[0]);
  return {
    src: post.photo_url,
    srcset: post.photo_srcset ?? undefined,
    alt: post.title,
    credit: post.photo_credit ?? "",
    license: "",
    page: "",
  };
}

function toSummary(post: PostSummary): ArticleSummary {
  return {
    slug: post.slug,
    title: post.title,
    date: post.published_on,
    league: post.league ?? null,
    teaser: post.teaser ?? "",
    photo: postPhoto(post),
    example: post.example,
  };
}

/** A post as its own page shows it — also what editorial's preview renders. */
export function articleOf(post: Post): Article {
  return {
    ...toSummary(post),
    body: post.body,
    author: post.author ?? undefined,
    quote: post.quote ? { text: post.quote, by: post.quote_by ?? "" } : undefined,
  };
}

/** A list read a page at a time (Story R-1: the news page reaches every post, not only
 *  the newest fifty). `more()` asks for the next page; the pages already read stay. */
export type Paged<T> = AsyncState<T[]> & {
  total: number;
  hasMore: boolean;
  loadingMore: boolean;
  more: () => void;
};

type PageOf = { items: unknown[]; total: number };

/** One query per page read so far, their items joined. ``key`` names the list: when it
 *  changes — another league — reading starts again from the first page. */
function usePages<P extends PageOf, R>(
  key: string,
  query: (offset: number) => UseQueryOptions<P, ApiError, P, QueryKey>,
  size: number,
  map: (item: P["items"][number]) => R,
): Paged<R> {
  const { t } = useTranslation();
  const [read, setRead] = useState({ key, pages: 1 });
  const pages = read.key === key ? read.pages : 1;
  const results = useQueries({
    queries: Array.from({ length: pages }, (_, page) => ({ ...query(page * size), placeholderData: keepPreviousData })),
  });
  const first = results[0];
  // Keyed on when each page last changed, so a page gets the same array back until one
  // does — the number of pages varies, and a dependency list may not.
  const stamp = results.map((r) => r.dataUpdatedAt).join();
  const items = useMemo(() => results.flatMap((r) => r.data?.items ?? []).map(map), [stamp, map]);
  const total = first?.data?.total ?? 0;
  return {
    data: first?.data ? items : null,
    error: first?.isError ? errorText(first.error, t("errors.loadFailed")) : null,
    loading: !!first?.isPending,
    total,
    hasMore: items.length < total,
    loadingMore: results.slice(1).some((r) => r.isPending),
    more: () => setRead({ key, pages: pages + 1 }),
  };
}

/** How many posts a list reads at a time. */
export const NEWS_PAGE = 12;

/** A league's news and the association's, newest first, a page at a time; without a
 *  league, everything. A card row reads `data` and needs only the first page. */
export function useNews(league?: string, size = NEWS_PAGE) {
  return usePages<PagePostSummary, ArticleSummary>(
    `news:${league ?? ""}:${size}`,
    (offset) => getListPostsQueryOptions({ kind: PostKind.news, league, limit: size, offset }),
    size,
    toSummary,
  );
}

/** A league's press releases and the association's, newest first — the press centre
 *  lists their dates and titles, and reads a release's text with `useArticle`. */
export function usePress(league: string, size = 20) {
  return usePages<PagePostSummary, ArticleSummary>(
    `press:${league}:${size}`,
    (offset) => getListPostsQueryOptions({ kind: PostKind.press, league, limit: size, offset }),
    size,
    toSummary,
  );
}

/** One published article, as the server answers it — `ArticleView` renders it, and
 *  `articleOf` turns it into the page's shape. `notFound` tells an unknown or withdrawn
 *  one (a 404) from a failure, so the page can lead back to the news for the one and say
 *  so for the other. */
export function useArticle(slug: string | undefined) {
  const query = useGetPost(slug ?? "", { query: { enabled: !!slug } });
  return { ...useAsync(query), notFound: query.error?.status === 404 };
}

export const PRESS_CONTACT = "presse@segelliga.example.com";

// ---------------------------------------------------------------- media

export type Video = { id: string; title: string; start: number };

// Embedded on deutsche-segelbundesliga.de; played muted as a background loop in the
// "video" setting, and with sound and controls on the media pages.
export const VIDEOS: Video[] = [
  { id: "gMxZptdnbxo", title: "1. Spieltag — Hamburg 2022", start: 30 },
  { id: "Vv0Fjvd1Q-0", title: "3. Spieltag — Travemünde 2022", start: 20 },
  { id: "IcKib7M-uB0", title: "3. Spieltag — Travemünde 2022, final day", start: 40 },
];

export function useVideos(_league: string) {
  return ready(VIDEOS);
}

/** A picture on a league's media page: the library's, with what it is of; or one of the
 *  site's own (`context` empty). */
export type GalleryPhoto = Photo & { id: string; context: string | null; width?: number; height?: number };

export const fromLibrary = (p: PublicPicture): GalleryPhoto => ({
  id: String(p.id),
  src: p.url,
  srcset: p.srcset,
  alt: p.alt,
  credit: p.credit ?? "",
  license: "",
  page: "",
  context: p.context ?? null,
  width: p.width,
  height: p.height,
});

const SITE_GALLERY: GalleryPhoto[] = Object.values(DSBL_PHOTOS).map((p) => ({ ...p, id: p.src, context: null }));

/** How many pictures the media page reads at a time. */
export const GALLERY_PAGE = 24;

/** A league's photos — the library's pictures of its regattas (Story R-3), newest regatta
 *  first, a page at a time; the site's own selection while it has none. `library` says
 *  which, so the page credits the site's pictures as before. */
export function useGallery(league: string, size = GALLERY_PAGE): Paged<GalleryPhoto> & { library: boolean } {
  const pages = usePages<PagePublicPicture, GalleryPhoto>(
    `gallery:${league}:${size}`,
    (offset) => getListLeagueMediaQueryOptions({ league, limit: size, offset }),
    size,
    fromLibrary,
  );
  if (pages.data && pages.total === 0) return { ...pages, ...ready(SITE_GALLERY), library: false };
  return { ...pages, library: true };
}

// ---------------------------------------------------------------- documents and notices

export type DocGroup = { title: Localized; docs: string[] };

const SEASON_DOCUMENTS: DocGroup[] = [
  { title: { en: "Rules", de: "Regeln" }, docs: ["League regulations", "Scoring and tie-breaks", "Promotion and relegation"] },
  { title: { en: "Notice of race", de: "Ausschreibung" }, docs: ["Season notice of race", "Amendment 1 (dates)"] },
  { title: { en: "Boats", de: "Boote" }, docs: ["J/70 charter terms", "Damage and deposit rules", "Boat handling guide"] },
  { title: { en: "Entry", de: "Meldung" }, docs: ["Squad registration deadline", "Liability waiver", "Advertising rules"] },
];

/** `example`: what is returned is placeholder content, and a page showing it says so —
 *  invented documents and jury decisions must never read as a real notice board. */
export function useSeasonDocuments(_league: string) {
  return ready({ groups: SEASON_DOCUMENTS, example: true });
}

export type Notice = { time: string; from: "race-committee" | "jury" | "organizer"; title: string; body: string };

const NOTICES: Notice[] = [
  { time: "Sun 07:50", from: "race-committee", title: "Postponement ashore", body: "AP ashore — no wind. Next signal not before 10:30." },
  { time: "Sat 18:05", from: "jury", title: "Decision protest 3", body: "A team is disqualified in race 14 (RRS 10). Score adjusted." },
  { time: "Sat 15:20", from: "jury", title: "Hearing schedule", body: "Protest 3 at 17:30, protest 4 at 17:45, in the jury room." },
  { time: "Sat 09:40", from: "organizer", title: "Amendment 2 to the sailing instructions", body: "SI 11.2: the leeward gate is replaced by a single mark to port. Takes effect from flight 4." },
  { time: "Sat 08:15", from: "race-committee", title: "First warning signal 10:00", body: "Racing area A. Briefing for helms at 09:00 in the club house." },
];

const EVENT_DOCUMENTS = ["Notice of race", "Sailing instructions", "Amendment 1", "Amendment 2", "Entry list"];

/** A matchday's notice board, newest first, and its documents. Placeholders until
 *  issue #14's question 5 (is this the official notice board?) is answered. */
export function useActNotices(_eventIds: number[]) {
  return ready({ notices: NOTICES, documents: EVENT_DOCUMENTS, example: true });
}

/** The association's members are the clubs of the 1. and 2. Liga
 *  (`docs/site-structure.md`) — content, because membership has no model of its own yet.
 *  The first also hosts the association's own news, which belongs to no league. */
export const MEMBER_LEAGUES = ["1-liga", "2-liga"] as const;
