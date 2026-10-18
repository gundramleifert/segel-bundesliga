import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, useParams } from "react-router-dom";

import { useGetLeagueSeason } from "../../api/generated/sbl";
import type { EventSummary, League, LeagueSeason } from "../../api/types";
import { useAsync } from "../../api/useApi";
import { ErrorMessage, Loading } from "../../components/Blocks";
import { PageLoading } from "../../components/site/Frame";
import { actsOf, href, type Act, type ActState } from "../../lib/site";
import { eventDates } from "../../lib/format";

export type LeagueYear = { league: League; season: LeagueSeason; acts: Act[]; year: number | null };

/** The league the URL names, and the year it names or else its current one (Story B-14).
 *  Renders the page only once the data is there; an unknown league goes home. */
export function LeagueGate({ children }: { children: (data: LeagueYear) => ReactNode }) {
  const { league = "", year } = useParams();
  const query = useGetLeagueSeason(league, year ? { year: Number(year) } : undefined);
  const season = useAsync(query);
  if (season.loading) return <PageLoading><Loading testId="league-loading" /></PageLoading>;
  // A path that names no league goes home: `/whatever` lands here, because a league's
  // path is a single free segment. Any other failure says so.
  if (query.error?.status === 404) return <Navigate to={href.home()} replace />;
  if (season.error) return <PageLoading><ErrorMessage text={season.error} testId="league-error" /></PageLoading>;
  if (!season.data) return null;
  const data = season.data;
  return <>{children({ league: data.league, season: data, acts: actsOf(data), year: data.year ?? null })}</>;
}


export { useActName, useActTitle } from "../../components/site/acts";

/** The act's date line, short: "17–19 Apr". */
export const actDates = (act: Act) => eventDates(act.first);

/** Where an act stands, as a small badge on the glass. */
export function StateBadge({ state }: { state: ActState }) {
  const { t } = useTranslation("site");
  const tone = state === "live" ? "bg-red-600 text-white" : state === "next" ? "bg-white text-slate-950" : "bg-white/10 text-white/80";
  return (
    <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold ${tone}`} data-testid={`act-state-${state}`}>
      {t(`state.${state}`)}
    </span>
  );
}

/** The division an event sails in — its series' short name without the year. */
export const divisionName = (event: EventSummary) =>
  event.series ? event.series.short_name.replace(/\s*\d{4}$/, "") : event.title;

/** Says that what follows is example content, not the real thing — for the parts of a page
 *  that have no backend yet and would otherwise read as official (Story B-14). */
export function ExampleNote({ text }: { text?: string }) {
  const { t } = useTranslation("site");
  return (
    <p role="note" data-testid="site-example-note" className="mb-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
      {text ?? t("example")}
    </p>
  );
}
