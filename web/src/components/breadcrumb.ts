import { useSyncExternalStore } from "react";

/** The current page's own title, published by whichever `PageHeader` is mounted.
 *
 * The header bar shows a breadcrumb — `Series › 1. Segel-Bundesliga 2026` (Story A-12) —
 * and the second crumb is the page's title. Deriving it from the URL instead would mean
 * the layout looking up a series by id, an event by id, a club by id, and being wrong for
 * anything it does not know about.
 *
 * A module-level store rather than React context: `PageHeader` writes on mount, and with
 * context that write is a `setState` inside an effect, which re-renders the whole tree a
 * second time on every navigation. `useSyncExternalStore` re-renders only the header.
 */
let title: string | null = null;
const listeners = new Set<() => void>();

export function setPageTitle(next: string | null): void {
  if (next === title) return;
  title = next;
  for (const listener of listeners) listener();
}

export function usePageTitle(): string | null {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => title,
    () => null,
  );
}
