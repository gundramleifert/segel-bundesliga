import { useState, type ReactNode } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";

import { Img, MyArea, Slideshow, setMediaMode, useMediaMode, type MediaMode } from "./kit";
import { LEAGUES, SLIDES, VIDEOS, type Photo, type ProtoLeague } from "./data";
import { href, setChapterMode, setDetailMode, useChapterMode, useDetailMode, type ChapterMode, type DetailMode } from "./state";

// The building blocks of the option-E prototype (issue #14). Clean on purpose: white and
// slate, one accent (the brand blue), generous space, type doing the work.

/** The one navigation row: logo (the association's home), the three leagues, the
 *  personal area. Over the picture on a chapter page, solid on a depth page. */
export function TopBar({
  overlay = false,
  active,
  league,
}: {
  overlay?: boolean;
  active?: string;
  /** With a league: the row offers that league's pages, and the leagues behind a switch. */
  league?: ProtoLeague | null;
}) {
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
        {league ? (
          <>
            <LeagueSwitch league={league} />
            <LeaguePages league={league} />
          </>
        ) : (
          <nav aria-label="Leagues" className="scrollbar-none min-w-0 flex-1 overflow-x-auto">
            <ul className="flex">
              {LEAGUES.map((l) => (
                <li key={l.slug} className="shrink-0">
                  <NavLink
                    to={href.league(l.slug)}
                    data-testid={`proto-tab-${l.slug}`}
                    className={({ isActive }) => {
                      const on = isActive || active === l.slug;
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
                    {l.short}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        )}
        <MyArea tone={overlay ? "dark" : "light"} />
      </div>
    </header>
  );
}

/** The current league as a pill that opens the other two — so the row has room for the
 *  league's own pages beside it. */
function LeagueSwitch({ league }: { league: ProtoLeague }) {
  return (
    <details className="relative shrink-0" data-testid="proto-league-switch">
      <summary className="flex cursor-pointer list-none items-center gap-1 rounded-full bg-slate-900 px-3 py-1.5 text-[13px] font-semibold text-white sm:text-sm [&::-webkit-details-marker]:hidden">
        {league.short} <span aria-hidden className="text-[10px] opacity-70">▾</span>
      </summary>
      <ul className="absolute left-0 z-50 mt-2 w-48 rounded-xl border border-slate-200 bg-white p-1.5 shadow-xl">
        {LEAGUES.map((l) => (
          <li key={l.slug}>
            <Link to={href.league(l.slug)} className={`block rounded-lg px-3 py-2 ${l.slug === league.slug ? "font-semibold text-slate-950" : "text-slate-600 hover:bg-slate-100"}`}>
              {l.short}
            </Link>
          </li>
        ))}
      </ul>
    </details>
  );
}

/** The league's pages, in the top row. */
function LeaguePages({ league }: { league: ProtoLeague }) {
  const current = useCurrentSibling(league);
  return (
    <nav aria-label="Pages" className="scrollbar-none min-w-0 flex-1 overflow-x-auto" data-testid="proto-league-pages">
      <ul className="flex">
        {siblings(league)
          .filter((s) => s.label !== "Overview")
          .map((s) => (
            <li key={s.to} className="shrink-0">
              <Link
                to={s.to}
                className={`block whitespace-nowrap px-2.5 py-1.5 text-[13px] transition sm:text-sm ${
                  current === s.to ? "font-semibold text-slate-950" : "text-slate-500 hover:text-slate-950"
                }`}
              >
                {s.label}
              </Link>
            </li>
          ))}
      </ul>
    </nav>
  );
}

/** A big picture: the photo, a slideshow (fading or sliding), or a muted YouTube loop —
 *  as the development switch says. `play` is false for a chapter not on screen, so a page
 *  of chapters plays one video, not seven. */
export function Picture({ photo, className = "", play = true, video = 0 }: { photo: Photo; className?: string; play?: boolean; video?: number }) {
  const mode = useMediaMode();
  const box = `absolute inset-0 overflow-hidden ${className}`;
  // No slide marks: on a chapter they read as a second set of dots beside the chapter
  // dots, and on a depth page's band they say nothing anyone needs.
  if (mode === "slideshow") return <Slideshow key="fade" photo={photo} slides={SLIDES} className={box} kind="fade" indicator={false} />;
  if (mode === "slide") return <Slideshow key="push" photo={photo} slides={SLIDES} className={box} kind="push" indicator={false} />;
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

type DepthProps = {
  league: ProtoLeague | null;
  title: string;
  kicker?: string;
  photo?: Photo;
  children: ReactNode;
};

/** The frame of a depth page, in the layout the development switch picks (A band, B
 *  sheet, C split). The content is the same in all three — only the frame differs. */
export function DepthPage(props: DepthProps) {
  const mode = useDetailMode();
  const Frame = mode === "sheet" ? SheetFrame : mode === "split" ? SplitFrame : BandFrame;
  return (
    <div className="min-h-dvh bg-white text-slate-900">
      {/* A: one row — the league's pages sit in the top bar, no second row of pills.
          B and C show the pages in their own place (the sheet's edge, the left column). */}
      <TopBar active={props.league?.slug} league={mode === "band" ? props.league : null} />
      <Frame {...props} />
      <Footer />
    </div>
  );
}

/** The pages beside this one — what the league's chapters lead to. */
function siblings(league: ProtoLeague | null) {
  if (!league) return [{ to: href.home(), label: "Home" }, { to: href.about(), label: "About" }];
  const l = league.slug;
  return [
    { to: href.league(l), label: "Overview" },
    { to: href.standings(l), label: "Standings" },
    { to: href.season(l), label: "Season" },
    { to: href.noticeBoard(l), label: "Notice board" },
    { to: href.clubs(l), label: "Clubs" },
    { to: href.news(l), label: "News" },
    { to: href.media(l), label: "Media" },
    { to: href.press(l), label: "Press" },
    { to: href.about(l), label: "About" },
  ];
}

/** Which sibling the current page belongs to: the longest one its path starts with,
 *  so a matchday or an article lights up its section rather than nothing. */
function useCurrentSibling(league: ProtoLeague | null) {
  const { pathname } = useLocation();
  // A matchday lives under /:league/:year/… — it belongs to the season, not the overview
  // whose path it happens to start with.
  if (league && /\/\d{4}\//.test(pathname)) return href.season(league.slug);
  const matches = siblings(league).filter((s) => pathname === s.to || pathname.startsWith(`${s.to}/`));
  return matches.sort((x, y) => y.to.length - x.to.length)[0]?.to ?? null;
}

function Crumbs({ league, light = true }: { league: ProtoLeague | null; light?: boolean }) {
  const tone = light ? "text-white/70 hover:text-white" : "text-slate-500 hover:text-slate-900";
  return (
    <nav aria-label="Breadcrumb" className={`text-sm ${light ? "text-white/70" : "text-slate-500"}`}>
      <Link to={href.home()} className={tone}>Deutsche Segel-Liga</Link>
      {league && (
        <>
          {" "}› <Link to={href.league(league.slug)} className={tone}>{league.short}</Link>
        </>
      )}
    </nav>
  );
}

/** A · Band — a big picture with the kicker and title on it, then the content on white;
 *  the league's pages are in the top row. Square edges: no sheet, no overlap. */
function BandFrame({ league, title, kicker, photo, children }: DepthProps) {
  // The title lies on the picture, so the picture can be big: about half the screen.
  // Under a league the top row already says where you are; a breadcrumb would repeat it.
  return (
    <>
      <header className="relative h-[52vh] min-h-72 max-h-[34rem] overflow-hidden bg-slate-900">
        <Picture photo={photo ?? league?.photo ?? SLIDES[0]} className="opacity-80" />
        <div className="absolute inset-0 bg-gradient-to-t from-slate-950/85 via-slate-950/20 to-transparent" />
        <div className="absolute inset-x-0 bottom-0 mx-auto max-w-6xl px-4 pb-8 text-white">
          {!league && <Crumbs league={league} />}
          {kicker && <p className="mt-3 text-xs font-semibold uppercase tracking-widest text-white/70">{kicker}</p>}
          <h1 className="mt-1 text-4xl font-semibold tracking-tight sm:text-6xl">{title}</h1>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-10">{children}</main>
    </>
  );
}

/** The sibling pages as a row of pills that sticks under the top bar while the page
 *  scrolls — B's way to the league's other pages (A has them in the top row). */
function SiblingPills({ league, className = "" }: { league: ProtoLeague | null; className?: string }) {
  const current = useCurrentSibling(league);
  return (
    <nav aria-label="Pages" className={`scrollbar-none sticky top-14 z-20 overflow-x-auto border-b border-slate-100 bg-white/95 backdrop-blur ${className}`}>
      <ul className="mx-auto flex max-w-6xl items-center gap-1 px-4 py-3">
        {siblings(league).map((s) => (
          <li key={s.to} className="shrink-0">
            <Link
              to={s.to}
              className={`block rounded-full px-3.5 py-1.5 text-sm font-medium transition ${current === s.to ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"}`}
            >
              {s.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

/** B · Sheet — the chapter goes on: a big picture with a big title, and the content as a
 *  white sheet sliding up over it, the sibling pages as pills at its top edge. */
function SheetFrame({ league, title, kicker, photo, children }: DepthProps) {
  return (
    <>
      <header className="relative h-[62vh] min-h-[22rem] overflow-hidden bg-slate-950">
        <Picture photo={photo ?? league?.photo ?? SLIDES[0]} />
        <div className="absolute inset-0 bg-gradient-to-t from-slate-950/90 via-slate-950/30 to-slate-950/20" />
        <div className="absolute inset-x-0 bottom-24 mx-auto max-w-6xl px-4 text-white">
          <Crumbs league={league} />
          {kicker && <p className="mt-4 font-mono text-xs tracking-widest text-white/60">{kicker}</p>}
          <h1 className="mt-2 text-4xl font-semibold leading-[1.02] tracking-tight sm:text-7xl">{title}</h1>
        </div>
      </header>
      <main className="relative z-10 -mt-16 rounded-t-[2rem] bg-white shadow-[0_-12px_40px_rgba(2,6,23,0.25)]">
        <SiblingPills league={league} className="rounded-t-[2rem]" />
        <div className="mx-auto max-w-6xl px-4 py-10">{children}</div>
      </main>
    </>
  );
}

/** C · Split — the page's picture, title and its siblings fixed on the left, the content
 *  scrolling on the right; on a phone the left column becomes a compact head with pills. */
function SplitFrame({ league, title, kicker, photo, children }: DepthProps) {
  const current = useCurrentSibling(league);
  const pages = siblings(league);
  return (
    <div className="mx-auto grid max-w-7xl grid-cols-[minmax(0,1fr)] lg:grid-cols-[19rem_minmax(0,1fr)] lg:gap-10 lg:px-6">
      <aside className="lg:sticky lg:top-14 lg:h-[calc(100dvh-3.5rem)] lg:overflow-y-auto lg:py-8">
        <div className="relative h-40 overflow-hidden bg-slate-900 lg:aspect-[4/3] lg:h-auto lg:rounded-2xl">
          <Picture photo={photo ?? league?.photo ?? SLIDES[0]} />
          <div className="absolute inset-0 bg-gradient-to-t from-slate-950/50 to-transparent lg:hidden" />
        </div>
        <div className="px-4 pt-5 lg:px-0">
          <Crumbs league={league} light={false} />
          {kicker && <p className="mt-3 text-xs font-semibold uppercase tracking-widest text-brand-600">{kicker}</p>}
          <h1 className="mt-1 text-3xl font-semibold leading-tight tracking-tight">{title}</h1>
        </div>
        <nav aria-label="Pages" className="scrollbar-none mt-5 overflow-x-auto px-4 lg:mt-8 lg:overflow-visible lg:px-0">
          <ul className="flex gap-1 pb-1 lg:flex-col lg:gap-0.5">
            {pages.map((s) => (
              <li key={s.to} className="shrink-0">
                <Link
                  to={s.to}
                  className={`block rounded-full px-3.5 py-1.5 text-sm font-medium transition lg:rounded-lg lg:px-3 lg:py-2 ${
                    current === s.to ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                  }`}
                >
                  {s.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </aside>
      <main className="min-w-0 border-t border-slate-100 px-4 py-8 lg:border-0 lg:px-0 lg:py-10">{children}</main>
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

const DETAIL_MODES: [DetailMode, string][] = [
  ["band", "A Band"],
  ["sheet", "B Sheet"],
  ["split", "C Split"],
];

/** The development switch: a small button that opens the variants still being decided —
 *  chapters snapping or scrolling freely, pictures as photo, fade, slide or video. */
export function DevSwitch() {
  const [open, setOpen] = useState(false);
  const chapters = useChapterMode();
  const media = useMediaMode();
  const detail = useDetailMode();
  return (
    <div className="fixed bottom-4 left-4 z-50 text-sm" data-testid="proto-dev">
      {open && (
        <div className="mb-2 w-64 rounded-2xl bg-slate-900/95 p-4 text-white shadow-2xl backdrop-blur">
          <Segment label="Chapters" value={chapters} options={CHAPTER_MODES} onChange={setChapterMode} testId="proto-dev-chapters" />
          <Segment label="Pictures" value={media} options={MEDIA_MODES} onChange={setMediaMode} testId="proto-dev-media" />
          <Segment label="Detail page" value={detail} options={DETAIL_MODES} onChange={setDetailMode} testId="proto-dev-detail" />
          <div className="mt-3 border-t border-white/10 pt-3 text-xs text-white/60">
            <Link to={href.home()} className="hover:text-white">Prototype home</Link>
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
