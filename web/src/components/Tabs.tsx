import { useRef, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";

/** One tabbed view, with the selected tab in the URL.
 *
 * Extracted when the admin screen needed tabs (Story A-11) and `Matchday.tsx` already had
 * a hand-rolled strip, with a third one specified for the club page (Story B-11). Three
 * copies of "buttons with `aria-selected` plus a `useState`" would have drifted apart on
 * the parts nobody looks at twice: the roving tabindex, the arrow keys, and the horizontal
 * scroll guard below.
 *
 * **The selection lives in a query parameter**, not in component state, because every
 * reason to switch tabs is also a reason to want a link: "look at the results tab of this
 * matchday", "the accounts screen". It also means a reload after a save comes back where
 * the organizer was instead of at tab one, and the browser's back button steps between
 * tabs the way people expect it to.
 *
 * **Only the selected panel is rendered.** Each `render` is a function, not a node, so an
 * unmounted tab issues none of its queries — on the admin screen that is the difference
 * between loading one area's data and loading five.
 */
export type TabDef<K extends string> = {
  key: K;
  label: string;
  render: () => ReactNode;
};

export function TabbedView<K extends string>({
  tabs,
  param,
  testIdPrefix,
  label,
  className,
}: {
  tabs: readonly TabDef<K>[];
  /** The query parameter holding the selection, e.g. `tab` → `/admin?tab=events`. */
  param: string;
  /** `admin` yields `admin-tabs` for the strip and `admin-events-tab` per tab. */
  testIdPrefix: string;
  /** Names the strip for screen readers — "Area", "View". */
  label: string;
  className?: string;
}) {
  const [searchParams, setSearchParams] = useSearchParams();
  const strip = useRef<HTMLDivElement>(null);

  // An unknown or missing value falls back to the first tab and is deliberately **not**
  // written into the URL: doing that on mount would push a history entry for a page the
  // visitor has not interacted with, so their first Back press would appear to do nothing.
  const requested = searchParams.get(param);
  const selected = tabs.find((tab) => tab.key === requested)?.key ?? tabs[0]?.key;

  const select = (key: K) =>
    setSearchParams(
      (previous) => {
        // Functional form and a copy: `setSearchParams({[param]: key})` would drop every
        // other parameter on the URL, which is how a filter or a page number disappears
        // the moment someone changes tab.
        const next = new URLSearchParams(previous);
        next.set(param, key);
        return next;
      },
      { replace: false },
    );

  /** Arrow keys move between tabs, Home/End jump to the ends — what the tab pattern
   *  requires, and what a roving tabindex is for: only the selected tab is in the tab
   *  order, so Tab moves *out* of the strip rather than through five buttons. */
  const onKeyDown = (event: React.KeyboardEvent) => {
    const index = tabs.findIndex((tab) => tab.key === selected);
    const target =
      event.key === "ArrowRight"
        ? (index + 1) % tabs.length
        : event.key === "ArrowLeft"
          ? (index - 1 + tabs.length) % tabs.length
          : event.key === "Home"
            ? 0
            : event.key === "End"
              ? tabs.length - 1
              : -1;
    if (target < 0) return;
    event.preventDefault();
    select(tabs[target].key);
    // Focus follows selection, as the pattern prescribes — otherwise the next arrow press
    // would start from the old tab again.
    strip.current
      ?.querySelectorAll<HTMLButtonElement>('[role="tab"]')
      [target]?.focus();
  };

  const active = tabs.find((tab) => tab.key === selected);

  return (
    <div className={className}>
      {/* The scroll container is not decoration. Five tabs do not fit across 412 px, and a
          strip wider than the viewport widens the page — which mobile Chromium answers by
          zooming everything out (Story A-10, docs/gotchas/grid-auto-columns-can-zoom-the-
          whole-page-out.md). Letting the strip scroll inside its own box keeps the overflow
          where it belongs. */}
      <div className="mb-4 overflow-x-auto">
        <div
          ref={strip}
          role="tablist"
          aria-label={label}
          data-testid={`${testIdPrefix}-tabs`}
          onKeyDown={onKeyDown}
          className="inline-flex rounded-lg border border-slate-200 bg-white p-1"
        >
          {tabs.map((tab) => {
            const isSelected = tab.key === selected;
            return (
              <button
                key={tab.key}
                type="button"
                role="tab"
                id={`${testIdPrefix}-tab-${tab.key}`}
                aria-selected={isSelected}
                aria-controls={`${testIdPrefix}-panel-${tab.key}`}
                tabIndex={isSelected ? 0 : -1}
                onClick={() => select(tab.key)}
                data-testid={`${testIdPrefix}-${tab.key}-tab`}
                className={`whitespace-nowrap rounded-md px-4 py-1.5 text-sm transition-colors ${
                  isSelected
                    ? "bg-brand-600 font-medium text-white"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {active && (
        <div
          role="tabpanel"
          id={`${testIdPrefix}-panel-${active.key}`}
          aria-labelledby={`${testIdPrefix}-tab-${active.key}`}
          data-testid={`${testIdPrefix}-panel-${active.key}`}
        >
          {active.render()}
        </div>
      )}
    </div>
  );
}
