import { useSyncExternalStore } from "react";

/** Whether a CSS media query matches, as React state.
 *
 * Used to decide *in the DOM* which variant of a screen this viewport gets, rather than
 * rendering both and hiding one with `hidden lg:flex`. That looks equivalent and is not:
 * two elements carry the same `data-testid`, and a click lands on whichever the test
 * found first.
 *
 * `useSyncExternalStore` over an effect: the first render already has the right answer,
 * so nothing flashes the wrong layout and nothing re-renders to correct it.
 */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (listener) => {
      const list = window.matchMedia(query);
      list.addEventListener("change", listener);
      return () => list.removeEventListener("change", listener);
    },
    () => window.matchMedia(query).matches,
    // No DOM to ask (a prerender): assume the narrow layout, which works at every width.
    () => false,
  );
}
