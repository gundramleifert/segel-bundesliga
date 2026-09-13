import {
  cloneElement,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type ReactElement,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

/** A tooltip, for the places that used the browser's own.
 *
 *     <Tip text={club.name}>
 *       <Link to={`/clubs/${club.id}`}>{club.short_name}</Link>
 *     </Tip>
 *
 * The native `title` attribute is free and ugly: a system rectangle in the OS font,
 * appearing after a delay nobody can change, in a place nobody can control, and invisible
 * to a touch screen entirely.
 *
 * Three decisions worth knowing:
 *
 * - **The child is cloned, not wrapped.** Half of these sit on a `<th>` or a `<td>`, which
 *   may not have a `<span>` between them and their row — so this adds no element of its
 *   own, only handlers.
 * - **The bubble is a portal, positioned `fixed`.** A CSS `::after` bubble is simpler and
 *   was the first attempt; it is also clipped by every ancestor that hides overflow, and
 *   the two places that most need a tooltip here are a `truncate`d name and a cell inside
 *   the horizontally scrolling content panel. Both would have cut it in half.
 * - **It is a real tooltip for assistive technology** — `role="tooltip"` plus
 *   `aria-describedby` on the trigger — which the CSS approach cannot be.
 */
export function Tip({
  text,
  children,
}: {
  /** Nothing shown when empty, so a caller may pass a value that is sometimes absent. */
  text: ReactNode;
  children: ReactElement<Record<string, unknown>>;
}) {
  const [anchor, setAnchor] = useState<DOMRect | null>(null);
  const [above, setAbove] = useState(true);
  const bubble = useRef<HTMLDivElement>(null);
  const id = useId();

  /** Above the trigger, or below it when there is no room above.
   *
   *  Measured rather than guessed: the bubble's height depends on how its text wraps, so
   *  a fixed threshold is wrong for exactly the long names that need a tooltip. In a
   *  *layout* effect, which runs before paint — so the corrected position is the first one
   *  drawn and nothing flashes in the wrong place.
   *
   *  It mattered on the breadcrumb, which sits a few pixels below the top of the window:
   *  the bubble was clamped to `top: 8` and then translated up by its own height, which
   *  put it off the screen entirely. */
  useLayoutEffect(() => {
    if (!anchor || !bubble.current) return;
    const height = bubble.current.getBoundingClientRect().height;
    setAbove(anchor.top - height - 8 >= 8);
  }, [anchor]);

  // A `fixed` bubble does not follow its trigger, so anything that moves the trigger has
  // to dismiss it rather than leave it pointing at nothing. Escape too: a tooltip that
  // covers what you are reading needs a way out that is not "move the mouse".
  useEffect(() => {
    if (!anchor) return;
    const hide = () => setAnchor(null);
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") hide();
    };
    window.addEventListener("scroll", hide, true);
    window.addEventListener("resize", hide);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("scroll", hide, true);
      window.removeEventListener("resize", hide);
      window.removeEventListener("keydown", onKey);
    };
  }, [anchor]);

  if (!text) return children;

  const show = (event: { currentTarget: Element }) =>
    setAnchor(event.currentTarget.getBoundingClientRect());

  return (
    <>
      {cloneElement(children, {
        onPointerEnter: show,
        onPointerLeave: () => setAnchor(null),
        onFocus: show,
        onBlur: () => setAnchor(null),
        "aria-describedby": anchor ? id : undefined,
      })}
      {anchor &&
        createPortal(
          <div
            ref={bubble}
            id={id}
            role="tooltip"
            data-testid="tooltip"
            // Centred over the trigger and clamped to the viewport, so a tooltip on the
            // last column of a wide table stays on screen instead of hanging off the edge.
            style={{
              top: above ? anchor.top - 8 : anchor.bottom + 8,
              left: Math.min(
                Math.max(8, anchor.left + anchor.width / 2),
                window.innerWidth - 8,
              ),
            }}
            className={`pointer-events-none fixed z-[60] -translate-x-1/2 rounded-lg bg-slate-900/95 px-2.5 py-1.5 text-xs font-medium text-white shadow-lg ${
              above ? "-translate-y-full" : ""
            }`}
          >
            {text}
            {/* The little point, on whichever side the bubble is not. `border` rather than
                a rotated square: a rotated element inside a translated one picks up the
                parent's transform origin and drifts. */}
            <span
              aria-hidden
              className={`absolute left-1/2 -ml-1 border-4 border-transparent ${
                above ? "top-full border-t-slate-900/95" : "bottom-full border-b-slate-900/95"
              }`}
            />
          </div>,
          document.body,
        )}
    </>
  );
}
