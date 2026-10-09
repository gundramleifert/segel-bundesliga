import { useState } from "react";

import { DIVISIONS, NEWS, PHOTOS, STANDINGS, VIDEOS } from "./data";
import { LeaguePage } from "./LeaguePage";
import {
  Footer,
  Img,
  LanguageToggle,
  TopBar,
  LiveDot,
  MatchdayList,
  MyArea,
  PressList,
  SectionTitle,
  StandingsTable,
  VideoTile,
} from "./kit";
import { formatDate, useWireframe } from "./nav";

const LAST_RACES = [
  "R26 · BYC 1 · NRV 2 · KYC 3",
  "R25 · NRV 1 · DTYC 2 · WYC 3",
  "R24 · VSaW 1 · BYC 2 · NRV 3",
  "R23 · KYC 1 · NRV 2 · BYC 3",
  "R22 · DTYC 1 · WYC 2 · VSaW 3",
];

/** Option 3 — "Results first", after the sports portals: the live state is the first
 *  thing under the header, every league's table is on the home page, and news, press and
 *  video move to a sidebar. */
export function Option3() {
  const { league } = useWireframe();
  return (
    <div className="min-h-dvh bg-slate-100 text-ink">
      <Ticker />
      <TopBar variant="brand" status right={<><LanguageToggle dark /><MyArea tone="dark" compact /></>} />
      {league ? <LeaguePage league={league} /> : <Home />}
      <Footer />
    </div>
  );
}

function Ticker() {
  return (
    <div className="bg-slate-900 text-sm text-white">
      <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-2 lg:px-8">
        <span className="inline-flex shrink-0 items-center gap-2 rounded bg-red-600 px-2 py-0.5 text-xs font-bold uppercase">
          <LiveDot /> Live
        </span>
        <span className="shrink-0 font-semibold">1. Liga · Act 5 Glücksburg · Flight 9/16</span>
        <ul className="scrollbar-none flex min-w-0 gap-6 overflow-x-auto text-white/70">
          {LAST_RACES.map((race) => <li key={race} className="shrink-0">{race}</li>)}
        </ul>
        <a href="#" className="ml-auto hidden shrink-0 font-semibold underline sm:inline">Live map →</a>
      </div>
    </div>
  );
}

function Home() {
  const [tab, setTab] = useState(DIVISIONS[0].slug);
  return (
    <main className="mx-auto grid max-w-7xl gap-8 px-4 py-8 lg:grid-cols-3 lg:px-8">
      <div className="min-w-0 space-y-10 lg:col-span-2">
        <section>
          <SectionTitle more="All tables">Standings</SectionTitle>
          <div className="mb-3 flex flex-wrap gap-2">
            {DIVISIONS.filter((l) => (STANDINGS[l.slug] ?? []).length).map((l) => (
              <button
                key={l.slug}
                type="button"
                onClick={() => setTab(l.slug)}
                className={`rounded-full px-4 py-1.5 text-sm font-semibold ${tab === l.slug ? "bg-brand-700 text-white" : "bg-white ring-1 ring-slate-200"}`}
              >
                {l.short}
              </button>
            ))}
          </div>
          <StandingsTable slug={tab} limit={10} />
        </section>

        <section>
          <SectionTitle more="Race by race">Last result · 1. Liga Act 4 Tutzing</SectionTitle>
          <ol className="grid gap-3 sm:grid-cols-3">
            {(STANDINGS["1-liga"] ?? []).slice(0, 3).map((row, i) => (
              <li key={row.short} className={`rounded-xl p-5 text-center ${i === 0 ? "bg-amber-100" : "bg-white ring-1 ring-slate-200"}`}>
                <p className="text-3xl font-extrabold">{i + 1}.</p>
                <p className="mt-1 text-lg font-bold">{row.short}</p>
                <p className="text-sm text-slate-600">{row.club}</p>
              </li>
            ))}
          </ol>
        </section>

        <section>
          <SectionTitle more="Full calendar">Calendar</SectionTitle>
          <MatchdayList />
        </section>

        <section>
          <SectionTitle more="Galleries">Photos</SectionTitle>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {[PHOTOS.helgaNrv, PHOTOS.kiel12, PHOTOS.helgaBahn, PHOTOS.eckernfoerde].map((p) => (
              <div key={p.src} className="aspect-square overflow-hidden rounded-lg"><Img photo={p} /></div>
            ))}
          </div>
        </section>
      </div>

      <aside className="min-w-0 space-y-10">
        <section>
          <SectionTitle more="All">News</SectionTitle>
          <ul className="space-y-3">
            {NEWS.slice(0, 5).map((item) => (
              <li key={item.title} className="flex gap-3 rounded-xl bg-white p-2 ring-1 ring-slate-200">
                <div className="size-20 shrink-0 overflow-hidden rounded-lg"><Img photo={item.photo} /></div>
                <div className="min-w-0">
                  <p className="text-xs text-slate-500">{item.league} · {formatDate(item.date)}</p>
                  <p className="line-clamp-2 text-sm font-semibold">{item.title}</p>
                </div>
              </li>
            ))}
          </ul>
        </section>
        <section>
          <SectionTitle>Video</SectionTitle>
          <VideoTile video={VIDEOS[1]} />
        </section>
        <section>
          <SectionTitle more="Press centre">Press</SectionTitle>
          <PressList />
        </section>
      </aside>
    </main>
  );
}
