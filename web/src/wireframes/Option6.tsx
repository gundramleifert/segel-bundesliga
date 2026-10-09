import { useState } from "react";
import { Link } from "react-router-dom";

import { LEAGUES, MATCHDAYS, NEWS, PHOTOS, STANDINGS, VIDEOS, inLeague } from "./data";
import { LeaguePage } from "./LeaguePage";
import { Footer, HeroMedia, Img, LanguageToggle, LiveDot, MyArea, PressList, TopBar, VideoTile } from "./kit";
import { formatDate, useWireframe } from "./nav";

const PANEL_PHOTO = [PHOTOS.alster, PHOTOS.helga2022, PHOTOS.stMoritz];

/** The season as one course: every matchday of every league, in date order. */
const SEASON = [
  { month: "Apr", title: "DSBL Act 1", venue: "Kiel", state: "done" },
  { month: "May", title: "DSBL Act 2", venue: "Travemünde", state: "done" },
  { month: "Jun", title: "Junioren Act 1", venue: "Berlin", state: "done" },
  { month: "Jun", title: "DSBL Act 3", venue: "Berlin", state: "done" },
  { month: "Aug", title: "Junioren Final", venue: "Hamburg", state: "done" },
  { month: "Sep", title: "DSBL Act 4", venue: "Tutzing", state: "done" },
  { month: "Oct", title: "DSBL Act 5", venue: "Glücksburg", state: "live" },
  { month: "Nov", title: "DSBL Final", venue: "Hamburg", state: "planned" },
  { month: "Nov", title: "DSL-Pokal", venue: "Wannsee", state: "planned" },
] as const;

/** Option 6 — "Open water", after none of the three references: the page *is* the
 *  picture from its first pixel, and the navigation lies over it. The three leagues are
 *  the hero — three panels, the chosen one opens wide — and everything below borrows from
 *  the sport rather than from a portal: the season drawn as a course with its matchdays
 *  as marks, standings set as huge type, news as a logbook, media as a film strip. */
export function Option6() {
  const { league } = useWireframe();
  return (
    <div className="min-h-dvh bg-slate-950 text-white">
      <div className="relative">
        <TopBar variant="overlay" status right={<><LanguageToggle dark /><MyArea tone="dark" /></>} />
        {league ? (
          <div className="bg-page text-ink">
            <LeaguePage league={league} />
          </div>
        ) : (
          <Home />
        )}
      </div>
      <Footer />
    </div>
  );
}

function Home() {
  return (
    <main>
      <LeaguePanels />
      <Course />
      <BigStandings />
      <Logbook />
      <FilmStrip />
      <section className="mx-auto max-w-7xl px-4 py-20 lg:px-8">
        {/* `minmax(0,1fr)`: a bare grid track is floored at its widest item's min-content,
            and a press title that may not wrap pushed the page sideways on a phone. */}
        <div className="grid grid-cols-[minmax(0,1fr)] gap-10 lg:grid-cols-3">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-white/50">Press</p>
            <h2 className="mt-3 text-4xl font-black leading-none">Everything for your story.</h2>
            <a href="#" className="mt-6 inline-block rounded-full bg-white px-6 py-3 font-semibold text-slate-950">Press kit ↓</a>
            <p className="mt-4 text-sm text-white/60">Accreditation · presse@segelliga.example.com</p>
          </div>
          <div className="lg:col-span-2"><PressList dark /></div>
        </div>
      </section>
    </main>
  );
}

/** The hero: one panel per league, full height from the very top. The chosen one opens
 *  wide (hover or tap); the others stay as slim strips with their name on the edge. */
function LeaguePanels() {
  const { to } = useWireframe();
  const [open, setOpen] = useState(0);
  return (
    <section className="flex h-dvh min-h-[36rem] flex-col lg:flex-row" data-testid="wf-panels">
      {LEAGUES.map((league, i) => {
        const isOpen = open === i;
        const live = MATCHDAYS.find((d) => inLeague(league, d.league) && d.state === "live");
        const next = MATCHDAYS.find((d) => inLeague(league, d.league) && d.state !== "done");
        return (
          <div
            key={league.slug}
            onMouseEnter={() => setOpen(i)}
            onClick={() => setOpen(i)}
            className={`relative min-h-0 cursor-pointer overflow-hidden transition-[flex-grow] duration-700 ease-out ${isOpen ? "grow-[5]" : "grow"} basis-0`}
          >
            <HeroMedia photo={PANEL_PHOTO[i]} className={`absolute inset-0 transition duration-700 ${isOpen ? "scale-100 opacity-90" : "scale-110 opacity-40 grayscale"}`} />
            <div className="absolute inset-0 bg-gradient-to-t from-slate-950/90 via-slate-950/20 to-slate-950/30" />
            {!isOpen && (
              <p className="absolute bottom-6 left-6 text-xl font-black uppercase tracking-widest lg:bottom-10 lg:left-1/2 lg:-translate-x-1/2 lg:rotate-180 lg:[writing-mode:vertical-rl]">
                {league.short}
              </p>
            )}
            {isOpen && (
              <div className="absolute inset-x-0 bottom-0 p-6 pb-10 lg:p-12 lg:pb-16">
                {live && (
                  <p className="mb-3 inline-flex items-center gap-2 rounded-full bg-red-600 px-3 py-1 text-xs font-bold uppercase">
                    <LiveDot /> Live · {live.title} {live.venue.split(",")[0]}
                  </p>
                )}
                <h1 className="text-5xl font-black uppercase leading-[0.9] tracking-tight sm:text-7xl lg:text-8xl">{league.short}</h1>
                <p className="mt-3 max-w-xl text-lg text-white/80">{league.tagline}</p>
                <div className="mt-6 flex flex-wrap gap-3">
                  <Link to={to(league.slug)} className="rounded-full bg-white px-6 py-3 font-semibold text-slate-950">Enter the league</Link>
                  {next && (
                    <span className="rounded-full border border-white/40 px-6 py-3 text-white/90">
                      {next.state === "live" ? "Racing now" : `Next: ${next.dates}`}
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </section>
  );
}

/** The season drawn as a race course: a line across the year, one mark per matchday. */
function Course() {
  return (
    <section className="border-y border-white/10 bg-gradient-to-b from-brand-900 to-slate-950 py-16">
      <div className="mx-auto max-w-7xl px-4 lg:px-8">
        <p className="text-sm uppercase tracking-[0.3em] text-white/50">Season 2026</p>
        <h2 className="mt-2 text-3xl font-black sm:text-4xl">The course so far</h2>
      </div>
      <div className="scrollbar-none mt-10 overflow-x-auto">
        <ol className="relative mx-auto flex min-w-[64rem] max-w-7xl justify-between px-8">
          <span aria-hidden className="absolute inset-x-8 top-[3.25rem] border-t-2 border-dashed border-white/30" />
          {SEASON.map((mark, i) => (
            <li key={mark.title} className={`relative flex w-28 flex-col items-center text-center ${i % 2 ? "pt-0" : ""}`}>
              <span className="text-xs font-semibold uppercase tracking-widest text-white/50">{mark.month}</span>
              <span
                className={`relative mt-6 grid size-6 place-items-center rounded-full ${mark.state === "done"
                    ? "bg-orange-500"
                    : mark.state === "live"
                      ? "bg-red-600 ring-8 ring-red-600/30"
                      : "border-2 border-white/60 bg-slate-950"
                }`}
              >
                {mark.state === "live" && <span className="absolute inset-0 animate-ping rounded-full bg-red-500/60" />}
              </span>
              <span className="mt-4 text-sm font-bold">{mark.title}</span>
              <span className="text-xs text-white/60">{mark.venue}</span>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

/** Standings set as type: the rank and the club's short name as big as the screen allows. */
function BigStandings() {
  const dsbl = LEAGUES[0];
  return (
    <section className="mx-auto max-w-7xl px-4 py-20 lg:px-8">
      <p className="text-sm uppercase tracking-[0.3em] text-white/50">Standings · DSBL</p>
      <div className="mt-6 grid grid-cols-[minmax(0,1fr)] gap-12 lg:grid-cols-2">
        {dsbl.divisions.map((division) => (
          <div key={division.slug}>
            <h3 className="mb-4 text-lg font-semibold text-white/70">{division.name}</h3>
            <ol className="space-y-1">
              {(STANDINGS[division.slug] ?? []).slice(0, 5).map((row) => (
                <li key={row.short} className="flex items-baseline gap-4 border-b border-white/10 pb-1">
                  <span className="w-12 text-5xl font-black text-transparent [-webkit-text-stroke:1px_rgba(255,255,255,0.5)] sm:text-6xl">
                    {row.rank}
                  </span>
                  <span className="flex-1 text-4xl font-black tracking-tight sm:text-6xl">{row.short}</span>
                  <span className="text-xl tabular-nums text-white/70">{row.points}</span>
                </li>
              ))}
            </ol>
          </div>
        ))}
      </div>
      <Link to="#" className="mt-8 inline-block text-white/80 underline-offset-4 hover:underline">Full tables →</Link>
    </section>
  );
}

/** News as the season's logbook: date on the left, entry on the right, one line down. */
function Logbook() {
  return (
    <section className="bg-white py-20 text-ink">
      <div className="mx-auto max-w-4xl px-4 lg:px-8">
        <p className="text-sm uppercase tracking-[0.3em] text-slate-400">Logbook</p>
        <h2 className="mt-2 text-3xl font-black sm:text-4xl">What happened</h2>
        <ol className="mt-10 border-l-2 border-slate-200">
          {NEWS.map((item) => (
            <li key={item.title} className="relative grid grid-cols-[minmax(0,1fr)] gap-4 pb-10 pl-8 sm:grid-cols-[8rem_1fr_9rem]">
              <span className="absolute -left-[7px] top-1.5 size-3 rounded-full bg-brand-600" />
              <p className="text-sm font-semibold text-slate-500">
                {formatDate(item.date)}
                <span className="block text-xs font-normal uppercase tracking-wide text-brand-600">{item.league}</span>
              </p>
              <div>
                <h3 className="text-xl font-bold leading-snug">{item.title}</h3>
                <p className="mt-1 text-slate-600">{item.teaser}</p>
              </div>
              <div className="aspect-[4/3] overflow-hidden rounded-lg"><Img photo={item.photo} /></div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

/** Media as one film strip across the full width, video first. */
function FilmStrip() {
  const frames = [PHOTOS.helgaNrv, PHOTOS.kiel4, PHOTOS.helgaBahn, PHOTOS.kiel12, PHOTOS.eckernfoerde, PHOTOS.mueritz];
  return (
    <section className="py-20">
      <div className="mx-auto mb-8 max-w-7xl px-4 lg:px-8">
        <p className="text-sm uppercase tracking-[0.3em] text-white/50">Media</p>
        <h2 className="mt-2 text-3xl font-black sm:text-4xl">From the water</h2>
      </div>
      <ul className="scrollbar-none flex snap-x gap-3 overflow-x-auto px-4 lg:px-8">
        <li className="w-[85vw] shrink-0 snap-start sm:w-[36rem]"><VideoTile video={VIDEOS[0]} /></li>
        {frames.map((p) => (
          <li key={p.src} className="aspect-video w-[70vw] shrink-0 snap-start overflow-hidden rounded-lg sm:w-[28rem]">
            <Img photo={p} />
          </li>
        ))}
      </ul>
    </section>
  );
}
