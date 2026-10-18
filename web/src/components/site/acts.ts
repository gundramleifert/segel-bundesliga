import { useQueries } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { getGetLeagueSeasonQueryOptions } from "../../api/generated/sbl";
import type { League } from "../../api/types";
import { actsOf, currentAct, type Act } from "../../lib/site";

/** "Act 2" — the act's number, or its event's title when it has none. */
export function useActName() {
  const { t } = useTranslation("site");
  return (act: Act) => (act.matchday != null ? t("act.title", { n: act.matchday }) : act.first.title);
}

/** "Act 2 · Kiel" — the act's number and its place. */
export function useActTitle() {
  const actName = useActName();
  return (act: Act) => {
    const place = act.first.venue?.city ?? act.first.host_club?.short_name;
    return place ? `${actName(act)} · ${place}` : actName(act);
  };
}

/** Each league's act now, or next, or last — in the order of `leagues`, `null` while a
 *  league's year is on its way. The footer asks on every official page and the
 *  association's home asks too, so the years are kept for minutes rather than the
 *  default half a minute, and the act is picked once per answer, not on every render. */
export function useCurrentActs(leagues: League[]): (Act | null)[] {
  return useQueries({
    queries: leagues.map((l) => ({ ...getGetLeagueSeasonQueryOptions(l.slug), staleTime: 5 * 60_000 })),
    combine: (results) => results.map((r) => (r.data ? currentAct(actsOf(r.data)) : null)),
  });
}
