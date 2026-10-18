import { useEffect, useRef, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation, type To } from "react-router-dom";

import { useListLeagues } from "../../api/generated/sbl";
import type { League } from "../../api/types";
import { useAccount } from "../../api/useApi";
import { DEV_TOOLS } from "../../dev/devTools";
import { SLIDES, type Photo } from "../../content";
import { href } from "../../lib/site";
import { UserMenu } from "../UserMenu";
import { Surface, useTone } from "./Cards";
import { Picture } from "./Media";
import { useDetailMode, useSiteVersion } from "./settings";

// The frame of the site (`docs/site-structure.md`, Stories B-13, B-14). Clean on purpose:
// white and slate, one accent (the brand blue), generous space, type doing the work.

/** The leagues for the top row — data, never a list in the code (Story B-13). */
export function useLeagues(): League[] {
  return useListLeagues().data ?? [];
}

/** The one navigation row: logo and *Association* (the association's home), the leagues,
 *  the account. Over the picture on a chapter page, solid and sticky everywhere else — and
 *  the same entries everywhere, the current one marked (Story B-13). */
export function TopBar({
  overlay = false,
  floating = true,
  league,
}: {
  overlay?: boolean;
  /** Over the picture, fixed to the top with its own shade — or, `false`, placed by the
   *  page, which shades the bars together (the sub-menu layout's chapter page). */
  floating?: boolean;
  /** The league the page belongs to, marked in the row. */
  league?: League | null;
}) {
  const { t } = useTranslation("site");
  const leagues = useLeagues();
  const { pathname } = useLocation();
  const { account, loading, hasRole } = useAccount();
  const inLeague = (slug: string) =>
    league?.slug === slug || pathname === href.league(slug) || pathname.startsWith(`${href.league(slug)}/`);
  const atHome = !league && (pathname === href.home() || pathname === href.about());
  const entries = [
    { key: "association", to: href.home(), label: t("nav.association"), on: atHome },
    ...leagues.map((l) => ({ key: `league-${l.slug}`, to: href.league(l.slug), label: l.short_name, on: inLeague(l.slug) })),
  ];
  return (
    <header
      className={`z-40 text-sm ${
        overlay
          ? floating
            ? "fixed inset-x-0 top-0 bg-gradient-to-b from-slate-950/70 to-transparent text-white/80"
            : "relative border-b border-white/15 text-white/80"
          : "sticky top-0 border-b border-slate-200 bg-white/95 text-slate-600 backdrop-blur"
      }`}
      data-testid="site-top-bar"
    >
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-2 px-3 sm:gap-3 sm:px-4">
        <Link to={href.home()} className="shrink-0" data-testid="site-logo">
          <img
            src="/brand/deutsche-segelliga-logo.jpg"
            alt="Deutsche Segel-Liga"
            className="h-7 w-auto rounded bg-white p-0.5 sm:h-8"
            width={200}
            height={58}
          />
        </Link>
        {/* A phone has no room for five entries: one button names where you are and opens
            them as a list. Keyed on the path, so it closes when a link is followed. */}
        <details key={pathname} className="relative min-w-0 flex-1 md:hidden" data-testid="site-menu">
          <summary
            className={`flex w-max max-w-full cursor-pointer list-none items-center gap-1.5 rounded-full px-3 py-1.5 text-[13px] font-semibold [&::-webkit-details-marker]:hidden ${
              overlay ? "bg-white text-slate-950" : "bg-slate-900 text-white"
            }`}
          >
            <span aria-hidden>☰</span>
            <span className="truncate">{entries.find((e) => e.on)?.label ?? t("nav.menu")}</span>
          </summary>
          <ul className="absolute left-0 z-50 mt-2 w-56 rounded-xl border border-slate-200 bg-white p-1.5 text-slate-600 shadow-xl" aria-label={t("nav.leagues")}>
            {entries.map((e) => (
              <li key={e.key}>
                <Link
                  to={e.to}
                  aria-current={e.on ? "page" : undefined}
                  data-testid={`site-menu-${e.key}`}
                  className={`block rounded-lg px-3 py-2 ${e.on ? "font-semibold text-slate-950" : "hover:bg-slate-100"}`}
                >
                  {e.label}
                </Link>
              </li>
            ))}
          </ul>
        </details>
        <nav aria-label={t("nav.leagues")} className="scrollbar-none hidden min-w-0 flex-1 overflow-x-auto md:block" data-testid="site-leagues">
          <ul className="flex">
            {entries.map((e) => (
              <li key={e.key} className="shrink-0">
                <Link
                  to={e.to}
                  aria-current={e.on ? "page" : undefined}
                  data-testid={`site-${e.key}`}
                  className={`block whitespace-nowrap rounded-full px-2.5 py-1.5 text-[13px] font-medium transition sm:px-3 sm:text-sm ${
                    e.on
                      ? overlay
                        ? "bg-white text-slate-950"
                        : "bg-slate-900 text-white"
                      : overlay
                        ? "hover:text-white"
                        : "hover:text-slate-950"
                  }`}
                >
                  {e.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <UserMenu
          account={account}
          loading={loading}
          admin={hasRole("admin", "editor", "series_manager", "event_manager", "jury")}
        />
      </div>
    </header>
  );
}

/** The top row and the sub-menu under it, together, in the layout with a sub-menu: in
 *  pixels for scrolling, as a class for `sticky`. 57 + 48 — the row's border included. */
export const BARS = { offset: 105, top: "top-[105px]" };

/** The rows' background in the sub-menu layout, everywhere: the picture shows through,
 *  darkened and blurred, so white type reads on any photo and on content passing under. */
export const BAR_SHADE = "bg-slate-950/70 backdrop-blur-md";

/** One entry of a sub-menu. */
export type SubItem = {
  key: string;
  to: To;
  label: string;
  current: boolean;
  testId: string;
  state?: unknown;
  onClick?: () => void;
};

/** The sub-menu under the top row, in the layout with a sub-menu — drawn like my space's
 *  (`Layout`): where you are on the left, what is beside it as tabs on the right, sticking
 *  under the top row. On a league's page it holds the league's pages, on a matchday page
 *  the matchday's tabs. One `nav`: the crumbs are part of it, not a second navigation. */
export function SubBar({
  crumbs,
  items,
  label,
  testId,
  overlay = false,
}: {
  /** Over the picture: no background of its own, white type. */
  overlay?: boolean;
  /** `current`: this crumb is the page you are on — the league's own page. */
  crumbs: { label: string; to?: string; current?: boolean }[];
  items: SubItem[];
  label: string;
  testId: string;
}) {
  // The current entry kept in view: on a phone the row is wider than the screen.
  const bar = useRef<HTMLElement>(null);
  const marked = items.find((item) => item.current)?.key;
  useEffect(() => {
    const row = bar.current;
    const entry = row?.querySelector<HTMLElement>('[aria-current="page"]');
    if (!row || !entry) return;
    const left = entry.offsetLeft - row.clientWidth / 2 + entry.offsetWidth / 2;
    row.scrollTo({ left: Math.max(0, left), behavior: "smooth" });
  }, [marked]);
  return (
    // The row scrolls sideways inside itself on a phone, crumbs and tabs together — a
    // row wider than the screen would zoom the page out (Story A-10).
    <nav ref={bar} aria-label={label} data-testid={testId} className={`scrollbar-none h-12 overflow-x-auto border-b text-sm ${overlay ? "border-white/15" : "border-slate-200 bg-white/95 backdrop-blur"}`}>
      <div className="mx-auto flex h-full max-w-6xl items-stretch px-4">
        <ol className={`flex shrink-0 items-center gap-1.5 whitespace-nowrap pr-3 ${overlay ? "text-white/70" : "text-slate-500"}`} data-testid="site-sub-crumbs">
          {crumbs.map((c, i) => (
            <li key={`${c.label}-${i}`} className="flex items-center gap-1.5">
              {i > 0 && <span aria-hidden className={overlay ? "text-white/40" : "text-slate-300"}>›</span>}
              {c.to ? (
                <Link
                  to={c.to}
                  aria-current={c.current ? "page" : undefined}
                  data-testid={c.current ? "site-sub-crumb-current" : undefined}
                  className={`hover:underline ${c.current ? `font-semibold ${overlay ? "text-white" : "text-slate-900"}` : ""} ${overlay ? "hover:text-white" : "hover:text-slate-900"}`}
                >
                  {c.label}
                </Link>
              ) : (
                <span className={`font-medium ${overlay ? "text-white" : "text-slate-700"}`}>{c.label}</span>
              )}
            </li>
          ))}
        </ol>
        {/* Pills, like the top row's leagues. */}
        <ul className={`my-2 flex shrink-0 items-center gap-1 border-l pl-2 ${overlay ? "border-white/20" : "border-slate-200"}`}>
          {items.map((item) => {
            const on = item.current;
            return (
            <li key={item.key} className="shrink-0">
              <Link
                to={item.to}
                state={item.state}
                onClick={item.onClick}
                aria-current={item.current ? "page" : undefined}
                data-testid={item.testId}
                className={`block whitespace-nowrap rounded-full px-3 py-1.5 font-medium transition-colors ${
                  on
                    ? overlay
                      ? "bg-white text-slate-950"
                      : "bg-slate-900 text-white"
                    : overlay
                      ? "text-white/75 hover:bg-white/10 hover:text-white"
                      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`}
              >
                {item.label}
              </Link>
            </li>
            );
          })}
        </ul>
      </div>
    </nav>
  );
}

/** A league's pages as the sub-menu — or the association's, outside a league. */
export function LeagueSubBar({ league, overlay = false }: { league: League | null; overlay?: boolean }) {
  const { t } = useTranslation("site");
  const current = useCurrentSibling(league);
  return (
    <SubBar
      label={t("nav.pages")}
      testId="site-league-pages"
      overlay={overlay}
      // The league's name is its overview: an entry *Overview* beside it said the same twice.
      crumbs={[
        league
          ? { label: league.short_name, to: href.league(league.slug), current: current === href.league(league.slug) }
          : { label: "Deutsche Segel-Liga", to: href.home(), current: current === href.home() },
      ]}
      items={siblings(league).filter((s) => s.key !== "overview" && s.key !== "home").map((s) => ({
        key: s.key,
        to: s.to,
        label: t(`pages.${s.key}`),
        current: current === s.to,
        testId: `site-page-${s.key}`,
      }))}
    />
  );
}

/** The top row and, in the layout with a sub-menu, the sub-menu under it — sticking
 *  together. `subnav` replaces the league's pages, as a matchday's tabs do. */
export function Bars({ league, subnav }: { league: League | null; subnav?: ReactNode }) {
  const version = useSiteVersion();
  if (version === "classic") return <TopBar league={league} />;
  // On the page's picture in white, shaded and blurred — the same as on the chapter page.
  return (
    <div className={`sticky top-0 z-40 ${BAR_SHADE}`}>
      <TopBar league={league} overlay floating={false} />
      {subnav ?? <LeagueSubBar league={league} overlay />}
    </div>
  );
}

type Sibling = { to: string; key: string };

/** The pages beside this one — what the league's chapters lead to. */
function siblings(league: League | null): Sibling[] {
  if (!league) return [
    { to: href.home(), key: "home" },
    { to: href.about(), key: "about" },
  ];
  const l = league.slug;
  return [
    { to: href.league(l), key: "overview" },
    { to: href.standings(l), key: "standings" },
    { to: href.season(l), key: "season" },
    { to: href.noticeBoard(l), key: "noticeBoard" },
    { to: href.clubs(l), key: "clubs" },
    { to: href.news(l), key: "news" },
    { to: href.media(l), key: "media" },
    { to: href.press(l), key: "press" },
    { to: href.about(l), key: "about" },
  ];
}

/** Which sibling the current page belongs to: a matchday or a past year belongs to the
 *  season (or the standings), an article to the news. */
function useCurrentSibling(league: League | null) {
  const { pathname } = useLocation();
  if (league) {
    const year = pathname.match(/^\/[^/]+\/\d{4}\/([^/]+)/);
    if (year) return year[1] === "standings" ? href.standings(league.slug) : href.season(league.slug);
  }
  const matches = siblings(league).filter((s) => pathname === s.to || (s.to !== "/" && pathname.startsWith(`${s.to}/`)));
  return matches.sort((x, y) => y.to.length - x.to.length)[0]?.to ?? null;
}

type DepthProps = {
  league: League | null;
  title: string;
  kicker?: string;
  photo?: Photo;
  children: ReactNode;
  /** The sub-menu in the layout with one, instead of the league's pages — a matchday's
   *  tabs. Ignored in the classic layout, where the page draws its own row. */
  subnav?: ReactNode;
};

type FrameProps = DepthProps & {
  /** Classic: the frame shows the league's pages itself. With a sub-menu they are in it. */
  classic: boolean;
};

/** The frame of a depth page, in the layout the DEV switch picks (A band, B sheet, C split).
 *  The content is the same in all three — only the frame differs. The title is the page's
 *  one `h1`. */
export function DepthPage(props: DepthProps) {
  const mode = useDetailMode();
  const version = useSiteVersion();
  const classic = version === "classic";
  // The sub-menu layout has one frame of its own: the variants A–C are the classic one's.
  const Frame = !classic ? BackdropFrame : mode === "sheet" ? SheetFrame : mode === "split" ? SplitFrame : BandFrame;
  return (
    <div
      className={`min-h-dvh text-slate-900 ${classic ? "bg-white" : "bg-slate-950"}`}
      data-testid="site-depth-page"
      data-frame={classic ? mode : "backdrop"}
      data-version={version}
    >
      {/* The top row names the association and every league on every page (Story B-13);
          the league's own pages sit in each frame's own place — under A's picture, at
          B's sheet edge, in C's left column. */}
      <Bars league={props.league} subnav={props.subnav} />
      <Frame {...props} classic={classic} />
      <Footer />
    </div>
  );
}

/** Where a depth page's sticky second row sits: under the top bar, and in variant B also
 *  under the sheet's own row of pills. In pixels, for scrolling; as a class, for `sticky`. */
export function useSecondRow() {
  const mode = useDetailMode();
  const version = useSiteVersion();
  if (version === "submenu") return BARS;
  return mode === "sheet" ? { offset: 113, top: "top-[113px]" } : { offset: 56, top: "top-14" };
}

function Crumbs({ league, light = true }: { league: League | null; light?: boolean }) {
  const tone = light ? "text-white/70 hover:text-white" : "text-slate-500 hover:text-slate-900";
  return (
    <nav aria-label="Breadcrumb" className={`text-sm ${light ? "text-white/70" : "text-slate-500"}`}>
      <Link to={href.home()} className={tone}>Deutsche Segel-Liga</Link>
      {league && (
        <>
          {" "}› <Link to={href.league(league.slug)} className={tone}>{league.short_name}</Link>
        </>
      )}
    </nav>
  );
}

/** The sub-menu layout's frame: the page's own picture fixed behind the whole page — as
 *  behind the chapters, so a page deeper is no break in style — the kicker, the title and
 *  the content on it, in the chapters' cards (`Cards.tsx`); what needs white paper sits on
 *  a `Panel`. */
function BackdropFrame({ title, kicker, photo, children }: FrameProps) {
  return (
    <>
      <div aria-hidden className="fixed inset-0" data-testid="site-depth-picture">
        <Picture photo={photo ?? SLIDES[0]} />
        {/* How dark is the look's `--site-shade`; darker at the foot, where the cards pile up. */}
        <div
          className="absolute inset-0"
          style={{ background: "linear-gradient(to bottom, rgb(2 6 23 / calc(var(--site-shade) + 0.1)), rgb(2 6 23 / calc(var(--site-shade) - 0.1)) 40%, rgb(2 6 23 / calc(var(--site-shade) + 0.3)))" }}
        />
      </div>
      <header className="relative mx-auto max-w-6xl px-4 pb-10 pt-20 text-white sm:pt-32">
        {kicker && <p className="text-xs font-semibold uppercase tracking-widest text-white/75" data-testid="site-kicker">{kicker}</p>}
        <h1 className="mt-2 text-4xl font-semibold leading-[1.05] tracking-tight sm:text-6xl">{title}</h1>
      </header>
      <main id="content" data-column className="relative mx-auto max-w-6xl px-4 pb-16 text-white">
        <Surface kind="dark">{children}</Surface>
      </main>
    </>
  );
}

/** A · Band — a big picture with the kicker and title on it, the league's pages in a row
 *  under it, then the content on white. Under a league the top row already says where you
 *  are; a breadcrumb would repeat it. */
function BandFrame({ league, title, kicker, photo, children, classic }: FrameProps) {
  return (
    <>
      {/* With the sub-menu the picture stands still and the page scrolls over it: fixed to
          the screen, and cut to the band by the clip-path, which — unlike overflow —
          clips a fixed child too. */}
      <header className={`relative h-[52vh] max-h-[34rem] min-h-72 overflow-hidden bg-slate-900 ${classic ? "" : "[clip-path:inset(0)]"}`}>
        {classic ? (
          <Picture photo={photo ?? SLIDES[0]} className="opacity-80" />
        ) : (
          <div className="fixed inset-0">
            <Picture photo={photo ?? SLIDES[0]} className="opacity-80" />
          </div>
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-slate-950/85 via-slate-950/20 to-transparent" />
        <div className="absolute inset-x-0 bottom-0 mx-auto max-w-6xl px-4 pb-8 text-white">
          {!league && classic && <Crumbs league={league} />}
          {kicker && <p className="mt-3 text-xs font-semibold uppercase tracking-widest text-white/70" data-testid="site-kicker">{kicker}</p>}
          <h1 className="mt-1 text-4xl font-semibold tracking-tight sm:text-6xl">{title}</h1>
        </div>
      </header>
      {/* Not sticky: a matchday page's tabs are the one second row that sticks (B-15). */}
      {league && classic && <SiblingPills league={league} sticky={false} />}
      <main id="content" className="mx-auto max-w-6xl px-4 py-10">{children}</main>
    </>
  );
}

/** The sibling pages as a row of pills — under A's picture, and sticking under the top bar
 *  at the edge of B's sheet. */
function SiblingPills({ league, className = "", sticky = true }: { league: League | null; className?: string; sticky?: boolean }) {
  const { t } = useTranslation("site");
  const current = useCurrentSibling(league);
  return (
    <nav aria-label={t("nav.pages")} data-testid="site-league-pages" className={`scrollbar-none ${sticky ? "sticky top-14 z-20" : ""} overflow-x-auto border-b border-slate-100 bg-white/95 backdrop-blur ${className}`}>
      <ul className="mx-auto flex max-w-6xl items-center gap-1 px-4 py-3">
        {siblings(league).map((s) => (
          <li key={s.to} className="shrink-0">
            <Link
              to={s.to}
              data-testid={`site-page-${s.key}`}
              className={`block rounded-full px-3.5 py-1.5 text-sm font-medium transition ${current === s.to ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"}`}
            >
              {t(`pages.${s.key}`)}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

/** B · Sheet — a big picture with a big title, and the content as a white sheet sliding
 *  up over it, the sibling pages as pills at its top edge. */
function SheetFrame({ league, title, kicker, photo, children, classic }: FrameProps) {
  return (
    <>
      <header className="relative h-[62vh] min-h-[22rem] overflow-hidden bg-slate-950">
        <Picture photo={photo ?? SLIDES[0]} />
        <div className="absolute inset-0 bg-gradient-to-t from-slate-950/90 via-slate-950/30 to-slate-950/20" />
        <div className="absolute inset-x-0 bottom-24 mx-auto max-w-6xl px-4 text-white">
          {classic && <Crumbs league={league} />}
          {kicker && <p className="mt-4 font-mono text-xs tracking-widest text-white/60" data-testid="site-kicker">{kicker}</p>}
          <h1 className="mt-2 text-4xl font-semibold leading-[1.02] tracking-tight sm:text-7xl">{title}</h1>
        </div>
      </header>
      <main id="content" className="relative z-10 -mt-16 rounded-t-[2rem] bg-white shadow-[0_-12px_40px_rgba(2,6,23,0.25)]">
        {classic && <SiblingPills league={league} className="rounded-t-[2rem]" />}
        <div className="mx-auto max-w-6xl px-4 py-10">{children}</div>
      </main>
    </>
  );
}

/** C · Split — the page's picture, title and siblings fixed on the left, the content
 *  scrolling on the right; on a phone the left column becomes a compact head with pills. */
function SplitFrame({ league, title, kicker, photo, children, classic }: FrameProps) {
  const { t } = useTranslation("site");
  const current = useCurrentSibling(league);
  return (
    <div className="mx-auto grid max-w-7xl grid-cols-[minmax(0,1fr)] lg:grid-cols-[19rem_minmax(0,1fr)] lg:gap-10 lg:px-6">
      <aside className={`lg:sticky lg:overflow-y-auto lg:py-8 ${classic ? "lg:top-14 lg:h-[calc(100dvh-3.5rem)]" : "lg:top-[105px] lg:h-[calc(100dvh-105px)]"}`}>
        <div className="relative h-40 overflow-hidden bg-slate-900 lg:aspect-[4/3] lg:h-auto lg:rounded-2xl">
          <Picture photo={photo ?? SLIDES[0]} />
          <div className="absolute inset-0 bg-gradient-to-t from-slate-950/50 to-transparent lg:hidden" />
        </div>
        <div className="px-4 pt-5 lg:px-0">
          {classic && <Crumbs league={league} light={false} />}
          {kicker && <p className="mt-3 text-xs font-semibold uppercase tracking-widest text-brand-600" data-testid="site-kicker">{kicker}</p>}
          <h1 className="mt-1 text-3xl font-semibold leading-tight tracking-tight">{title}</h1>
        </div>
        {classic && <nav aria-label={t("nav.pages")} className="scrollbar-none mt-5 overflow-x-auto px-4 lg:mt-8 lg:overflow-visible lg:px-0">
          <ul className="flex gap-1 pb-1 lg:flex-col lg:gap-0.5">
            {siblings(league).map((s) => (
              <li key={s.to} className="shrink-0">
                <Link
                  to={s.to}
                  data-testid={`site-page-${s.key}`}
                  className={`block rounded-full px-3.5 py-1.5 text-sm font-medium transition lg:rounded-lg lg:px-3 lg:py-2 ${
                    current === s.to ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                  }`}
                >
                  {t(`pages.${s.key}`)}
                </Link>
              </li>
            ))}
          </ul>
        </nav>}
      </aside>
      <main id="content" className="min-w-0 border-t border-slate-100 px-4 py-8 lg:border-0 lg:px-0 lg:py-10">{children}</main>
    </div>
  );
}

/** A heading for a block on a depth page, with an optional link at its end. */
export function Block({
  title,
  more,
  children,
  testId,
}: {
  title: string;
  more?: { to: string; label: string };
  children: ReactNode;
  testId?: string;
}) {
  const tone = useTone();
  return (
    <section className="mb-12" data-testid={testId} data-flow>
      <div className={`mb-4 flex items-end justify-between gap-4 border-b pb-2 ${tone.line}`}>
        <h2 className={`text-xl font-semibold tracking-tight ${tone.text}`}>{title}</h2>
        {more && (
          <Link to={more.to} className={`shrink-0 text-sm ${tone.link}`}>
            {more.label} →
          </Link>
        )}
      </div>
      {children}
    </section>
  );
}

/** What expands in place: a row with a summary that opens to its detail. */
export function Expand({
  summary,
  children,
  open = false,
  testId,
}: {
  summary: ReactNode;
  children: ReactNode;
  open?: boolean;
  testId?: string;
}) {
  const tone = useTone();
  return (
    <details open={open} className={`group border-b last:border-0 ${tone.line}`} data-testid={testId}>
      <summary className={`flex cursor-pointer list-none items-center gap-3 py-3 [&::-webkit-details-marker]:hidden ${tone.text}`}>
        <span className="min-w-0 flex-1">{summary}</span>
        <span aria-hidden className={`transition group-open:rotate-90 ${tone.faint}`}>›</span>
      </summary>
      <div className={`pb-4 pl-1 text-sm ${tone.muted}`}>{children}</div>
    </details>
  );
}

/** Each league's pages, and the legal pages § 5 DDG wants reachable from every page. */
export function Footer() {
  const { t } = useTranslation("site");
  const { t: tc } = useTranslation();
  const leagues = useLeagues();
  return (
    <footer className="relative border-t border-slate-200 bg-slate-50 text-sm text-slate-600" data-testid="site-footer">
      <div className="mx-auto grid max-w-6xl grid-cols-[minmax(0,1fr)] gap-8 px-4 py-10 sm:grid-cols-3">
        {leagues.map((league) => (
          <div key={league.slug}>
            <Link to={href.league(league.slug)} className="font-semibold text-slate-900">{league.short_name}</Link>
            <ul className="mt-2 space-y-1">
              <li><Link to={href.standings(league.slug)} className="hover:text-slate-900">{t("pages.standings")}</Link></li>
              <li><Link to={href.season(league.slug)} className="hover:text-slate-900">{t("pages.season")}</Link></li>
              <li><Link to={href.noticeBoard(league.slug)} className="hover:text-slate-900">{t("pages.noticeBoard")}</Link></li>
              <li><Link to={href.press(league.slug)} className="hover:text-slate-900">{t("pages.press")}</Link></li>
            </ul>
          </div>
        ))}
      </div>
      {/* The foot of every page, so the clearance for the fixed dev switches belongs here:
          without it they sit on the legal links § 5 DDG wants reachable. The same
          constant as the switches themselves (`SiteShell`). */}
      <div className={`border-t border-slate-200 px-4 py-4 text-center text-xs text-slate-500 ${DEV_TOOLS ? "pb-24" : ""}`}>
        <Link to="/events" className="hover:text-slate-900">{t("footer.calendar")}</Link> ·{" "}
        <Link to="/clubs" className="hover:text-slate-900">{t("footer.allClubs")}</Link> ·{" "}
        <Link to="/legal-notice" className="hover:text-slate-900" data-testid="site-footer-legal-notice">{tc("userMenu.legalNotice")}</Link> ·{" "}
        <Link to="/privacy" className="hover:text-slate-900">{tc("userMenu.privacy")}</Link>
        <p className="mt-2">{t("footer.credits")}</p>
      </div>
    </footer>
  );
}
