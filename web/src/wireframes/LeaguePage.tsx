import { LEAGUES, MATCHDAYS, NEWS, PHOTOS, STANDINGS, VIDEOS, type League } from "./data";
import { Img, LiveDot, MatchdayList, NewsCard, PressList, SectionTitle, StandingsTable, VideoTile } from "./kit";

const HERO: Record<string, keyof typeof PHOTOS> = {
  "1-liga": "alster",
  "2-liga": "helgaBahn",
  junioren: "helga2022",
  pokal: "stMoritz",
};

const SECTIONS = [
  ["overview", "Overview"],
  ["standings", "Standings"],
  ["matchdays", "Matchdays"],
  ["clubs", "Clubs"],
  ["media", "Media"],
  ["news", "News"],
  ["press", "Press"],
] as const;

/** A league is one page (issue #13): everything about it on one URL, the sections reached
 *  by a sticky row of anchors rather than by sub-pages. Shared by all five options — they
 *  differ in how you *get* here, not in what a league is. */
export function LeaguePage({ league }: { league: League }) {
  const live = MATCHDAYS.find((day) => day.league === league.short && (day.state === "live" || day.state === "next"));
  const rows = STANDINGS[league.slug] ?? [];
  const news = NEWS.filter((item) => item.league === league.short);

  return (
    <div data-testid={`wf-league-${league.slug}`}>
      <section className="relative h-72 overflow-hidden bg-slate-900 sm:h-96">
        <Img photo={PHOTOS[HERO[league.slug] ?? "alster"]} className="opacity-70" />
        <div className="absolute inset-0 bg-gradient-to-t from-slate-950/90 via-slate-950/30 to-transparent" />
        <div className="absolute inset-x-0 bottom-0 mx-auto max-w-7xl px-4 pb-8 text-white lg:px-8">
          <p className="text-sm font-semibold uppercase tracking-widest text-white/70">Season 2026</p>
          <h1 className="mt-1 text-3xl font-extrabold tracking-tight sm:text-5xl">{league.name}</h1>
          <p className="mt-2 max-w-xl text-white/80">{league.tagline}</p>
          <div className="mt-4 flex flex-wrap gap-2 text-sm">
            {live && (
              <a href="#overview" className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1.5 font-semibold text-slate-900">
                {live.state === "live" && <LiveDot />}
                {live.state === "live" ? "Live now" : "Next"}: {live.title} · {live.venue.split(",")[0]}
              </a>
            )}
            <span className="rounded-full bg-white/15 px-3 py-1.5">{league.teams} clubs</span>
            <span className="rounded-full bg-white/15 px-3 py-1.5">{league.events} matchdays</span>
          </div>
        </div>
      </section>

      <nav
        aria-label="On this page"
        className="scrollbar-none sticky top-0 z-30 overflow-x-auto border-b border-slate-200 bg-white/95 backdrop-blur"
      >
        <ul className="mx-auto flex max-w-7xl gap-1 px-4 text-sm font-medium lg:px-8">
          {SECTIONS.map(([id, label]) => (
            <li key={id}>
              <a href={`#${id}`} className="block whitespace-nowrap border-b-2 border-transparent px-3 py-3 text-slate-600 hover:border-brand-600 hover:text-slate-900">
                {label}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      <div className="mx-auto max-w-7xl space-y-14 px-4 py-10 lg:px-8">
        <section id="overview" className="grid gap-6 lg:grid-cols-3">
          <div className="rounded-2xl bg-brand-700 p-6 text-white lg:col-span-2">
            <p className="text-sm uppercase tracking-wide text-white/70">{live?.state === "live" ? "Racing now" : "Coming up"}</p>
            <h2 className="mt-1 text-2xl font-bold">{live ? `${live.title} · ${live.venue}` : "Season complete"}</h2>
            <p className="mt-1 text-white/80">{live?.dates}</p>
            <div className="mt-5 flex flex-wrap gap-2">
              {["Live map", "Race results", "Pairing list", "Notice board"].map((label) => (
                <a key={label} href="#" className="rounded-full bg-white/15 px-4 py-2 text-sm font-medium hover:bg-white/25">
                  {label}
                </a>
              ))}
            </div>
          </div>
          <div className="rounded-2xl bg-white p-6 ring-1 ring-slate-200">
            <p className="text-sm text-slate-500">Leader</p>
            <p className="mt-1 text-2xl font-bold">{rows[0]?.club ?? "—"}</p>
            <p className="text-slate-600">{rows[0] ? `${rows[0].points} points after ${league.events - 2} acts` : "No races yet"}</p>
          </div>
        </section>

        <section id="standings">
          <SectionTitle more="Full table & race-by-race">Standings</SectionTitle>
          <StandingsTable slug={league.slug} limit={12} />
        </section>

        <section id="matchdays">
          <SectionTitle more="Add to calendar">Matchdays</SectionTitle>
          <MatchdayList league={league.short} />
        </section>

        <section id="clubs">
          <SectionTitle>Clubs</SectionTitle>
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            {(rows.length ? rows : (STANDINGS["1-liga"] ?? [])).map((row) => (
              <li key={row.short} className="flex flex-col items-center gap-2 rounded-xl bg-white p-4 text-center ring-1 ring-slate-200">
                <span className="grid size-12 place-items-center rounded-full bg-slate-100 text-sm font-bold text-slate-600">{row.short}</span>
                <span className="line-clamp-2 text-xs text-slate-600">{row.club}</span>
              </li>
            ))}
          </ul>
        </section>

        <section id="media">
          <SectionTitle more="Media library">Media</SectionTitle>
          <div className="grid gap-4 md:grid-cols-2">
            <VideoTile video={VIDEOS[0]} />
            <div className="grid grid-cols-2 gap-2">
              {[PHOTOS.helgaNrv, PHOTOS.helgaBahn, PHOTOS.kiel12, PHOTOS.alster].map((p) => (
                <div key={p.src} className="aspect-[4/3] overflow-hidden rounded-lg">
                  <Img photo={p} />
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="news">
          <SectionTitle more="All news">News</SectionTitle>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {(news.length ? news : NEWS.slice(0, 3)).map((item) => (
              <NewsCard key={item.title} item={item} />
            ))}
          </div>
        </section>

        <section id="press">
          <SectionTitle more="Press centre">Press</SectionTitle>
          <PressList />
        </section>

        <p className="text-sm text-slate-500">
          Other leagues: {LEAGUES.filter((l) => l.slug !== league.slug).map((l) => l.short).join(" · ")}
        </p>
      </div>
    </div>
  );
}
