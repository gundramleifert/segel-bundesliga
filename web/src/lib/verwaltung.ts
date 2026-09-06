/** Helpers for the admin forms that aren't components.
 *
 * Own file so the component file only exports components — otherwise Vite's Fast Refresh
 * stops working there.
 */
import i18n from "../i18n";
import { ApiError } from "../api/client";

export const EINGABE =
  "w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none " +
  "focus:border-marke-500 focus:ring-2 focus:ring-marke-200";

/** The server's own message, not a made-up one — it says what went wrong. */
export function fehlertext(error: unknown): string {
  return error instanceof ApiError ? error.message : i18n.t("common:errors.actionFailed");
}

/** A toggle for a selection set — the same move used in several places. */
export function umschalter(
  setzen: (aktualisieren: (vorher: Set<number>) => Set<number>) => void,
) {
  return (id: number) =>
    setzen((vorher) => {
      const neu = new Set(vorher);
      if (neu.has(id)) neu.delete(id);
      else neu.add(id);
      return neu;
    });
}
