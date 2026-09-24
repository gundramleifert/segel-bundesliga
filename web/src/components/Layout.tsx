import { useTranslation } from "react-i18next";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import { useMyClubs } from "../api/generated/sbl";
import { useAccount } from "../api/useApi";
import { WIDE_LAYOUT, useMediaQuery } from "../lib/useMediaQuery";
import { DEV_TOOLS } from "../dev/devTools";
import { RoleSwitcher } from "../dev/RoleSwitcher";
import { Breadcrumb } from "./Breadcrumb";
import { UserMenu } from "./UserMenu";
import { useDisclosure } from "../lib/useDisclosure";

// What someone came to the site for, and nothing else. Help, the legal pages, the
// language and the profile are each used rarely and none is about the page being read —
// they live behind the account button instead (`UserMenu`).
const NAV_ITEMS = [
  { path: "/", key: "start", exact: true },
  { path: "/series", key: "series", exact: false },
  { path: "/events", key: "events", exact: false },
  { path: "/clubs", key: "clubs", exact: false },
] as const;

type NavChild = { path: string; key: string; label: string; clubId: number };
type NavItem = { path: string; key: string; exact: boolean; children?: NavChild[] };

/** The frame every page sits in — Story A-12.
 *
 * Two arrangements, one set of links. From `lg` up the navigation is a **column on the
 * left** and the top bar carries only a breadcrumb; below that it is the top bar a phone
 * expects — **burger left, logo centre, account right** — with the same links behind the
 * burger.
 *
 * One horizontal row used to serve both. On a wide screen it spent the full width on six
 * links and had nowhere left to say where you are; as the site gained "My club" and the
 * admin area it started competing with the language switcher for space. On a phone it
 * scrolled sideways, which is a navigation nobody finds.
 */
export function Layout() {
  const { t } = useTranslation();
  const { hasRole, account, loading } = useAccount();
  const menu = useDisclosure("site-menu");
  const wide = useMediaQuery(WIDE_LAYOUT);

  // Both extra entries appear only when they actually lead somewhere — a link that ends
  // in a 403, or in "you belong to no club", is worse than no link. "My club" is for
  // whoever belongs to a club or organizes one (Story V-12): the link opens the club the
  // account acts for, and with several clubs a dropdown beneath it picks another — the
  // club is chosen here, not on the page. Administration keeps its own, wider way in.
  const clubs = useMyClubs({ query: { enabled: Boolean(account) } });
  const mine = clubs.data ?? [];
  const navigation: NavItem[] = [
    ...NAV_ITEMS,
    ...(mine.length || hasRole("club_manager")
      ? [
          {
            path: "/club",
            key: "myClub",
            exact: false,
            children:
              mine.length > 1
                ? mine.map((entry) => ({
                    path: `/club?club=${entry.club.id}`,
                    key: `myClub-${entry.club.id}`,
                    label: entry.club.short_name || entry.club.name,
                    clubId: entry.club.id,
                  }))
                : undefined,
          },
        ]
      : []),
    // The organizer of one event or series, and its jury, reach the admin area too — it
    // shows them their events and nothing else (Story Z-2).
    ...(hasRole("admin", "editor", "series_manager", "event_manager", "jury")
      ? [{ path: "/admin", key: "admin", exact: false }]
      : []),
  ];

  return (
    // The frame is white and the page is the tinted panel inside it, not the other way
    // round. That is what lets the panel's corner be visible at all: a rounded grey
    // corner against grey chrome draws nothing.
    <div className="min-h-dvh bg-white text-ink lg:flex">
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
          className="sticky top-0 flex h-dvh w-60 shrink-0 flex-col bg-white"
        >
          <SiteLogo className="px-4 py-4" />
          <NavList
            navigation={navigation}
            t={t}
            activeClubId={account?.club_id ?? null}
            className="flex-1 overflow-y-auto px-3 py-2"
          />
          <div className="flex items-center justify-end px-4 py-3">
            <UserMenu account={account} loading={loading} placement="top" />
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        {/* ------------------------------------------------ narrow: the phone top bar */}
        {/* Burger, logo, account — in that order, because that is where a phone user's
            thumb and eye already expect them. */}
        <header
          data-testid="layout-header"
          className="sticky top-0 z-40 bg-white/90 backdrop-blur"
        >
          {!wide && (
          <div className="flex items-center gap-3 px-4 py-3">
            <button
              type="button"
              {...menu.triggerProps}
              aria-label={t("nav.menu")}
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
                {menu.open ? (
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
            {/* Top right, where a phone's account button belongs — and the menu opens
                downward from it, pinned to the same edge. */}
            <UserMenu account={account} loading={loading} />
          </div>
          )}

          {/* Rendered once, in both arrangements. On a wide screen it is the whole of the
              header — the navigation has moved to the left, so this bar has one job:
              saying where you are. */}
          <div
            className={`flex min-w-0 items-center gap-3 ${
              wide ? "px-6 py-3" : "px-4 pb-2"
            }`}
          >
            <Breadcrumb />
          </div>
        </header>

        {/* The panel behind the burger. An overlay, so it adds no width to the page
            (Story A-10) and no layout shift when it opens. */}
        {!wide && menu.open && (
          <>
            <button
              type="button"
              aria-hidden
              tabIndex={-1}
              onClick={menu.close}
              data-testid="layout-menu-backdrop"
              className="fixed inset-0 z-40 bg-slate-900/30"
            />
            <div
              {...menu.panelProps}
              data-testid="layout-menu"
              className="fixed inset-y-0 left-0 z-50 flex w-64 max-w-[80vw] flex-col bg-white shadow-xl"
            >
              <SiteLogo className="px-4 py-4" />
              <NavList
                navigation={navigation}
                t={t}
                activeClubId={account?.club_id ?? null}
                className="flex-1 overflow-y-auto px-3 py-2"
              />
            </div>
          </>
        )}

        {/* The panel. Its top-left corner is rounded — the point where the navigation
            on the left, the breadcrumb above and the page itself meet — so the frame
            reads as wrapping around the page rather than being ruled off from it. On a
            phone there is no sidebar, so both top corners are rounded instead. */}
        <main
          id="content"
          data-testid="layout-main"
          // `panel-scroll`: a table wider than the panel scrolls the panel, not the
          // document. The document staying at viewport width is what Story A-10 is about;
          // *which* box scrolls is a choice, and one region beats a scrollbar per table.
          className={`panel-scroll w-full min-w-0 flex-1 bg-page px-4 py-6 lg:px-6 lg:py-8 ${
            wide ? "rounded-tl-2xl" : "rounded-t-2xl"
          } ${
            // Clearance for the dev role switcher, which is `fixed bottom-4 right-4 z-50`
            // and otherwise sits on top of whatever is at the foot of the page. The same
            // constant as the switcher itself, so the two cannot disagree — they did
            // once, and it covered the legal links.
            DEV_TOOLS ? "pb-28" : ""
          }`}
        >
          <div className="mx-auto w-full max-w-6xl">
            <Outlet />
          </div>
        </main>

        {/* Gated on the *build* rather than on whether the backend happens to answer
            `/api/dev`. Those two used to disagree: the switcher showed itself whenever the
            backend offered dev login, while the footer's clearance for it was
            `import.meta.env.DEV` — so in a built bundle against a dev-login backend, which
            is exactly what the e2e suite runs, the switcher sat on top of the legal links
            that § 5 DDG requires to be reachable. One condition now, shared with the
            clearance above, and a build opts in with `VITE_DEV_TOOLS=true`. */}
        {DEV_TOOLS && <RoleSwitcher />}

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
  activeClubId,
  className = "",
}: {
  navigation: NavItem[];
  t: (key: string) => string;
  activeClubId: number | null;
  className?: string;
}) {
  // Which club the dropdown shows: the one open on `/club` (read off the URL, which
  // `ClubScreen` completes), otherwise the one the account acts for.
  const location = useLocation();
  const navigate = useNavigate();
  const openClub = location.pathname.startsWith("/club")
    ? new URLSearchParams(location.search).get("club")
    : null;
  return (
    // `min-h-0` is not optional here, and it is not cosmetic. This nav is a flex child
    // with `overflow-y-auto`, and a flex child's minimum height is its *content* height
    // unless told otherwise — so with enough links it grows past the panel instead of
    // scrolling inside it, and silently covers the row beneath (the language switcher,
    // the account button). The symptom is Playwright's "<nav …> intercepts pointer
    // events" on a control that is plainly visible: the same misleading shape as Story
    // A-10, one axis over.
    <nav
      aria-label={t("nav.label")}
      data-testid="layout-nav"
      className={`min-h-0 ${className}`}
    >
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
              {/* "My clubs" once there is more than one to choose from — the private view,
                  as against the public "Clubs" list above it. */}
              {t(`nav.${item.key === "myClub" && item.children ? "myClubs" : item.key}`)}
            </NavLink>
            {item.children && (
              // A dropdown, not one link per club: two clubs are rare, ten are possible
              // for a person who organizes for a federation, and a strip of ten links
              // would swallow the navigation. Choosing navigates; the page remembers.
              <div className="ml-3 mt-1 border-l border-slate-200 pl-2">
                <label className="sr-only" htmlFor="layout-nav-club-select">
                  {t("nav.myClubSelectLabel")}
                </label>
                <select
                  id="layout-nav-club-select"
                  data-testid="layout-nav-myClub-select"
                  className="w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-700"
                  value={
                    openClub ??
                    (activeClubId != null && item.children.some((c) => c.clubId === activeClubId)
                      ? String(activeClubId)
                      : String(item.children[0].clubId))
                  }
                  onChange={(e) => navigate(`/club?club=${e.target.value}`)}
                >
                  {item.children.map((child) => (
                    <option key={child.key} value={child.clubId} data-testid={`layout-nav-${child.key}`}>
                      {child.label}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </li>
        ))}
      </ul>
    </nav>
  );
}
