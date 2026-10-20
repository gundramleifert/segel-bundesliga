import { useTranslation } from "react-i18next";

import { setTheme, useTheme } from "./site/settings";

/** Dark or light, in the top row beside the language or the account button (Story B-19).
 *  One button, labelled with what it switches *to* — a pair of options would be two
 *  targets for one choice. Its icon is that target too: the sun leads to light. */
export function ThemeSwitch() {
  const { t } = useTranslation();
  const theme = useTheme();
  const next = theme === "dark" ? "light" : "dark";
  return (
    <button
      type="button"
      onClick={() => setTheme(next)}
      aria-label={t(next === "light" ? "theme.toLight" : "theme.toDark")}
      title={t(next === "light" ? "theme.toLight" : "theme.toDark")}
      data-testid="layout-theme"
      className="grid size-8 shrink-0 place-items-center rounded-full transition hover:bg-default hover:text-foreground"
    >
      {next === "light" ? (
        <svg aria-hidden viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" className="size-4">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
        </svg>
      ) : (
        <svg aria-hidden viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinejoin="round" className="size-4">
          <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" />
        </svg>
      )}
    </button>
  );
}
