import { useTranslation } from "react-i18next";

import { SUPPORTED_LANGUAGES, type SupportedLanguage } from "../i18n";

/** A plain two-button toggle — a full dropdown would be overkill for two languages. */
export function LanguageSwitcher() {
  const { t, i18n } = useTranslation();
  const current = i18n.resolvedLanguage ?? i18n.language;

  return (
    <div
      role="group"
      aria-label={t("language.label")}
      data-testid="language-switcher"
      // shrink-0 matters here, not just cosmetically: overflow-hidden makes a flex item's
      // automatic minimum width 0 per the flexbox spec, so without shrink-0 the navbar's
      // flex-shrink algorithm was free to squeeze this element below its own two-button
      // content width under space pressure — and overflow-hidden then silently clipped the
      // second button instead of showing it (this is exactly what happened: "EN" stayed
      // visible, "DE" vanished at the edge of the header).
      className="flex shrink-0 overflow-hidden rounded-md border border-slate-300 text-xs"
    >
      {SUPPORTED_LANGUAGES.map((lang: SupportedLanguage) => (
        <button
          key={lang}
          type="button"
          aria-pressed={current === lang}
          onClick={() => void i18n.changeLanguage(lang)}
          data-testid={`language-switcher-${lang}`}
          className={`px-2 py-1.5 uppercase transition-colors ${
            current === lang
              ? "bg-marke-600 font-medium text-white"
              : "bg-white text-slate-600 hover:bg-slate-100"
          }`}
        >
          {lang}
        </button>
      ))}
    </div>
  );
}
