import { useEffect, useState, type PointerEvent, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { LEAGUES, NEWS, PHOTOS, VIDEOS, type Photo } from "./data";
import { LeaguePage } from "./LeaguePage";
import { Footer, HeroMedia, LanguageToggle, LiveDot, MatchdayList, MyArea, PressList, StandingsTable, TopBar, VideoTile } from "./kit";
import { useWireframe } from "./nav";

const CHAPTERS = [
  ["now", "Now"],
  ["table", "Table"],
  ["season", "Season"],
  ["leagues", "Leagues"],
  ["stories", "Stories"],
  ["media", "Media"],
  ["press", "Press"],
] as const;

/** Option 8 — "Chapters": the home page told as a story in full-screen chapters that snap
 *  into place as you scroll — now, the table, the season, the leagues, stories, media,
 *  press — each over its own picture, with a column of dots on the right to jump between
 *  them. The bar stays fixed over every chapter. */
export function Option8() {
  const { league } = useWireframe();
  if (league) {
    return (
      <div className="min-h-dvh bg-page text-ink">
        <div className="relative">
          <TopBar variant="overlay" status right={<><LanguageToggle dark /><MyArea tone="dark" /></>} />
          <LeaguePage league={league} />
        </div>
        <Footer />
      </div>
    );
  }
  return <Story />;
}

function Story() {
  const active = useActiveChapter();
  const { to } = useWireframe();
  return (
    // The scroller is this box, not the document, so the snapping stays on this page. Fixed
    // over the whole screen, so the document behind it has nothing left to scroll — two
    // scrollbars otherwise, the box's and the page's. Its own bar is hidden too: the dots
    // on the right are this page's scrollbar.
    <div className="scrollbar-none fixed inset-0 snap-y snap-mandatory overflow-y-auto bg-slate-950 text-white">
      <div className="fixed inset-x-0 top-0 z-40">
        <TopBar variant="overlay" status right={<><LanguageToggle dark /><MyArea tone="dark" /></>} />
      </div>

      <ChapterDots active={active} />

      <Chapter id="now" n="01" photo={PHOTOS.alster} title="Racing now.">
        <p className="inline-flex items-center gap-2 rounded-full bg-red-600 px-3 py-1 text-sm font-bold"><LiveDot /> DSBL · Act 5 · Glücksburg</p>
        <p className="mt-4 max-w-lg text-lg text-white/80">Flight 9 of 16. NRV leads the day by two points, BYC is closing in.</p>
        <div className="mt-6 flex flex-wrap gap-3">
          <a href="#" className="rounded-full bg-white px-6 py-3 font-semibold text-slate-950">Live map</a>
          <a href="#" className="rounded-full border border-white/50 px-6 py-3 font-semibold">Race results</a>
        </div>
      </Chapter>

      <Chapter id="table" n="02" photo={PHOTOS.helgaNrv} title="Where everyone stands.">
        <div className="grid grid-cols-[minmax(0,1fr)] gap-4 text-ink md:grid-cols-2">
          {LEAGUES[0].divisions.map((d) => (
            <div key={d.slug}>
              <p className="mb-2 text-sm font-semibold text-white/80">{d.name}</p>
              <StandingsTable slug={d.slug} limit={5} dense />
            </div>
          ))}
        </div>
      </Chapter>

      <Chapter id="season" n="03" photo={PHOTOS.stMoritz} title="Eleven weekends, one season.">
        <div className="max-w-2xl text-ink"><MatchdayList /></div>
      </Chapter>

      <Chapter id="leagues" n="04" photo={PHOTOS.helga2022} title="Three competitions.">
        <ul className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-3">
          {LEAGUES.map((l) => (
            <li key={l.slug}>
              <Link to={to(l.slug)} className="block h-full rounded-2xl bg-white/10 p-5 backdrop-blur transition hover:bg-white/20">
                <p className="text-2xl font-black">{l.short}</p>
                <p className="mt-1 text-sm text-white/75">{l.tagline}</p>
                <p className="mt-4 text-sm font-semibold">Enter →</p>
              </Link>
            </li>
          ))}
        </ul>
      </Chapter>

      <Chapter id="stories" n="05" photo={PHOTOS.kiel7} title="Stories from the water.">
        <ul className="space-y-4">
          {NEWS.slice(0, 3).map((item) => (
            <li key={item.title} className="border-l-2 border-white/60 pl-4">
              <p className="text-xs font-bold uppercase tracking-widest text-white/60">{item.league}</p>
              <p className="text-xl font-bold sm:text-2xl">{item.title}</p>
            </li>
          ))}
        </ul>
      </Chapter>

      <Chapter id="media" n="06" photo={PHOTOS.kiel4} title="Watch it again.">
        <div className="grid max-w-3xl grid-cols-[minmax(0,1fr)] gap-4 sm:grid-cols-2">
          {VIDEOS.slice(0, 2).map((v) => <VideoTile key={v.src} video={v} />)}
        </div>
      </Chapter>

      <Chapter id="press" n="07" photo={PHOTOS.helgaBahn} title="For the press.">
        <div className="max-w-2xl"><PressList dark /></div>
      </Chapter>

      <div className="snap-start"><Footer /></div>
    </div>
  );
}

/** The column of dots on the right. With a mouse, hovering shows a dot's name. With a
 *  thumb there is no hover, so it works like the letter index of a phone's contacts:
 *  put the thumb on the dots and slide — every chapter's name appears, the one under the
 *  thumb lights up, and the page follows it. Letting go keeps you there. */
function ChapterDots({ active }: { active: string }) {
  const [scrub, setScrub] = useState<string | null>(null);

  const chapterAt = (event: PointerEvent) =>
    (document.elementFromPoint(event.clientX, event.clientY)?.closest("[data-dot]") as HTMLElement | null)?.dataset.dot ?? null;

  const follow = (event: PointerEvent) => {
    const id = chapterAt(event);
    if (!id || id === scrub) return;
    setScrub(id);
    document.getElementById(id)?.scrollIntoView({ block: "start" });
  };

  return (
    <nav
      aria-label="Chapters"
      // `touch-none`: sliding along the dots is this control's gesture, not a page scroll.
      // While sliding, a dark band behind the names keeps them readable over the chapter.
      className={`fixed right-0 top-1/2 z-40 -translate-y-1/2 touch-none select-none rounded-l-3xl py-2 pl-6 pr-3 transition-colors lg:pr-6 ${
        scrub ? "bg-gradient-to-l from-slate-950/95 via-slate-950/80 to-slate-950/0" : ""
      }`}
      onPointerDown={(event) => {
        if (event.pointerType === "mouse") return;
        // Keeps the slide on the dots even when the thumb drifts off the column.
        try {
          event.currentTarget.setPointerCapture(event.pointerId);
        } catch {
          // A pointer the browser no longer tracks — the slide still works, uncaptured.
        }
        follow(event);
      }}
      onPointerMove={(event) => scrub && follow(event)}
      onPointerUp={() => setScrub(null)}
      onPointerCancel={() => setScrub(null)}
    >
      <ol className="flex flex-col">
        {CHAPTERS.map(([id, label]) => {
          const current = (scrub ?? active) === id;
          return (
            <li key={id}>
              <a href={`#${id}`} data-dot={id} className="group flex items-center justify-end gap-3 py-1.5">
                <span
                  className={`whitespace-nowrap rounded-full text-xs font-semibold uppercase tracking-widest transition ${
                    scrub
                      ? current
                        ? "bg-white px-3 py-1 text-sm text-slate-950"
                        : "text-white/70"
                      : "text-white/0 group-hover:text-white/80"
                  }`}
                >
                  {label}
                </span>
                <span className={`block shrink-0 rounded-full transition-all ${current ? "h-6 w-2 bg-white" : "size-2 bg-white/40 group-hover:bg-white/80"}`} />
              </a>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

function Chapter({ id, n, photo, title, children }: { id: string; n: string; photo: Photo; title: string; children: ReactNode }) {
  return (
    <section id={id} data-chapter={id} className="relative flex min-h-dvh snap-start items-end overflow-hidden">
      <HeroMedia photo={photo} className="absolute inset-0" />
      <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/60 to-slate-950/20" />
      <div className="relative mx-auto w-full max-w-7xl px-4 pb-16 pr-12 pt-24 lg:px-8 lg:pr-24">
        <p className="font-mono text-sm text-white/60">{n} / 07</p>
        <h2 className="mb-6 mt-2 text-4xl font-black leading-[0.95] tracking-tight sm:text-7xl">{title}</h2>
        {children}
      </div>
    </section>
  );
}

/** Which chapter fills most of the screen — for the dot that is drawn long. */
function useActiveChapter() {
  const [active, setActive] = useState<string>(CHAPTERS[0][0]);
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) setActive((entry.target as HTMLElement).dataset.chapter ?? CHAPTERS[0][0]);
        }
      },
      { threshold: 0.6 },
    );
    document.querySelectorAll("[data-chapter]").forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);
  return active;
}
