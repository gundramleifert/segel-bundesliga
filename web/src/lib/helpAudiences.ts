import { useMemo } from "react";

import { useMyContexts } from "../api/generated/sbl";
import type { Account, MyContext } from "../api/types";
import { useAccount } from "../api/useApi";
import { AUDIENCES, type Audience, type HelpPage } from "../handbook";

/** Story B-18: whose help a signed-in person reads — and, since 2026-11-24, the only help
 * they see. From the answer my space uses (`GET /api/me/contexts`, Story Z-8): the
 * relations on my clubs, series and events, and the league office's site relations —
 * never the summary roles (CLAUDE.md: never gate on `User.roles`).
 *
 * Every account is a person with a profile, so everyone has the sailor's help — a parent
 * linked as guardian (Story V-13) included. The site's admin may do everything, so reads
 * everything. */
export function audiencesOf(
  account: Account | null,
  contexts: MyContext[],
  office: readonly string[],
): Set<Audience> {
  const out = new Set<Audience>();
  if (!account) return out;
  out.add("sailor");
  if (office.includes("admin")) return new Set(AUDIENCES);
  if (office.includes("editor")) out.add("administration");
  if (office.some((r) => r === "race_officer" || r === "jury_organizer" || r === "judge")) out.add("race-committee");
  for (const context of contexts) {
    for (const relation of context.relations) {
      // A club's admin decides and pays its claims too (CLAUDE.md, Permissions by area).
      if (context.kind === "club" && relation === "admin") out.add("treasurer");
      if (relation === "treasurer") out.add("treasurer");
      else if (relation === "race_officer" || relation === "jury") out.add("race-committee");
      else if (relation === "manager" || relation === "admin" || relation === "helper") {
        out.add(context.kind === "club" && relation !== "helper" ? "club" : "event-organizer");
      }
    }
  }
  return out;
}

/** A page is for me when it is written for an audience I have. */
export const isForMe = (page: HelpPage, mine: Set<Audience>): boolean => page.audience.some((a) => mine.has(a));

export function useReaderAudiences(): { mine: Set<Audience>; ready: boolean } {
  const { account } = useAccount();
  const contexts = useMyContexts({
    query: { enabled: Boolean(account), staleTime: 5 * 60_000, refetchOnWindowFocus: false },
  });
  const mine = useMemo(
    () => audiencesOf(account, contexts.data?.contexts ?? [], contexts.data?.office?.relations ?? []),
    [account, contexts.data],
  );
  return { mine, ready: !account || contexts.isSuccess || contexts.isError };
}
