import { useState } from "react";
import { Link } from "react-router-dom";

import { LEAGUES, MATCHDAYS, NEWS, PHOTOS, STANDINGS, VIDEOS } from "./data";
import { LeaguePage } from "./LeaguePage";
import { Footer, Img, LanguageToggle, LeagueTabs, LiveDot, Logo, MatchdayList, MyArea, NewsCard, PressList, VideoTile } from "./kit";
import { useWireframe } from "./nav";

const CARD_PHOTO = [PHOTOS.alster, PHOTOS.helgaBahn, PHOTOS.helga2022, PHOTOS.stMoritz];
const TABS = ["News", "Media", "Press", "Calendar"] as const;

/** Option 5 — "League hub": the thin bar on top *is* the navigation. The home page is
 *  only a way into the leagues — one card each, with leader, next date and live state —
 *  plus the association's own news, media and press in tabs. No second menu. */
export function Option5() {
  const { league } = useWireframe();
  return (
    <div className="min-h-dvh bg-page text-ink">
      <LeagueTabs variant="brand" status right={<><LanguageToggle dark /><MyArea tone="dark" /></>} />
      <header className="bg-white">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-4 px-4 lg:px-8">
          <Logo />
          <span className="ml-auto text-sm text-slate-500">Search clubs, sailors, matchdays…</span>
        </div>
      </header>
      {league ? <LeaguePage league={league} /> : <Home />}
      <Footer />
    </div>
  );
}

function Home() {
  const { to } = useWireframe();
  const [tab, setTab] = useState<(typeof TABS)[number]>("News");
  return (
    <main className="mx-auto max-w-7xl space-y-12 px-4 py-10 lg:px-8">
      <section>
        <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">Deutsche Segel-Liga</h1>
        <p className="mt-1 text-slate-600">Four competitions, one association. Pick your league.</p>
      </section>

      <section className="grid gap-5 md:grid-cols-2">
        {LEAGUES.map((league, i) => {
          const rows = STANDINGS[league.slug] ?? [];
          const day = MATCHDAYS.find((d) => d.league === league.short && d.state !== "done");
          return (
            <article key={league.slug} className="overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-slate-200">
              <Link to={to(league.slug)} className="relative block h-40 bg-slate-900">
                <Img photo={CARD_PHOTO[i]} className="opacity-75" />
                <div className="absolute inset-0 flex items-end justify-between bg-gradient-to-t from-slate-950/80 to-transparent p-5 text-white">
                  <h2 className="text-2xl font-bold">{league.short}</h2>
                  {day?.state === "live" && (
                    <span className="inline-flex items-center gap-2 rounded-full bg-red-600 px-3 py-1 text-xs font-bold"><LiveDot /> LIVE</span>
                  )}
                </div>
              </Link>
              <div className="grid grid-cols-2 gap-4 p-5 text-sm">
                <div>
                  <p className="text-xs uppercase text-slate-500">Top 3</p>
                  {rows.length ? (
                    <ol className="mt-1 space-y-0.5">
                      {rows.slice(0, 3).map((r) => (
                        <li key={r.short}><b>{r.rank}.</b> {r.short} <span className="text-slate-500">{r.points}</span></li>
                      ))}
                    </ol>
                  ) : (
                    <p className="mt-1 text-slate-500">No races yet</p>
                  )}
                </div>
                <div>
                  <p className="text-xs uppercase text-slate-500">{day?.state === "live" ? "Racing now" : "Next"}</p>
                  <p className="mt-1 font-semibold">{day ? day.title : "Season over"}</p>
                  <p className="text-slate-500">{day ? `${day.dates} · ${day.venue.split(",")[0]}` : ""}</p>
                </div>
              </div>
              <div className="flex gap-2 border-t border-slate-100 px-5 py-3 text-sm font-semibold">
                {["Standings", "Matchdays", "Live"].map((label) => (
                  <Link key={label} to={to(league.slug)} className="rounded-full bg-slate-100 px-3 py-1 hover:bg-brand-50">{label}</Link>
                ))}
              </div>
            </article>
          );
        })}
      </section>

      <section>
        <div role="tablist" className="mb-5 flex gap-1 border-b border-slate-300">
          {TABS.map((t) => (
            <button
              key={t}
              type="button"
              role="tab"
              aria-selected={tab === t}
              onClick={() => setTab(t)}
              className={`-mb-px border-b-2 px-4 py-2 font-semibold ${tab === t ? "border-brand-600 text-brand-700" : "border-transparent text-slate-500"}`}
            >
              {t}
            </button>
          ))}
        </div>
        {tab === "News" && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{NEWS.slice(0, 6).map((n) => <NewsCard key={n.title} item={n} />)}</div>
        )}
        {tab === "Media" && (
          <div className="grid gap-4 md:grid-cols-2">{VIDEOS.map((v) => <VideoTile key={v.src} video={v} />)}</div>
        )}
        {tab === "Press" && <PressList />}
        {tab === "Calendar" && <MatchdayList />}
      </section>

      <section className="rounded-2xl bg-brand-700 p-8 text-white">
        <h2 className="text-2xl font-bold">Your club, your regatta</h2>
        <p className="mt-1 max-w-2xl text-white/80">
          The association offers this platform to every club: pairing lists, result entry, live tracking, waivers and expense claims.
        </p>
        <a href="#" className="mt-4 inline-block rounded-full bg-white px-5 py-2 font-semibold text-brand-800">Organise an event</a>
      </section>
    </main>
  );
}
