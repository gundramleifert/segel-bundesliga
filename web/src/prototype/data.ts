// Mock content for the option-E prototype (issue #14). The structure is the point; the
// content is invented except where noted. Throwaway, like the wireframes: the real pages
// are built from stories once the open questions of #14 are answered.

import { NEWS as WF_NEWS, PRESS as WF_PRESS, type Photo, type Row } from "../wireframes/data";

const DSBL_UPLOADS = "https://deutsche-segelbundesliga.de/wp-content/uploads";

const dsbl = (path: string, alt: string, credit = "Deutsche Segel-Bundesliga"): Photo => ({
  src: `${DSBL_UPLOADS}/${path}`,
  alt,
  credit,
  license: "all rights reserved",
  page: "https://deutsche-segelbundesliga.de/media/",
});

// The league's own pictures, from deutsche-segelbundesliga.de/media and its home page.
// Linked, never copied: this repository is public, and these are not freely licensed.
// Three exist only as originals of 3–5 MB — fine for a prototype, not for the real site.
export const DSBL_PHOTOS = {
  race: dsbl("2026/07/DSC06520-1536x1024.jpg", "NRV's J/70 racing upwind"),
  aerial: dsbl("2025/03/BundelLiga_Berlin_Day1_HR@Adam.Burdylo-115.jpg", "J/70 fleet from above, Berlin", "Adam Burdylo"),
  podium: dsbl("2026/08/DSC07807-1536x1024.jpg", "Podium with BYC, NRV and NSC"),
  swimmer: dsbl("2025/03/SBL211971411-0964-1536x1024.jpg", "A sailor in the water beside the league's mark"),
  studio: dsbl("2025/03/SBL182931401-6308-2.jpg", "The live broadcast studio"),
  camera: dsbl("2025/03/SBL182911202-2694.jpg", "A cameraman filming from a RIB"),
} satisfies Record<string, Photo>;

const own = (file: string, alt: string): Photo => ({
  src: `/prototype-media/${file}`,
  alt,
  credit: "Deutsche Segel-Liga e.V.",
  license: "the association's own",
  page: "https://deutsche-segelliga.de/",
});

// From deutsche-segelliga.de — the user's own site, so these are copied, not linked.
export const DSL_PHOTOS = {
  title: own("titelbild.jpg", "J/70 racing close, spray flying"),
} satisfies Record<string, Photo>;

export const BOARD = [
  { name: "Peter Weichsel", role: "Chair", photo: own("DSF4018-2.jpg", "Peter Weichsel") },
  { name: "Markus Westerwalbesloh", role: "Vice chair", photo: own("DSF3979.jpg", "Markus Westerwalbesloh") },
  { name: "Tom Lukas Voigt", role: "Treasurer", photo: own("DSF4037.jpg", "Tom Lukas Voigt") },
];

export const ASSOCIATION = {
  founded: "15 March 2014, Hamburg",
  clubs: 36,
  competitions: 4,
  history:
    "The Deutsche Segel-Bundesliga was started on 7 April 2013 by 17 founding clubs; the association followed on 15 March 2014 and has run the league on behalf of the Deutscher Segler-Verband since May 2014. It unites all 36 clubs of the 1. and 2. Liga.",
  record: "Record champion: Norddeutscher Regatta Verein, eight titles (2013, 2014, 2017, 2018, 2020, 2022, 2023, 2025).",
};

export const SLIDES: Photo[] = [DSBL_PHOTOS.race, DSL_PHOTOS.title, DSBL_PHOTOS.aerial, DSBL_PHOTOS.podium];

export type YouTube = { id: string; title: string; start: number };

// Embedded on deutsche-segelbundesliga.de; played muted as a background loop in the
// "video" setting, and with sound and controls in the media pages.
export const VIDEOS: YouTube[] = [
  { id: "gMxZptdnbxo", title: "1. Spieltag — Hamburg 2022", start: 30 },
  { id: "Vv0Fjvd1Q-0", title: "3. Spieltag — Travemünde 2022", start: 20 },
  { id: "IcKib7M-uB0", title: "3. Spieltag — Travemünde 2022, final day", start: 40 },
];

export type Division = { slug: string; short: string; name: string; rows: Row[] };
export type ActState = "done" | "next" | "live" | "planned";
export type Act = {
  slug: string;
  title: string;
  venue: string;
  water: string;
  host: string;
  dates: string;
  state: ActState;
  divisions: string[];
};
export type ProtoLeague = {
  slug: string;
  short: string;
  name: string;
  tagline: string;
  photo: Photo;
  divisions: Division[];
  acts: Act[];
  about: About;
};

// The member clubs of 2026, from deutsche-segelliga.de/ueber-uns/mitgliedsvereine (the
// user's own site — reused with permission). The points are invented.
const CLUBS_1: [string, string][] = [
  ["NRV", "Norddeutscher Regatta Verein"], ["BYC (Ba)", "Bayerischer Yacht-Club"], ["WYC", "Württembergischer Yacht-Club"],
  ["MSC", "Mühlenberger Segel-Club"], ["KYC (SH)", "Kieler Yacht-Club"], ["BYC (Be)", "Berliner Yacht-Club"],
  ["PYC", "Potsdamer Yacht-Club"], ["JSC", "Joersfelder Segel-Club"], ["BYCÜ", "Bodensee Yacht-Club Überlingen"],
  ["SMCÜ", "Segel- und Motorboot Club Überlingen"], ["MYC", "Münchner Yacht-Club"], ["DYC", "Düsseldorfer Yachtclub"],
  ["BSC", "Blankeneser Segel Club"], ["KAR", "Klub am Rupenhorn"], ["SVI", "Seglervereinigung Itzehoe"],
  ["BOH-YC", "Bocholter Yacht-Club"], ["ENSF", "Entdecker- und Seefahrerfördervereinigung"], ["SVWu", "Segler-Vereinigung Wuppertal"],
];
const CLUBS_2: [string, string][] = [
  ["VSaW", "Verein Seglerhaus am Wannsee"], ["DTYC", "Deutscher Touring Yacht-Club"], ["LYC", "Lübecker Yacht-Club"],
  ["MRSV", "Münchner Ruder- und Segelverein „Bayern“"], ["FSC", "Flensburger Segel-Club"], ["KYC (BW)", "Konstanzer Yacht Club"],
  ["HSC", "Hamburger Segel-Club"], ["ASVW", "Akademischer Seglerverein Warnemünde"], ["SV03", "Seglervereinigung 1903 Berlin"],
  ["FYC", "Frankfurter Yachtclub"], ["BuSC", "Bucerius Segel Club"], ["SCR", "Segelclub Rheingau"],
  ["LSV", "Lübecker Segler Verein von 1885"], ["ETUF", "Essener Turn- und Fechtklub"], ["RSN", "Regatta-Segler Neuruppin"],
  ["SHM", "Segelclub Hansa Münster"], ["SCV", "Segel-Club Ville"], ["WsW", "Wir sind Wir"],
];

function table(clubs: [string, string][], count = clubs.length): Row[] {
  let points = 9;
  return clubs.slice(0, count).map(([short, club], i) => {
    points += 2 + ((i * 7) % 4);
    return { rank: i + 1, short, club, points, trend: (((i * 5) % 3) - 1) as -1 | 0 | 1 };
  });
}

/** What the league is and what is at stake — condensed from deutsche-segelliga.de/wettbewerbe. */
export type About = { intro: string; facts: string[] };

export const LEAGUES: ProtoLeague[] = [
  {
    slug: "dsbl",
    short: "DSBL",
    name: "Deutsche Segel-Bundesliga 2026",
    tagline: "Two divisions, 36 clubs, promotion and relegation.",
    photo: DSBL_PHOTOS.race,
    divisions: [
      { slug: "1-liga", short: "1. Liga", name: "1. Segel-Bundesliga", rows: table(CLUBS_1) },
      { slug: "2-liga", short: "2. Liga", name: "2. Segel-Bundesliga", rows: table(CLUBS_2) },
    ],
    about: {
      intro:
        "The top of German club sailing since 2013: the best sailors of 36 clubs — Olympians, seasoned professionals and rising talents — race side by side for their club, on J/70s the league provides and rotates after every race.",
      facts: [
        "1. Liga: 18 clubs, 6 matchdays, the German championship plate and SAILING Champions League places.",
        "2. Liga: 18 clubs, 5 matchdays, sailed alongside the 1. Liga's events.",
        "The last four of the 1. Liga go down, the first four of the 2. Liga go up.",
        "Places 13–18 of the 2. Liga must requalify at the DSL-Pokal.",
      ],
    },
    // The real 2026 calendar of deutsche-segelbundesliga.de/saison-2025/.
    acts: [
      { slug: "act-1", title: "Act 1", venue: "Starnberg", water: "Starnberger See", host: "MRSV & DTYC", dates: "17–19 Apr", state: "done", divisions: ["1. Liga", "2. Liga"] },
      { slug: "act-2", title: "Act 2", venue: "Starnberg", water: "Starnberger See", host: "Bayerischer Yacht-Club", dates: "1–3 May", state: "done", divisions: ["1. Liga", "2. Liga"] },
      { slug: "act-3", title: "Act 3", venue: "Kiel", water: "Kieler Förde", host: "Kieler Yacht-Club", dates: "10–12 Jul", state: "done", divisions: ["1. Liga", "2. Liga"] },
      { slug: "act-4", title: "Act 4", venue: "Hamburg", water: "Alster", host: "Norddeutscher Regatta Verein", dates: "31 Jul–2 Aug", state: "done", divisions: ["1. Liga"] },
      { slug: "act-5", title: "Act 5", venue: "Berlin", water: "Wannsee", host: "Potsdamer Yacht-Club", dates: "18–20 Sep", state: "done", divisions: ["1. Liga", "2. Liga"] },
      { slug: "act-6", title: "Final", venue: "Berlin", water: "Wannsee", host: "Verein Seglerhaus am Wannsee", dates: "15–17 Oct", state: "next", divisions: ["1. Liga", "2. Liga"] },
    ],
  },
  {
    slug: "junioren-liga",
    short: "Junioren-Liga",
    name: "Junioren-Segel-Liga 2026",
    tagline: "AK16 to AK21 — the talent school of club sailing.",
    photo: DSBL_PHOTOS.swimmer,
    divisions: [{ slug: "junioren", short: "Junioren-Liga", name: "Deutsche Junioren Segel-Liga", rows: table(CLUBS_1, 12).map((r) => ({ ...r, club: `${r.club} (juniors)` })) }],
    about: {
      intro:
        "The talent school of German club sailing since 2016: sailors aged AK16 to AK21 race the league's format — J/70, fleet race — with a real path upwards. Under the patronage of the Deutsche Segel-Liga e.V.; the Heinz Nixdorf Verein (HNV) provides the boats.",
      facts: [
        "Open to youth teams of every German sailing club.",
        "The best teams qualify for the DSL-Pokal and the Youth SAILING Champions League.",
        "Each act is organised by the club that hosts it.",
      ],
    },
    acts: [
      { slug: "act-1", title: "Act 1", venue: "Berlin", water: "Wannsee", host: "Berliner Yacht-Club", dates: "13–14 Jun", state: "done", divisions: ["Junioren-Liga"] },
      { slug: "act-2", title: "Act 2", venue: "Travemünde", water: "Ostsee", host: "Lübecker Yacht-Club", dates: "18–19 Jul", state: "done", divisions: ["Junioren-Liga"] },
      { slug: "act-3", title: "Final", venue: "Hamburg", water: "Alster", host: "Norddeutscher Regatta Verein", dates: "29–30 Aug", state: "done", divisions: ["Junioren-Liga"] },
    ],
  },
  {
    slug: "dsl-pokal",
    short: "DSL-Pokal",
    name: "DSL-Pokal 2026",
    tagline: "One weekend where amateur meets professional.",
    photo: DSBL_PHOTOS.aerial,
    divisions: [{ slug: "pokal", short: "DSL-Pokal", name: "DSL-Pokal", rows: [] }],
    about: {
      intro:
        "Where amateur meets professional, since 2017: one compact weekend in autumn, after the league season, in which clubs from every level race each other — and the way into the 2. Liga.",
      facts: [
        "Who starts: the best of the 1. Liga, the top and the threatened of the 2. Liga, the best junior teams, and clubs that qualify by pre-entry.",
        "The best teams not yet in a Bundesliga earn a place in next season's 2. Liga.",
        "A trophy of its own — coveted by established league teams too.",
      ],
    },
    acts: [
      { slug: "final", title: "Final", venue: "Berlin", water: "Wannsee", host: "Verein Seglerhaus am Wannsee", dates: "14–15 Nov", state: "planned", divisions: ["DSL-Pokal"] },
    ],
  },
];

export const findLeague = (slug: string | undefined) => LEAGUES.find((league) => league.slug === slug) ?? null;
export const YEAR = 2026;

/** The act that is running, else the next one, else the last. */
export const currentAct = (league: ProtoLeague) =>
  league.acts.find((act) => act.state === "live") ??
  league.acts.find((act) => act.state === "next" || act.state === "planned") ??
  league.acts[league.acts.length - 1];

/** The last act with results. */
export const lastSailed = (league: ProtoLeague) => [...league.acts].reverse().find((act) => act.state === "done") ?? null;

export type Article = { slug: string; title: string; date: string; league: string; teaser: string; photo: Photo; body: string[] };

const NEWS_PHOTOS = [DSBL_PHOTOS.podium, DSBL_PHOTOS.race, DSBL_PHOTOS.swimmer, DSBL_PHOTOS.aerial, DSBL_PHOTOS.camera, DSBL_PHOTOS.studio];

// The association's real article, from deutsche-segelliga.de/category/news — content, so
// in the language it was written in.
const BOARD_ELECTED: Article = {
  slug: "neuer-vorstand-gewaehlt",
  title: "Neuer Vorstand gewählt – es geht los!",
  date: "2026-01-27",
  league: "Association",
  teaser: "Was für ein Tag in Düsseldorf! Mitten im Trubel der boot haben wir uns mit 34 von 36 Vereinen getroffen.",
  photo: { ...DSL_PHOTOS.title },
  body: [
    "Was für ein Tag in Düsseldorf! Mitten im Trubel der boot haben wir uns mit 34 von 36 Vereinen getroffen – und gemeinsam die Weichen für die Zukunft der Segel-Bundesliga gestellt.",
    "Von Gundram Leifert.",
  ],
};

export const NEWS: Article[] = [BOARD_ELECTED, ...WF_NEWS.map((item, i) => ({
  slug: item.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "").slice(0, 48),
  title: item.title,
  date: item.date,
  league: item.league.startsWith("1.") || item.league.startsWith("2.") ? "DSBL" : item.league,
  teaser: item.teaser,
  photo: NEWS_PHOTOS[i % NEWS_PHOTOS.length],
  body: [
    item.teaser,
    "Placeholder text for the article. A real article is written by the league office (site role `editor`) and carries a byline, a date, the matchday it belongs to and its photos.",
    "A second paragraph, so the page has the length of a real report.",
  ],
}))];

export const newsOf = (league: ProtoLeague) => NEWS.filter((item) => item.league === league.short || item.league === "Association");

export type Release = { title: string; date: string; kind: string; body: string };

export const PRESS: Release[] = WF_PRESS.map((item) => ({
  ...item,
  body: "Placeholder text of the release: the facts in the first paragraph, a quote, the next dates, and the press contact.",
}));

export type Notice = { time: string; from: "Race committee" | "Jury" | "Organizer"; title: string; body: string };

export const NOTICES: Notice[] = [
  { time: "Sat 08:15", from: "Race committee", title: "First warning signal 10:00", body: "Racing area A. Briefing for helms at 09:00 in the club house." },
  { time: "Sat 09:40", from: "Organizer", title: "Amendment 2 to the sailing instructions", body: "SI 11.2: the leeward gate is replaced by a single mark to port. Takes effect from flight 4." },
  { time: "Sat 15:20", from: "Jury", title: "Hearing schedule", body: "Protest 3 (BYC v KYC) 17:30, protest 4 (DTYC v NRV) 17:45, in the jury room." },
  { time: "Sat 18:05", from: "Jury", title: "Decision protest 3", body: "BYC is disqualified in race 14 (RRS 10). Score adjusted." },
  { time: "Sun 07:50", from: "Race committee", title: "Postponement ashore", body: "AP ashore — no wind. Next signal not before 10:30." },
];

export const EVENT_DOCUMENTS = ["Notice of race", "Sailing instructions", "Amendment 1", "Amendment 2", "Entry list"];

export type DocGroup = { title: string; docs: string[] };

export const SEASON_DOCUMENTS: DocGroup[] = [
  { title: "Rules", docs: ["League regulations 2026", "Scoring and tie-breaks", "Promotion and relegation"] },
  { title: "Notice of race", docs: ["Season notice of race 2026", "Amendment 1 (dates)"] },
  { title: "Boats", docs: ["J/70 charter terms", "Damage and deposit rules", "Boat handling guide"] },
  { title: "Entry", docs: ["Squad registration deadline", "Liability waiver", "Advertising rules"] },
];

export const BOAT_COLORS = [
  ["Black", "#111827"],
  ["Green", "#16a34a"],
  ["Dark blue", "#1e3a8a"],
  ["Red", "#dc2626"],
  ["Gray", "#9ca3af"],
  ["Orange", "#f97316"],
] as const;

/** A flight's three races: six teams each, in the order they finished. Deterministic. */
export function flightRaces(clubs: string[], flight: number) {
  return [0, 1, 2].map((race) => {
    const teams = clubs.slice(race * 6, race * 6 + 6);
    const shift = (flight * 5 + race * 2) % 6;
    return { number: (flight - 1) * 3 + race + 1, order: teams.map((_, i) => teams[(i + shift) % teams.length]) };
  });
}

export const CREW_NAMES = ["A. Becker", "J. Hansen", "L. Krüger", "M. Schulz", "F. Wagner", "S. Neumann"];
