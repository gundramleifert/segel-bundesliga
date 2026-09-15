/** What a race result is made of, shared by the two screens that enter one (Stories WL-2, WL-3).
 *
 * The results tab in `pages/Matchday.tsx` and the race-control page both turn taps and
 * codes into the raw fields the endpoint wants — `code`, `finish_position`,
 * `redress_points` — and both have to agree on what "complete" means, which codes need a
 * position, and what a redress suggestion is. Pure functions, no React: the state that
 * uses them is `useFinishOrder` in `components/FinishOrderPad.tsx`.
 */
import type { StandingRow } from "../api/types";

/** One boat's result as the screens hold it before it is sent. */
export interface ResultRow {
  boat_number: number;
  code: string;
  finish_position: number | null;
  redress_points: number | null;
  /** Only meaningful while `code === "RDG"`: RRS A10's recommended convention is the average
   *  of the team's other scored races in this event, which covers the large majority of
   *  redress cases — "auto" keeps `redress_points` pinned to that live average; "fixed" is a
   *  jury figure entered by hand instead. Not a backend field — inferred on load by comparing
   *  the stored value against the computed average, since only the raw points are persisted. */
  redress_mode: "auto" | "fixed";
}

/** Every code except FINISHED — that one is picked as a finish position number directly in
 *  the results tab's merged dropdown, not as its own entry in this list. UFD and BFD are the
 *  U-flag and black-flag start penalties (Story WL-3). */
export const SPECIAL_CODES = [
  "DNS",
  "DNF",
  "OCS",
  "UFD",
  "BFD",
  "DSQ",
  "DNE",
  "RET",
  "RDG",
  "ZFP",
  "SCP",
] as const;

/** `DID_NOT_FINISH_CODES` in `api/app/scoring/low_point.py`: all scored identically —
 *  starters + 1 points, worse than finishing last. Frontend copy of that fact for the
 *  tooltip text; the backend file is the source of truth and isn't touched here. */
export const NOT_FINISHED_CODES = new Set(["DNS", "DNF", "OCS", "UFD", "BFD", "DSQ", "DNE", "RET"]);

/** What a boat over the line at the start is scored as, by the preparatory flag that was
 *  flying (RRS 30). Mirrors `PreparatoryFlag.over_early_code` in `api/app/models/racing.py`:
 *  under P and I the boat may return and start correctly, so its OCS is clearable; under Z,
 *  U and the black flag the penalty stands. */
export const OVER_EARLY_CODE: Record<string, string> = {
  P: "OCS",
  I: "OCS",
  Z: "ZFP",
  U: "UFD",
  BLACK: "BFD",
};

export const PREPARATORY_FLAGS = ["P", "I", "Z", "U", "BLACK"] as const;
export type PreparatoryFlag = (typeof PREPARATORY_FLAGS)[number];

export function needsPosition(code: string): boolean {
  return code === "FINISHED" || code === "ZFP" || code === "SCP";
}

/** Only ZFP/SCP still need their own position input — FINISHED's position comes directly
 *  from picking a number in the merged dropdown, so showing a second input for it would just
 *  be two controls for the same value. */
export function needsOwnInput(code: string): boolean {
  return code === "ZFP" || code === "SCP";
}

/** Whether this row already carries a complete result: a finish position for
 *  FINISHED/ZFP/SCP, redress points for RDG, or — for the rest — simply having chosen the
 *  code at all. */
export function resultComplete(row: ResultRow): boolean {
  if (needsPosition(row.code)) return row.finish_position != null;
  if (row.code === "RDG") return row.redress_points != null;
  return true;
}

/** The tap fast-path only ever assigns/undoes a *FINISHED* position — once a special code has
 *  been chosen, tapping would silently overwrite it back to a numbered finish. */
export function canBeTapped(row: ResultRow): boolean {
  return row.code === "FINISHED";
}

/** Smallest finish position not currently occupied by a `FINISHED` boat — so the tap flow
 *  always continues 1, 2, 3, … even across a single-boat undo, without renumbering anyone. */
export function nextFreePosition(rows: Record<number, ResultRow>): number {
  const taken = new Set(
    Object.values(rows)
      .filter((row) => row.code === "FINISHED" && row.finish_position != null)
      .map((row) => row.finish_position as number),
  );
  let position = 1;
  while (taken.has(position)) position += 1;
  return position;
}

/** The boats whose finish position another boat also claims. */
export function duplicatePositions(rows: Record<number, ResultRow>): Set<number> {
  const counts = new Map<number, number>();
  for (const row of Object.values(rows)) {
    if (needsPosition(row.code) && row.finish_position != null) {
      counts.set(row.finish_position, (counts.get(row.finish_position) ?? 0) + 1);
    }
  }
  return new Set(
    Object.values(rows)
      .filter(
        (row) =>
          needsPosition(row.code) &&
          row.finish_position != null &&
          (counts.get(row.finish_position) ?? 0) > 1,
      )
      .map((row) => row.boat_number),
  );
}

/** RRS Appendix A10: nearest tenth, 0.05 rounds up — `Math.round` already rounds half away
 *  from zero for these non-negative point values, so this is exact for the RDG suggestion. */
function roundToTenth(value: number): number {
  return Math.round(value * 10) / 10;
}

/** RRS A10's suggested redress convention: the average of the team's points in this event's
 *  other already-scored races (this race's own sequence excluded). A suggestion the race
 *  officer can override, not something the app enforces — A10 allows alternatives too. */
export function redressSuggestion(
  teamId: number,
  excludedSequence: number,
  standings: StandingRow[],
): number | null {
  const row = standings.find((z) => z.team.id === teamId);
  if (!row) return null;
  const values = Object.entries(row.points_by_race)
    .filter(([sequenceText]) => Number(sequenceText) !== excludedSequence)
    .map(([, value]) => value);
  if (!values.length) return null;
  return roundToTenth(values.reduce((sum, value) => sum + value, 0) / values.length);
}

/** A row in the shape the endpoint wants.
 *
 *  A row that is not a complete result is sent as `code: null` — "nothing recorded for this
 *  boat" (Story WL-2). Every race starts as six of those and is filled in one boat at a time;
 *  reporting such a row as `FINISHED` with no position instead earned a correct-but-useless
 *  "Enter a finish position for boat 4" on the way to every hand-entered result. `null` is
 *  also what undoing a tap sends, so clearing a boat and never having entered it are the same
 *  request. */
export function toResultIn(
  row: ResultRow,
  redressValue: number | null,
): { boat_number: number; code: string | null; finish_position?: number | null; redress_points?: number | null } {
  return resultComplete(row)
    ? {
        boat_number: row.boat_number,
        code: row.code,
        finish_position: needsPosition(row.code) ? row.finish_position : null,
        redress_points: redressValue,
      }
    : { boat_number: row.boat_number, code: null };
}
