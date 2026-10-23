import { useEffect, useRef, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation, type To } from "react-router-dom";

import { useListLeagues } from "../../api/generated/sbl";
import type { League } from "../../api/types";
import { mayOpenAdmin, useAccount } from "../../api/useApi";
import type { Photo } from "../../content";
import { href } from "../../lib/site";
import { ThemeSwitch } from "../ThemeSwitch";
import { UserMenu } from "../UserMenu";
import { BAR_SHADE, PAGE_TITLE, SHADE_DOWN, tone } from "./Cards";
import { GlassFooter } from "./Footer";
import { Backdrop } from "./Media";

// The frame of the site (`docs/site-structure.md`, Stories B-13, B-14). Clean on purpose:
// white and slate, one accent (the brand blue), generous space, type doing the work.

/** The leagues for the top row — data, never a list in the code (Story B-13). */
export function useLeagues(): League[] {
  return useListLeagues().data ?? [];
}

/** The one navigation row: logo and *Association* (the association's home), the leagues,
 *  the account — the same entries everywhere, the current one marked (Story B-13). In the
 *  theme's colours, on whatever the page puts under it: the page shades the rows
 *  together and makes them stick (`Bars`, `Layout`). */
export function TopBar({
  league,
}: {
  /** The league the page belongs to, marked in the row. */
  league?: League | null;
}) {
  const { t } = useTranslation("site");
  const leagues = useLeagues();
  const { pathname } = useLocation();
  const { account, loading } = useAccount();
  const inLeague = (slug: string) =>
    league?.slug === slug || pathname === href.league(slug) || pathname.startsWith(`${href.league(slug)}/`);
  const atHome = !league && (pathname === href.home() || pathname === href.about());
  const entries = [
    { key: "association", to: href.home(), label: t("nav.association"), on: atHome },
    ...leagues.map((l) => ({ key: `league-${l.slug}`, to: href.league(l.slug), label: l.short_name, on: inLeague(l.slug) })),
  ];
  return (
    <header
      className="relative z-40 border-b border-separator text-sm text-muted"
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
            className="flex w-max max-w-full cursor-pointer list-none items-center gap-1.5 rounded-full bg-foreground px-3 py-1.5 text-[13px] font-semibold text-background [&::-webkit-details-marker]:hidden"
          >
            <span aria-hidden>☰</span>
            <span className="truncate">{entries.find((e) => e.on)?.label ?? t("nav.menu")}</span>
          </summary>
          <ul className="absolute left-0 z-50 mt-2 w-56 rounded-xl border border-separator bg-overlay p-1.5 text-muted shadow-xl" aria-label={t("nav.leagues")}>
            {entries.map((e) => (
              <li key={e.key}>
                <Link
                  to={e.to}
                  aria-current={e.on ? "page" : undefined}
                  data-testid={`site-menu-${e.key}`}
                  className={`block rounded-lg px-3 py-2 ${e.on ? "font-semibold text-foreground" : "hover:bg-default"}`}
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
                    e.on ? "bg-foreground text-background" : "hover:text-foreground"
                  }`}
                >
                  {e.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <ThemeSwitch />
        <UserMenu
          account={account}
          loading={loading}
          admin={mayOpenAdmin(account)}
        />
      </div>
    </header>
  );
}

/** The top row and the sub-menu under it, together: in pixels for scrolling, as a class
 *  for `sticky`. 57 + 48 — the row's border included. */
export const BARS = { offset: 105, top: "top-[105px]" };

/** The top row alone — a chapter page has no sub-menu under it. */
export const TOP_ROW = { offset: 57, top: "top-[57px]" };

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

/** The sub-menu under the top row, on the picture in white — drawn like my space's
 *  (`Layout`): where you are on the left, the pages beside it as pills, sticking under the
 *  top row. On a league's page it holds the league's pages, on a matchday page the
 *  matchday's tabs. One `nav`: the crumbs are part of it, not a second navigation. */
export function SubBar({
  crumbs,
  items,
  label,
  testId,
}: {
  /** `current`: this crumb is the page you are on — the league's own page. */
  crumbs: { label: string; to?: string; current?: boolean }[];
  items: SubItem[];
  label: string;
  testId: string;
}) {
  // The current entry kept in view: on a phone the row is wider than the screen.
  const bar = useRef<HTMLElement>(null);
  const current = items.find((item) => item.current)?.key;
  useEffect(() => {
    const row = bar.current;
    const entry = row?.querySelector<HTMLElement>('[aria-current="page"]');
    if (!row || !entry) return;
    const left = entry.offsetLeft - row.clientWidth / 2 + entry.offsetWidth / 2;
    row.scrollTo({ left: Math.max(0, left), behavior: "smooth" });
  }, [current]);
  return (
    // The row scrolls sideways inside itself on a phone, crumbs and pills together — a
    // row wider than the screen would zoom the page out (Story A-10).
    <nav ref={bar} aria-label={label} data-testid={testId} className="scrollbar-none h-12 overflow-x-auto border-b border-separator text-sm">
      <div className="mx-auto flex h-full max-w-6xl items-stretch px-4">
        <ol className="flex shrink-0 items-center gap-1.5 whitespace-nowrap pr-3 text-muted" data-testid="site-sub-crumbs">
          {crumbs.map((c, i) => (
            <li key={`${c.label}-${i}`} className="flex items-center gap-1.5">
              {i > 0 && <span aria-hidden className="text-faint">›</span>}
              {c.to ? (
                <Link
                  to={c.to}
                  aria-current={c.current ? "page" : undefined}
                  data-testid={c.current ? "site-sub-crumb-current" : undefined}
                  className={`hover:text-foreground hover:underline ${c.current ? "font-semibold text-foreground" : ""}`}
                >
                  {c.label}
                </Link>
              ) : (
                <span className="font-medium text-foreground">{c.label}</span>
              )}
            </li>
          ))}
        </ol>
        {/* Pills, like the top row's leagues. */}
        <ul className="my-2 flex shrink-0 items-center gap-1 border-l border-separator pl-2">
          {items.map((item) => (
            <li key={item.key} className="shrink-0">
              <Link
                to={item.to}
                state={item.state}
                onClick={item.onClick}
                aria-current={item.current ? "page" : undefined}
                data-testid={item.testId}
                className={`block whitespace-nowrap rounded-full px-3 py-1.5 font-medium transition-colors ${
                  item.current ? "bg-foreground text-background" : "text-muted hover:bg-default hover:text-foreground"
                }`}
              >
                {item.label}
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </nav>
  );
}

/** A league's pages as the sub-menu — or the association's, outside a league. */
export function LeagueSubBar({ league }: { league: League | null }) {
  const { t } = useTranslation("site");
  const current = useCurrentSibling(league);
  return (
    <SubBar
      label={t("nav.pages")}
      testId="site-league-pages"
      // The league's name is its overview: an entry *Overview* beside it said the same twice.
      crumbs={[
        league
          ? { label: league.short_name, to: href.league(league.slug), current: current === href.league(league.slug) }
          : { label: "Deutsche Segel-Liga", to: href.home(), current: current === href.home() },
      ]}
      items={siblings(league)
        .filter((s) => s.key !== "overview" && s.key !== "home")
        .map((s) => ({ key: s.key, to: s.to, label: t(`pages.${s.key}`), current: current === s.to, testId: `site-page-${s.key}` }))}
    />
  );
}

/** The top row and the sub-menu under it, sticking together, on the page's picture in
 *  white — shaded and blurred, as on the chapter page. `subnav` replaces the league's
 *  pages, as a matchday's tabs do. */
export function Bars({ league, subnav }: { league: League | null; subnav?: ReactNode }) {
  return (
    <div className={`sticky top-0 z-40 ${BAR_SHADE}`}>
      <TopBar league={league} />
      {subnav ?? <LeagueSubBar league={league} />}
    </div>
  );
}

/** What an official page shows while its data is on the way: the same frame and rows, an
 *  empty sub-menu of the same height — never a white page. A white one flashed on every
 *  change of league, where the next league's year is fetched before its page is drawn. */
export function PageLoading({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-dvh bg-background text-foreground">
      <Bars league={null} subnav={<div className="h-12 border-b border-separator" />} />
      <main id="content" className="mx-auto max-w-6xl px-4 py-16">
        {children}
      </main>
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
  /** The sub-menu, instead of the league's pages — a matchday's tabs. */
  subnav?: ReactNode;
};

/** The frame of a page behind a chapter: the page's own picture fixed behind the whole
 *  page — as behind the chapters, so a page deeper is no break in style — the rows, the
 *  kicker, the title and the content on it, in the chapters' cards (`Cards.tsx`); what
 *  needs close reading sits on a `Panel`. The title is the page's one `h1`. */
export function DepthPage({ league, title, kicker, photo, children, subnav }: DepthProps) {
  return (
    <div className="min-h-dvh bg-background text-foreground" data-testid="site-depth-page">
      <div aria-hidden className="fixed inset-0" data-testid="site-depth-picture">
        <Backdrop league={league?.slug} photo={photo} seed={title} />
        <div className="absolute inset-0" style={{ background: SHADE_DOWN }} />
      </div>
      {/* The top row names the association and every league on every page (Story B-13);
          the sub-menu under it, the league's pages or the matchday's tabs. */}
      <Bars league={league} subnav={subnav} />
      <header className="relative mx-auto max-w-6xl px-4 pb-10 pt-20 sm:pt-32">
        {kicker && <p className="text-xs font-semibold uppercase tracking-widest text-muted" data-testid="site-kicker">{kicker}</p>}
        <h1 className={`mt-2 ${PAGE_TITLE}`}>{title}</h1>
      </header>
      <main id="content" data-column className="relative mx-auto max-w-6xl px-4 pb-16">
        {children}
      </main>
      <GlassFooter />
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
  onToggle,
  testId,
}: {
  summary: ReactNode;
  children: ReactNode;
  open?: boolean;
  /** Told whether it is now open — for content loaded only once someone opens it. */
  onToggle?: (open: boolean) => void;
  testId?: string;
}) {
  return (
    <details
      open={open}
      onToggle={onToggle && ((e) => onToggle(e.currentTarget.open))}
      className={`group border-b last:border-0 ${tone.line}`}
      data-testid={testId}
    >
      <summary className={`flex cursor-pointer list-none items-center gap-3 py-3 [&::-webkit-details-marker]:hidden ${tone.text}`}>
        <span className="min-w-0 flex-1">{summary}</span>
        <span aria-hidden className={`transition group-open:rotate-90 ${tone.faint}`}>›</span>
      </summary>
      <div className={`pb-4 pl-1 text-sm ${tone.muted}`}>{children}</div>
    </details>
  );
}
