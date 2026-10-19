import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation } from "react-router-dom";

import { useMyContexts } from "../api/generated/sbl";
import type { Account } from "../api/types";
import { useDisclosure } from "../lib/useDisclosure";
import { SUPPORTED_LANGUAGES, type SupportedLanguage } from "../i18n";
import { helpFor, helpPath } from "../handbook";

/** Everything that is about *you*, top right in the one row (Story A-12).
 *
 * **A guest gets no menu**: the language, as a dropdown, and *Sign in*, side by side —
 * the only two things about the reader a guest has, so a menu that opened to two entries
 * was a tap more than either needed.
 *
 * **Signed in**, the account button opens a menu: my space, profile, administration (for
 * the roles that can use it), help (the handbook is internal) and the language. Each is
 * used rarely and none is about the page being read, so as separate items they competed
 * with the navigation for room. The legal pages are not here: both footers carry them on
 * every page, which is what § 5 DDG asks.
 *
 * Signed in, the button carries a **badge** with the number of things that need the
 * person — my space's `total`, each thing once (Story Z-8) — so it is seen from any page,
 * and *My space* in the menu repeats it. It reads the same request as my space, so
 * whatever clears a need there (every such mutation invalidates it) clears the badge.
 * The request is a heavy one, and the button is on every page: it is not refetched on
 * every focus or page change.
 */
export function UserMenu({
  account,
  loading,
  admin = false,
  overlay = false,
}: {
  account: Account | null;
  loading: boolean;
  /** The row is on a picture, in white (`TopBar`). */
  overlay?: boolean;
  /** Whether the administration is offered — only to the roles that can use it, because a
   *  link that ends in a 403 is worse than no link (Story A-12). */
  admin?: boolean;
}) {
  const { t, i18n } = useTranslation();
  const menu = useDisclosure("user-menu");
  const space = useMyContexts({
    query: { enabled: Boolean(account), staleTime: 5 * 60_000, refetchOnWindowFocus: false },
  });
  const needs = account ? (space.data?.total ?? 0) : 0;
  const { pathname } = useLocation();
  // Help for this page (Story B-18): the handbook page whose route is this screen, else
  // the help's landing page. The handbook is internal, so only a signed-in account is
  // offered it, and a public screen never has a page of its own (`helpFor`).
  const pageHelp = account ? helpFor(pathname, i18n.resolvedLanguage) : undefined;

  // Not known yet: a quiet placeholder of the button's size, so the row does not jump
  // from the guest's controls to the avatar when a stored session turns out valid.
  if (!account && loading) {
    return <div aria-hidden className="size-8 shrink-0 animate-pulse rounded-full bg-slate-100" />;
  }
  if (!account) return <GuestControls overlay={overlay} />;

  // My space and my own page in it (Stories Z-8, S-7).
  const links = [
    { to: "/me", key: "mySpace" },
    { to: "/me/profile", key: "profile" },
    ...(admin ? [{ to: "/admin", key: "admin" }] : []),
    { to: pageHelp ? helpPath(pageHelp.id) : helpPath(), key: "help" },
  ];

  return (
    <div className="relative shrink-0">
      <button
        type="button"
        {...menu.triggerProps}
        aria-label={needs ? `${t("userMenu.label")} — ${t("userMenu.needs", { count: needs })}` : t("userMenu.label")}
        data-testid="layout-profile-button"
        className="relative grid size-8 shrink-0 place-items-center rounded-full bg-brand-600 text-xs font-bold uppercase text-white transition-colors hover:bg-brand-700"
      >
        {needs > 0 && (
          <span
            aria-hidden
            data-testid="layout-profile-badge"
            className="absolute -right-1.5 -top-1.5 grid h-4 min-w-4 place-items-center rounded-full bg-amber-500 px-1 text-[10px] font-bold leading-none text-white ring-2 ring-white"
          >
            {needs > 9 ? "9+" : needs}
          </span>
        )}
        {initials(account.display_name)}
      </button>

      {menu.open && (
        <div
          {...menu.panelProps}
          data-testid="layout-user-menu"
          // Anchored to the button and pinned to its right edge, so it opens inward from
          // whichever corner the button is in and never off the side of the screen.
          className="absolute right-0 z-50 mt-2 w-56 rounded-xl bg-white p-2 shadow-xl ring-1 ring-slate-900/5"
        >
          <p className="truncate px-3 pb-2 pt-1 text-sm font-medium text-slate-900">
            {account.display_name}
          </p>

          <ul>
            {links.map((link) => (
              <li key={link.key}>
                <Link
                  to={link.to}
                  data-testid={`layout-user-menu-${link.key}`}
                  className="flex items-center justify-between gap-2 rounded-md px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
                >
                  {link.key === "help" && pageHelp ? (
                    <span data-testid="help-for-this-page">{t("forThisPage", { ns: "help" })}</span>
                  ) : (
                    t(`userMenu.${link.key}`)
                  )}
                  {link.key === "mySpace" && needs > 0 && (
                    <span
                      className="rounded-full bg-amber-100 px-2 text-xs font-medium text-amber-800"
                      data-testid="layout-user-menu-mySpace-needs"
                    >
                      {needs}
                    </span>
                  )}
                </Link>
              </li>
            ))}
            <li>
              <LanguageChoice />
            </li>
          </ul>
        </div>
      )}
    </div>
  );
}

/** A guest's two things, in the row itself: the language and the way in. */
function GuestControls({ overlay }: { overlay: boolean }) {
  const { t } = useTranslation();
  return (
    <div className="flex shrink-0 items-center gap-1 sm:gap-2">
      <LanguageMenu overlay={overlay} />
      <Link
        to="/account"
        data-testid="layout-sign-in"
        className="whitespace-nowrap rounded-full bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700"
      >
        {t("userMenu.signIn")}
      </Link>
    </div>
  );
}

/** The guest's language: an entry of the row that opens a small menu in the account
 *  menu's style — a panel, each language named **in itself** ("English", "Deutsch":
 *  someone looking for their own language looks for the word they would recognise), the
 *  current one checked. Not a native `<select>`: the list a browser opens for one cannot
 *  be styled, and on the site it looked like a form, not like the row it hangs from. Not
 *  an EN|DE pair either: a third language fits a list and would not fit the pair. */
function LanguageMenu({ overlay }: { overlay: boolean }) {
  const { t, i18n } = useTranslation();
  const menu = useDisclosure("language-menu");
  const current = (i18n.resolvedLanguage ?? i18n.language) as SupportedLanguage;
  return (
    <div className="relative shrink-0">
      <button
        type="button"
        {...menu.triggerProps}
        aria-haspopup="menu"
        aria-label={`${t("language.label")}: ${t(`language.${current}`)}`}
        data-testid="layout-language"
        className={`flex items-center gap-1 rounded-full px-2.5 py-1.5 text-[13px] font-medium transition sm:px-3 sm:text-sm ${
          overlay ? "hover:bg-white/10 hover:text-white" : "hover:bg-slate-100 hover:text-slate-950"
        } ${menu.open ? (overlay ? "bg-white/10 text-white" : "bg-slate-100 text-slate-950") : ""}`}
      >
        <svg aria-hidden viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="size-4">
          <circle cx="12" cy="12" r="9" />
          <path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9s1.3-6.4 3.8-9z" />
        </svg>
        <span className="uppercase">{current}</span>
        <svg
          aria-hidden
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          className={`size-3.5 transition-transform ${menu.open ? "rotate-180" : ""}`}
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>
      {menu.open && (
        <div {...menu.panelProps} className="absolute right-0 z-50 mt-2 w-44 rounded-xl bg-white p-1.5 shadow-xl ring-1 ring-slate-900/5">
        <ul role="menu" data-testid="language-switcher">
          {SUPPORTED_LANGUAGES.map((lang) => (
            <li key={lang} role="none">
              <button
                type="button"
                role="menuitemradio"
                aria-checked={current === lang}
                onClick={() => {
                  void i18n.changeLanguage(lang);
                  menu.close();
                }}
                data-testid={`language-switcher-${lang}`}
                className={`flex w-full items-center justify-between gap-2 rounded-lg px-3 py-2 text-sm transition hover:bg-slate-100 ${
                  current === lang ? "bg-brand-50 font-semibold text-brand-700" : "text-slate-700"
                }`}
              >
                <span>{t(`language.${lang}`)}</span>
                <span className="text-xs uppercase text-slate-400">{lang}</span>
              </button>
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
