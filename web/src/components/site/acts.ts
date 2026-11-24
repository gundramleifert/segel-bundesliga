import { useQueries } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { getGetLeagueSeasonQueryOptions } from "../../api/generated/sbl";
import type { League } from "../../api/types";
import { eventNumber } from "../../lib/format";
import { actsOf, currentAct, type Act } from "../../lib/site";

/** "2. Spieltag", "Act 2" — the act's number in its league's word, or its event's title
 *  where the league names its events (Story B-22). */
export function useActName() {
  useTranslation("site"); // re-renders on a language switch; the words are `common`'s
  return (act: Act) => eventNumber(act.first) ?? act.first.title;
}

/** "2. Spieltag · Kiel" — the act's name and its place. */
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
