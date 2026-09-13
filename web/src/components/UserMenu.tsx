import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import type { Account } from "../api/types";
import { useDisclosure } from "../lib/useDisclosure";
import { SUPPORTED_LANGUAGES, type SupportedLanguage } from "../i18n";

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

          <ul>
            <li>
              <LanguageChoice />
            </li>
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

/** The language, as a submenu rather than a pair of toggle buttons.
 *
 * Two languages fitted a segmented EN|DE control; a third would not, and the control read
 * as a widget wedged into a list of links rather than as one of its entries. A row that
 * says what the language currently is, and opens to the choices, is the same shape as
 * everything else in this menu and does not change when a language is added.
 *
 * Each language is named **in itself** — "English", "Deutsch" — never translated. Someone
 * looking for their own language is looking for the word they would recognise, which is
 * not the word for it in a language they do not read.
 */
function LanguageChoice() {
  const { t, i18n } = useTranslation();
  const [side, setSide] = useState<"right" | "left" | null>(null);
  const open = side !== null;
  const current = (i18n.resolvedLanguage ?? i18n.language) as SupportedLanguage;

  /** Opens beside the row — to the right, or to the left when there is no room there.
   *
   *  The account menu is anchored to the top right of the window, so "to the right" is
   *  off-screen as often as not. Decided when it opens, from the row's own rectangle,
   *  rather than assumed: a flyout that hangs off the edge of a phone is not a menu. */
  const toggle = (event: { currentTarget: HTMLElement }) => {
    if (open) return setSide(null);
    const rect = event.currentTarget.getBoundingClientRect();
    setSide(rect.right + SUBMENU_WIDTH + 8 <= window.innerWidth ? "right" : "left");
  };

  return (
    <div className="relative">
      <button
        type="button"
        aria-expanded={open}
        aria-controls="user-menu-language"
        aria-haspopup="menu"
        onClick={toggle}
        data-testid="layout-user-menu-language"
        className="flex w-full items-center justify-between gap-2 rounded-md px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
      >
        <span>{t("language.label")}</span>
        {/* The chosen language stays on this row, so the menu says what it is without
            being opened. */}
        <span className="flex items-center gap-1 text-slate-500">
          {t(`language.${current}`)}
          <svg
            aria-hidden
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
            className="size-3.5"
          >
            <path d="M9 6l6 6-6 6" />
          </svg>
        </span>
      </button>

      {open && (
        <ul
          id="user-menu-language"
          data-testid="language-switcher"
          role="menu"
          className={`absolute top-0 z-10 w-40 rounded-xl bg-white p-2 shadow-xl ring-1 ring-slate-900/5 ${
            side === "right" ? "left-full ml-1" : "right-full mr-1"
          }`}
        >
          {SUPPORTED_LANGUAGES.map((lang) => (
            <li key={lang} role="none">
              <button
                type="button"
                role="menuitemradio"
                // `menuitemradio` + `aria-checked`: a set of alternatives of which
                // exactly one holds, which is what this is — not two independent toggles,
                // which is what `aria-pressed` would have claimed.
                aria-checked={current === lang}
                onClick={() => void i18n.changeLanguage(lang)}
                data-testid={`language-switcher-${lang}`}
                className={`flex w-full items-center gap-2 rounded-md py-1.5 pl-7 pr-3 text-sm hover:bg-slate-100 ${
                  current === lang ? "font-medium text-slate-900" : "text-slate-600"
                }`}
              >
                <span aria-hidden className="w-3 text-brand-600">
                  {current === lang ? "✓" : ""}
                </span>
                {t(`language.${lang}`)}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Matches `w-40` on the panel below — the number the flip decision needs. */
const SUBMENU_WIDTH = 160;
