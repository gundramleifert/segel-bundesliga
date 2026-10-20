import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { devLogin, listTestUsers, me as fetchMe } from "../api/generated/sbl";
import type { Account, TestAccount } from "../api/types";
import { getToken, onTokenChange, setToken } from "../api/session";

/** Development role switcher.
 *
 * Only shows up in development, and only when the backend has `/api/dev` enabled
 * (`SBL_DEV_LOGIN=true`). Lets you browse the site as admin, editor, race officer, club
 * manager, or a plain participant without fishing a one-time code out of the server log
 * every time.
 *
 * The seed is a small cast on one club, one series and one event (`app/seed_users.py`),
 * and the list is grouped by where each person's tuples are — the server says which
 * (`group`): league office, series, event, club, sailors, guest. The sailors are the
 * long group and stay folded until opened or searched.
 */

const GROUPS = ["league", "series", "event", "club", "sailor", "guest"] as const;
type Group = (typeof GROUPS)[number];
export function RoleSwitcher() {
  const { t } = useTranslation("dev");
  const [open, setOpen] = useState(false);
  const [accounts, setAccounts] = useState<TestAccount[] | null>(null);
  const [me, setMe] = useState<Account | null>(null);
  const [search, setSearch] = useState("");
  const [available, setAvailable] = useState(true);
  const [sailorsOpen, setSailorsOpen] = useState(false);

  useEffect(() => {
    // The plain generated function, not its hook: this panel is mounted outside the page
    // tree and has nothing to cache — /api/dev is either there or it is not.
    listTestUsers()
      .then(setAccounts)
      .catch(() => setAvailable(false));
  }, []);

  useEffect(() => {
    const load = () => {
      if (!getToken()) {
        setMe(null);
        return;
      }
      fetchMe()
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

  const term = search.trim().toLowerCase();
  const grouped = useMemo(() => {
    const matched = (accounts ?? []).filter(
      (k: TestAccount) =>
        !term ||
        k.email.toLowerCase().includes(term) ||
        k.display_name.toLowerCase().includes(term) ||
        (k.club ?? "").toLowerCase().includes(term) ||
        k.roles.some((r: string) => r.includes(term)),
    );
    return GROUPS.map((group) => ({
      group,
      accounts: matched
        .filter((k) => k.group === group)
        .sort((a, b) => a.display_name.localeCompare(b.display_name)),
    })).filter((g) => g.accounts.length);
  }, [accounts, term]);

  if (!available) return null;

  async function signIn(email: string) {
    const { access_token } = await devLogin({ email });
    setToken(access_token);
    setOpen(false);
  }

  return (
    <div data-testid="dev-role-switcher" className="fixed bottom-4 right-4 z-50 text-sm">
      {open && (
        <div
          data-testid="dev-role-switcher-panel"
          className="mb-2 max-h-[70vh] w-[22rem] overflow-hidden rounded-xl border border-warning/50 bg-overlay shadow-xl"
        >
          <div className="border-b border-warning/50 bg-warning-soft px-3 py-2">
            <p className="font-medium text-warning-soft-foreground">{t("title")}</p>
            <p className="text-xs text-warning-soft-foreground">{t("subtitle")}</p>
          </div>

          <div className="border-b border-separator p-2">
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t("searchPlaceholder")}
              aria-label={t("searchLabel")}
              data-testid="dev-role-switcher-search-input"
              className="w-full rounded-md border border-border px-2.5 py-1.5 outline-none focus:border-focus focus:ring-1 focus:ring-focus"
            />
          </div>

          <div data-testid="dev-role-switcher-list" className="max-h-[50vh] overflow-y-auto">
            {grouped.map(({ group, accounts: members }) => {
              // A search opens every group: what it found is what the reader is after.
              const folded = group === "sailor" && !sailorsOpen && !term;
              return (
                <section key={group} data-testid={`dev-role-switcher-group-${group}`}>
                  <button
                    type="button"
                    onClick={() => group === "sailor" && setSailorsOpen((o) => !o)}
                    aria-expanded={group === "sailor" ? !folded : undefined}
                    disabled={group !== "sailor"}
                    data-testid={`dev-role-switcher-group-${group}-heading`}
                    className="sticky top-0 flex w-full items-center justify-between bg-surface-tertiary px-3 py-1 text-left text-xs font-semibold uppercase tracking-wide text-muted enabled:hover:bg-default-hover"
                  >
                    <span>{t(`groups.${group as Group}`)}</span>
                    <span className="font-normal normal-case">
                      {members.length}
                      {group === "sailor" && !term && <span aria-hidden> {folded ? "▸" : "▾"}</span>}
                    </span>
                  </button>
                  {!folded && (
                    <ul>
                      {members.map((account) => (
                        <li key={account.id}>
                          <button
                            onClick={() => signIn(account.email)}
                            data-testid={`dev-role-switcher-account-${account.id}`}
                            className={`block w-full px-3 py-1.5 text-left hover:bg-surface-secondary ${
                              me?.email === account.email ? "bg-accent-soft" : ""
                            }`}
                          >
                            <span className="font-medium">{account.display_name}</span>
                            {account.club && <span className="ml-1.5 text-muted">[{account.club}]</span>}
                            <span className="block text-xs text-muted">
                              {account.email}
                              {account.roles.length > 0 && (
                                <span className="text-accent-soft-foreground"> · {account.roles.join(", ")}</span>
                              )}
                            </span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              );
            })}
            {!grouped.length && (
              <p data-testid="dev-role-switcher-empty" className="px-3 py-6 text-center text-muted">
                {t("notFound")}
              </p>
            )}
          </div>

          {me && (
            <div className="border-t border-separator p-2">
              <button
                onClick={() => setToken(null)}
                data-testid="dev-role-switcher-signout-button"
                className="w-full rounded-md border border-border px-3 py-1.5 hover:bg-surface-secondary"
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
        className="flex items-center gap-2 rounded-full border border-warning/50 bg-warning-soft px-4 py-2 font-medium text-warning-soft-foreground shadow-lg hover:bg-warning-soft-hover"
      >
        <span aria-hidden>🔧</span>
        {me ? `${me.display_name} · ${me.roles.join(", ") || t("noRole")}` : t("notSignedIn")}
      </button>
    </div>
  );
}
