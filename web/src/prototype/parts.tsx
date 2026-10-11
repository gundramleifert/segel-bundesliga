import { useState, type ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";

import { Img, MyArea, Slideshow } from "../wireframes/kit";
import type { Photo } from "../wireframes/data";
import { setMediaMode, useMediaMode, type MediaMode } from "../wireframes/nav";
import { LEAGUES, SLIDES, VIDEOS, type ProtoLeague } from "./data";
import { href, setChapterMode, useChapterMode, type ChapterMode } from "./state";

// The building blocks of the option-E prototype (issue #14). Clean on purpose: white and
// slate, one accent (the brand blue), generous space, type doing the work.

/** The one navigation row: logo (the association's home), the three leagues, the
 *  personal area. Over the picture on a chapter page, solid on a depth page. */
export function TopBar({ overlay = false, active }: { overlay?: boolean; active?: string }) {
  return (
    <header
      className={`z-40 text-sm ${
        overlay
          ? "fixed inset-x-0 top-0 bg-gradient-to-b from-slate-950/70 to-transparent text-white/80"
          : "sticky top-0 border-b border-slate-200 bg-white/95 text-slate-600 backdrop-blur"
      }`}
      data-testid="proto-top-bar"
    >
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-2 px-3 sm:gap-3 sm:px-4">
        <Link to={href.home()} className="shrink-0" data-testid="proto-logo">
          <img src="/brand/deutsche-segelliga-logo.jpg" alt="Deutsche Segel-Liga" className="h-7 w-auto rounded bg-white p-0.5 sm:h-8" width={200} height={58} />
        </Link>
        <nav aria-label="Leagues" className="scrollbar-none min-w-0 flex-1 overflow-x-auto">
          <ul className="flex">
            {LEAGUES.map((league) => (
              <li key={league.slug} className="shrink-0">
                <NavLink
                  to={href.league(league.slug)}
                  data-testid={`proto-tab-${league.slug}`}
                  className={({ isActive }) => {
                    const on = isActive || active === league.slug;
                    return `block whitespace-nowrap rounded-full px-2.5 py-1.5 text-[13px] font-medium transition sm:px-3 sm:text-sm ${
                      on
                        ? overlay
                          ? "bg-white text-slate-950"
                          : "bg-slate-900 text-white"
                        : overlay
                          ? "hover:text-white"
                          : "hover:text-slate-950"
                    }`;
                  }}
                >
                  {league.short}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <MyArea tone={overlay ? "dark" : "light"} />
      </div>
    </header>
  );
}

/** A big picture: the photo, a slideshow (fading or sliding), or a muted YouTube loop —
 *  as the development switch says. `play` is false for a chapter not on screen, so a page
 *  of chapters plays one video, not seven. */
export function Picture({ photo, className = "", play = true, video = 0 }: { photo: Photo; className?: string; play?: boolean; video?: number }) {
  const mode = useMediaMode();
  const box = `absolute inset-0 overflow-hidden ${className}`;
  if (mode === "slideshow") return <Slideshow key="fade" photo={photo} slides={SLIDES} className={box} kind="fade" />;
  if (mode === "slide") return <Slideshow key="push" photo={photo} slides={SLIDES} className={box} kind="push" />;
  if (mode === "video" && play) return <YouTubeBackground video={video} photo={photo} className={box} />;
  return <Img photo={photo} className={box} />;
}

function YouTubeBackground({ video, photo, className }: { video: number; photo: Photo; className: string }) {
  const clip = VIDEOS[video % VIDEOS.length];
  const params = new URLSearchParams({
    autoplay: "1",
    mute: "1",
    loop: "1",
    playlist: clip.id,
    controls: "0",
    playsinline: "1",
    rel: "0",
    modestbranding: "1",
    start: String(clip.start),
  });
  return (
    // `container-type: size` lets the frame cover the box like `object-fit: cover`: at
    // least as wide as 16:9 of the box's height, and as tall as 9:16 of its width.
    <div className={`${className} [container-type:size]`}>
      <Img photo={photo} className="absolute inset-0" />
      <iframe
        title={clip.title}
        src={`https://www.youtube-nocookie.com/embed/${clip.id}?${params}`}
        allow="autoplay; encrypted-media; picture-in-picture"
        tabIndex={-1}
        className="pointer-events-none absolute left-1/2 top-1/2 h-[max(100cqh,56.25cqw)] w-[max(100cqw,177.78cqh)] -translate-x-1/2 -translate-y-1/2 border-0"
      />
    </div>
  );
}

/** A YouTube player with controls, for the media pages. */
export function YouTubePlayer({ video }: { video: number }) {
  const clip = VIDEOS[video % VIDEOS.length];
  return (
    <figure>
      <iframe
        title={clip.title}
        src={`https://www.youtube-nocookie.com/embed/${clip.id}?rel=0`}
        allow="encrypted-media; picture-in-picture; fullscreen"
        loading="lazy"
        className="aspect-video w-full rounded-xl border-0 bg-slate-900"
      />
      <figcaption className="mt-2 text-sm font-medium text-slate-700">{clip.title}</figcaption>
    </figure>
  );
}

/** One full-screen chapter of a league's page: a picture, a number, a title, a short
 *  preview — and the link to the chapter's own page, which is option E. */
export function Chapter({
  id,
  n,
  of,
  photo,
  title,
  more,
  playing,
  video,
  children,
}: {
  id: string;
  n: number;
  of: number;
  photo: Photo;
  title: string;
  more?: { to: string; label: string };
  playing: boolean;
  video?: number;
  children: ReactNode;
}) {
  const mode = useChapterMode();
  return (
    <section
      id={id}
      data-chapter={id}
      className={`relative flex items-end overflow-hidden ${mode === "snap" ? "min-h-dvh snap-start" : "min-h-[85dvh]"}`}
    >
      <Picture photo={photo} play={playing} video={video ?? n} />
      <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/65 to-slate-950/25" />
      <div className="relative mx-auto w-full max-w-6xl px-4 pb-16 pr-14 pt-24 text-white lg:pr-24">
        <p className="font-mono text-xs tracking-widest text-white/60">
          {String(n).padStart(2, "0")} / {String(of).padStart(2, "0")}
        </p>
        <h2 className="mb-6 mt-2 text-4xl font-semibold leading-[1.02] tracking-tight sm:text-6xl">{title}</h2>
        {children}
        {more && (
          <Link to={more.to} className="mt-8 inline-flex items-center gap-2 rounded-full bg-white px-5 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-white/90">
            {more.label} <span aria-hidden>→</span>
          </Link>
        )}
      </div>
    </section>
  );
}

/** The frame of a depth page: solid bar, a slim picture band with the title and the way
 *  back to the league's page, then the content on white. */
export function DepthPage({
  league,
  title,
  kicker,
  photo,
  children,
}: {
  league: ProtoLeague | null;
  title: string;
  kicker?: string;
  photo?: Photo;
  children: ReactNode;
}) {
  return (
    <div className="min-h-dvh bg-white text-slate-900">
      <TopBar active={league?.slug} />
      <header className="relative h-56 overflow-hidden bg-slate-900 sm:h-72">
        <Picture photo={photo ?? league?.photo ?? SLIDES[0]} className="opacity-70" />
        <div className="absolute inset-0 bg-gradient-to-t from-slate-950/85 to-slate-950/10" />
        <div className="absolute inset-x-0 bottom-0 mx-auto max-w-6xl px-4 pb-6 text-white">
          <nav aria-label="Breadcrumb" className="text-sm text-white/70">
            <Link to={href.home()} className="hover:text-white">Deutsche Segel-Liga</Link>
            {league && (
              <>
                {" "}› <Link to={href.league(league.slug)} className="hover:text-white">{league.short}</Link>
              </>
            )}
          </nav>
          {kicker && <p className="mt-3 text-xs font-semibold uppercase tracking-widest text-white/60">{kicker}</p>}
          <h1 className="mt-1 text-3xl font-semibold tracking-tight sm:text-5xl">{title}</h1>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-10">{children}</main>
      <Footer />
    </div>
  );
}

/** A heading for a block on a depth page, with an optional link at its end. */
export function Block({ title, more, children }: { title: string; more?: { to: string; label: string }; children: ReactNode }) {
  return (
    <section className="mb-12">
      <div className="mb-4 flex items-end justify-between gap-4 border-b border-slate-200 pb-2">
        <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
        {more && (
          <Link to={more.to} className="shrink-0 text-sm font-medium text-brand-700 hover:underline">
            {more.label} →
          </Link>
        )}
      </div>
      {children}
    </section>
  );
}

/** What expands in place: a row with a summary that opens to its detail. */
export function Expand({ summary, children, open = false }: { summary: ReactNode; children: ReactNode; open?: boolean }) {
  return (
    <details open={open} className="group border-b border-slate-200 last:border-0">
      <summary className="flex cursor-pointer list-none items-center gap-3 py-3 [&::-webkit-details-marker]:hidden">
        <span className="min-w-0 flex-1">{summary}</span>
        <span aria-hidden className="text-slate-400 transition group-open:rotate-90">›</span>
      </summary>
      <div className="pb-4 pl-1 text-sm text-slate-600">{children}</div>
    </details>
  );
}

export function Footer() {
  return (
    <footer className="border-t border-slate-200 bg-slate-50 text-sm text-slate-600">
      <div className="mx-auto grid max-w-6xl grid-cols-[minmax(0,1fr)] gap-8 px-4 py-10 sm:grid-cols-3">
        {LEAGUES.map((league) => (
          <div key={league.slug}>
            <Link to={href.league(league.slug)} className="font-semibold text-slate-900">{league.short}</Link>
            <ul className="mt-2 space-y-1">
              <li><Link to={href.standings(league.slug)} className="hover:text-slate-900">Standings</Link></li>
              <li><Link to={href.season(league.slug)} className="hover:text-slate-900">Season & matchdays</Link></li>
              <li><Link to={href.noticeBoard(league.slug)} className="hover:text-slate-900">Notice board</Link></li>
              <li><Link to={href.press(league.slug)} className="hover:text-slate-900">Press</Link></li>
            </ul>
          </div>
        ))}
      </div>
      <div className="border-t border-slate-200 px-4 py-4 text-center text-xs text-slate-500">
        Prototype · photos and videos © Deutsche Segel-Bundesliga, linked from deutsche-segelbundesliga.de · Legal notice · Privacy
      </div>
    </footer>
  );
}

const CHAPTER_MODES: [ChapterMode, string][] = [
  ["snap", "Snap"],
  ["free", "Free"],
];
const MEDIA_MODES: [MediaMode, string][] = [
  ["photo", "Photo"],
  ["slideshow", "Fade"],
  ["slide", "Slide"],
  ["video", "Video"],
];

/** The development switch: a small button that opens the variants still being decided —
 *  chapters snapping or scrolling freely, pictures as photo, fade, slide or video. */
export function DevSwitch() {
  const [open, setOpen] = useState(false);
  const chapters = useChapterMode();
  const media = useMediaMode();
  return (
    <div className="fixed bottom-4 left-4 z-50 text-sm" data-testid="proto-dev">
      {open && (
        <div className="mb-2 w-64 rounded-2xl bg-slate-900/95 p-4 text-white shadow-2xl backdrop-blur">
          <Segment label="Chapters" value={chapters} options={CHAPTER_MODES} onChange={setChapterMode} testId="proto-dev-chapters" />
          <Segment label="Pictures" value={media} options={MEDIA_MODES} onChange={setMediaMode} testId="proto-dev-media" />
          <div className="mt-3 border-t border-white/10 pt-3 text-xs text-white/60">
            <Link to={href.home()} className="hover:text-white">Prototype home</Link> ·{" "}
            <Link to="/wireframes" className="hover:text-white">Wireframes</Link>
          </div>
        </div>
      )}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        data-testid="proto-dev-button"
        className="rounded-full bg-slate-900/90 px-4 py-2 font-mono text-xs font-semibold tracking-widest text-white shadow-xl backdrop-blur"
      >
        DEV {open ? "×" : "⚙"}
      </button>
    </div>
  );
}

function Segment<T extends string>({
  label,
  value,
  options,
  onChange,
  testId,
}: {
  label: string;
  value: T;
  options: [T, string][];
  onChange: (value: T) => void;
  testId: string;
}) {
  return (
    <div className="mb-3">
      <p className="mb-1.5 text-xs uppercase tracking-widest text-white/50">{label}</p>
      <div role="radiogroup" aria-label={label} className="flex rounded-full bg-white/10 p-0.5" data-testid={testId}>
        {options.map(([v, text]) => (
          <button
            key={v}
            type="button"
            role="radio"
            aria-checked={value === v}
            onClick={() => onChange(v)}
            data-testid={`${testId}-${v}`}
            className={`flex-1 rounded-full px-2 py-1 text-xs font-semibold ${value === v ? "bg-white text-slate-900" : "text-white/70 hover:text-white"}`}
          >
            {text}
          </button>
        ))}
      </div>
    </div>
  );
}
