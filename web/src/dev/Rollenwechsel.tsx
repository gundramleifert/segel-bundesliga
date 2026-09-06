import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { api, type Account, type TestAccount } from "../api/client";
import { getToken, onTokenChange, setToken } from "../api/session";

/** Development role switcher.
 *
 * Only shows up in development, and only when the backend has `/api/dev` enabled
 * (`SBL_DEV_LOGIN=true`). Lets you browse the site as admin, editor, race officer, club
 * manager, or a plain participant without fishing a one-time code out of the server log
 * every time.
 */
export function Rollenwechsel() {
  const { t } = useTranslation("dev");
  const [offen, setOffen] = useState(false);
  const [konten, setKonten] = useState<TestAccount[] | null>(null);
  const [ich, setIch] = useState<Account | null>(null);
  const [suche, setSuche] = useState("");
  const [verfuegbar, setVerfuegbar] = useState(true);

  useEffect(() => {
    api
      .testAccounts()
      .then(setKonten)
      .catch(() => setVerfuegbar(false));
  }, []);

  useEffect(() => {
    const laden = () => {
      if (!getToken()) {
        setIch(null);
        return;
      }
      api
        .me()
        .then(setIch)
        .catch(() => {
          // Expired or invalid token: better to sign out than get stuck half-signed-in.
          setToken(null);
          setIch(null);
        });
    };
    laden();
    return onTokenChange(laden);
  }, []);

  const gefiltert = useMemo(() => {
    if (!konten) return [];
    const begriff = suche.trim().toLowerCase();
    const passt = begriff
      ? konten.filter(
          (k: TestAccount) =>
            k.email.toLowerCase().includes(begriff) ||
            k.display_name.toLowerCase().includes(begriff) ||
            (k.club ?? "").toLowerCase().includes(begriff) ||
            k.roles.some((r: string) => r.includes(begriff)),
        )
      : konten;
    // Accounts with a role first — those are the interesting ones to try out.
    return [...passt]
      .sort((a, b) => b.roles.length - a.roles.length || a.email.localeCompare(b.email))
      .slice(0, 40);
  }, [konten, suche]);

  if (!verfuegbar) return null;

  async function anmelden(email: string) {
    setToken(await api.devLogin(email));
    setOffen(false);
  }

  return (
    <div className="fixed bottom-4 right-4 z-50 text-sm">
      {offen && (
        <div className="mb-2 max-h-[70vh] w-[22rem] overflow-hidden rounded-xl border border-amber-300 bg-white shadow-xl">
          <div className="border-b border-amber-200 bg-amber-50 px-3 py-2">
            <p className="font-medium text-amber-900">{t("title")}</p>
            <p className="text-xs text-amber-800">{t("subtitle")}</p>
          </div>

          <div className="border-b border-slate-200 p-2">
            <input
              type="search"
              value={suche}
              onChange={(e) => setSuche(e.target.value)}
              placeholder={t("searchPlaceholder")}
              aria-label={t("searchLabel")}
              className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 outline-none focus:border-sky-600 focus:ring-1 focus:ring-sky-600"
            />
          </div>

          <ul className="max-h-[42vh] overflow-y-auto">
            {gefiltert.map((konto) => (
              <li key={konto.id}>
                <button
                  onClick={() => anmelden(konto.email)}
                  className={`block w-full px-3 py-2 text-left hover:bg-slate-50 ${
                    ich?.email === konto.email ? "bg-sky-50" : ""
                  }`}
                >
                  <span className="font-medium">{konto.display_name}</span>
                  {konto.club && <span className="ml-1.5 text-slate-500">[{konto.club}]</span>}
                  <span className="block text-xs text-slate-500">{konto.email}</span>
                  <span className="block text-xs text-sky-800">
                    {konto.roles.join(", ") || t("noRole")}
                  </span>
                </button>
              </li>
            ))}
            {!gefiltert.length && (
              <li className="px-3 py-6 text-center text-slate-500">{t("notFound")}</li>
            )}
          </ul>

          {ich && (
            <div className="border-t border-slate-200 p-2">
              <button
                onClick={() => setToken(null)}
                className="w-full rounded-md border border-slate-300 px-3 py-1.5 hover:bg-slate-50"
              >
                {t("signOut")}
              </button>
            </div>
          )}
        </div>
      )}

      <button
        onClick={() => setOffen((o) => !o)}
        aria-expanded={offen}
        className="flex items-center gap-2 rounded-full border border-amber-300 bg-amber-100 px-4 py-2 font-medium text-amber-900 shadow-lg hover:bg-amber-200"
      >
        <span aria-hidden>🔧</span>
        {ich ? `${ich.display_name} · ${ich.roles.join(", ") || t("noRole")}` : t("notSignedIn")}
      </button>
    </div>
  );
}
