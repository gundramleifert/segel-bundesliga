import { Navigate } from "react-router-dom";

import { useGetLiveNow } from "../api/generated/sbl";
import { useAsync } from "../api/useApi";
import { ErrorMessage, Loading } from "../components/Blocks";

/** B-5: `/live` leads to the running event — or to the next date, never to an empty table.
 *
 * A redirect rather than a page of its own: the matchday page already shows the running
 * race, the day's standings and the live badge, and a second live page would be a copy
 * of it. With nothing ahead at all, the calendar is the honest answer.
 */
export function LiveNow() {
  const now = useAsync(useGetLiveNow());

  if (now.loading) return <Loading testId="live-now-loading" />;
  if (now.error) return <ErrorMessage text={now.error} testId="live-now-error" />;
  if (!now.data?.event) return <Navigate to="/events" replace />;
  return <Navigate to={`/events/${now.data.event.id}`} replace />;
}
