import { Navigate, useSearchParams } from "react-router-dom";

import { MySpaceOverview } from "./Overview";

/** The addresses my space replaced (Story S-7) — kept, because they were real URLs of a
 *  deployed build and are in people's bookmarks and in mails. */

/** `/me` — the overview; `/me?tab=documents|bank|claims` was the old papers page. */
export function MeIndex() {
  const [params] = useSearchParams();
  const tab = params.get("tab");
  if (tab) return <Navigate to={`/me/profile?tab=${encodeURIComponent(tab)}`} replace />;
  return <MySpaceOverview />;
}

/** `/club?club=N&tab=…&event=…` — the club screen, now the club's page in my space. */
export function ClubRedirect() {
  const [params] = useSearchParams();
  const club = params.get("club");
  if (!club) return <Navigate to="/me" replace />;
  const rest = new URLSearchParams(params);
  rest.delete("club");
  const query = rest.toString();
  return <Navigate to={`/me/club/${encodeURIComponent(club)}${query ? `?${query}` : ""}`} replace />;
}
