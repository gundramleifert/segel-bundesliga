/** i18next setup: English is the source language, German the second locale.
 *
 * Namespaces mirror the pages that use them (`start`, `events`, `standings`, `club`, …)
 * plus `common` for anything shared (nav, status labels, boat colours, crew roles).
 * Resources are bundled at build time via static imports — this is a small app with two
 * locales, and a runtime backend would only add complexity for no benefit here.
 *
 * The detected/stored language persists in `localStorage` under `sbl.language`; without a
 * stored preference, the browser's language decides, and English is the fallback.
 */
import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";

import accountDe from "./locales/de/account.json";
import adminDe from "./locales/de/admin.json";
import clubDe from "./locales/de/club.json";
import clubsDe from "./locales/de/clubs.json";
import commonDe from "./locales/de/common.json";
import devDe from "./locales/de/dev.json";
import eventsDe from "./locales/de/events.json";
import matchdayDe from "./locales/de/matchday.json";
import sailorDe from "./locales/de/sailor.json";
import standingsDe from "./locales/de/standings.json";
import startDe from "./locales/de/start.json";
import accountEn from "./locales/en/account.json";
import adminEn from "./locales/en/admin.json";
import clubEn from "./locales/en/club.json";
import clubsEn from "./locales/en/clubs.json";
import commonEn from "./locales/en/common.json";
import devEn from "./locales/en/dev.json";
import eventsEn from "./locales/en/events.json";
import matchdayEn from "./locales/en/matchday.json";
import sailorEn from "./locales/en/sailor.json";
import standingsEn from "./locales/en/standings.json";
import startEn from "./locales/en/start.json";

export const SUPPORTED_LANGUAGES = ["en", "de"] as const;
export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number];

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: {
        common: commonEn,
        start: startEn,
        events: eventsEn,
        standings: standingsEn,
        clubs: clubsEn,
        club: clubEn,
        sailor: sailorEn,
        matchday: matchdayEn,
        account: accountEn,
        admin: adminEn,
        dev: devEn,
      },
      de: {
        common: commonDe,
        start: startDe,
        events: eventsDe,
        standings: standingsDe,
        clubs: clubsDe,
        club: clubDe,
        sailor: sailorDe,
        matchday: matchdayDe,
        account: accountDe,
        admin: adminDe,
        dev: devDe,
      },
    },
    fallbackLng: "en",
    supportedLngs: SUPPORTED_LANGUAGES,
    ns: [
      "common",
      "start",
      "events",
      "standings",
      "clubs",
      "club",
      "sailor",
      "matchday",
      "account",
      "admin",
      "dev",
    ],
    defaultNS: "common",
    interpolation: { escapeValue: false },
    detection: {
      order: ["localStorage", "navigator"],
      lookupLocalStorage: "sbl.language",
      caches: ["localStorage"],
    },
  });

// Keep the document's language attribute and tab title in sync with the active locale —
// otherwise a screen reader or the browser tab would keep announcing the wrong language
// after someone switches it.
function syncDocument() {
  document.documentElement.lang = i18n.resolvedLanguage ?? i18n.language;
  document.title = i18n.t("common:siteTitle");
}
i18n.on("languageChanged", syncDocument);
i18n.on("initialized", syncDocument);

export default i18n;
