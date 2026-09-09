import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError, api, type Account } from "./client";
import { getToken, onTokenChange } from "./session";

export interface AsyncState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

function message(error: unknown, fallback: string): string {
  if (error instanceof ApiError) return error.message;
  return fallback;
}

/** Loads data via TanStack Query.
 *
 * The key doubles as the cache identity: the same query is only fetched once even if two
 * pages need it, and a change in the admin area can invalidate it precisely
 * (`useInvalidate`). Cancelling on navigation is handled by Query itself — that's why
 * the passed-through `signal` is all that's needed here.
 */
export function useApi<T>(
  key: readonly unknown[],
  load: (signal: AbortSignal) => Promise<T>,
): AsyncState<T> {
  const { t } = useTranslation();
  const query = useQuery({
    queryKey: key,
    queryFn: ({ signal }) => load(signal),
  });

  return {
    data: query.data ?? null,
    error: query.isError ? message(query.error, t("errors.loadFailed")) : null,
    loading: query.isPending,
  };
}

/** Invalidates cached queries — after every mutation. */
export function useInvalidate() {
  const client = useQueryClient();
  return (...keys: readonly unknown[][]) => {
    for (const key of keys) void client.invalidateQueries({ queryKey: key });
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
  const query = useQuery({
    queryKey: ["me", token],
    queryFn: ({ signal }) => api.me(signal),
    enabled: Boolean(token),
    // An expired token isn't an error worth retrying.
    retry: false,
  });

  const account = token ? (query.data ?? null) : null;
  return {
    account,
    loading: Boolean(token) && query.isPending,
    hasRole: (...roles) => Boolean(account && roles.some((r) => account.roles.includes(r))),
  };
}
