import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Outlet, useLocation, useNavigationType } from "react-router-dom";

import { DEV_TOOLS } from "../dev/devTools";
import { RoleSwitcher } from "../dev/RoleSwitcher";
import { Breadcrumb } from "./Breadcrumb";
import { HeaderSlotContext } from "./HeaderSlot";
import { DevSwitch } from "./site/DevSwitch";
import { BAR_SHADE } from "./site/Cards";
import { GlassFooter } from "./site/Footer";
import { TopBar } from "./site/Frame";

/** Around every page: the development tools, wherever they are built in (`DEV_TOOLS`) —
 *  the role switcher bottom right, the DEV switch for the open variants bottom left
 *  (Story B-13). The league pages draw their own frame; everything else sits in `Layout`. */
export function SiteShell() {
  const { t } = useTranslation();
  useScrollToTop();
  return (
    <>
      {/* Once, for every page: the chapter pages and the depth pages draw their own frame,
          and each of them has a `main#content`. */}
      <a
        href="#content"
        data-testid="layout-skip-link"
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[60] focus:rounded-md focus:bg-surface focus:px-4 focus:py-2 focus:ring-2 focus:ring-focus"
      >
        {t("skipToContent")}
      </a>
      <Outlet />
      {/* Gated on the *build* rather than on whether the backend happens to answer
          `/api/dev`: the switcher and the clearance `Layout` leaves for it must never
          disagree — they once did, and the switcher covered the legal links. A build opts
          in with `VITE_DEV_TOOLS=true`. */}
      {DEV_TOOLS && <RoleSwitcher />}
      {DEV_TOOLS && <DevSwitch />}
    </>
  );
}

/** A new page opens at its top. The router keeps the window's scroll position, so a link
 *  in the footer opened the next page at *its* footer, past its picture and its title.
 *  Back and forward (`POP`) are left alone, and a link that scrolls on purpose — a
 *  matchday's tabs bring their row under the top bar — says so with `keepScroll`. */
function useScrollToTop() {
  const { pathname, state } = useLocation();
  const type = useNavigationType();
  const keep = (state as { keepScroll?: boolean } | null)?.keepScroll;
  useEffect(() => {
    if (type !== "POP" && !keep) window.scrollTo(0, 0);
  }, [pathname, type, keep]);
}

/** The frame of the pages outside the leagues — my space, administration, help, a club, a
 *  sailor, the legal pages (Stories B-13, A-12).
 *
 * Drawn like a page behind a league's chapter (`DepthPage`), without its picture: the top
 * row and a sub-menu row under it, sticking together — where you are on the left (the
 * breadcrumb, whose last crumb is the page's `h1`), the page's own tabs beside it as pills
 * (`InHeader`) — and the same footer.
 *
 * **The theme is set here and only here** (`THEME`): the pages name their colours
 * (`text-muted`, `bg-surface` — index.css), and `data-theme` gives the names their values,
 * for this frame and everything in it, HeroUI's components included. The official pages
 * stay dark, on their pictures. A light/dark switch is this value.
 */
const THEME: "light" | "dark" = "dark";

export function Layout() {
  // State, not a ref: the page's portal has to render again once the slot exists.
  const [slot, setSlot] = useState<HTMLElement | null>(null);
  return (
    <div
      data-theme={THEME}
      data-testid="layout"
      // `glass-plain`: the cards that are glass over a picture take the theme's surface on
      // this plain ground.
      className={`${THEME === "dark" ? "dark" : ""} glass-plain flex min-h-dvh flex-col bg-background text-foreground`}
    >
      <div className={`sticky top-0 z-40 ${BAR_SHADE}`}>
        <TopBar />
        {/* With a sub-menu the whole row scrolls sideways on a phone, name and tabs
            together, as the league's row does — squeezed, the name wrapped into a column.
            Without one, the name truncates instead (`Breadcrumb`). */}
        <div data-testid="layout-header" className="border-b border-separator text-sm">
          <div className="scrollbar-none mx-auto flex h-12 w-full max-w-6xl min-w-0 items-center gap-3 px-4 has-[[role=tablist]]:overflow-x-auto has-[[role=tablist]]:[&>nav]:shrink-0 has-[[role=tablist]]:[&>nav]:whitespace-nowrap">
            <Breadcrumb />
            <div ref={setSlot} data-testid="layout-header-slot" className="contents" />
          </div>
        </div>
      </div>
      <main
        id="content"
        data-testid="layout-main"
        // `panel-scroll`: a table wider than the panel scrolls the panel, not the document
        // (Story A-10).
        className="panel-scroll w-full min-w-0 flex-1 px-4 pb-16 pt-8 sm:pt-12"
      >
        <div className="mx-auto w-full max-w-6xl">
          <HeaderSlotContext.Provider value={slot}>
            <Outlet />
          </HeaderSlotContext.Provider>
        </div>
      </main>
      <GlassFooter />
    </div>
  );
}
