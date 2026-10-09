import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { LEAGUES, MATCHDAYS, NEWS, PHOTOS, STANDINGS, VIDEOS } from "./data";
import { LeaguePage } from "./LeaguePage";
import { Footer, HeroMedia, Img, LanguageToggle, LiveDot, MyArea, PressList, TopBar, VideoTile } from "./kit";
import { formatDate, useWireframe } from "./nav";

const KEYFRAMES =
  "@keyframes wf-drift{0%,100%{transform:translate(0,0) scale(1)}50%{transform:translate(8%,6%) scale(1.15)}}" +
  "@keyframes wf-drift2{0%,100%{transform:translate(0,0) scale(1.1)}50%{transform:translate(-10%,4%) scale(0.95)}}";

/** Option 11 — "Aurora glass": dark, with slow coloured light drifting behind frosted
 *  glass — the 2025 "liquid glass" look. The navigation floats as a glass pill, the
 *  headline is thin and huge with a fading gradient, and every block is a pane of glass
 *  over the moving light. */
export function Option11() {
  const { league } = useWireframe();
  return (
    <div className="relative min-h-dvh overflow-hidden bg-[#05060a] text-white">
      <style>{KEYFRAMES}</style>
      <Aurora />
      <div className="relative">
        <TopBar variant="glass" status right={<><LanguageToggle dark /><MyArea tone="dark" /></>} />
        {league ? <div className="bg-page pt-20 text-ink"><LeaguePage league={league} /></div> : <Home />}
      </div>
      <div className="relative"><Footer /></div>
    </div>
  );
}

function Aurora() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-[140vh] motion-reduce:hidden">
      <div className="absolute -left-1/4 -top-1/4 size-[70vw] animate-[wf-drift_18s_ease-in-out_infinite] rounded-full bg-brand-500/40 blur-[120px]" />
      <div className="absolute -right-1/4 top-0 size-[60vw] animate-[wf-drift2_22s_ease-in-out_infinite] rounded-full bg-teal-400/30 blur-[120px]" />
      <div className="absolute left-1/4 top-1/3 size-[50vw] animate-[wf-drift_26s_ease-in-out_infinite] rounded-full bg-violet-500/25 blur-[140px]" />
    </div>
  );
}

function Glass({ className = "", children }: { className?: string; children: ReactNode }) {
  return (
    <div className={`rounded-3xl bg-white/[0.06] p-6 ring-1 ring-inset ring-white/15 backdrop-blur-2xl shadow-[inset_0_1px_0_rgba(255,255,255,0.15)] ${className}`}>
      {children}
    </div>
  );
}

function Home() {
  const { to } = useWireframe();
  const live = MATCHDAYS.find((d) => d.state === "live");
  return (
    <main>
      <section className="mx-auto grid min-h-dvh max-w-7xl grid-cols-[minmax(0,1fr)] items-center gap-10 px-4 pb-16 pt-28 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] lg:px-8">
        <div>
          <p className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-sm ring-1 ring-white/15 backdrop-blur"><LiveDot /> {live?.league} · {live?.title} · {live?.venue.split(",")[0]}</p>
          <h1 className="mt-6 bg-gradient-to-b from-white to-white/30 bg-clip-text text-6xl font-extralight leading-[0.95] tracking-tighter text-transparent sm:text-8xl lg:text-9xl">
            Sailing,<br />live.
          </h1>
          <p className="mt-6 max-w-lg text-lg font-light text-white/70">Three competitions, one association — every race, every boat, as it happens.</p>
          <div className="mt-8 flex flex-wrap gap-2">
            {LEAGUES.map((l) => (
              <Link key={l.slug} to={to(l.slug)} className="rounded-full bg-white/10 px-5 py-2.5 text-sm ring-1 ring-white/20 backdrop-blur transition hover:bg-white/20">
                {l.short} →
              </Link>
            ))}
          </div>
        </div>
        <div className="relative">
          <div className="aspect-[4/5] overflow-hidden rounded-[3rem] ring-1 ring-white/20"><HeroMedia photo={PHOTOS.stMoritz} /></div>
          <Glass className="absolute -bottom-6 -left-4 right-8 !p-4 sm:-left-10">
            <p className="text-xs uppercase tracking-widest text-white/50">Leading the DSBL</p>
            <div className="mt-2 flex items-end justify-between">
              <p className="text-2xl font-light">Norddeutscher Regatta Verein</p>
              <p className="text-3xl font-extralight tabular-nums">14</p>
            </div>
          </Glass>
        </div>
      </section>

      <div className="mx-auto max-w-7xl space-y-6 px-4 pb-24 lg:px-8">
        <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-3">
          {[...LEAGUES[0].divisions, LEAGUES[1].divisions[0]].map((d) => (
            <Glass key={d.slug}>
              <p className="text-sm text-white/50">{d.name}</p>
              <ol className="mt-4 space-y-3">
                {(STANDINGS[d.slug] ?? []).slice(0, 4).map((row) => (
                  <li key={row.short} className="flex items-center gap-3 font-light">
                    <span className="w-5 text-white/40">{row.rank}</span>
                    <span className="flex-1 text-lg">{row.short}</span>
                    <span className="tabular-nums">{row.points}</span>
                  </li>
                ))}
              </ol>
            </Glass>
          ))}
        </div>

        <Glass>
          <p className="text-sm text-white/50">Season 2026</p>
          <ul className="mt-4 flex flex-wrap gap-2">
            {MATCHDAYS.map((d) => (
              <li key={`${d.league}-${d.title}`} className={`rounded-full px-4 py-2 text-sm ring-1 ${d.state === "live" ? "bg-white text-slate-950 ring-white" : d.state === "done" ? "text-white/40 ring-white/10" : "ring-white/25"}`}>
                {d.dates} · {d.league} {d.title} · {d.venue.split(",")[0]}
              </li>
            ))}
          </ul>
        </Glass>

        <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
          <Glass className="!p-3"><VideoTile video={VIDEOS[1]} /></Glass>
          <div className="space-y-6">
            {NEWS.slice(0, 2).map((n) => (
              <Glass key={n.title} className="!p-0 overflow-hidden">
                <div className="aspect-[2/1]"><Img photo={n.photo} /></div>
                <div className="p-4">
                  <p className="text-xs text-white/50">{n.league} · {formatDate(n.date)}</p>
                  <p className="font-light">{n.title}</p>
                </div>
              </Glass>
            ))}
          </div>
        </div>

        <Glass>
          <p className="mb-4 text-sm text-white/50">Press</p>
          <PressList dark />
        </Glass>
      </div>
    </main>
  );
}
