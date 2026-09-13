import { useSyncExternalStore } from "react";

/** Whether a CSS media query matches, as React state.
 *
 * Used to decide *in the DOM* which navigation this viewport gets (Story A-12), rather
 * than rendering both and hiding one with `hidden lg:flex`. That looks equivalent and is
 * not: two `<nav aria-label="Main navigation">` elements exist, two elements carry the
 * same `data-testid`, and a click lands on whichever the test found first — which is how
 * the burger menu appeared to be already open before anyone touched it.
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

/** Tailwind's `lg`. The line where the navigation becomes a column beside the page rather
 *  than a panel behind a burger — tablet portrait gets the phone layout, which is what a
 *  portrait screen has room for. */
export const WIDE_LAYOUT = "(min-width: 1024px)";
