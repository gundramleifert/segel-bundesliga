import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { LEAGUES, NEWS, PHOTOS, STANDINGS, VIDEOS } from "./data";
import { LeaguePage } from "./LeaguePage";
import { Footer, Img, LanguageToggle, LiveDot, MatchdayList, MyArea, NewsCard, TopBar, VideoTile } from "./kit";
import { useWireframe } from "./nav";

/** Option 9 — "Bento": the first screen is a grid of rounded tiles of different sizes, each
 *  one thing at a glance — the live act, the table, the countdown, the wind, a video, the
 *  press kit, a story. Light, quiet, generous radii and soft shadows, in the manner of
 *  Apple's and Linear's product pages. */
export function Option9() {
  const { league } = useWireframe();
  return (
    <div className="min-h-dvh bg-[#f5f5f7] text-slate-900">
      <TopBar variant="light" status right={<><LanguageToggle /><MyArea /></>} />
      {league ? <LeaguePage league={league} /> : <Home />}
      <Footer />
    </div>
  );
}

function Tile({ className = "", children, dark = false }: { className?: string; children: ReactNode; dark?: boolean }) {
  return (
    <div
      className={`relative overflow-hidden rounded-[1.75rem] p-5 shadow-[0_1px_2px_rgba(0,0,0,0.04),0_8px_24px_rgba(0,0,0,0.06)] transition hover:-translate-y-0.5 hover:shadow-[0_12px_32px_rgba(0,0,0,0.1)] ${
        dark ? "bg-slate-950 text-white" : "bg-white"
      } ${className}`}
    >
      {children}
    </div>
  );
}

function Label({ children, light = false }: { children: ReactNode; light?: boolean }) {
  return <p className={`text-xs font-semibold uppercase tracking-wider ${light ? "text-white/70" : "text-slate-400"}`}>{children}</p>;
}

function Home() {
  const { to } = useWireframe();
  const top = STANDINGS["1-liga"] ?? [];
  return (
    <main className="mx-auto max-w-7xl px-3 py-3 lg:px-6">
      <div className="grid auto-rows-[10.5rem] grid-cols-2 gap-3 lg:grid-cols-4">
        <Tile className="col-span-2 row-span-2 !p-0" dark>
          <Img photo={PHOTOS.alster} className="absolute inset-0 opacity-80" />
          <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/10 to-transparent" />
          <div className="absolute inset-x-0 bottom-0 p-6">
            <p className="inline-flex items-center gap-2 rounded-full bg-white/15 px-3 py-1 text-xs font-semibold backdrop-blur"><LiveDot /> Live · DSBL Act 5</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-5xl">Glücksburg.<br />Flight 9 of 16.</h1>
            <a href="#" className="mt-4 inline-block rounded-full bg-white px-5 py-2 text-sm font-semibold text-slate-950">Watch live</a>
          </div>
        </Tile>

        <Tile className="row-span-2">
          <Label>1. Liga · top 5</Label>
          <ol className="mt-3 space-y-2.5">
            {top.slice(0, 5).map((row) => (
              <li key={row.short} className="flex items-center gap-3">
                <span className={`grid size-7 place-items-center rounded-full text-xs font-bold ${row.rank === 1 ? "bg-amber-300" : "bg-slate-100"}`}>{row.rank}</span>
                <span className="flex-1 font-semibold">{row.short}</span>
                <span className="tabular-nums text-slate-500">{row.points}</span>
              </li>
            ))}
          </ol>
          <Link to={to("dsbl")} className="absolute bottom-5 left-5 text-sm font-semibold text-brand-600">Both tables →</Link>
        </Tile>

        <Tile className="bg-gradient-to-br from-brand-500 to-brand-800 text-white">
          <Label light>Next · 2. Liga</Label>
          <p className="mt-2 text-6xl font-semibold tracking-tighter">14<span className="text-2xl"> days</span></p>
          <p className="text-sm text-white/80">Act 5 · Kiel</p>
        </Tile>

        <Tile>
          <Label>Wind on the course</Label>
          <div className="mt-2 flex items-center gap-4">
            <svg viewBox="0 0 40 40" className="size-16" aria-hidden>
              <circle cx="20" cy="20" r="18" fill="none" stroke="#e2e8f0" strokeWidth="2" />
              <path d="M20 6 L25 24 L20 21 L15 24 Z" fill="#3166b1" transform="rotate(220 20 20)" />
            </svg>
            <p className="text-4xl font-semibold tracking-tight">12<span className="text-lg text-slate-400"> kn</span></p>
          </div>
          <p className="text-sm text-slate-500">NE · gusts 16</p>
        </Tile>

        <Tile className="col-span-2">
          <Label>Leagues</Label>
          <div className="mt-3 grid grid-cols-3 gap-2">
            {LEAGUES.map((l, i) => (
              <Link key={l.slug} to={to(l.slug)} className={`flex h-20 flex-col justify-end rounded-2xl p-3 text-sm font-semibold ${["bg-sky-100", "bg-emerald-100", "bg-amber-100"][i]}`}>
                {l.short}
                <span className="text-xs font-normal text-slate-600">{l.teams} clubs</span>
              </Link>
            ))}
          </div>
        </Tile>

        <Tile className="col-span-2 row-span-2 !p-0" dark>
          <div className="absolute inset-0 p-3"><VideoTile video={VIDEOS[0]} /></div>
        </Tile>

        <Tile className="col-span-2 !p-0">
          <div className="flex h-full">
            <div className="w-2/5 shrink-0"><Img photo={NEWS[1].photo} /></div>
            <div className="min-w-0 p-5">
              <Label>{NEWS[1].league}</Label>
              <p className="mt-1 line-clamp-3 text-lg font-semibold leading-snug">{NEWS[1].title}</p>
            </div>
          </div>
        </Tile>

        <Tile dark>
          <Label light>Press</Label>
          <p className="mt-2 text-xl font-semibold">Press kit 2026</p>
          <p className="text-sm text-white/60">Logos · fact sheet · photos</p>
          <a href="#" className="absolute bottom-5 right-5 grid size-10 place-items-center rounded-full bg-white text-slate-950">↓</a>
        </Tile>

        <Tile className="!p-0">
          <Img photo={PHOTOS.stMoritz} className="absolute inset-0" />
          <p className="absolute bottom-3 left-3 rounded-full bg-white/90 px-3 py-1 text-xs font-semibold backdrop-blur">248 photos →</p>
        </Tile>

        <Tile className="col-span-2 bg-gradient-to-br from-emerald-50 to-sky-50">
          <Label>For clubs</Label>
          <p className="mt-2 max-w-sm text-2xl font-semibold tracking-tight">Run your own regatta on this platform.</p>
          <p className="text-sm text-slate-500">Pairing lists · results · live tracking · expenses</p>
          <a href="#" className="absolute bottom-5 right-5 rounded-full bg-slate-950 px-4 py-2 text-sm font-semibold text-white">Learn more</a>
        </Tile>
      </div>

      <section className="mt-16 grid grid-cols-[minmax(0,1fr)] gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
        <div>
          <h2 className="text-3xl font-semibold tracking-tight">The season</h2>
          <p className="mt-2 text-slate-500">Every matchday of every league, in one list.</p>
        </div>
        <MatchdayList />
      </section>

      <section className="mt-16">
        <h2 className="mb-6 text-3xl font-semibold tracking-tight">Stories</h2>
        <div className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-3">
          {NEWS.slice(2, 5).map((n) => <NewsCard key={n.title} item={n} />)}
        </div>
      </section>
    </main>
  );
}
