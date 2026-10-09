import { useState } from "react";
import { Link } from "react-router-dom";

import { MATCHDAYS, NEWS, PHOTOS, VIDEOS } from "./data";
import { LeaguePage } from "./LeaguePage";
import { Footer, Img, TopBar, LiveDot, MyArea, NewsCard, SectionTitle, VideoTile } from "./kit";
import { useWireframe } from "./nav";

const SLIDES = [
  { photo: PHOTOS.alster, kicker: "1. Liga · Act 5", title: "Glücksburg: the title race is on", cta: "Follow live" },
  { photo: PHOTOS.stMoritz, kicker: "Live tracking", title: "Every boat on the map", cta: "Open the live map" },
  { photo: PHOTOS.helga2022, kicker: "DSL-Pokal 2027", title: "Your club, one weekend, one cup", cta: "Register" },
];

const PATHS = [
  ["🏆", "Results"],
  ["📡", "Live"],
  ["📅", "Calendar"],
  ["⛵", "Clubs"],
  ["🎬", "Media"],
  ["📰", "Press"],
] as const;

const CARD_PHOTOS = [PHOTOS.helgaBahn, PHOTOS.kiel10, PHOTOS.helgaNrv, PHOTOS.alster, PHOTOS.helga2022, PHOTOS.stMoritz];

/** Option 2 — "Pathfinder", after vodafone.de: segment tabs on a light bar with the
 *  personal area at its end ("MeinVodafone"), a hero carousel, round entry tiles, and
 *  rows of cards that scroll sideways on a phone. The tiles *are* the menu — a menu row
 *  in the header beside them listed the same six entries twice. */
export function Option2() {
  const { league } = useWireframe();
  return (
    <div className="min-h-dvh bg-white text-ink">
      <TopBar variant="light" right={<><span className="hidden text-slate-500 sm:inline">Search</span><MyArea /></>} />
      {league ? <LeaguePage league={league} /> : <Home />}
      <Footer />
    </div>
  );
}

function Home() {
  const [slide, setSlide] = useState(0);
  const current = SLIDES[slide];
  return (
    <main className="mx-auto max-w-7xl space-y-14 px-4 py-6 lg:px-8">
      <section>
        <div className="relative h-80 overflow-hidden rounded-3xl bg-slate-900 sm:h-[26rem]">
          <Img photo={current.photo} className="opacity-85" />
          <div className="absolute inset-0 bg-gradient-to-r from-slate-950/80 to-transparent" />
          <div className="absolute inset-y-0 left-0 flex max-w-lg flex-col justify-center px-6 text-white sm:px-12">
            <p className="text-sm font-semibold text-white/75">{current.kicker}</p>
            <h1 className="mt-2 text-3xl font-extrabold leading-tight sm:text-5xl">{current.title}</h1>
            <a href="#" className="mt-6 w-fit rounded-full bg-brand-600 px-6 py-3 font-semibold">{current.cta}</a>
          </div>
        </div>
        <div className="mt-3 flex justify-center gap-2">
          {SLIDES.map((s, i) => (
            <button
              key={s.title}
              type="button"
              aria-label={`Slide ${i + 1}`}
              onClick={() => setSlide(i)}
              className={`h-2 rounded-full transition-all ${i === slide ? "w-8 bg-brand-600" : "w-2 bg-slate-300"}`}
            />
          ))}
        </div>
      </section>

      <section>
        <ul className="grid grid-cols-3 gap-4 sm:grid-cols-6">
          {PATHS.map(([icon, label]) => (
            <li key={label}>
              <a href="#" className="group flex flex-col items-center gap-2 text-center text-sm font-semibold">
                <span className="grid grid-cols-[minmax(0,1fr)] size-16 place-items-center rounded-full bg-slate-100 text-2xl transition group-hover:bg-brand-50 sm:size-20">{icon}</span>
                {label}
              </a>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <SectionTitle more="All matchdays">Matchdays</SectionTitle>
        <ul className="scrollbar-none -mx-4 flex snap-x gap-4 overflow-x-auto px-4 pb-2">
          {MATCHDAYS.map((day, i) => (
            <li key={`${day.league}-${day.title}`} className="w-72 shrink-0 snap-start">
              <article className="flex h-full flex-col overflow-hidden rounded-2xl ring-1 ring-slate-200">
                <div className="aspect-[16/9]"><Img photo={CARD_PHOTOS[i % CARD_PHOTOS.length]} /></div>
                <div className="flex flex-1 flex-col p-4">
                  <span className="w-fit rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold">{day.league}</span>
                  <h3 className="mt-2 text-lg font-bold">{day.title} · {day.venue.split(",")[0]}</h3>
                  <p className="text-sm text-slate-500">{day.dates}{day.winner && ` · Winner ${day.winner}`}</p>
                  <div className="mt-auto pt-4">
                    <a
                      href="#"
                      className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold text-white ${
                        day.state === "live" ? "bg-red-600" : "bg-brand-600"
                      }`}
                    >
                      {day.state === "live" && <LiveDot />}
                      {day.state === "done" ? "Results" : day.state === "live" ? "Follow live" : "Details"}
                    </a>
                  </div>
                </div>
              </article>
            </li>
          ))}
        </ul>
      </section>

      <section className="flex flex-col items-start gap-4 rounded-3xl bg-brand-50 p-8 sm:flex-row sm:items-center">
        <div className="flex-1">
          <p className="text-sm font-semibold text-brand-700">For clubs</p>
          <h2 className="text-2xl font-bold">Run your own regatta on this platform</h2>
          <p className="mt-1 text-slate-600">Pairing lists, result entry, live tracking and expense claims — a service of the association.</p>
        </div>
        <a href="#" className="rounded-full bg-brand-600 px-6 py-3 font-semibold text-white">Learn more</a>
      </section>

      <section>
        <SectionTitle more="All news">News from the leagues</SectionTitle>
        <ul className="scrollbar-none -mx-4 flex snap-x gap-4 overflow-x-auto px-4 pb-2">
          {NEWS.map((item) => (
            <li key={item.title} className="w-72 shrink-0 snap-start"><NewsCard item={item} /></li>
          ))}
        </ul>
      </section>

      <section>
        <SectionTitle more="Media library">Media</SectionTitle>
        <div className="grid grid-cols-[minmax(0,1fr)] gap-4 md:grid-cols-2">
          {VIDEOS.slice(0, 2).map((video) => <VideoTile key={video.src} video={video} />)}
        </div>
      </section>

      <section className="grid grid-cols-[minmax(0,1fr)] gap-6 rounded-3xl bg-slate-50 p-8 sm:grid-cols-3">
        {[
          ["Results & tables", ["DSBL: 1. and 2. Liga", "Junioren-Liga", "DSL-Pokal", "Archive"]],
          ["Media & press", ["Press releases", "Press kit", "Photo galleries", "Accreditation"]],
          ["Clubs & sailors", ["All clubs", "Sailor profiles", "Waiver", "Organise an event"]],
        ].map(([title, links]) => (
          <div key={title as string}>
            <p className="font-bold">{title as string}</p>
            <ul className="mt-2 space-y-1 text-sm text-brand-700">
              {(links as string[]).map((l) => <li key={l}><Link to="#">{l}</Link></li>)}
            </ul>
          </div>
        ))}
      </section>
    </main>
  );
}
