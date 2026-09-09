import { useTranslation } from "react-i18next";
import { Link, NavLink, Outlet } from "react-router-dom";

import { useKonto } from "../api/useApi";
import { Rollenwechsel } from "../dev/Rollenwechsel";
import { LanguageSwitcher } from "./LanguageSwitcher";

const NAV_ITEMS = [
  { path: "/", key: "start", exact: true },
  { path: "/series", key: "series", exact: false },
  { path: "/events", key: "events", exact: false },
  { path: "/clubs", key: "clubs", exact: false },
  { path: "/help", key: "help", exact: false },
] as const;

/** Initials for the profile button's avatar — there's no separate first/last name on
 *  `Account`, only `display_name`, so this splits on whitespace instead. One word gives
 *  its first two letters, several words give the first letter of the first and last. */
function initialen(displayName: string): string {
  const teile = displayName.trim().split(/\s+/).filter(Boolean);
  if (!teile.length) return "";
  if (teile.length === 1) return teile[0].slice(0, 2).toUpperCase();
  return `${teile[0].charAt(0)}${teile[teile.length - 1].charAt(0)}`.toUpperCase();
}

export function Layout() {
  const { t } = useTranslation();
  // Admin only shows up when it's actually open — a link that leads to a 403 is worse
  // than no link.
  const { hatRolle, konto, laedt } = useKonto();
  const navigation = hatRolle("admin", "editor")
    ? [...NAV_ITEMS, { path: "/admin", key: "admin", exact: false } as const]
    : NAV_ITEMS;

  return (
    <div className="flex min-h-dvh flex-col bg-flaeche text-tinte">
      <a
        href="#content"
        data-testid="layout-skip-link"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:m-3 focus:rounded-md focus:bg-white focus:px-4 focus:py-2 focus:ring-2 focus:ring-marke-500"
      >
        {t("skipToContent")}
      </a>

      <header
        data-testid="layout-header"
        className="sticky top-0 z-40 border-b border-slate-200 bg-white/90 backdrop-blur"
      >
        <div className="mx-auto flex max-w-6xl items-center gap-6 px-4 py-3">
          {/* The logo links out to the league's official site, not to our own home route —
              internal navigation to "/" is still reachable via the "Start" nav item below. */}
          <a
            href="https://deutsche-segelliga.de"
            target="_blank"
            rel="noopener noreferrer"
            data-testid="layout-logo-link"
            className="flex shrink-0 items-center gap-3"
          >
            <img
              src="/marke/deutsche-segelliga-logo.jpg"
              alt="Deutsche Segel-Liga"
              className="h-9 w-auto"
              width={200}
              height={58}
            />
          </a>

          {/* min-w-0 lets this row actually shrink instead of forcing the whole page to
              overflow horizontally — without it, a flex child's default min-width is its
              content width, so on a narrow phone the last items (e.g. "Standings") end up
              past the viewport edge with no visible way to reach them. overflow-x-auto on
              the list then makes the remaining items reachable by swiping the nav itself.
              scrollbar-none hides the native scrollbar track that swipe area would otherwise
              draw across the navbar — touch/wheel scrolling still works, only the visible
              scrollbar is suppressed. */}
          <nav
            aria-label="Main navigation"
            data-testid="layout-nav"
            className="ml-auto flex min-w-0 items-center gap-3"
          >
            <ul className="scrollbar-none flex min-w-0 items-center gap-1 overflow-x-auto text-sm">
              {navigation.map((item) => (
                <li key={item.path} className="shrink-0">
                  <NavLink
                    to={item.path}
                    end={item.exact}
                    data-testid={`layout-nav-${item.key}`}
                    className={({ isActive }) =>
                      `rounded-md px-3 py-2 transition-colors ${
                        isActive
                          ? "bg-marke-50 font-medium text-marke-800"
                          : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                      }`
                    }
                  >
                    {t(`nav.${item.key}`)}
                  </NavLink>
                </li>
              ))}
            </ul>
            <LanguageSwitcher />
            {/* The corner-most element of the header: always present, signed in or not —
                signed out it's a plain account icon leading to the sign-in form, signed
                in it becomes an initials avatar. Either way it's just a link to
                `/account`, which already renders the right view for both cases. */}
            <Link
              to="/account"
              aria-label={t("nav.account")}
              data-testid="layout-profile-button"
              className={`grid size-8 shrink-0 place-items-center rounded-full text-xs font-bold uppercase transition-colors ${
                konto
                  ? "bg-marke-600 text-white hover:bg-marke-700"
                  : `bg-slate-100 text-slate-500 hover:bg-slate-200 ${laedt ? "animate-pulse" : ""}`
              }`}
            >
              {konto ? (
                initialen(konto.display_name)
              ) : (
                <svg
                  aria-hidden
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={2}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="size-4"
                >
                  <circle cx="12" cy="8" r="3.5" />
                  <path d="M4.5 20c0-3.6 3.4-6.5 7.5-6.5s7.5 2.9 7.5 6.5" />
                </svg>
              )}
            </Link>
          </nav>
        </div>
      </header>

      <main id="content" data-testid="layout-main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        <Outlet />
      </main>

      <Rollenwechsel />

      <footer data-testid="layout-footer" className="border-t border-slate-200 bg-white">
        <div className="mx-auto max-w-6xl px-4 py-6 text-sm text-slate-500">
          {/* Once results from SAP Sailing Analytics are shown, the SAP attribution
              notice must go here — see docs/findings.md, section 3. */}
          {t("footer")}
        </div>
      </footer>
    </div>
  );
}
