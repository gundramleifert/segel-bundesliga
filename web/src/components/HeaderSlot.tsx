import { createContext, useContext, type ReactNode } from "react";
import { createPortal } from "react-dom";

/** The place in `Layout`'s header row, beside the breadcrumb, where a page may put its
 *  own sub-menu — the matchday page's row of tabs, for the pages outside the leagues.
 *
 * A portal rather than a store like the page title's: the tabs are live elements with
 * their own handlers and focus, and a portal keeps them in the page's React tree while the
 * browser draws them in the header. `null` outside a `Layout` — the page then shows its
 * tabs where it is. */
export const HeaderSlotContext = createContext<HTMLElement | null>(null);

/** Renders `children` into the header row, or in place where there is no header. */
export function InHeader({ children }: { children: ReactNode }) {
  const slot = useContext(HeaderSlotContext);
  return slot ? createPortal(children, slot) : <>{children}</>;
}
