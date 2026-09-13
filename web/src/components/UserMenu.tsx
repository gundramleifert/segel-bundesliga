import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import type { Account } from "../api/types";
import { useDisclosure } from "../lib/useDisclosure";
import { LanguageSwitcher } from "./LanguageSwitcher";

/** Everything that is about *you* and about the site, behind the account button.
 *
 * Language, profile, help and the legal pages are each used rarely and none of them is
 * about the page being read — so they were four things competing with the navigation for
 * room in the frame. Collected here, the frame carries only what someone came for.
 *
 * The button itself is the same in both layouts: initials when signed in, a plain account
 * icon when not. Signed out the menu still opens, because the language switcher and the
 * legal pages belong to a guest as much as to anybody.
 */
export function UserMenu({
  account,
  loading,
  placement = "bottom",
}: {
  account: Account | null;
  loading: boolean;
  /** Which way the panel opens. The button sits at the **foot** of the sidebar on a wide
   *  screen, so a panel below it falls off the bottom of the window — there it opens
   *  upward. On a phone the button is in the top bar and it opens downward. */
  placement?: "top" | "bottom";
}) {
  const { t } = useTranslation();
  const menu = useDisclosure("user-menu");

  const links = [
    { to: "/account", key: "profile" },
    { to: "/help", key: "help" },
    { to: "/legal-notice", key: "legalNotice" },
    { to: "/privacy", key: "privacy" },
  ];

  return (
    <div className="relative shrink-0">
      <button
        type="button"
        {...menu.triggerProps}
        aria-label={t("userMenu.label")}
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
      </button>

      {menu.open && (
        <div
          {...menu.panelProps}
          data-testid="layout-user-menu"
          // Anchored to the button and pinned to its right edge, so it opens inward from
          // whichever corner the button is in and never off the side of the screen.
          className={`absolute right-0 z-50 w-56 rounded-xl bg-white p-2 shadow-xl ring-1 ring-slate-900/5 ${
            placement === "top" ? "bottom-full mb-2" : "mt-2"
          }`}
        >
          {account && (
            <p className="truncate px-3 pb-2 pt-1 text-sm font-medium text-slate-900">
              {account.display_name}
            </p>
          )}

          <div className="px-3 pb-2">
            <LanguageSwitcher />
          </div>

          <ul>
            {links.map((link) => (
              <li key={link.key}>
                <Link
                  to={link.to}
                  data-testid={`layout-user-menu-${link.key}`}
                  className="block rounded-md px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
                >
                  {t(`userMenu.${link.key}`)}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/** Initials for the avatar — there's no separate first/last name on `Account`, only
 *  `display_name`, so this splits on whitespace instead. One word gives its first two
 *  letters, several words give the first letter of the first and last. */
function initials(displayName: string): string {
  const parts = displayName.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0].charAt(0)}${parts[parts.length - 1].charAt(0)}`.toUpperCase();
}
