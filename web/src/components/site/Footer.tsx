import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { DEV_TOOLS } from "../../dev/devTools";
import { useAssociation, useLocalized } from "../../content";
import { eventDates } from "../../lib/format";
import { href, type Act } from "../../lib/site";
import { useActTitle, useCurrentActs } from "./acts";
import { Card, CardRow, TextCard } from "./Cards";
import { useLeagues } from "./Frame";

/** The official pages' footer: the last band on the picture, built from the same pieces
 *  as the page above it — one column, the same grid (`Cards.tsx`), darkened behind it. A card per league, the association (signing in and the language are the account menu's,
 *  in the top row), and the line § 5 DDG wants on every page: the legal notice and privacy. */
export function GlassFooter() {
  const { t } = useTranslation("site");
  const { t: tc } = useTranslation();
  const localized = useLocalized();
  const leagues = useLeagues();
  const association = useAssociation().data;
  const acts = useCurrentActs(leagues);
  const link = "text-muted hover:text-foreground hover:underline";
  return (
    // Darkened but not blurred: a blur here would make the footer a backdrop root, and its
    // cards' own glass could then blur nothing but this shade (docs/gotchas).
    <footer className="relative bg-background/70 text-sm text-foreground" data-testid="site-footer">
      <div data-column className="mx-auto max-w-6xl space-y-4 px-4 py-10">
        <CardRow columns={4} testId="site-footer-leagues">
          {leagues.map((league, i) => {
            const act = acts[i];
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
        <TextCard>
          <Link to={href.about()} className="text-base font-semibold text-foreground hover:underline">
            Deutsche Segel-Liga e.V.
          </Link>
          {association && <p className="mt-2 leading-relaxed">{localized(association.service)}</p>}
          <p className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
            <Link to="/events" className={link}>{t("footer.calendar")}</Link>
            <Link to="/clubs" className={link}>{t("footer.allClubs")}</Link>
          </p>
        </TextCard>
        {/* The foot of every page, so the clearance for the fixed dev switches belongs here:
            without it they sit on the legal links § 5 DDG wants reachable. */}
        <div className={`flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2 border-t border-separator pt-4 text-xs text-muted ${DEV_TOOLS ? "pb-20" : ""}`}>
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
  const title = useActTitle()(act);
  if (act.state === "done" || act.state === "cancelled") return null;
  return (
    <p className="mt-1 text-xs text-muted">
      {t(act.state === "live" ? "footer.now" : "footer.next", { act: title, dates: eventDates(act.first) })}
    </p>
  );
}
