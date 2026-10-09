import { useState } from "react";
import { Link } from "react-router-dom";

import { FACTS, LEAGUES, NEWS, PHOTOS, VIDEOS } from "./data";
import { LeaguePage } from "./LeaguePage";
import {
  Footer,
  Img,
  LanguageToggle,
  LeagueTabs,
  Logo,
  MatchdayList,
  MyArea,
  NewsCard,
  PressList,
  SectionTitle,
  VideoTile,
} from "./kit";
import { useWireframe } from "./nav";

const MENU: Record<string, string[]> = {
  Results: ["Standings 1. Liga", "Standings 2. Liga", "Junioren-Liga", "Results archive"],
  Calendar: ["All matchdays 2026", "Venues", "Add to calendar"],
  Clubs: ["All clubs", "Sailors", "Register your club"],
  Media: ["Videos", "Photo galleries", "Live tracking", "Social media"],
  Press: ["Press releases", "Press kit", "Accreditation", "Contact"],
  About: ["The association", "Organise your event here", "Partners", "Charter J/70"],
};

/** Option 1 — "Corporate", after telekom.com: a dark utility bar, a white main bar whose
 *  items open a mega menu, a big hero, then an audience switch and a strict section rhythm. */
export function Option1() {
  const { league } = useWireframe();
  return (
    <div className="min-h-dvh bg-slate-50 text-ink">
      <LeagueTabs variant="dark" right={<><LanguageToggle dark /><span className="hidden text-white/70 sm:inline">Search</span></>} />
      <header className="relative z-40 border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-16 max-w-7xl items-center gap-6 px-4 lg:px-8">
          <Logo />
          <nav className="hidden flex-1 lg:block">
            <ul className="flex gap-1 text-[15px] font-medium">
              {Object.entries(MENU).map(([label, items]) => (
                <li key={label} className="group relative">
                  <button type="button" className="rounded-md px-3 py-2 hover:bg-slate-100">
                    {label}
                  </button>
                  {/* The mega menu: one column per entry here, the full-width panel on the
                      real site. Opens on hover and on focus. */}
                  <div className="invisible absolute left-0 top-full z-50 w-64 rounded-b-xl border border-slate-200 bg-white p-3 opacity-0 shadow-xl transition group-focus-within:visible group-focus-within:opacity-100 group-hover:visible group-hover:opacity-100">
                    <p className="px-2 pb-1 text-xs font-semibold uppercase text-slate-400">{label}</p>
                    {items.map((item) => (
                      <a key={item} href="#" className="block rounded-md px-2 py-1.5 text-sm font-normal hover:bg-slate-100">
                        {item}
                      </a>
                    ))}
                  </div>
                </li>
              ))}
            </ul>
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <button type="button" className="rounded-md px-3 py-2 text-sm font-medium hover:bg-slate-100 lg:hidden">
              Menu
            </button>
            <MyArea />
          </div>
        </div>
      </header>
      {league ? <LeaguePage league={league} /> : <Home />}
      <Footer />
    </div>
  );
}

const AUDIENCES = ["All", "Fans", "Clubs & sailors", "Press", "Partners"] as const;

function Home() {
  const { to } = useWireframe();
  const [audience, setAudience] = useState<(typeof AUDIENCES)[number]>("All");

  return (
    <main>
      <section className="relative h-[28rem] overflow-hidden bg-slate-900 sm:h-[34rem]">
        <Img photo={PHOTOS.alster} className="opacity-80" />
        <div className="absolute inset-0 bg-gradient-to-r from-slate-950/80 via-slate-950/30 to-transparent" />
        <div className="absolute inset-0 mx-auto flex max-w-7xl flex-col justify-end px-4 pb-14 text-white lg:px-8">
          <p className="text-sm font-semibold uppercase tracking-widest text-white/70">Season 2026 · Act 5 live</p>
          <h1 className="mt-2 max-w-2xl text-4xl font-extrabold leading-tight sm:text-6xl">Club against club. Race by race.</h1>
          <div className="mt-6 flex flex-wrap gap-3">
            <a href="#" className="rounded-full bg-white px-5 py-2.5 font-semibold text-slate-900">Watch live</a>
            <a href="#" className="rounded-full border border-white/60 px-5 py-2.5 font-semibold">Results Act 4</a>
          </div>
        </div>
      </section>

      <div className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center gap-3 overflow-x-auto px-4 py-3 text-sm lg:px-8">
          <span className="shrink-0 text-slate-500">Information for</span>
          {AUDIENCES.map((a) => (
            <button
              key={a}
              type="button"
              onClick={() => setAudience(a)}
              className={`shrink-0 rounded-full px-4 py-1.5 ${audience === a ? "bg-slate-900 text-white" : "bg-slate-100 hover:bg-slate-200"}`}
            >
              {a}
            </button>
          ))}
        </div>
      </div>

      <div className="mx-auto max-w-7xl space-y-16 px-4 py-12 lg:px-8">
        <section className="grid items-center gap-8 overflow-hidden rounded-2xl bg-white ring-1 ring-slate-200 lg:grid-cols-2">
          <div className="aspect-[16/10] lg:aspect-auto lg:h-full">
            <Img photo={NEWS[0].photo} />
          </div>
          <div className="p-6 lg:p-10">
            <p className="text-sm font-semibold uppercase tracking-wide text-brand-600">Top story · {NEWS[0].league}</p>
            <h2 className="mt-2 text-3xl font-bold leading-tight">{NEWS[0].title}</h2>
            <p className="mt-3 text-slate-600">{NEWS[0].teaser}</p>
            <a href="#" className="mt-6 inline-block rounded-full bg-brand-600 px-5 py-2.5 font-semibold text-white">Read the report</a>
          </div>
        </section>

        <section>
          <SectionTitle>Our leagues</SectionTitle>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {LEAGUES.map((league, i) => (
              <Link key={league.slug} to={to(league.slug)} className="group relative block aspect-[4/5] overflow-hidden rounded-2xl bg-slate-900">
                <Img photo={[PHOTOS.helgaNrv, PHOTOS.helgaBahn, PHOTOS.helga2022, PHOTOS.stMoritz][i]} className="opacity-75 transition group-hover:scale-105" />
                <div className="absolute inset-0 flex flex-col justify-end bg-gradient-to-t from-slate-950/90 to-transparent p-5 text-white">
                  <p className="text-xl font-bold">{league.short}</p>
                  <p className="text-sm text-white/80">{league.tagline}</p>
                </div>
              </Link>
            ))}
          </div>
        </section>

        <section>
          <SectionTitle more="All news">Latest news</SectionTitle>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {NEWS.slice(1, 4).map((item) => (
              <NewsCard key={item.title} item={item} />
            ))}
          </div>
          <div className="mt-6 text-center">
            <button type="button" className="rounded-full border border-slate-300 bg-white px-6 py-2 text-sm font-medium">Load more</button>
          </div>
        </section>

        <section className="grid grid-cols-2 gap-4 rounded-2xl bg-brand-700 p-8 text-white lg:grid-cols-4">
          {FACTS.map((fact) => (
            <div key={fact.label}>
              <p className="text-4xl font-extrabold">{fact.value}</p>
              <p className="text-white/80">{fact.label}</p>
            </div>
          ))}
        </section>

        <section className="grid gap-10 lg:grid-cols-2">
          <div>
            <SectionTitle more="Full calendar">Matchdays</SectionTitle>
            <MatchdayList />
          </div>
          <div>
            <SectionTitle more="Press centre">Press</SectionTitle>
            <PressList />
          </div>
        </section>

        <section>
          <SectionTitle more="YouTube">Videos</SectionTitle>
          <div className="grid gap-4 md:grid-cols-3">
            {VIDEOS.slice(0, 3).map((video) => (
              <VideoTile key={video.src} video={video} />
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
