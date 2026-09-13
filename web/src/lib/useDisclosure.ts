import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";

/** A panel that opens, and closes for all the reasons a panel has to close.
 *
 * The frame has two of them — the burger menu and the account menu — and they agree on
 * everything that is easy to forget and invisible when missing: **Escape** closes it,
 * a click **outside** closes it, and any **navigation** closes it. A menu left standing
 * over the page it just navigated to reads as a broken link.
 *
 * The open state is the pathname the panel was opened at, not a boolean. Navigating then
 * closes it by arithmetic rather than by an effect that resets a boolean — which would
 * re-render the whole frame a second time on every navigation to undo a state nobody
 * asked for.
 */
export function useDisclosure(panelId: string, { closeOnOutsideClick = true } = {}) {
  const { pathname } = useLocation();
  const [openedAt, setOpenedAt] = useState<string | null>(null);
  const open = openedAt === pathname;
  const panel = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;

    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpenedAt(null);
      // Focus goes back where it came from — otherwise Escape leaves the keyboard at the
      // top of the document, several tab stops from what the reader was doing.
      trigger.current?.focus();
    };
    const onPointerDown = (event: PointerEvent) => {
      if (!closeOnOutsideClick) return;
      const target = event.target as Node;
      if (panel.current?.contains(target) || trigger.current?.contains(target)) return;
      setOpenedAt(null);
    };

    window.addEventListener("keydown", onKey);
    // `pointerdown`, not `click`: a click that starts inside the panel and ends outside it
    // (a drag over a link) is not a dismissal, and `click` would treat it as one.
    window.addEventListener("pointerdown", onPointerDown);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("pointerdown", onPointerDown);
    };
  }, [open, closeOnOutsideClick]);

  return {
    open,
    close: () => setOpenedAt(null),
    toggle: () => setOpenedAt(open ? null : pathname),
    /** Spread onto the button that opens it. */
    triggerProps: {
      ref: trigger,
      "aria-expanded": open,
      "aria-controls": panelId,
      onClick: () => setOpenedAt(open ? null : pathname),
    },
    /** Spread onto the panel itself — the ref the outside-click check needs, and the id
     *  the trigger's `aria-controls` points at. A props bag rather than two fields, so a
     *  caller cannot wire up one and forget the other. */
    panelProps: { ref: panel, id: panelId },
  };
}
