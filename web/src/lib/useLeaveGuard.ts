import { useEffect } from "react";

/** Asks before leaving a page whose work is not saved — closing the tab, reloading, or a
 *  link inside the site. The app runs under a plain `BrowserRouter`, which has no
 *  navigation blocker, so a link is caught where it is clicked, before the router sees it.
 *  The browser's own back button is not caught. */
export function useLeaveGuard(active: boolean, question: string) {
  useEffect(() => {
    if (!active) return;
    const unload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    const click = (event: MouseEvent) => {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey) return;
      const link = (event.target as Element | null)?.closest?.("a[href]");
      if (!(link instanceof HTMLAnchorElement) || link.target === "_blank") return;
      if (link.origin !== window.location.origin) return; // `beforeunload` asks for these
      if (!window.confirm(question)) {
        event.preventDefault();
        event.stopPropagation();
      }
    };
    window.addEventListener("beforeunload", unload);
    document.addEventListener("click", click, true);
    return () => {
      window.removeEventListener("beforeunload", unload);
      document.removeEventListener("click", click, true);
    };
  }, [active, question]);
}
