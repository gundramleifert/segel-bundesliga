/** Helpers for the admin forms that aren't components.
 *
 * Own file so the component file only exports components — otherwise Vite's Fast Refresh
 * stops working there.
 */
import i18n from "../i18n";
import { ApiError } from "../api/client";

export const INPUT_CLASS =
  "w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none " +
  "focus:border-marke-500 focus:ring-2 focus:ring-marke-200";

/** The server's own message, not a made-up one — it says what went wrong. */
export function errorText(error: unknown): string {
  return error instanceof ApiError ? error.message : i18n.t("common:errors.actionFailed");
}

/** A toggle for a selection set — the same move used in several places. */
export function toggleSet(
  setValue: (updater: (prev: Set<number>) => Set<number>) => void,
) {
  return (id: number) =>
    setValue((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
}
