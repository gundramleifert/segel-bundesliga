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
      className="flex overflow-hidden rounded-md border border-slate-300 text-xs"
    >
      {SUPPORTED_LANGUAGES.map((lang: SupportedLanguage) => (
        <button
          key={lang}
          type="button"
          aria-pressed={current === lang}
          onClick={() => void i18n.changeLanguage(lang)}
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
