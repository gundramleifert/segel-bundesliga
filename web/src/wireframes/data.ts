// Mock content for the homepage wireframes (issue #13). Nothing here comes from the API on
// purpose: the wireframes compare *layouts*, and fixed content keeps the five options
// comparable side by side. Throwaway — the chosen option is rebuilt on real data.

export type League = {
  slug: string;
  short: string;
  name: string;
  teams: number;
  events: number;
  tagline: string;
};

export const LEAGUES: League[] = [
  {
    slug: "1-liga",
    short: "1. Liga",
    name: "1. Segel-Bundesliga 2026",
    teams: 18,
    events: 6,
    tagline: "18 clubs, six acts, one champion.",
  },
  {
    slug: "2-liga",
    short: "2. Liga",
    name: "2. Segel-Bundesliga 2026",
    teams: 18,
    events: 5,
    tagline: "The race for promotion.",
  },
  {
    slug: "junioren",
    short: "Junioren-Liga",
    name: "Junioren-Segel-Liga 2026",
    teams: 12,
    events: 3,
    tagline: "Under 23, same boats, same pressure.",
  },
  {
    slug: "pokal",
    short: "DSL-Pokal",
    name: "DSL-Pokal 2026",
    teams: 24,
    events: 1,
    tagline: "One weekend, every club can enter.",
  },
];

export const findLeague = (slug: string | undefined) =>
  LEAGUES.find((league) => league.slug === slug) ?? null;

export type Photo = { src: string; alt: string; credit: string; license: string; page: string };

const thumb = (path: string, file: string, width = 1280) =>
  `https://upload.wikimedia.org/wikipedia/commons/thumb/${path}/${width}px-${file}`;
const commons = (file: string) => `https://commons.wikimedia.org/wiki/File:${file}`;

function photo(path: string, file: string, alt: string, credit: string, license: string): Photo {
  return { src: thumb(path, file), alt, credit, license, page: commons(file) };
}

// Freely licensed photos from Wikimedia Commons, hotlinked — Commons allows that, with the
// attribution the credits list on the wireframe index carries.
export const PHOTOS = {
  alster: photo(
    "3/33",
    "J70_Boote_auf_der_Alster_in_Hamburg.jpg",
    "Two J/70 on the Alster in Hamburg at dusk",
    "Lars Wehrmann",
    "CC BY-SA 4.0",
  ),
  helgaBahn: photo(
    "7/7d",
    "Helga_Cup_2019_Bahn_ActiveCity.jpg",
    "J/70 racing close on the Alster",
    "Hein.Mück",
    "CC BY-SA 4.0",
  ),
  helga2022: photo(
    "6/62",
    "Helga_Cup_2022-2.jpg",
    "J/70 fleet at the Helga Cup 2022",
    "Hein.Mück",
    "CC BY-SA 4.0",
  ),
  helgaNrv: photo(
    "0/05",
    "Helga_Cup2019_NRV.jpg",
    "J/70 at the Norddeutscher Regatta Verein",
    "Hein.Mück",
    "CC BY-SA 4.0",
  ),
  stMoritz: photo(
    "a/a2",
    "Sailing_on_Lake_St._Moritz_at_the_SAILING_Champions_League_Final_2018.jpg",
    "J/70 fleet on Lake St. Moritz below the mountains",
    "Sailing Energy",
    "CC BY-SA 4.0",
  ),
  kiel4: photo(
    "0/0c",
    "Kiel_Week_2023-06-24_%284%29.jpg",
    "Kiel Week 2023 on the Förde",
    "Snoopy1964",
    "CC BY-SA 4.0",
  ),
  kiel7: photo(
    "f/f0",
    "Kiel_Week_2023-06-24_%287%29.jpg",
    "Kiel Week 2023, boats under sail",
    "Snoopy1964",
    "CC BY-SA 4.0",
  ),
  kiel10: photo(
    "2/25",
    "Kiel_Week_2023-06-24_%2810%29.jpg",
    "Kiel Week 2023, regatta course",
    "Snoopy1964",
    "CC BY-SA 4.0",
  ),
  kiel12: photo(
    "4/4c",
    "Kiel_Week_2023-06-24_%2812%29.jpg",
    "Kiel Week 2023, sails on the water",
    "Snoopy1964",
    "CC BY-SA 4.0",
  ),
  kiel17: photo(
    "e/eb",
    "Kiel_Week_2023-06-24_%2817%29.jpg",
    "Kiel Week 2023, harbour",
    "Snoopy1964",
    "CC BY-SA 4.0",
  ),
  eckernfoerde: photo(
    "d/df",
    "2023_Juni_Eckernfoerde_Aalregatta.jpg",
    "Aalregatta in Eckernförde 2023",
    "Exil",
    "CC BY-SA 4.0",
  ),
  mueritz: photo(
    "9/9e",
    "IDM_M%C3%BCritz_O-Jolle_%28Regatta%29.jpg",
    "Dinghy regatta on the Müritz",
    "Fontane",
    "CC BY-SA 4.0",
  ),
} satisfies Record<string, Photo>;

export type Video = { src: string; poster: string; title: string; credit: string; license: string; page: string };

function video(path: string, file: string, title: string, credit: string, license: string): Video {
  return {
    // The 480p transcode: the originals are ~90 MB each.
    src: `https://upload.wikimedia.org/wikipedia/commons/transcoded/${path}/${file}/${file}.480p.vp9.webm`,
    poster: `https://upload.wikimedia.org/wikipedia/commons/thumb/${path}/${file}/960px--${file}.jpg`,
    title,
    credit,
    license,
    page: commons(file),
  };
}

export const VIDEOS: Video[] = [
  video(
    "d/d0",
    "Fireball_EC-WC_2013_Portoro%C5%BE%2C_Slovenia.webm",
    "Highlights: Act 3 in three minutes",
    "Blaž Režabek",
    "CC BY 3.0",
  ),
  video(
    "4/45",
    "Final_day_of_racing_for_the_2017_J_Class_World_Championships_by_Don_Ramey_Logan.webm",
    "Final day: the decisive flight",
    "Don Ramey Logan",
    "CC BY-SA 4.0",
  ),
  video(
    "7/7f",
    "Sailing_on_Velenje_lake.webm",
    "Junioren-Liga: training camp",
    "Blaž Režabek",
    "CC BY 3.0",
  ),
  video(
    "e/ec",
    "Trening-_Ankaran_29.4.13.webm",
    "Onboard: a start from the committee boat",
    "Blaž Režabek",
    "CC BY 3.0",
  ),
];

export type NewsItem = { title: string; date: string; league: string; teaser: string; photo: Photo };

export const NEWS: NewsItem[] = [
  {
    title: "NRV takes the lead after a perfect Sunday in Glücksburg",
    date: "2026-09-21",
    league: "1. Liga",
    teaser: "Six wins in eight races — and the table has a new name at the top.",
    photo: PHOTOS.helgaNrv,
  },
  {
    title: "Promotion race: three clubs within two points",
    date: "2026-09-14",
    league: "2. Liga",
    teaser: "Before the final act in Kiel, nothing is decided.",
    photo: PHOTOS.helgaBahn,
  },
  {
    title: "Junioren-Liga crowns its champion on the Alster",
    date: "2026-08-30",
    league: "Junioren-Liga",
    teaser: "The youngest crew in the field wins the last flight and the title.",
    photo: PHOTOS.alster,
  },
  {
    title: "DSL-Pokal: registration for 2027 opens",
    date: "2026-08-12",
    league: "DSL-Pokal",
    teaser: "Every member club can enter one crew. Deadline 31 January.",
    photo: PHOTOS.helga2022,
  },
  {
    title: "Live tracking: every boat on the map, from every phone",
    date: "2026-07-28",
    league: "Association",
    teaser: "From this season the tracker is the sailor's own phone.",
    photo: PHOTOS.stMoritz,
  },
  {
    title: "Kiel Week: league clubs sail the J/70 cup",
    date: "2026-06-24",
    league: "Association",
    teaser: "Twelve league clubs, one week, the Förde.",
    photo: PHOTOS.kiel7,
  },
];

export type Matchday = {
  league: string;
  title: string;
  venue: string;
  dates: string;
  state: "done" | "live" | "next" | "planned";
  winner?: string;
};

export const MATCHDAYS: Matchday[] = [
  { league: "1. Liga", title: "Act 4", venue: "Tutzing, Starnberger See", dates: "4.–6. Sep", state: "done", winner: "Bayerischer YC" },
  { league: "1. Liga", title: "Act 5", venue: "Glücksburg, Flensburger Förde", dates: "9.–11. Oct", state: "live" },
  { league: "2. Liga", title: "Act 5", venue: "Kiel, Kieler Förde", dates: "23.–25. Oct", state: "next" },
  { league: "1. Liga", title: "Act 6 · Final", venue: "Hamburg, Alster", dates: "6.–8. Nov", state: "planned" },
  { league: "Junioren-Liga", title: "Act 3", venue: "Hamburg, Alster", dates: "29.–30. Aug", state: "done", winner: "NRV Junioren" },
  { league: "DSL-Pokal", title: "Final", venue: "Berlin, Wannsee", dates: "14.–15. Nov", state: "planned" },
];

export type Row = { rank: number; club: string; short: string; points: number; trend: -1 | 0 | 1 };

export const STANDINGS: Record<string, Row[]> = {
  "1-liga": [
    { rank: 1, club: "Norddeutscher Regatta Verein", short: "NRV", points: 14, trend: 1 },
    { rank: 2, club: "Bayerischer Yacht-Club", short: "BYC", points: 16, trend: -1 },
    { rank: 3, club: "Deutscher Touring Yacht-Club", short: "DTYC", points: 21, trend: 0 },
    { rank: 4, club: "Württembergischer Yacht-Club", short: "WYC", points: 24, trend: 1 },
    { rank: 5, club: "Verein Seglerhaus am Wannsee", short: "VSaW", points: 27, trend: -1 },
    { rank: 6, club: "Kieler Yacht-Club", short: "KYC", points: 29, trend: 0 },
  ],
  "2-liga": [
    { rank: 1, club: "Mühlenberger Segel-Club", short: "MSC", points: 11, trend: 0 },
    { rank: 2, club: "Segelclub Eckernförde", short: "SCE", points: 13, trend: 1 },
    { rank: 3, club: "Flensburger Segel-Club", short: "FSC", points: 13, trend: -1 },
    { rank: 4, club: "Joersfelder Segel-Club", short: "JSC", points: 19, trend: 0 },
    { rank: 5, club: "Segler-Verein Itzehoe", short: "SVI", points: 22, trend: 1 },
    { rank: 6, club: "Berliner Segel-Club", short: "BSC", points: 25, trend: -1 },
  ],
  junioren: [
    { rank: 1, club: "NRV Junioren", short: "NRV", points: 6, trend: 0 },
    { rank: 2, club: "BYC Junioren", short: "BYC", points: 9, trend: 1 },
    { rank: 3, club: "KYC Junioren", short: "KYC", points: 10, trend: -1 },
    { rank: 4, club: "WYC Junioren", short: "WYC", points: 14, trend: 0 },
  ],
  pokal: [],
};

export type PressRelease = { title: string; date: string; kind: "Press release" | "Press kit" | "Photos" };

export const PRESS: PressRelease[] = [
  { title: "Act 5 Glücksburg: NRV takes over the lead", date: "2026-09-21", kind: "Press release" },
  { title: "Season 2027: calendar and venues confirmed", date: "2026-09-02", kind: "Press release" },
  { title: "Media kit 2026: logos, fact sheet, contacts", date: "2026-04-01", kind: "Press kit" },
  { title: "Photo pool Act 4 Tutzing (print resolution)", date: "2026-09-07", kind: "Photos" },
];

export const FACTS = [
  { value: "64", label: "member clubs" },
  { value: "4", label: "leagues and cups" },
  { value: "15", label: "matchdays in 2026" },
  { value: "≈ 900", label: "races sailed" },
];
