import { useQueries } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { getGetLeagueSeasonQueryOptions } from "../../api/generated/sbl";
import { useAccount } from "../../api/useApi";
import { DEV_TOOLS } from "../../dev/devTools";
import { SUPPORTED_LANGUAGES } from "../../i18n";
import { useAssociation, useLocalized } from "../../content";
import { eventDates } from "../../lib/format";
import { actsOf, currentAct, href, type Act } from "../../lib/site";
import { BAR_SHADE, Card, CardRow, Columns, TextCard } from "./Cards";
import { useLeagues } from "./Frame";

/** The official pages' footer in the sub-menu layout: the last band on the picture, built
 *  from the same pieces as the page above it — one column, the same grid (`Cards.tsx`),
 *  the rows' shade behind it. A card per league, the association and the account beside
 *  each other, and the line § 5 DDG wants on every page: the legal notice and privacy. */
export function GlassFooter() {
  const { t } = useTranslation("site");
  const { t: tc, i18n } = useTranslation();
  const localized = useLocalized();
  const leagues = useLeagues();
  const association = useAssociation().data;
  const { account } = useAccount();
  const seasons = useQueries({ queries: leagues.map((l) => getGetLeagueSeasonQueryOptions(l.slug)) });
  const link = "text-white/80 hover:text-white hover:underline";
  return (
    <footer className={`relative text-sm text-white ${BAR_SHADE}`} data-testid="site-footer">
      <div data-column className="mx-auto max-w-6xl space-y-4 px-4 py-10">
        <CardRow columns={4} testId="site-footer-leagues">
          {leagues.map((league, i) => {
            const season = seasons[i]?.data;
            const act = season ? currentAct(actsOf(season)) : null;
            return (
              <li key={league.slug}>
                <Card className="h-full p-4" testId={`site-footer-league-${league.slug}`}>
                  <Link to={href.league(league.slug)} className="text-base font-semibold hover:underline">
                    {league.short_name}
                  </Link>
                  {act && <NextAct act={act} />}
                  {/* A row on a phone, a column from a wide screen: four leagues of four
                      links each would otherwise make the footer screens long. */}
                  <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 lg:flex-col">
                    <li><Link to={href.standings(league.slug)} className={link}>{t("pages.standings")}</Link></li>
                    <li><Link to={href.season(league.slug)} className={link}>{t("pages.season")}</Link></li>
                    <li><Link to={href.noticeBoard(league.slug)} className={link}>{t("pages.noticeBoard")}</Link></li>
                    <li><Link to={href.press(league.slug)} className={link}>{t("pages.press")}</Link></li>
                  </ul>
                </Card>
              </li>
            );
          })}
        </CardRow>
        <Columns split="twoToOne">
          <TextCard>
            <Link to={href.about()} className="text-base font-semibold text-white hover:underline">
              Deutsche Segel-Liga e.V.
            </Link>
            {association && <p className="mt-2 leading-relaxed">{localized(association.service)}</p>}
            <p className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
              <Link to="/events" className={link}>{t("footer.calendar")}</Link>
              <Link to="/clubs" className={link}>{t("footer.allClubs")}</Link>
            </p>
          </TextCard>
          <Card className="p-4 sm:p-5" testId="site-footer-account">
            <p className="text-base font-semibold">{t("footer.account")}</p>
            <p className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
              {account ? (
                <Link to="/me" className={link}>{tc("userMenu.mySpace")}</Link>
              ) : (
                <Link to="/account" className={link}>{tc("userMenu.signIn")}</Link>
              )}
              {account && <Link to="/help" className={link}>{tc("userMenu.help")}</Link>}
            </p>
            <div role="radiogroup" aria-label={t("footer.language")} className="mt-3 inline-flex rounded-full bg-white/10 p-0.5">
              {SUPPORTED_LANGUAGES.map((lang) => (
                <button
                  key={lang}
                  type="button"
                  role="radio"
                  aria-checked={i18n.language?.startsWith(lang)}
                  onClick={() => void i18n.changeLanguage(lang)}
                  data-testid={`site-footer-language-${lang}`}
                  className={`rounded-full px-3 py-1 text-xs font-semibold uppercase ${
                    i18n.language?.startsWith(lang) ? "bg-white text-slate-950" : "text-white/75 hover:text-white"
                  }`}
                >
                  {lang}
                </button>
              ))}
            </div>
          </Card>
        </Columns>
        {/* The foot of every page, so the clearance for the fixed dev switches belongs here:
            without it they sit on the legal links § 5 DDG wants reachable. */}
        <div className={`flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2 border-t border-white/15 pt-4 text-xs text-white/70 ${DEV_TOOLS ? "pb-20" : ""}`}>
          <p className="flex flex-wrap gap-x-4 gap-y-1">
            <Link to="/legal-notice" className={link} data-testid="site-footer-legal-notice">{tc("userMenu.legalNotice")}</Link>
            <Link to="/privacy" className={link}>{tc("userMenu.privacy")}</Link>
          </p>
          <p>{t("footer.credits")}</p>
        </div>
      </div>
    </footer>
  );
}

/** The league's act now or next, in one line. */
function NextAct({ act }: { act: Act }) {
  const { t } = useTranslation("site");
  const place = act.first.venue?.city ?? act.first.host_club?.short_name;
  const name = act.matchday != null ? t("act.title", { n: act.matchday }) : act.first.title;
  const title = place ? `${name} · ${place}` : name;
  if (act.state === "done" || act.state === "cancelled") return null;
  return (
    <p className="mt-1 text-xs text-white/70">
      {t(act.state === "live" ? "footer.now" : "footer.next", { act: title, dates: eventDates(act.first) })}
    </p>
  );
}
