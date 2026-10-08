import { useMyContexts } from "../../api/generated/sbl";
import type { MyContext } from "../../api/types";
import { useAccount, useAsync } from "../../api/useApi";

/** What the overview and every context page read: one request (Story Z-8). */
export function useMySpace() {
  const { account, loading } = useAccount();
  const space = useAsync(useMyContexts({ query: { enabled: Boolean(account) } }));
  return { account, accountLoading: loading, space };
}

export function contextPath(context: Pick<MyContext, "kind" | "id">): string {
  return `/me/${context.kind}/${context.id}`;
}

/** Over once its last day has passed; an undated event is still to come. */
export function isPast(context: Pick<MyContext, "starts_on" | "ends_on">, today = todayIso()): boolean {
  const last = context.ends_on ?? context.starts_on;
  return last != null && last < today;
}

function todayIso(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}
