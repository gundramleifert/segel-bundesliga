import { useState } from "react";
import { Link } from "react-router-dom";

import { DIVISIONS, NEWS, STANDINGS, VIDEOS } from "./data";
import { LeaguePage } from "./LeaguePage";
import { Footer, Img, LanguageToggle, LiveDot, MyArea, PressList, TopBar, VideoTile } from "./kit";
import { formatDate, useWireframe } from "./nav";

// The six boat colours an event assigns (CLAUDE.md, "Boats have colors").
const BOATS = [
  { color: "#111827", name: "Black", team: "NRV", gap: "—" },
  { color: "#16a34a", name: "Green", team: "BYC", gap: "+0:08" },
  { color: "#1e3a8a", name: "Dark blue", team: "KYC", gap: "+0:15" },
  { color: "#dc2626", name: "Red", team: "DTYC", gap: "+0:21" },
  { color: "#9ca3af", name: "Gray", team: "WYC", gap: "+0:34" },
  { color: "#f97316", name: "Orange", team: "VSaW", gap: "+0:52" },
];

// One lap of a windward/leeward course in the chart's coordinates: up the left side to
// the windward mark, down the right side to the gate, and round again.
const LAP = "M 480 560 C 380 420, 430 250, 600 140 C 760 250, 800 420, 640 560 C 600 600, 520 600, 480 560 Z";

const BOARD = [
  { date: "09 OCT", league: "DSBL 1", act: "ACT 5", venue: "GLÜCKSBURG", status: "LIVE" },
  { date: "23 OCT", league: "DSBL 2", act: "ACT 5", venue: "KIEL", status: "NEXT" },
  { date: "06 NOV", league: "DSBL 1", act: "FINAL", venue: "HAMBURG", status: "PLANNED" },
  { date: "14 NOV", league: "POKAL", act: "FINAL", venue: "WANNSEE", status: "PLANNED" },
  { date: "04 SEP", league: "DSBL 1", act: "ACT 4", venue: "TUTZING", status: "FINAL" },
  { date: "29 AUG", league: "JUNIOREN", act: "ACT 3", venue: "HAMBURG", status: "FINAL" },
];

/** Option 7 — "Broadcast": the site as the TV coverage of a race. The page opens on the
 *  water itself — a chart with the six boats moving round the course, the wind, the live
 *  ranking — and the rest is set like on-screen graphics: standings as lower thirds, the
 *  calendar as a departures board, videos as replays. */
export function Option7() {
  const { league } = useWireframe();
  return (
    <div className="min-h-dvh bg-[#06121f] text-white">
      <div className="relative">
        <TopBar variant="overlay" status right={<><LanguageToggle dark /><MyArea tone="dark" /></>} />
        {league ? <div className="bg-page text-ink"><LeaguePage league={league} /></div> : <Home />}
      </div>
      <Footer />
    </div>
  );
}

function Home() {
  return (
    <main>
      <RaceChart />
      <LowerThirds />
      <DeparturesBoard />
      <section className="mx-auto max-w-7xl px-4 py-16 lg:px-8">
        <Kicker>Replays</Kicker>
        <div className="mt-6 grid grid-cols-[minmax(0,1fr)] gap-4 md:grid-cols-2 lg:grid-cols-4">
          {VIDEOS.map((video) => <VideoTile key={video.src} video={video} />)}
        </div>
      </section>
      <section className="mx-auto grid max-w-7xl grid-cols-[minmax(0,1fr)] gap-10 px-4 pb-20 lg:grid-cols-2 lg:px-8">
        <div>
          <Kicker>Headlines</Kicker>
          <ul className="mt-6 space-y-3">
            {NEWS.slice(0, 4).map((item) => (
              <li key={item.title} className="flex gap-4 rounded-lg bg-white/5 p-3">
                <div className="h-16 w-24 shrink-0 overflow-hidden rounded"><Img photo={item.photo} /></div>
                <div className="min-w-0">
                  <p className="text-xs font-bold uppercase text-cyan-300">{item.league} · {formatDate(item.date)}</p>
                  <p className="line-clamp-2 font-semibold">{item.title}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <Kicker>Press room</Kicker>
          <div className="mt-6"><PressList dark /></div>
        </div>
      </section>
    </main>
  );
}

function Kicker({ children }: { children: string }) {
  return (
    <h2 className="inline-flex items-center gap-3 text-sm font-black uppercase tracking-[0.25em]">
      <span className="h-5 w-1.5 bg-cyan-400" />
      {children}
    </h2>
  );
}

/** The hero: a nautical chart, the course, six boats lapping it, and the broadcast's HUD. */
function RaceChart() {
  return (
    <section className="relative h-dvh min-h-[38rem] overflow-hidden bg-[radial-gradient(ellipse_at_center,#0e3a5c_0%,#06121f_70%)]">
      <svg viewBox="0 0 1200 700" preserveAspectRatio="xMidYMid slice" className="absolute inset-0 h-full w-full" aria-hidden>
        {/* Depth contours and a chart grid — water, not a picture of water. */}
        {Array.from({ length: 9 }, (_, i) => (
          <ellipse key={i} cx="600" cy="360" rx={120 + i * 70} ry={70 + i * 45} fill="none" stroke="#38bdf8" strokeOpacity={0.07} />
        ))}
        {Array.from({ length: 13 }, (_, i) => (
          <line key={`v${i}`} x1={i * 100} y1="0" x2={i * 100} y2="700" stroke="#fff" strokeOpacity={0.04} />
        ))}
        {/* Course: start line, windward mark, leeward gate. */}
        <line x1="470" y1="600" x2="650" y2="600" stroke="#fde047" strokeDasharray="6 6" strokeWidth="2" />
        <circle cx="470" cy="600" r="7" fill="#fde047" />
        <rect x="644" y="592" width="14" height="14" fill="#f8fafc" />
        <circle cx="600" cy="130" r="9" fill="#f97316" />
        <circle cx="560" cy="560" r="7" fill="#f97316" />
        <circle cx="620" cy="560" r="7" fill="#f97316" />
        <path d={LAP} fill="none" stroke="#fff" strokeOpacity="0.12" strokeWidth="1.5" strokeDasharray="2 8" />
        {BOATS.map((boat, i) => (
          <g key={boat.name}>
            <path d="M 0 -11 L 7 9 L -7 9 Z" fill={boat.color} stroke="#fff" strokeWidth="1.5" />
            <animateMotion dur="36s" repeatCount="indefinite" rotate="auto" begin={`-${i * 1.6}s`} path={LAP} />
          </g>
        ))}
      </svg>

      <div className="absolute right-4 top-20 rounded-lg bg-black/50 px-4 py-3 text-right backdrop-blur lg:right-8">
        <p className="text-xs uppercase tracking-widest text-white/60">Wind</p>
        <p className="flex items-center justify-end gap-2 text-2xl font-black">
          <span className="inline-block rotate-[220deg] text-cyan-300">➤</span> 12 kn
        </p>
        <p className="text-xs text-white/60">from 040°</p>
      </div>

      <div className="absolute inset-x-0 bottom-0 mx-auto flex max-w-7xl flex-col gap-4 px-4 pb-16 lg:flex-row lg:items-end lg:justify-between lg:px-8">
        <div>
          <p className="inline-flex items-center gap-2 bg-red-600 px-3 py-1 text-xs font-black uppercase tracking-widest">
            <LiveDot /> Live
          </p>
          <h1 className="mt-3 text-4xl font-black uppercase leading-none sm:text-6xl">DSBL · Act 5</h1>
          <p className="mt-2 text-lg text-white/80">Glücksburg · Flight 9 · Race 26 · Leg 3 of 4</p>
          <Link to="#" className="mt-5 inline-block bg-white px-5 py-3 font-bold text-slate-950">Open the live map</Link>
        </div>
        <ol className="w-full max-w-xs overflow-hidden rounded-lg bg-black/55 text-sm backdrop-blur">
          {BOATS.map((boat, i) => (
            <li key={boat.name} className="flex items-center gap-3 border-b border-white/10 px-3 py-1.5 last:border-0">
              <span className="w-4 font-black">{i + 1}</span>
              <span className="size-3 rounded-sm ring-1 ring-white/50" style={{ background: boat.color }} />
              <span className="flex-1 font-semibold">{boat.team}</span>
              <span className="tabular-nums text-white/60">{boat.gap}</span>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

/** Standings as the lower-third graphics of a broadcast. */
function LowerThirds() {
  const tables = DIVISIONS.filter((d) => (STANDINGS[d.slug] ?? []).length);
  const [slug, setSlug] = useState(tables[0].slug);
  return (
    <section className="mx-auto max-w-7xl px-4 py-16 lg:px-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <Kicker>Standings</Kicker>
        <div className="flex gap-1">
          {tables.map((d) => (
            <button
              key={d.slug}
              type="button"
              onClick={() => setSlug(d.slug)}
              className={`px-3 py-1.5 text-sm font-bold uppercase ${slug === d.slug ? "bg-cyan-400 text-slate-950" : "bg-white/10"}`}
            >
              {d.short}
            </button>
          ))}
        </div>
      </div>
      <ol className="mt-6 space-y-1.5">
        {(STANDINGS[slug] ?? []).map((row, i) => (
          <li key={row.short} className="flex items-stretch overflow-hidden" style={{ animationDelay: `${i * 60}ms` }}>
            <span className={`grid w-14 shrink-0 place-items-center text-2xl font-black ${i === 0 ? "bg-amber-400 text-slate-950" : "bg-cyan-500 text-slate-950"}`}>
              {row.rank}
            </span>
            <span className="flex min-w-0 flex-1 items-center gap-3 bg-white px-4 py-2 text-slate-950">
              <b className="text-xl">{row.short}</b>
              <span className="hidden truncate text-slate-500 sm:inline">{row.club}</span>
            </span>
            <span className="grid w-20 shrink-0 place-items-center bg-slate-800 text-xl font-black tabular-nums">{row.points}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

/** The calendar as an airport's departures board. */
function DeparturesBoard() {
  return (
    <section className="bg-black py-16">
      <div className="mx-auto max-w-7xl px-4 lg:px-8">
        <Kicker>Departures</Kicker>
        <div className="scrollbar-none mt-6 overflow-x-auto">
          <table className="w-full min-w-[40rem] border-separate border-spacing-y-1 font-mono text-amber-300">
            <thead className="text-left text-xs text-white/40">
              <tr>{["Date", "League", "Act", "Venue", "Status"].map((h) => <th key={h} className="px-3 font-normal uppercase">{h}</th>)}</tr>
            </thead>
            <tbody>
              {BOARD.map((row) => (
                <tr key={`${row.date}-${row.act}`} className="bg-neutral-900 text-lg tracking-widest">
                  <td className="px-3 py-2">{row.date}</td>
                  <td className="px-3 py-2">{row.league}</td>
                  <td className="px-3 py-2">{row.act}</td>
                  <td className="px-3 py-2">{row.venue}</td>
                  <td className={`px-3 py-2 ${row.status === "LIVE" ? "animate-pulse text-red-400" : row.status === "FINAL" ? "text-white/50" : "text-green-400"}`}>
                    {row.status}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
