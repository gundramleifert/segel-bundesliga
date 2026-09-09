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
export function RoleSwitcher() {
  const { t } = useTranslation("dev");
  const [open, setOpen] = useState(false);
  const [accounts, setAccounts] = useState<TestAccount[] | null>(null);
  const [me, setMe] = useState<Account | null>(null);
  const [search, setSearch] = useState("");
  const [available, setAvailable] = useState(true);

  useEffect(() => {
    api
      .testAccounts()
      .then(setAccounts)
      .catch(() => setAvailable(false));
  }, []);

  useEffect(() => {
    const load = () => {
      if (!getToken()) {
        setMe(null);
        return;
      }
      api
        .me()
        .then(setMe)
        .catch(() => {
          // Expired or invalid token: better to sign out than get stuck half-signed-in.
          setToken(null);
          setMe(null);
        });
    };
    load();
    return onTokenChange(load);
  }, []);

  const filtered = useMemo(() => {
    if (!accounts) return [];
    const term = search.trim().toLowerCase();
    const matched = term
      ? accounts.filter(
          (k: TestAccount) =>
            k.email.toLowerCase().includes(term) ||
            k.display_name.toLowerCase().includes(term) ||
            (k.club ?? "").toLowerCase().includes(term) ||
            k.roles.some((r: string) => r.includes(term)),
        )
      : accounts;
    // Accounts with a role first — those are the interesting ones to try out.
    return [...matched]
      .sort((a, b) => b.roles.length - a.roles.length || a.email.localeCompare(b.email))
      .slice(0, 40);
  }, [accounts, search]);

  if (!available) return null;

  async function signIn(email: string) {
    setToken(await api.devLogin(email));
    setOpen(false);
  }

  return (
    <div data-testid="dev-role-switcher" className="fixed bottom-4 right-4 z-50 text-sm">
      {open && (
        <div
          data-testid="dev-role-switcher-panel"
          className="mb-2 max-h-[70vh] w-[22rem] overflow-hidden rounded-xl border border-amber-300 bg-white shadow-xl"
        >
          <div className="border-b border-amber-200 bg-amber-50 px-3 py-2">
            <p className="font-medium text-amber-900">{t("title")}</p>
            <p className="text-xs text-amber-800">{t("subtitle")}</p>
          </div>

          <div className="border-b border-slate-200 p-2">
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t("searchPlaceholder")}
              aria-label={t("searchLabel")}
              data-testid="dev-role-switcher-search-input"
              className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 outline-none focus:border-sky-600 focus:ring-1 focus:ring-sky-600"
            />
          </div>

          <ul data-testid="dev-role-switcher-list" className="max-h-[42vh] overflow-y-auto">
            {filtered.map((account) => (
              <li key={account.id}>
                <button
                  onClick={() => signIn(account.email)}
                  data-testid={`dev-role-switcher-account-${account.id}`}
                  className={`block w-full px-3 py-2 text-left hover:bg-slate-50 ${
                    me?.email === account.email ? "bg-sky-50" : ""
                  }`}
                >
                  <span className="font-medium">{account.display_name}</span>
                  {account.club && <span className="ml-1.5 text-slate-500">[{account.club}]</span>}
                  <span className="block text-xs text-slate-500">{account.email}</span>
                  <span className="block text-xs text-sky-800">
                    {account.roles.join(", ") || t("noRole")}
                  </span>
                </button>
              </li>
            ))}
            {!filtered.length && (
              <li data-testid="dev-role-switcher-empty" className="px-3 py-6 text-center text-slate-500">
                {t("notFound")}
              </li>
            )}
          </ul>

          {me && (
            <div className="border-t border-slate-200 p-2">
              <button
                onClick={() => setToken(null)}
                data-testid="dev-role-switcher-signout-button"
                className="w-full rounded-md border border-slate-300 px-3 py-1.5 hover:bg-slate-50"
              >
                {t("signOut")}
              </button>
            </div>
          )}
        </div>
      )}

      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        data-testid="dev-role-switcher-toggle"
        className="flex items-center gap-2 rounded-full border border-amber-300 bg-amber-100 px-4 py-2 font-medium text-amber-900 shadow-lg hover:bg-amber-200"
      >
        <span aria-hidden>🔧</span>
        {me ? `${me.display_name} · ${me.roles.join(", ") || t("noRole")}` : t("notSignedIn")}
      </button>
    </div>
  );
}
