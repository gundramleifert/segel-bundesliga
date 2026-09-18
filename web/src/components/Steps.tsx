/** Where you are in a short, ordered sequence of steps (Story VA-6).
 *
 * One numbered marker per step: done steps carry a check, the current one is filled, the
 * rest are outlined. `current` is 1-based; a value past the last step means "all done",
 * which is what the closing screen of a wizard shows.
 *
 * Deliberately not tabs: `TabbedView` lets the reader jump anywhere and keeps the choice
 * in the URL, and neither is wanted here — the steps are ordered because each needs what
 * the one before it produced, and a half-created event is not a place to link to.
 *
 * Test ids: `${testId}` on the list, `${testId}-${n}` on each step with
 * `data-state="done" | "current" | "upcoming"`, and `aria-current="step"` on the current one.
 */
export function Steps({
  steps,
  current,
  testId,
}: {
  steps: string[];
  current: number;
  testId: string;
}) {
  return (
    <ol data-testid={testId} className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
      {steps.map((label, index) => {
        const number = index + 1;
        const state = number < current ? "done" : number === current ? "current" : "upcoming";
        const marker =
          state === "done"
            ? "bg-emerald-600 text-white"
            : state === "current"
              ? "bg-brand-600 text-white"
              : "border border-slate-300 text-slate-500";
        return (
          <li
            key={label}
            data-testid={`${testId}-${number}`}
            data-state={state}
            aria-current={state === "current" ? "step" : undefined}
            className={`flex items-center gap-2 ${state === "upcoming" ? "text-slate-500" : "text-slate-900"}`}
          >
            <span
              aria-hidden="true"
              className={`inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${marker}`}
            >
              {state === "done" ? "✓" : number}
            </span>
            <span className={state === "current" ? "font-semibold" : undefined}>{label}</span>
          </li>
        );
      })}
    </ol>
  );
}
