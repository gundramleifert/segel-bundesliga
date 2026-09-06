import { useTranslation } from "react-i18next";
import { NavLink, Outlet } from "react-router-dom";

import { useKonto } from "../api/useApi";
import { Rollenwechsel } from "../dev/Rollenwechsel";
import { LanguageSwitcher } from "./LanguageSwitcher";

const NAV_ITEMS = [
  { path: "/", key: "start", exact: true },
  { path: "/standings", key: "standings", exact: false },
  { path: "/events", key: "events", exact: false },
  { path: "/clubs", key: "clubs", exact: false },
  { path: "/account", key: "account", exact: false },
] as const;

export function Layout() {
  const { t } = useTranslation();
  // Admin only shows up when it's actually open — a link that leads to a 403 is worse
  // than no link.
  const { hatRolle } = useKonto();
  const navigation = hatRolle("admin", "editor")
    ? [...NAV_ITEMS, { path: "/admin", key: "admin", exact: false } as const]
    : NAV_ITEMS;

  return (
    <div className="flex min-h-dvh flex-col bg-flaeche text-tinte">
      <a
        href="#content"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:m-3 focus:rounded-md focus:bg-white focus:px-4 focus:py-2 focus:ring-2 focus:ring-marke-500"
      >
        {t("skipToContent")}
      </a>

      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-6 px-4 py-3">
          <NavLink to="/" className="flex items-center gap-3">
            <img
              src="/marke/segelbundesliga.png"
              alt="German Sailing Bundesliga"
              className="h-9 w-auto"
              width={120}
              height={59}
            />
          </NavLink>

          <nav aria-label="Main navigation" className="ml-auto flex items-center gap-3">
            <ul className="flex items-center gap-1 text-sm">
              {navigation.map((item) => (
                <li key={item.path}>
                  <NavLink
                    to={item.path}
                    end={item.exact}
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
          </nav>
        </div>
      </header>

      <main id="content" className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        <Outlet />
      </main>

      <Rollenwechsel />

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto max-w-6xl px-4 py-6 text-sm text-slate-500">
          {/* Once results from SAP Sailing Analytics are shown, the SAP attribution
              notice must go here — see docs/findings.md, section 3. */}
          {t("footer")}
        </div>
      </footer>
    </div>
  );
}
