import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { useMe } from "./generated/sbl";
import { ApiError } from "./http";
import { getToken, onTokenChange } from "./session";
import type { Account } from "./types";

export interface AsyncState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

/** What a screen needs from a generated query hook, and nothing else.
 *
 * The hooks in `generated/sbl.ts` return TanStack's full `UseQueryResult` — twenty fields,
 * of which the pages here use three. This narrows it to those three and turns the error
 * into a sentence on the way, which is the part that must not be repeated: an `ApiError`
 * already carries a translated message from its problem code, and anything else has to
 * fall back to a generic one. Done per page, one of them would eventually render
 * "[object Object]".
 *
 *     const { data, error, loading } = useAsync(useListClubs());
 *
 * Reach past it — `const q = useListClubs()` — whenever a screen genuinely needs more:
 * `isFetching` for a background refresh, `refetch` for a retry button.
 */
export function useAsync<Q extends QueryLike>(query: Q): AsyncState<Payload<Q>> {
  const { t } = useTranslation();
  return {
    data: (query.data ?? null) as Payload<Q> | null,
    error: query.isError ? errorMessage(query.error, t("errors.loadFailed")) : null,
    loading: query.isPending,
  };
}

/** The four fields taken off a query result, and nothing more. */
interface QueryLike {
  data: unknown;
  isError: boolean;
  error: unknown;
  isPending: boolean;
}

/** What the query resolves to.
 *
 * Inferred *from the argument* rather than declared as `useAsync<T>(q: UseQueryResult<T>)`.
 * `UseQueryResult` is a union over the pending, error and success states, and in two of
 * them `data` is `undefined`; asking TypeScript to unify `T` across all three infers it as
 * `never`, and then every `data.map(...)` on the page stops compiling with an error that
 * points at the page rather than at this line.
 */
type Payload<Q extends QueryLike> = NonNullable<Q["data"]>;

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

/** Invalidates cached queries — after every mutation. Takes two kinds of argument:
 *
 * - **A generated key**, `getListAllClubsQueryKey()`, for one query. Never a key written
 *   out by hand here: one that no longer matches any query invalidates nothing, silently,
 *   and the screen simply keeps showing what it showed before.
 * - **A path prefix**, `"/api/clubs"`, for every query underneath it — the list *and*
 *   `/api/clubs/7` *and* `/api/clubs/7/members`. Generated keys start with the request
 *   path, so a prefix is the honest way to say "anything about clubs is now stale".
 *   Naming each affected page instead means the one that gets forgotten shows a stale
 *   club until the tab is reloaded.
 */
export function useInvalidate() {
  const client = useQueryClient();
  return (...targets: (readonly unknown[] | string)[]) => {
    for (const target of targets) {
      if (typeof target === "string") {
        void client.invalidateQueries({
          predicate: (query) => {
            const path = query.queryKey[0];
            return typeof path === "string" && path.startsWith(target);
          },
        });
      } else {
        void client.invalidateQueries({ queryKey: target });
      }
    }
  };
}

/** Whether someone is currently signed in. Reacts to sign-in/out in the same tab. */
export function useToken(): string | null {
  const [token, setStoredToken] = useState(getToken);
  useEffect(() => onTokenChange(() => setStoredToken(getToken())), []);
  return token;
}

export interface AccountState {
  account: Account | null;
  loading: boolean;
  hasRole: (...roles: string[]) => boolean;
}

/** The own account, including roles. Without a token, it's not even requested. */
export function useAccount(): AccountState {
  const token = useToken();
  const query = useMe({
    query: {
      // The token is part of the key on purpose: signing in as someone else must not be
      // answered from the previous account's cache entry, and signing out must not leave
      // the old roles behind. The generated key alone does not know about identity.
      queryKey: ["/api/auth/me", token],
      enabled: Boolean(token),
      // An expired token isn't an error worth retrying.
      retry: false,
    },
  });

  const account = token ? (query.data ?? null) : null;
  return {
    account,
    loading: Boolean(token) && query.isPending,
    hasRole: (...roles) => Boolean(account && roles.some((r) => account.roles.includes(r))),
  };
}
