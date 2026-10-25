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

/** One crumb of a published trail: its words, and where it leads (none — where I am). */
export type Crumb = { label: string; to?: string };

/** A whole trail, published by a page that knows more about where it is than the route
 *  does — the workspace's `ASVW › Members` (Story Z-10), the context and the section the
 *  layout cannot look up. The same store as the title, for the same reason. */
let crumbs: readonly Crumb[] | null = null;
const crumbListeners = new Set<() => void>();

export function setPageCrumbs(next: readonly Crumb[] | null): void {
  if (JSON.stringify(next) === JSON.stringify(crumbs)) return;
  crumbs = next;
  for (const listener of crumbListeners) listener();
}

export function usePageCrumbs(): readonly Crumb[] | null {
  return useSyncExternalStore(
    (listener) => {
      crumbListeners.add(listener);
      return () => crumbListeners.delete(listener);
    },
    () => crumbs,
    () => null,
  );
}
