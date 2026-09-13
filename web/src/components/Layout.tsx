import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

import { useAccount } from "../api/useApi";
import { WIDE_LAYOUT, useMediaQuery } from "../lib/useMediaQuery";
import { RoleSwitcher } from "../dev/RoleSwitcher";
import { Breadcrumb } from "./Breadcrumb";
import { LanguageSwitcher } from "./LanguageSwitcher";

const NAV_ITEMS = [
  { path: "/", key: "start", exact: true },
  { path: "/series", key: "series", exact: false },
  { path: "/events", key: "events", exact: false },
  { path: "/clubs", key: "clubs", exact: false },
  { path: "/help", key: "help", exact: false },
] as const;

type NavItem = { path: string; key: string; exact: boolean };

/** Initials for the profile button's avatar — there's no separate first/last name on
 *  `Account`, only `display_name`, so this splits on whitespace instead. One word gives
 *  its first two letters, several words give the first letter of the first and last. */
function initials(displayName: string): string {
  const parts = displayName.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0].charAt(0)}${parts[parts.length - 1].charAt(0)}`.toUpperCase();
}

/** The frame every page sits in — Story A-12.
 *
 * Two arrangements, one set of links. From `lg` up the navigation is a **column on the
 * left** and the top bar carries only a breadcrumb; below that it is the top bar a phone
 * expects — **burger left, logo centre, account right** — with the same links behind the
 * burger.
 *
 * One horizontal row used to serve both. On a wide screen it spent the full width on six
 * links and had nowhere left to say where you are; as the site gained "Our club" and the
 * admin area it started competing with the language switcher for space. On a phone it
 * scrolled sideways, which is a navigation nobody finds.
 */
export function Layout() {
  const { t } = useTranslation();
  const { hasRole, account, loading } = useAccount();
  const { pathname } = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  // Which arrangement this viewport gets, decided in the DOM rather than with
  // `hidden lg:flex`. Rendering both and hiding one leaves two navigations and two
  // breadcrumbs in the document, which is ambiguous for assistive technology and for
  // tests, and lets a click land on the copy nobody can see.
  const wide = useMediaQuery(WIDE_LAYOUT);

  // Both extra entries appear only when they actually lead somewhere — a link that ends
  // in a 403, or in "you belong to no club", is worse than no link. "Our club" is for
  // whoever organizes one (Story V-12); administration keeps its own, wider way in.
  const navigation: NavItem[] = [
    ...NAV_ITEMS,
    ...(hasRole("club_manager") ? [{ path: "/club", key: "myClub", exact: false }] : []),
    ...(hasRole("admin", "editor") ? [{ path: "/admin", key: "admin", exact: false }] : []),
  ];

  // A menu left open over the page it just navigated to reads as a broken link.
  useEffect(() => setMenuOpen(false), [pathname]);

  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMenuOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  const profile = (
    /* Always present, signed in or not — signed out it's a plain account icon leading to
       the sign-in form, signed in it becomes an initials avatar. Either way it's just a
       link to `/account`, which already renders the right view for both cases. */
    <Link
      to="/account"
      aria-label={t("nav.account")}
      data-testid="layout-profile-button"
      className={`grid size-8 shrink-0 place-items-center rounded-full text-xs font-bold uppercase transition-colors ${
        account
          ? "bg-brand-600 text-white hover:bg-brand-700"
          : `bg-slate-100 text-slate-500 hover:bg-slate-200 ${loading ? "animate-pulse" : ""}`
      }`}
    >
      {account ? (
        initials(account.display_name)
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
  );

  return (
    <div className="min-h-dvh bg-page text-ink lg:flex">
      <a
        href="#content"
        data-testid="layout-skip-link"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:m-3 focus:rounded-md focus:bg-white focus:px-4 focus:py-2 focus:ring-2 focus:ring-brand-500"
      >
        {t("skipToContent")}
      </a>

      {/* ---------------------------------------------------- wide: the left column */}
      {/* `shrink-0` with a fixed width, and `min-w-0` on the content column below: a flex
          child's default minimum is its content width, so without both a wide table in the
          page would push the whole layout past the viewport — which mobile Chromium
          answers by zooming the page out (Story A-10). */}
      {wide && (
        <div
          data-testid="layout-sidebar"
          className="sticky top-0 flex h-dvh w-60 shrink-0 flex-col border-r border-slate-200 bg-white"
        >
          <SiteLogo className="border-b border-slate-200 px-4 py-4" />
          <NavList navigation={navigation} t={t} className="flex-1 overflow-y-auto px-3 py-4" />
          <div className="flex items-center justify-between gap-3 border-t border-slate-200 px-4 py-3">
            <LanguageSwitcher />
            {profile}
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        {/* ------------------------------------------------ narrow: the phone top bar */}
        {/* Burger, logo, account — in that order, because that is where a phone user's
            thumb and eye already expect them. */}
        <header
          data-testid="layout-header"
          className="sticky top-0 z-40 border-b border-slate-200 bg-white/90 backdrop-blur"
        >
          {!wide && (
          <div className="flex items-center gap-3 px-4 py-3">
            <button
              type="button"
              aria-label={t("nav.menu")}
              aria-expanded={menuOpen}
              aria-controls="site-menu"
              onClick={() => setMenuOpen((open) => !open)}
              data-testid="layout-menu-button"
              className="grid size-9 shrink-0 place-items-center rounded-md text-slate-700 hover:bg-slate-100"
            >
              <svg
                aria-hidden
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth={2}
                strokeLinecap="round"
                className="size-5"
              >
                {menuOpen ? (
                  <>
                    <path d="M6 6l12 12" />
                    <path d="M18 6L6 18" />
                  </>
                ) : (
                  <>
                    <path d="M4 7h16" />
                    <path d="M4 12h16" />
                    <path d="M4 17h16" />
                  </>
                )}
              </svg>
            </button>
            <SiteLogo className="mx-auto min-w-0" />
            {profile}
          </div>
          )}

          {/* Rendered once, in both arrangements. On a wide screen it is the whole of the
              header — the navigation has moved to the left, so this bar has one job:
              saying where you are. */}
          <div
            className={`flex min-w-0 items-center gap-3 ${
              wide ? "px-6 py-3" : "border-t border-slate-100 px-4 py-2"
            }`}
          >
            <Breadcrumb />
          </div>
        </header>

        {/* The panel behind the burger. An overlay, so it adds no width to the page
            (Story A-10) and no layout shift when it opens. */}
        {!wide && menuOpen && (
          <>
            <button
              type="button"
              aria-hidden
              tabIndex={-1}
              onClick={() => setMenuOpen(false)}
              data-testid="layout-menu-backdrop"
              className="fixed inset-0 z-40 bg-slate-900/30"
            />
            <div
              id="site-menu"
              data-testid="layout-menu"
              className="fixed inset-y-0 left-0 z-50 flex w-64 max-w-[80vw] flex-col border-r border-slate-200 bg-white shadow-xl"
            >
              <SiteLogo className="border-b border-slate-200 px-4 py-4" />
              <NavList
                navigation={navigation}
                t={t}
                className="flex-1 overflow-y-auto px-3 py-4"
              />
              <div className="border-t border-slate-200 px-4 py-3">
                <LanguageSwitcher />
              </div>
            </div>
          </>
        )}

        <main
          id="content"
          data-testid="layout-main"
          className="w-full min-w-0 flex-1 px-4 py-6 lg:px-6 lg:py-8"
        >
          <div className="mx-auto w-full max-w-6xl">
            <Outlet />
          </div>
        </main>

        <RoleSwitcher />

        {/* The extra bottom padding is clearance for the dev role switcher, which is
            `fixed bottom-4 right-4 z-50` and otherwise sits directly on top of this footer —
            it intercepted the clicks on the legal-notice and privacy links, which § 5 DDG
            requires to be reachable from every page.

            Padding rather than a lower z-index on the switcher: the switcher has to stay
            above page content to be usable at all, so the fix is to stop putting content
            underneath it. And only in a dev build — the switcher cannot exist in production
            (see `dev/RoleSwitcher.tsx`), so the real site pays no dead space for it. */}
        <footer
          data-testid="layout-footer"
          className={`border-t border-slate-200 bg-white ${import.meta.env.DEV ? "pb-24" : ""}`}
        >
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-6 text-sm text-slate-500">
            {/* Once results from SAP Sailing Analytics are shown, the SAP attribution
                notice must go here — see docs/findings.md, section 3. */}
            <span>{t("footer")}</span>
            {/* Legal notice and privacy policy are mandatory for a German public site and
                must be reachable from every page — hence here, not in the main nav. */}
            <nav aria-label={t("footerLegal.label")} data-testid="layout-footer-legal">
              <ul className="flex flex-wrap items-center gap-x-4 gap-y-1">
                <li>
                  <Link
                    to="/legal-notice"
                    data-testid="layout-footer-legal-notice"
                    className="hover:text-slate-900 hover:underline"
                  >
                    {t("footerLegal.legalNotice")}
                  </Link>
                </li>
                <li>
                  <Link
                    to="/privacy"
                    data-testid="layout-footer-privacy"
                    className="hover:text-slate-900 hover:underline"
                  >
                    {t("footerLegal.privacy")}
                  </Link>
                </li>
              </ul>
            </nav>
          </div>
        </footer>
      </div>
    </div>
  );
}

/** The league's mark. Links **out** to the association's official site, not to our own
 *  home route — internal navigation to "/" is the "Start" nav item. */
function SiteLogo({ className = "" }: { className?: string }) {
  return (
    <a
      href="https://deutsche-segelliga.de"
      target="_blank"
      rel="noopener noreferrer"
      data-testid="layout-logo-link"
      className={`flex shrink-0 items-center ${className}`}
    >
      <img
        src="/brand/deutsche-segelliga-logo.jpg"
        alt="Deutsche Segel-Liga"
        className="h-9 w-auto"
        width={200}
        height={58}
      />
    </a>
  );
}

/** The links, identical in the sidebar and behind the burger.
 *
 * One list rendered twice rather than two lists: the entries are role-dependent, and two
 * copies would eventually disagree about who sees what. The testids are the same in both,
 * so only one of the two is ever in the document.
 */
function NavList({
  navigation,
  t,
  className = "",
}: {
  navigation: NavItem[];
  t: (key: string) => string;
  className?: string;
}) {
  return (
    <nav aria-label={t("nav.label")} data-testid="layout-nav" className={className}>
      <ul className="flex flex-col gap-1 text-sm">
        {navigation.map((item) => (
          <li key={item.path}>
            <NavLink
              to={item.path}
              end={item.exact}
              data-testid={`layout-nav-${item.key}`}
              className={({ isActive }) =>
                `block rounded-md px-3 py-2 transition-colors ${
                  isActive
                    ? "bg-brand-50 font-medium text-brand-800"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`
              }
            >
              {t(`nav.${item.key}`)}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
