import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Outlet, useLocation, useNavigationType } from "react-router-dom";

import { DEV_TOOLS } from "../dev/devTools";
import { RoleSwitcher } from "../dev/RoleSwitcher";
import { Breadcrumb } from "./Breadcrumb";
import { HeaderSlotContext } from "./HeaderSlot";
import { DevSwitch } from "./site/DevSwitch";
import { Footer, TopBar } from "./site/Frame";

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
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[60] focus:rounded-md focus:bg-white focus:px-4 focus:py-2 focus:ring-2 focus:ring-brand-500"
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

/** The frame of the pages outside the leagues — my space, administration, a club, a
 *  sailor, the legal pages (Stories B-13, A-12).
 *
 * The same one row on top as everywhere else: logo, the leagues, the account button. It
 * replaced a column of links on the left and a burger on a phone — the leagues *are* the
 * navigation now, and the account menu holds the rest. Under the row, a breadcrumb names
 * the page; it is the page's `h1`.
 */
export function Layout() {
  // State, not a ref: the page's portal has to render again once the slot exists.
  const [slot, setSlot] = useState<HTMLElement | null>(null);
  return (
    <div className="flex min-h-dvh flex-col bg-white text-ink">
      <TopBar />
      {/* A page with a sub-menu (`InHeader`) puts it beside the breadcrumb — the row then
          stays under the top bar, as the matchday page's tabs do (Story S-7). `:has`, so
          a page without one keeps a row that scrolls away. */}
      <div
        data-testid="layout-header"
        className="z-10 bg-white/95 backdrop-blur has-[[role=tablist]]:sticky has-[[role=tablist]]:top-14 has-[[role=tablist]]:border-b has-[[role=tablist]]:border-slate-200"
      >
        {/* With a sub-menu the whole row scrolls sideways on a phone, name and tabs together,
            as the matchday row does — squeezed, the name wrapped into a column. */}
        <div
          className="scrollbar-none mx-auto flex w-full max-w-6xl min-w-0 items-center gap-3 px-4 py-3 has-[[role=tablist]]:overflow-x-auto has-[[role=tablist]]:py-0 has-[[role=tablist]]:[&>nav]:shrink-0 has-[[role=tablist]]:[&>nav]:whitespace-nowrap lg:px-6">
          <Breadcrumb />
          <div ref={setSlot} data-testid="layout-header-slot" className="contents" />
        </div>
      </div>
      <main
        id="content"
        data-testid="layout-main"
        // `panel-scroll`: a table wider than the panel scrolls the panel, not the document
        // (Story A-10).
        className="panel-scroll w-full min-w-0 flex-1 rounded-t-2xl bg-page px-4 py-6 lg:px-6 lg:py-8"
      >
        <div className="mx-auto w-full max-w-6xl">
          <HeaderSlotContext.Provider value={slot}>
            <Outlet />
          </HeaderSlotContext.Provider>
        </div>
      </main>
      <Footer />
    </div>
  );
}
