import { useEffect, useRef, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation } from "react-router-dom";

import { useListLeagues } from "../../api/generated/sbl";
import type { League } from "../../api/types";
import { useAccount } from "../../api/useApi";
import { DEV_TOOLS } from "../../dev/devTools";
import { SLIDES, type Photo } from "../../content";
import { href } from "../../lib/site";
import { UserMenu } from "../UserMenu";
import { Picture } from "./Media";
import { useDetailMode } from "./settings";

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
  league,
}: {
  overlay?: boolean;
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
  // On a phone the row scrolls inside itself; keep the marked entry in view.
  const row = useRef<HTMLUListElement>(null);
  const marked = entries.find((e) => e.on)?.key;
  useEffect(() => {
    row.current?.querySelector<HTMLElement>("[aria-current=page]")?.scrollIntoView?.({ block: "nearest", inline: "nearest" });
  }, [marked, leagues.length]);
  return (
    <header
      className={`z-40 text-sm ${
        overlay
          ? "fixed inset-x-0 top-0 bg-gradient-to-b from-slate-950/70 to-transparent text-white/80"
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
        <nav aria-label={t("nav.leagues")} className="scrollbar-none min-w-0 flex-1 overflow-x-auto" data-testid="site-leagues">
          <ul ref={row} className="flex">
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
};

/** The frame of a depth page, in the layout the DEV switch picks (A band, B sheet, C split).
 *  The content is the same in all three — only the frame differs. The title is the page's
 *  one `h1`. */
export function DepthPage(props: DepthProps) {
  const mode = useDetailMode();
  const Frame = mode === "sheet" ? SheetFrame : mode === "split" ? SplitFrame : BandFrame;
  return (
    <div className="min-h-dvh bg-white text-slate-900" data-testid="site-depth-page" data-frame={mode}>
      {/* The top row names the association and every league on every page (Story B-13);
          the league's own pages sit in each frame's own place — under A's picture, at
          B's sheet edge, in C's left column. */}
      <TopBar league={props.league} />
      <Frame {...props} />
      <Footer />
    </div>
  );
}

/** Where a depth page's sticky second row sits: under the top bar, and in variant B also
 *  under the sheet's own row of pills. In pixels, for scrolling; as a class, for `sticky`. */
export function useSecondRow() {
  const mode = useDetailMode();
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

/** A · Band — a big picture with the kicker and title on it, the league's pages in a row
 *  under it, then the content on white. Under a league the top row already says where you
 *  are; a breadcrumb would repeat it. */
function BandFrame({ league, title, kicker, photo, children }: DepthProps) {
  return (
    <>
      <header className="relative h-[52vh] max-h-[34rem] min-h-72 overflow-hidden bg-slate-900">
        <Picture photo={photo ?? SLIDES[0]} className="opacity-80" />
        <div className="absolute inset-0 bg-gradient-to-t from-slate-950/85 via-slate-950/20 to-transparent" />
        <div className="absolute inset-x-0 bottom-0 mx-auto max-w-6xl px-4 pb-8 text-white">
          {!league && <Crumbs league={league} />}
          {kicker && <p className="mt-3 text-xs font-semibold uppercase tracking-widest text-white/70" data-testid="site-kicker">{kicker}</p>}
          <h1 className="mt-1 text-4xl font-semibold tracking-tight sm:text-6xl">{title}</h1>
        </div>
      </header>
      {/* Not sticky: a matchday page's tabs are the one second row that sticks (B-15). */}
      {league && <SiblingPills league={league} sticky={false} />}
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
function SheetFrame({ league, title, kicker, photo, children }: DepthProps) {
  return (
    <>
      <header className="relative h-[62vh] min-h-[22rem] overflow-hidden bg-slate-950">
        <Picture photo={photo ?? SLIDES[0]} />
        <div className="absolute inset-0 bg-gradient-to-t from-slate-950/90 via-slate-950/30 to-slate-950/20" />
        <div className="absolute inset-x-0 bottom-24 mx-auto max-w-6xl px-4 text-white">
          <Crumbs league={league} />
          {kicker && <p className="mt-4 font-mono text-xs tracking-widest text-white/60" data-testid="site-kicker">{kicker}</p>}
          <h1 className="mt-2 text-4xl font-semibold leading-[1.02] tracking-tight sm:text-7xl">{title}</h1>
        </div>
      </header>
      <main id="content" className="relative z-10 -mt-16 rounded-t-[2rem] bg-white shadow-[0_-12px_40px_rgba(2,6,23,0.25)]">
        <SiblingPills league={league} className="rounded-t-[2rem]" />
        <div className="mx-auto max-w-6xl px-4 py-10">{children}</div>
      </main>
    </>
  );
}

/** C · Split — the page's picture, title and siblings fixed on the left, the content
 *  scrolling on the right; on a phone the left column becomes a compact head with pills. */
function SplitFrame({ league, title, kicker, photo, children }: DepthProps) {
  const { t } = useTranslation("site");
  const current = useCurrentSibling(league);
  return (
    <div className="mx-auto grid max-w-7xl grid-cols-[minmax(0,1fr)] lg:grid-cols-[19rem_minmax(0,1fr)] lg:gap-10 lg:px-6">
      <aside className="lg:sticky lg:top-14 lg:h-[calc(100dvh-3.5rem)] lg:overflow-y-auto lg:py-8">
        <div className="relative h-40 overflow-hidden bg-slate-900 lg:aspect-[4/3] lg:h-auto lg:rounded-2xl">
          <Picture photo={photo ?? SLIDES[0]} />
          <div className="absolute inset-0 bg-gradient-to-t from-slate-950/50 to-transparent lg:hidden" />
        </div>
        <div className="px-4 pt-5 lg:px-0">
          <Crumbs league={league} light={false} />
          {kicker && <p className="mt-3 text-xs font-semibold uppercase tracking-widest text-brand-600" data-testid="site-kicker">{kicker}</p>}
          <h1 className="mt-1 text-3xl font-semibold leading-tight tracking-tight">{title}</h1>
        </div>
        <nav aria-label={t("nav.pages")} className="scrollbar-none mt-5 overflow-x-auto px-4 lg:mt-8 lg:overflow-visible lg:px-0">
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
        </nav>
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
  return (
    <section className="mb-12" data-testid={testId}>
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
  return (
    <details open={open} className="group border-b border-slate-200 last:border-0" data-testid={testId}>
      <summary className="flex cursor-pointer list-none items-center gap-3 py-3 [&::-webkit-details-marker]:hidden">
        <span className="min-w-0 flex-1">{summary}</span>
        <span aria-hidden className="text-slate-400 transition group-open:rotate-90">›</span>
      </summary>
      <div className="pb-4 pl-1 text-sm text-slate-600">{children}</div>
    </details>
  );
}

/** Each league's pages, and the legal pages § 5 DDG wants reachable from every page. */
export function Footer() {
  const { t } = useTranslation("site");
  const { t: tc } = useTranslation();
  const leagues = useLeagues();
  return (
    <footer className="border-t border-slate-200 bg-slate-50 text-sm text-slate-600" data-testid="site-footer">
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
