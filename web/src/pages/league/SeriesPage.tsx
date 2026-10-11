import { Navigate, useParams } from "react-router-dom";

import { useGetSeriesTable } from "../../api/generated/sbl";
import { useLeagues } from "../../components/site/Frame";
import { href } from "../../lib/site";
import { Standings } from "../Standings";

/** `/series/:id` — a series in a league is a division of that league's year, and its table
 *  lives at `/:league/:year/standings` (Story B-16). A series in no league keeps its page. */
export function SeriesPage() {
  const { id = "" } = useParams();
  const leagues = useLeagues();
  const series = useGetSeriesTable(Number(id)).data?.series;
  const league = series ? leagues.find((l) => l.id === series.league_id) : undefined;
  if (league) return <Navigate to={href.standings(league.slug, series?.year ?? undefined)} replace />;
  return <Standings />;
}
