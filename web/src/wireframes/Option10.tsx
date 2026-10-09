import { Link } from "react-router-dom";

import { LEAGUES, NEWS, PHOTOS, PRESS, STANDINGS, VIDEOS } from "./data";
import { LeaguePage } from "./LeaguePage";
import { Footer, HeroMedia, Img, MyArea, TopBar, VideoTile } from "./kit";
import { formatDate, useWireframe } from "./nav";

const INK = "border-[3px] border-black";
const HARD = "shadow-[6px_6px_0_0_#000]";
const LEAGUE_COLORS = ["bg-[#c6f432]", "bg-[#ff6ad5]", "bg-[#5ce1e6]"];
const TICKER = ["R26 BYC WINS", "NRV LEADS ACT 5", "R25 NRV · DTYC · WYC", "WIND 12 KN NE", "FLIGHT 9 OF 16", "NEXT: 2. LIGA KIEL 23 OCT"];

/** Option 10 — "Neo-brutal": loud on purpose. Cream paper, heavy black rules, hard offset
 *  shadows, lime/pink/cyan, chunky uppercase type, a results ticker running across, and a
 *  "LIVE" sticker slapped on the picture — for a sport that wants younger crews. */
export function Option10() {
  const { league } = useWireframe();
  return (
    <div className="min-h-dvh bg-[#fffbea] text-black">
      <style>{"@keyframes wf-marquee{from{transform:translateX(0)}to{transform:translateX(-50%)}}"}</style>
      <TopBar variant="brutal" status right={<MyArea />} />
      {league ? <LeaguePage league={league} /> : <Home />}
      <Footer />
    </div>
  );
}

function Home() {
  const { to } = useWireframe();
  return (
    <main>
      <section className="mx-auto grid max-w-7xl grid-cols-[minmax(0,1fr)] items-center gap-8 px-4 py-10 lg:grid-cols-2 lg:px-8 lg:py-16">
        <div>
          <h1 className="text-6xl font-black uppercase leading-[0.85] tracking-tighter sm:text-8xl">
            Sail.<br />
            <span className="bg-[#ff6ad5] px-2">Race.</span><br />
            Repeat.
          </h1>
          <p className="mt-6 max-w-md text-lg font-medium">Club against club, six boats, eighteen teams, one weekend at a time.</p>
          <div className="mt-8 flex flex-wrap gap-4">
            <a href="#" className={`${INK} ${HARD} bg-[#c6f432] px-6 py-3 font-black uppercase transition hover:translate-x-1 hover:translate-y-1 hover:shadow-none`}>Watch live</a>
            <a href="#" className={`${INK} ${HARD} bg-white px-6 py-3 font-black uppercase transition hover:translate-x-1 hover:translate-y-1 hover:shadow-none`}>Results</a>
          </div>
        </div>
        <div className="relative">
          <div className={`${INK} ${HARD} aspect-[4/3] rotate-2 overflow-hidden bg-white`}><HeroMedia photo={PHOTOS.helgaBahn} /></div>
          <span className={`${INK} absolute -left-3 -top-5 grid size-28 -rotate-12 place-items-center rounded-full bg-[#ff6ad5] text-center text-lg font-black uppercase leading-none`}>
            Live<br />now!
          </span>
        </div>
      </section>

      <div className="overflow-hidden border-y-4 border-black bg-black py-3 text-[#c6f432]">
        <div className="flex w-max animate-[wf-marquee_25s_linear_infinite] gap-10 whitespace-nowrap text-xl font-black uppercase motion-reduce:animate-none">
          {[...TICKER, ...TICKER].map((t, i) => <span key={i}>✦ {t}</span>)}
        </div>
      </div>

      <div className="mx-auto max-w-7xl space-y-16 px-4 py-16 lg:px-8">
        <section>
          <h2 className="mb-6 text-4xl font-black uppercase">Pick your league</h2>
          <div className="grid grid-cols-[minmax(0,1fr)] gap-6 md:grid-cols-3">
            {LEAGUES.map((l, i) => (
              <Link key={l.slug} to={to(l.slug)} className={`${INK} ${HARD} ${LEAGUE_COLORS[i]} block p-6 transition hover:-translate-y-1`}>
                <p className="text-4xl font-black uppercase leading-none">{l.short}</p>
                <p className="mt-3 font-medium">{l.tagline}</p>
                <p className="mt-6 inline-block border-2 border-black bg-white px-3 py-1 text-sm font-black uppercase">Go →</p>
              </Link>
            ))}
          </div>
        </section>

        <section className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-2">
          {LEAGUES[0].divisions.map((d) => (
            <div key={d.slug} className={`${INK} ${HARD} bg-white`}>
              <p className="border-b-[3px] border-black bg-black px-4 py-2 font-black uppercase text-white">{d.name}</p>
              <table className="w-full text-lg">
                <tbody>
                  {(STANDINGS[d.slug] ?? []).slice(0, 6).map((row) => (
                    <tr key={row.short} className="border-b-2 border-black last:border-0">
                      <td className="w-14 border-r-2 border-black px-3 py-2 text-center font-black">{row.rank}</td>
                      <td className="px-3 py-2 font-bold">{row.short}</td>
                      <td className="px-3 py-2 text-right font-black tabular-nums">{row.points}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </section>

        <section>
          <h2 className="mb-6 text-4xl font-black uppercase">Fresh from the water</h2>
          <div className="grid grid-cols-[minmax(0,1fr)] gap-6 md:grid-cols-3">
            {NEWS.slice(0, 3).map((n, i) => (
              <article key={n.title} className={`${INK} ${HARD} bg-white ${i === 1 ? "md:-rotate-1" : i === 2 ? "md:rotate-1" : ""}`}>
                <div className="aspect-[3/2] border-b-[3px] border-black"><Img photo={n.photo} /></div>
                <div className="p-4">
                  <p className="inline-block bg-[#5ce1e6] px-2 text-xs font-black uppercase">{n.league}</p>
                  <h3 className="mt-2 text-xl font-black leading-tight">{n.title}</h3>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-2">
          <div className={`${INK} ${HARD} bg-white p-3`}><VideoTile video={VIDEOS[1]} /></div>
          <div className={`${INK} ${HARD} bg-[#c6f432] p-6`}>
            <h2 className="text-3xl font-black uppercase">Press</h2>
            <ul className="mt-4 space-y-3">
              {PRESS.map((p) => (
                <li key={p.title} className="flex items-center justify-between gap-3 border-2 border-black bg-white px-3 py-2">
                  <span className="min-w-0 truncate font-bold">{p.title}</span>
                  <span className="shrink-0 text-xs font-black uppercase">{formatDate(p.date)} ↓</span>
                </li>
              ))}
            </ul>
          </div>
        </section>
      </div>
    </main>
  );
}
