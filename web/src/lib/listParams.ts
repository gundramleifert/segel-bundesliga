import { useSearchParams } from "react-router-dom";

import { PAGE_SIZE } from "../components/Pager";

/** Page, sort and search — in the URL, where they can be linked and survive a reload.
 *
 * Story A-13. The three belong together because they interact: a new search term invalidates
 * the page someone was on, and both are part of the request the screen makes. Keeping them
 * in the query string rather than in component state is what makes a found row something
 * you can send to someone (`?page=3&sort=-last_name&q=mann`), and what stops a reload from
 * throwing the work away.
 *
 *     const list = useListParams();
 *     const query = useListSailors(
 *       { ...list.request, q: list.q || undefined },
 *       { query: { placeholderData: keepPreviousData } },
 *     );
 *
 * The names are the plain ones from the story — a screen shows one paged list at a time
 * (the admin areas are tabs, and an unmounted tab issues no query), so there is nothing to
 * disambiguate and every list reads the same way.
 */
export function useListParams(limit: number = PAGE_SIZE): ListParams {
  const [params, setParams] = useSearchParams();

  const page = Math.max(1, Number(params.get("page") ?? 1) || 1);
  const sort = params.get("sort");
  const q = params.get("q") ?? "";

  /** Writes the keys this hook owns, leaving everything else in the URL alone —
   *  `?view=pairing` and `?tab=events` are somebody else's and must survive. A `null`
   *  removes the key, so a default never shows up in the address bar. */
  const update = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value === null) next.delete(key);
      else next.set(key, value);
    }
    // `replace`: paging through a list should not fill the Back button with every step
    // someone took on the way — Back belongs to the page they came from.
    setParams(next, { replace: true });
  };

  return {
    page,
    limit,
    sort,
    q,
    request: { limit, offset: (page - 1) * limit },
    setPage: (next: number) => update({ page: next <= 1 ? null : String(next) }),
    setSort: (next: string | null) => update({ sort: next, page: null }),
    setQuery: (next: string) =>
      // Back to the first page: page 4 of the previous search says nothing about this one,
      // and an offset past the end would answer with an empty page.
      update({ q: next.trim() ? next : null, page: null }),
  };
}

export interface ListParams {
  /** 1-based, as it reads in the URL. */
  page: number;
  limit: number;
  /** The server's column name, `-` prefixed for descending; `null` for its default order. */
  sort: string | null;
  q: string;
  /** Spread straight into a generated hook's params. */
  request: { limit: number; offset: number };
  setPage: (page: number) => void;
  setSort: (sort: string | null) => void;
  setQuery: (q: string) => void;
}

/** Splits `-last_name` into the column and its direction, for the table's sorting state. */
export function parseSort(sort: string | null): { id: string; desc: boolean }[] {
  if (!sort) return [];
  return [{ id: sort.replace(/^-/, ""), desc: sort.startsWith("-") }];
}

/** The inverse: what goes back into the URL. */
export function formatSort(sorting: { id: string; desc: boolean }[]): string | null {
  const first = sorting[0];
  return first ? `${first.desc ? "-" : ""}${first.id}` : null;
}
