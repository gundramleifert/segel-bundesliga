/** i18next setup: English is the source language, German the second locale.
 *
 * Namespaces mirror the pages that use them (`site`, `events`, `standings`, `club`, …)
 * plus `common` for anything shared (nav, status labels, boat colours, crew roles).
 * Resources are bundled at build time via static imports — this is a small app with two
 * locales, and a runtime backend would only add complexity for no benefit here.
 *
 * Messages are ICU MessageFormat (`i18next-icu`): `{name}` for a value, and plurals in one
 * key — `{count, plural, one {# event} other {# events}}` — instead of i18next's `{{name}}`
 * and `_one`/`_other` keys. `scripts/check-i18n.mjs` parses every message, because a
 * message that does not parse is otherwise shown raw, braces and all, without an error.
 *
 * The detected/stored language persists in `localStorage` under `sbl.language`; without a
 * stored preference, the browser's language decides, and English is the fallback.
 */
import i18n from "i18next";
import ICU from "i18next-icu";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";

import accountDe from "./locales/de/account.json";
import adminDe from "./locales/de/admin.json";
import clubDe from "./locales/de/club.json";
import clubsDe from "./locales/de/clubs.json";
import commonDe from "./locales/de/common.json";
import devDe from "./locales/de/dev.json";
import errorsDe from "./locales/de/errors.json";
import eventsDe from "./locales/de/events.json";
import helpDe from "./locales/de/help.json";
import legalDe from "./locales/de/legal.json";
import liveDe from "./locales/de/live.json";
import matchdayDe from "./locales/de/matchday.json";
import racecontrolDe from "./locales/de/racecontrol.json";
import sailorDe from "./locales/de/sailor.json";
import siteDe from "./locales/de/site.json";
import spaceDe from "./locales/de/space.json";
import standingsDe from "./locales/de/standings.json";
import accountEn from "./locales/en/account.json";
import adminEn from "./locales/en/admin.json";
import clubEn from "./locales/en/club.json";
import clubsEn from "./locales/en/clubs.json";
import commonEn from "./locales/en/common.json";
import devEn from "./locales/en/dev.json";
import errorsEn from "./locales/en/errors.json";
import eventsEn from "./locales/en/events.json";
import helpEn from "./locales/en/help.json";
import legalEn from "./locales/en/legal.json";
import liveEn from "./locales/en/live.json";
import matchdayEn from "./locales/en/matchday.json";
import racecontrolEn from "./locales/en/racecontrol.json";
import sailorEn from "./locales/en/sailor.json";
import siteEn from "./locales/en/site.json";
import spaceEn from "./locales/en/space.json";
import standingsEn from "./locales/en/standings.json";

export const SUPPORTED_LANGUAGES = ["en", "de"] as const;
export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number];

void i18n
  .use(new ICU())
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: {
        common: commonEn,
        site: siteEn,
        events: eventsEn,
        standings: standingsEn,
        clubs: clubsEn,
        club: clubEn,
        sailor: sailorEn,
        matchday: matchdayEn,
        racecontrol: racecontrolEn,
        account: accountEn,
        admin: adminEn,
        dev: devEn,
        errors: errorsEn,
        help: helpEn,
        legal: legalEn,
        live: liveEn,
        space: spaceEn,
      },
      de: {
        common: commonDe,
        site: siteDe,
        events: eventsDe,
        standings: standingsDe,
        clubs: clubsDe,
        club: clubDe,
        sailor: sailorDe,
        matchday: matchdayDe,
        racecontrol: racecontrolDe,
        account: accountDe,
        admin: adminDe,
        dev: devDe,
        errors: errorsDe,
        help: helpDe,
        legal: legalDe,
        live: liveDe,
        space: spaceDe,
      },
    },
    fallbackLng: "en",
    supportedLngs: SUPPORTED_LANGUAGES,
    ns: [
      "common",
      "site",
      "events",
      "standings",
      "clubs",
      "club",
      "sailor",
      "matchday",
      "racecontrol",
      "account",
      "admin",
      "dev",
      "errors",
      "help",
      "legal",
      "live",
      "space",
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
