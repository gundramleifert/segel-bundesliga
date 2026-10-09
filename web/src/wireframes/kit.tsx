import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import {
  LEAGUES,
  MATCHDAYS,
  PRESS,
  STANDINGS,
  inLeague,
  type League,
  type Matchday,
  type NewsItem,
  type Photo,
  type Video,
} from "./data";
import { OPTIONS, formatDate, useWireframe, wireHref } from "./nav";

// The building blocks the five wireframes share (issue #13). What differs between the
// options is the arrangement — header, order, emphasis — so the parts stay identical and
// a comparison is about the layout, not about one option having nicer tables.

export function Img({ photo, className = "" }: { photo: Photo; className?: string }) {
  return (
    <img
      src={photo.src}
      alt={photo.alt}
      title={`Photo: ${photo.credit}, ${photo.license}`}
      loading="lazy"
      className={`block h-full w-full object-cover ${className}`}
    />
  );
}

export function VideoTile({ video, className = "" }: { video: Video; className?: string }) {
  return (
    <figure className={className}>
      {/* `preload="none"`: four videos on one page would otherwise start four downloads. */}
      <video
        controls
        preload="none"
        poster={video.poster}
        className="aspect-video w-full rounded-lg bg-slate-900 object-cover"
      >
        <source src={video.src} type="video/webm" />
      </video>
      <figcaption className="mt-2 text-sm font-medium">{video.title}</figcaption>
    </figure>
  );
}

export function Logo({ light = false }: { light?: boolean }) {
  const { home } = useWireframe();
  return (
    <Link to={home} className="flex shrink-0 items-center gap-2" data-testid="wf-logo">
      <img
        src="/brand/deutsche-segelliga-logo.jpg"
        alt="Deutsche Segel-Liga"
        className={`h-9 w-auto rounded ${light ? "bg-white p-0.5" : ""}`}
        width={200}
        height={58}
      />
    </Link>
  );
}

/** Top right on every option: the personal area. A `<details>`, so it opens without any
 *  state — this is a wireframe, the real one is `UserMenu`. */
export function MyArea({ tone = "light", compact = false }: { tone?: "light" | "dark"; compact?: boolean }) {
  const dark = tone === "dark";
  return (
    <details className="relative" data-testid="wf-my-area">
      <summary
        className={`flex cursor-pointer list-none items-center gap-2 rounded-full px-2 py-1 text-sm ${
          dark ? "text-white hover:bg-white/10" : "text-slate-700 hover:bg-slate-100"
        }`}
      >
        <span
          className={`grid size-7 place-items-center rounded-full text-xs font-semibold ${
            dark ? "bg-white text-brand-800" : "bg-brand-600 text-white"
          }`}
        >
          AS
        </span>
        {!compact && <span className="hidden sm:inline">My area</span>}
      </summary>
      <div className="absolute right-0 z-50 mt-2 w-60 rounded-xl border border-slate-200 bg-white p-2 text-sm text-slate-700 shadow-xl">
        <p className="px-3 py-2 text-xs text-slate-500">Signed in as Anna Sailor</p>
        {["My clubs (2)", "My matchdays", "Waiver & documents", "Expense claims", "Administration"].map(
          (item) => (
            <a key={item} href="#" className="block rounded-md px-3 py-2 hover:bg-slate-100">
              {item}
            </a>
          ),
        )}
        <hr className="my-1 border-slate-200" />
        <a href="#" className="block rounded-md px-3 py-2 hover:bg-slate-100">
          Sign out
        </a>
      </div>
    </details>
  );
}

export function LanguageToggle({ dark = false }: { dark?: boolean }) {
  return (
    <span className={`text-xs ${dark ? "text-white/70" : "text-slate-500"}`}>
      <b className={dark ? "text-white" : "text-slate-900"}>EN</b> | DE
    </span>
  );
}

export function SectionTitle({ children, more, light = false }: { children: ReactNode; more?: string; light?: boolean }) {
  return (
    <div className="mb-4 flex items-end justify-between gap-4">
      <h2 className={`text-xl font-bold tracking-tight sm:text-2xl ${light ? "text-white" : ""}`}>{children}</h2>
      {more && (
        <a href="#" className={`shrink-0 text-sm font-medium ${light ? "text-white/80" : "text-brand-700"} hover:underline`}>
          {more} →
        </a>
      )}
    </div>
  );
}

export function NewsCard({ item, size = "md" }: { item: NewsItem; size?: "md" | "lg" }) {
  return (
    <article className="group flex h-full flex-col overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-slate-200">
      <div className={size === "lg" ? "aspect-[16/9]" : "aspect-[3/2]"}>
        <Img photo={item.photo} />
      </div>
      <div className="flex flex-1 flex-col p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">
          {item.league} · {formatDate(item.date)}
        </p>
        <h3 className={`mt-1 font-semibold leading-snug group-hover:underline ${size === "lg" ? "text-xl" : ""}`}>
          {item.title}
        </h3>
        <p className="mt-1 text-sm text-slate-600">{item.teaser}</p>
      </div>
    </article>
  );
}

export function LiveDot() {
  return (
    <span className="relative inline-flex size-2.5">
      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-500 opacity-60" />
      <span className="relative inline-flex size-2.5 rounded-full bg-red-600" />
    </span>
  );
}

const STATE_LABEL: Record<Matchday["state"], string> = {
  done: "Result",
  live: "Live now",
  next: "Next",
  planned: "Planned",
};

export function MatchdayRow({ day }: { day: Matchday }) {
  return (
    <li className="flex items-center gap-3 border-b border-slate-100 py-3 last:border-0">
      <div className="w-20 shrink-0 text-sm font-semibold text-slate-900">{day.dates}</div>
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium">
          {day.league} · {day.title}
        </p>
        <p className="truncate text-sm text-slate-500">
          {day.venue}
          {day.winner && ` · Winner ${day.winner}`}
        </p>
      </div>
      <span
        className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${
          day.state === "live"
            ? "bg-red-50 text-red-700"
            : day.state === "done"
              ? "bg-slate-100 text-slate-700"
              : "bg-brand-50 text-brand-700"
        }`}
      >
        {day.state === "live" && <LiveDot />}
        {STATE_LABEL[day.state]}
      </span>
    </li>
  );
}

export function MatchdayList({ league }: { league?: League }) {
  const days = league ? MATCHDAYS.filter((day) => inLeague(league, day.league)) : MATCHDAYS;
  return <ul className="rounded-xl bg-white px-4 ring-1 ring-slate-200">{days.map((day) => <MatchdayRow key={`${day.league}-${day.title}`} day={day} />)}</ul>;
}

export function StandingsTable({ slug, limit = 6, dense = false }: { slug: string; limit?: number; dense?: boolean }) {
  const rows = (STANDINGS[slug] ?? []).slice(0, limit);
  if (!rows.length) {
    return <p className="rounded-xl bg-white p-4 text-sm text-slate-500 ring-1 ring-slate-200">No races sailed yet.</p>;
  }
  return (
    <table className="data-table w-full border-collapse text-sm">
      <thead>
        <tr className="border-b border-slate-200 bg-slate-50 text-left text-slate-600">
          <th className="w-10 font-medium">#</th>
          <th className="font-medium">Club</th>
          <th className="w-14 text-right font-medium">Pts</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.short} className="border-b border-slate-100 last:border-0">
            <td className="font-semibold">{row.rank}</td>
            <td className="max-w-0 truncate">
              <span className="font-medium">{row.short}</span>
              {!dense && <span className="ml-2 hidden text-slate-500 sm:inline">{row.club}</span>}
            </td>
            <td className="text-right tabular-nums">
              {row.points}
              <span className={`ml-1 text-xs ${row.trend > 0 ? "text-green-600" : row.trend < 0 ? "text-red-600" : "text-slate-400"}`}>
                {row.trend > 0 ? "▲" : row.trend < 0 ? "▼" : "–"}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function PressList({ dark = false }: { dark?: boolean }) {
  return (
    <ul className={`divide-y rounded-xl ${dark ? "divide-white/10 bg-white/5" : "divide-slate-100 bg-white ring-1 ring-slate-200"}`}>
      {PRESS.map((item) => (
        <li key={item.title} className="flex items-center gap-3 px-4 py-3">
          <span
            className={`grid size-9 shrink-0 place-items-center rounded-md text-[10px] font-bold ${
              dark ? "bg-white/10 text-white" : "bg-slate-100 text-slate-600"
            }`}
          >
            {item.kind === "Photos" ? "ZIP" : "PDF"}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{item.title}</p>
            <p className={`text-xs ${dark ? "text-white/60" : "text-slate-500"}`}>
              {item.kind} · {formatDate(item.date)}
            </p>
          </div>
          <a href="#" className={`shrink-0 text-sm ${dark ? "text-white" : "text-brand-700"}`} aria-label="Download">
            ↓
          </a>
        </li>
      ))}
    </ul>
  );
}

/** One footer for all five: the legal links (§ 5 DDG) and the leagues once more. */
export function Footer() {
  const { to } = useWireframe();
  return (
    <footer className="mt-16 bg-slate-900 text-slate-300">
      <div className="mx-auto grid max-w-7xl gap-8 px-4 py-12 sm:grid-cols-2 lg:grid-cols-4 lg:px-8">
        <div>
          <p className="font-semibold text-white">Leagues</p>
          <ul className="mt-3 space-y-2 text-sm">
            {LEAGUES.map((league) => (
              <li key={league.slug}>
                <Link to={to(league.slug)} className="hover:text-white">
                  {league.name}
                </Link>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="font-semibold text-white">Follow</p>
          <ul className="mt-3 space-y-2 text-sm">
            {["Results archive", "Calendar (iCal)", "Live tracking", "Media library"].map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <div>
          <p className="font-semibold text-white">Press & partners</p>
          <ul className="mt-3 space-y-2 text-sm">
            {["Press centre", "Accreditation", "Partners & sponsors", "J/70 charter"].map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <div>
          <p className="font-semibold text-white">Deutsche Segel-Liga e.V.</p>
          <ul className="mt-3 space-y-2 text-sm">
            {["About the association", "Organise your event here", "Help", "Legal notice", "Privacy"].map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      </div>
      <div className="border-t border-white/10 px-4 py-4 text-center text-xs text-slate-500">
        Wireframe · photos and videos from Wikimedia Commons —{" "}
        <Link to="/wireframes#credits" className="underline">
          credits
        </Link>
      </div>
    </footer>
  );
}

/** The floating bar to step between the options while comparing them. */
export function Switcher() {
  const { option, league } = useWireframe();
  const current = OPTIONS.find((o) => o.n === option);
  return (
    <nav
      aria-label="Wireframe options"
      data-testid="wf-switcher"
      className="fixed inset-x-0 bottom-3 z-50 mx-auto flex w-fit max-w-[calc(100vw-1.5rem)] items-center gap-1 rounded-full bg-slate-900/90 p-1 text-sm text-white shadow-2xl backdrop-blur"
    >
      <Link to="/wireframes" className="rounded-full px-3 py-1.5 hover:bg-white/10">
        All
      </Link>
      {OPTIONS.map((o) => (
        <Link
          key={o.n}
          to={wireHref(o.n, league?.slug)}
          title={o.name}
          data-testid={`wf-switch-${o.n}`}
          className={`grid size-8 place-items-center rounded-full ${o.n === option ? "bg-white font-semibold text-slate-900" : "hover:bg-white/10"}`}
        >
          {o.n}
        </Link>
      ))}
      {current && <span className="hidden px-3 text-white/70 sm:inline">{current.name}</span>}
    </nav>
  );
}

const TAB_STYLES = {
  dark: {
    bar: "bg-slate-900 text-white/75",
    item: "border-b-2 border-transparent px-3 py-4 hover:text-white",
    active: "border-white text-white font-semibold",
    logoOnDark: true,
  },
  brand: {
    bar: "bg-brand-800 text-white/75",
    item: "rounded-md px-3 py-1.5 hover:text-white",
    active: "bg-white/15 text-white font-semibold",
    logoOnDark: true,
  },
  light: {
    bar: "bg-white text-slate-600 border-b border-slate-200",
    item: "rounded-full px-4 py-1.5 hover:bg-slate-100",
    active: "bg-slate-900 text-white font-semibold",
    logoOnDark: false,
  },
  editorial: {
    bar: "bg-white text-slate-600 border-b border-slate-200",
    item: "border-b-2 border-transparent px-3 py-4 uppercase tracking-widest text-xs hover:text-slate-900",
    active: "border-brand-600 text-slate-900 font-semibold",
    logoOnDark: false,
  },
} as const;

/** The site's one navigation row (issue #13): logo, then DSBL · Junioren-Liga · DSL-Pokal —
 *  each its own URL — and the personal area at the far end. The logo is the way home.
 *
 *  One row, not two: a thin league bar above a main menu made two navigation rows, and
 *  the main menu's entries (results, media, press) are on the pages themselves anyway.
 *  `menus` hangs a drop-down under a league tab — option 1's mega menu. */
export function TopBar({
  variant,
  right,
  status = false,
  menus,
}: {
  variant: keyof typeof TAB_STYLES;
  right?: ReactNode;
  status?: boolean;
  menus?: Record<string, string[]>;
}) {
  const { league, to } = useWireframe();
  const style = TAB_STYLES[variant];
  return (
    <header className={`relative z-40 text-sm ${style.bar}`} data-testid="wf-top-bar">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-3 lg:px-6">
        <Logo light={style.logoOnDark} />
        <nav aria-label="Leagues" className="scrollbar-none min-w-0 flex-1 overflow-x-auto lg:overflow-visible">
          <ul className="flex items-center">
            {LEAGUES.map((tab) => {
              const active = league?.slug === tab.slug;
              const isLive = status && MATCHDAYS.some((d) => inLeague(tab, d.league) && d.state === "live");
              const menu = menus?.[tab.slug];
              return (
                <li key={tab.slug} className="group relative shrink-0">
                  <Link
                    to={to(tab.slug)}
                    data-testid={`wf-tab-${tab.slug}`}
                    aria-current={active ? "page" : undefined}
                    className={`inline-flex items-center gap-1.5 whitespace-nowrap ${style.item} ${active ? style.active : ""}`}
                  >
                    {tab.short}
                    {isLive && <LiveDot />}
                    {menu && <span aria-hidden className="text-[10px] opacity-60">▾</span>}
                  </Link>
                  {menu && (
                    <div className="invisible absolute left-0 top-full z-50 hidden w-60 rounded-b-xl border border-slate-200 bg-white p-2 text-slate-700 opacity-0 shadow-xl transition group-focus-within:visible group-focus-within:opacity-100 group-hover:visible group-hover:opacity-100 lg:block">
                      {menu.map((item) => (
                        <Link key={item} to={`${to(tab.slug)}#${item.toLowerCase().split(" ")[0]}`} className="block rounded-md px-3 py-1.5 hover:bg-slate-100">
                          {item}
                        </Link>
                      ))}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </nav>
        {right && <div className="flex shrink-0 items-center gap-3">{right}</div>}
      </div>
    </header>
  );
}
