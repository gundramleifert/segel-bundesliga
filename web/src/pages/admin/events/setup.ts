/** The pure pieces of an event's setup form: boat rows, the catalog's sizes, the default
 *  size (Stories VA-6, VA-7). No React here — the form is `GeneralDataStep`. */
import type { BoatSpec } from "../../../api/types";
import i18n from "../../../i18n";
import { INPUT_CLASS } from "../../../lib/admin";
import { BOAT_COLORS, boatColor } from "../../../lib/format";

/** `INPUT_CLASS` at another width. Replaced rather than appended: a second `w-*` class does
 *  nothing when the shared one comes later in the stylesheet (docs/gotchas). */
export function sizedInput(width: string): string {
  return INPUT_CLASS.replace("w-full", width);
}

/** The league's predefined boat colors, in pairing-list order — the first six are the
 *  backend's own `BOAT_COLORS` (`app/models/racing.py`); `WHITE` is a UI-only addition on top
 *  (`lib/format.ts`), a real, sensible hull color and the fallback whenever a boat must have
 *  *some* color but none has been chosen — "no color" is deliberately not a choice here (the
 *  backend column is a free string either way, so this is a UI convention, not a schema one). */
export const PREDEFINED_COLORS = Object.keys(BOAT_COLORS);

/** Sentinel select value for "type your own color" — distinct from every real color string. */
export const CUSTOM_COLOR = "__custom__";

export interface BoatRow {
  color: string;
  customColor: string;
  name: string;
}

/** The color the backend would assign by position if boats aren't configured explicitly:
 *  the predefined colors in order, `WHITE` beyond that — never "no color". */
function defaultColor(position: number): string {
  return position <= PREDEFINED_COLORS.length ? PREDEFINED_COLORS[position - 1] : "WHITE";
}

/** Default name for a freshly added row — "Boat 1".."Boat N" by position, unique by
 *  construction and a clearer starting point than an empty required field. Freely
 *  editable afterwards; a rename is never overwritten by a later resize. */
function defaultName(position: number): string {
  return i18n.t("admin:events.boatDefaultName", { number: position });
}

/** A fresh row's `customColor` starts out matching its predefined default, not empty — the
 *  picker and free-text field are always visible now (not just once "Custom" is chosen), so
 *  they need a real value to show from the very first render, not a black fallback. */
function emptyBoatRow(position: number): BoatRow {
  const color = defaultColor(position);
  return { color, customColor: boatColor(color).hex, name: defaultName(position) };
}

/** `<input type="color">` needs a well-formed 6-digit hex or it silently resets to black —
 *  falls back to black only for the picker's own value, the free-text field keeps showing
 *  whatever was actually typed. */
export function hexForPicker(text: string): string {
  const trimmed = text.trim();
  return /^#[0-9a-f]{6}$/i.test(trimmed) ? trimmed.toLowerCase() : "#000000";
}

/** Resizes the boat rows to a new boat count — growing appends default rows, shrinking
 *  trims from the end, and rows in between keep whatever was already entered. */
export function resizedBoatRows(prev: BoatRow[], target: number): BoatRow[] {
  if (target === prev.length) return prev;
  if (target < prev.length) return prev.slice(0, target);
  const additional = Array.from({ length: target - prev.length }, (_, i) =>
    emptyBoatRow(prev.length + i + 1),
  );
  return [...prev, ...additional];
}

/** Builds the `boats` array position by position — `number` is the row's position, `color`
 *  resolves the custom-color sentinel to its free-text value. The name is required (the
 *  sail number is not collected here); `sail_number` stays null. */
export function boatSpecs(rows: BoatRow[]): BoatSpec[] {
  return rows.map((row, index) => ({
    number: index + 1,
    color: row.color === CUSTOM_COLOR ? row.customColor.trim() || "#ffffff" : row.color || "WHITE",
    name: row.name.trim(),
    sail_number: null,
  }));
}

/** Whether every row has the name it now requires — gates the submit button. */
export function boatNamesComplete(rows: BoatRow[]): boolean {
  return rows.every((row) => row.name.trim().length > 0);
}

export interface Size {
  teams: number;
  boats: number;
  maxFlights: number;
}

/** Identifies a teams-and-boats combination for the <select>. */
export function sizeKey(entry: { teams: number; boats: number }): string {
  return `${entry.teams}-${entry.boats}`;
}

/** The catalog as the form offers it: one row per teams-and-boats combination, with the
 *  most flights any stored list of that size holds. The flights are then a second choice,
 *  1 up to that (Story VA-7): a shorter day is the stored list cut after that flight. */
export function sizeOptions(catalog: { teams: number; boats: number; flights: number }[]): Size[] {
  const bySize = new Map<string, Size>();
  for (const entry of catalog) {
    const current = bySize.get(sizeKey(entry));
    if (!current || entry.flights > current.maxFlights) {
      bySize.set(sizeKey(entry), { teams: entry.teams, boats: entry.boats, maxFlights: entry.flights });
    }
  }
  return [...bySize.values()];
}

/** The size the form starts on until the organizer picks one (Story VA-6): for an act of a
 *  series, the catalog size for as many teams as the series has registered clubs — they are
 *  adopted as the act's entries on creation — else the catalog's first entry. Never a
 *  league's "18 on 6" written into the screen. */
export function defaultSize(sizes: Size[], registeredClubs: number | null): Size | undefined {
  const forSeries =
    registeredClubs != null ? sizes.find((size) => size.teams === registeredClubs) : undefined;
  return forSeries ?? sizes[0];
}
