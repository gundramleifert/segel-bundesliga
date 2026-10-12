// The site's editorial content — news, press, media, documents, the about texts.
//
// **Static for now, shaped for an API later** (Story B-14). Nothing here has a backend
// yet: who writes news and releases, and whether documents are the official notice board,
// are open questions of issue #14. So every page reads this content through a hook that
// returns what a generated query returns — `{ data, error, loading }` — and renders it
// through `Async`. The day an endpoint exists, the hook's body becomes
// `useAsync(useListNews({ league }))` and no page changes.
//
// Content is data, not interface copy: an article stays in the language it was written
// in. The texts that describe the leagues and the association are given in both
// languages, because they stand where interface copy would.

import { useTranslation } from "react-i18next";

import type { AsyncState } from "../api/useApi";
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
  dsbl: {
    photo: DSBL_PHOTOS.race,
    intro: {
      en: "The top of German club sailing since 2013: the best sailors of 36 clubs — Olympians, seasoned professionals and rising talents — race side by side for their club, on J/70s the league provides and rotates after every race.",
      de: "Die Spitze des deutschen Vereinssegelns seit 2013: Die besten Seglerinnen und Segler aus 36 Vereinen — Olympioniken, erfahrene Profis und junge Talente — segeln Seite an Seite für ihren Club, auf J/70, die die Liga stellt und nach jeder Wettfahrt tauscht.",
    },
    facts: [
      { en: "1. Liga: 18 clubs, 6 matchdays, the German championship plate and SAILING Champions League places.", de: "1. Liga: 18 Vereine, 6 Spieltage, die Meisterschale und Startplätze in der SAILING Champions League." },
      { en: "2. Liga: 18 clubs, 5 matchdays, sailed alongside the 1. Liga's events.", de: "2. Liga: 18 Vereine, 5 Spieltage, gesegelt bei den Events der 1. Liga." },
      { en: "The last four of the 1. Liga go down, the first four of the 2. Liga go up.", de: "Die letzten vier der 1. Liga steigen ab, die ersten vier der 2. Liga steigen auf." },
      { en: "Places 13–18 of the 2. Liga must requalify at the DSL-Pokal.", de: "Die Plätze 13–18 der 2. Liga müssen sich beim DSL-Pokal neu qualifizieren." },
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
export const leaguePhoto = (league: string) => LEAGUE_ABOUT[league]?.photo ?? DSBL_PHOTOS.race;

/** Where a table marks promotion, relegation and requalification — the league's rules,
 *  per division (`Series.level`). Content for now; it belongs to the series' rules
 *  (`Series.scoring`) once someone needs to change it without a release. */
export type TableMarks = { promotion?: number; relegation?: number; requalify?: [number, number] };

const TABLE_MARKS: Record<string, Record<number, TableMarks>> = {
  // deutsche-segelliga.de/wettbewerbe: four down, four up, 13–18 of the 2. Liga requalify.
  dsbl: { 1: { relegation: 4 }, 2: { promotion: 4, requalify: [13, 18] } },
};

export const tableMarks = (league: string, level: number | null | undefined): TableMarks =>
  (level != null && TABLE_MARKS[league]?.[level]) || {};

// ---------------------------------------------------------------- news

export type Article = {
  slug: string;
  title: string;
  date: string;
  /** The league's slug, or null for the association's own news (shown in every league). */
  league: string | null;
  teaser: string;
  photo: Photo;
  body: string[];
};

const PLACEHOLDER =
  "Placeholder text for the article. A real article is written by the league office and carries a byline, a date, the matchday it belongs to and its photos.";

const NEWS: Article[] = [
  {
    // The association's real article, from deutsche-segelliga.de/category/news.
    slug: "neuer-vorstand-gewaehlt",
    title: "Neuer Vorstand gewählt – es geht los!",
    date: "2026-01-27",
    league: null,
    teaser: "Was für ein Tag in Düsseldorf! Mitten im Trubel der boot haben wir uns mit 34 von 36 Vereinen getroffen.",
    photo: OWN_PHOTOS.title,
    body: [
      "Was für ein Tag in Düsseldorf! Mitten im Trubel der boot haben wir uns mit 34 von 36 Vereinen getroffen – und gemeinsam die Weichen für die Zukunft der Segel-Bundesliga gestellt.",
      "Von Gundram Leifert.",
    ],
  },
  {
    slug: "nrv-takes-the-lead",
    title: "NRV takes the lead after a perfect Sunday",
    date: "2026-09-21",
    league: "dsbl",
    teaser: "Six wins in eight races — and the table has a new name at the top.",
    photo: DSBL_PHOTOS.podium,
    body: ["Six wins in eight races — and the table has a new name at the top.", PLACEHOLDER],
  },
  {
    slug: "promotion-race",
    title: "Promotion race: three clubs within two points",
    date: "2026-09-14",
    league: "dsbl",
    teaser: "Before the final act, nothing is decided.",
    photo: DSBL_PHOTOS.race,
    body: ["Before the final act, nothing is decided.", PLACEHOLDER],
  },
  {
    slug: "junioren-liga-champion",
    title: "Junioren-Liga crowns its champion on the Alster",
    date: "2026-08-30",
    league: "junioren-liga",
    teaser: "The youngest crew in the field wins the last flight and the title.",
    photo: DSBL_PHOTOS.swimmer,
    body: ["The youngest crew in the field wins the last flight and the title.", PLACEHOLDER],
  },
  {
    slug: "dsl-pokal-registration",
    title: "DSL-Pokal: registration opens",
    date: "2026-08-12",
    league: "dsl-pokal",
    teaser: "Every member club can enter one crew. Deadline 31 January.",
    photo: DSBL_PHOTOS.aerial,
    body: ["Every member club can enter one crew. Deadline 31 January.", PLACEHOLDER],
  },
  {
    slug: "live-tracking",
    title: "Live tracking: every boat on the map, from every phone",
    date: "2026-07-28",
    league: null,
    teaser: "From this season the tracker is the sailor's own phone.",
    photo: DSBL_PHOTOS.camera,
    body: ["From this season the tracker is the sailor's own phone.", PLACEHOLDER],
  },
];

const byDate = <T extends { date: string }>(items: T[]) => [...items].sort((a, b) => b.date.localeCompare(a.date));

/** A league's news and the association's, newest first; without a league, everything. */
export function useNews(league?: string) {
  return ready(byDate(NEWS.filter((n) => !league || n.league === league || n.league === null)));
}

export function useArticle(slug: string | undefined) {
  return ready(NEWS.find((n) => n.slug === slug) ?? null);
}

// ---------------------------------------------------------------- press

export type Release = { title: string; date: string; body: string };

const PRESS: Release[] = [
  { title: "Act 5: NRV takes over the lead", date: "2026-09-21", body: "Placeholder text of the release: the facts in the first paragraph, a quote, the next dates, and the press contact." },
  { title: "Season 2027: calendar and venues confirmed", date: "2026-09-02", body: "Placeholder text of the release: the facts in the first paragraph, a quote, the next dates, and the press contact." },
  { title: "Media kit 2026: logos, fact sheet, contacts", date: "2026-04-01", body: "Placeholder text of the release: the facts in the first paragraph, a quote, the next dates, and the press contact." },
];

export function usePress(_league: string) {
  return ready(byDate(PRESS));
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

export function useGallery(_league: string) {
  return ready(Object.values(DSBL_PHOTOS));
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

/** The association's members are the clubs of this league's divisions
 *  (`docs/site-structure.md`) — content, because membership has no model of its own yet. */
export const MEMBER_LEAGUE = "dsbl";
