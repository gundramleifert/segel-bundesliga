/** The finish line as taps: the state of one race's result, and the chips that enter it.
 *
 * Two screens record results — the results tab in `pages/Matchday.tsx` (Story WL-2, the
 * correction screen) and the race-control page (Story WL-3, the one used on the water) —
 * and they must not drift apart on what a tap means, which position comes next, or what is
 * sent. So the state lives in one hook, `useFinishOrder`, and the chip a boat is tapped on
 * is one component, `FinishChip`, rendered compact inside a table cell or large on the pad.
 *
 * The two screens differ in *when* they write. The results tab writes through on every
 * change (`onChange`) — it corrects one boat at a time, and a save button was a tap wasted.
 * The race-control page keeps taps local until "Finish", so a mis-tap on the last boat does
 * not end the race by itself; it passes a `mirrorKey` instead, and the taps survive a reload
 * or a dropped connection in `localStorage` until the race is finished. Not WL-1's offline
 * sync — a morning without coverage is still open — but it removes the likeliest way to
 * lose a race.
 */
import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { AdminRace, BoatOut, StandingRow } from "../api/types";
import { boatColor } from "../lib/format";
import {
  type ResultRow,
  canBeTapped,
  duplicatePositions,
  nextFreePosition,
  redressSuggestion,
  resultComplete,
  toResultIn,
} from "../lib/results";

export interface FinishOrder {
  rows: Record<number, ResultRow>;
  /** Tap a boat: the next free finish position, or undo its own. With `overEarlyCode` set
   *  (flag X is up), the tap marks the boat over the line with that code instead — and a
   *  second tap clears the mark again. */
  tap: (boatNumber: number, overEarlyCode?: string | null) => void;
  setField: (boatNumber: number, patch: Partial<ResultRow>) => void;
  /** Boats whose finish position another boat also claims. Nothing is sent while non-empty. */
  duplicateBoats: Set<number>;
  /** Every boat has a position or a code — what "Finish" waits for. */
  complete: boolean;
  /** The request body for the current rows, redress averages resolved at this moment. */
  body: () => { results: ReturnType<typeof toResultIn>[] };
  /** Forget the mirrored taps (after a successful finish). */
  clearMirror: () => void;
}

interface Options {
  /** Called with the new rows after every change that has no duplicate positions —
   *  the results tab saves from here. */
  onChange?: (body: { results: ReturnType<typeof toResultIn>[] }) => void;
  /** `localStorage` key under which taps are kept between renders of the same race. */
  mirrorKey?: string;
}

interface Mirror {
  version: number;
  rows: Record<number, ResultRow>;
}

function readMirror(key: string | undefined, version: number): Record<number, ResultRow> | null {
  if (!key) return null;
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return null;
    const saved = JSON.parse(raw) as Mirror;
    // Only for the race as the server last knew it: a version bump means something was
    // written since (a start, a partial result), and the mirror is older than that.
    return saved.version === version ? saved.rows : null;
  } catch {
    return null;
  }
}

function writeMirror(key: string | undefined, version: number, rows: Record<number, ResultRow>) {
  if (!key) return;
  try {
    window.localStorage.setItem(key, JSON.stringify({ version, rows } satisfies Mirror));
  } catch {
    // Storage blocked or full: the taps still live in state, they just do not survive a reload.
  }
}

function initialRows(race: AdminRace, standings: StandingRow[]): Record<number, ResultRow> {
  return Object.fromEntries(
    race.entries.map((entry) => {
      const code = entry.code ?? "FINISHED";
      const redress_points = entry.redress_points ?? null;
      // No backend field says whether a stored RDG value was the auto-average or a jury's
      // own figure — guess "auto" when it still matches today's average, "fixed" otherwise.
      let redress_mode: "auto" | "fixed" = "auto";
      if (code === "RDG" && redress_points != null) {
        const suggestion = redressSuggestion(entry.team.id, race.sequence, standings);
        redress_mode =
          suggestion != null && Math.abs(suggestion - redress_points) < 0.05 ? "auto" : "fixed";
      }
      return [
        entry.boat_number,
        {
          boat_number: entry.boat_number,
          code,
          finish_position: entry.finish_position ?? null,
          redress_points,
          redress_mode,
        },
      ];
    }),
  );
}

export function useFinishOrder(
  race: AdminRace,
  standings: StandingRow[],
  options: Options = {},
): FinishOrder {
  const [rows, setRows] = useState<Record<number, ResultRow>>(() => {
    const fromServer = initialRows(race, standings);
    // The mirror only fills in for a race the server has nothing for yet — once a result
    // is stored, the server is the truth and a stale mirror must not overwrite it.
    const untouched = race.entries.every((entry) => entry.code == null);
    return (untouched && readMirror(options.mirrorKey, race.version)) || fromServer;
  });
  const byBoat = new Map(race.entries.map((entry) => [entry.boat_number, entry]));

  // In "auto" mode the stored `redress_points` can be stale (the average moves as other
  // races get scored) — resolve it fresh from `standings` when sending.
  function effectiveRedress(row: ResultRow): number | null {
    if (row.code !== "RDG") return null;
    if (row.redress_mode === "fixed") return row.redress_points;
    const teamId = byBoat.get(row.boat_number)?.team.id;
    if (teamId == null) return row.redress_points;
    return redressSuggestion(teamId, race.sequence, standings) ?? row.redress_points;
  }

  const bodyFor = (next: Record<number, ResultRow>) => ({
    results: Object.values(next).map((row) => toResultIn(row, effectiveRedress(row))),
  });

  function apply(next: Record<number, ResultRow>) {
    setRows(next);
    writeMirror(options.mirrorKey, race.version, next);
    if (duplicatePositions(next).size === 0) options.onChange?.(bodyFor(next));
  }

  return {
    rows,
    tap: (boatNumber, overEarlyCode) => {
      const row = rows[boatNumber];
      if (!row) return;
      let next: ResultRow;
      if (overEarlyCode) {
        // Flag X is up: the boat was over the line. Under P and I the code is OCS and a
        // second tap takes it back (the boat returned and started correctly); under Z, U
        // and black the code stands, and taking it back is a deliberate correction too.
        next =
          row.code === overEarlyCode
            ? { ...row, code: "FINISHED", finish_position: null }
            : { ...row, code: overEarlyCode, finish_position: null };
      } else if (!canBeTapped(row)) {
        return;
      } else {
        next =
          row.finish_position != null
            ? { ...row, finish_position: null }
            : { ...row, finish_position: nextFreePosition(rows) };
      }
      apply({ ...rows, [boatNumber]: next });
    },
    setField: (boatNumber, patch) =>
      apply({ ...rows, [boatNumber]: { ...rows[boatNumber], ...patch } }),
    duplicateBoats: duplicatePositions(rows),
    complete: Object.values(rows).every(resultComplete),
    body: () => bodyFor(rows),
    clearMirror: () => {
      if (!options.mirrorKey) return;
      try {
        window.localStorage.removeItem(options.mirrorKey);
      } catch {
        // Nothing to do: it was never written either.
      }
    },
  };
}

/** One boat as a tappable chip: its colour, the team on it, and what it has so far. */
export function FinishChip({
  boat,
  teamName,
  row,
  onTap,
  size = "sm",
  disabled = false,
  testId,
}: {
  boat: BoatOut;
  teamName: string;
  row: ResultRow;
  onTap: () => void;
  size?: "sm" | "lg";
  disabled?: boolean;
  testId?: string;
}) {
  const { t } = useTranslation("matchday");
  const color = boatColor(boat.color);
  const complete = resultComplete(row);
  const finished = row.code === "FINISHED";
  const tappable = !disabled && canBeTapped(row);
  // What the chip shows: a finish position, a code, or nothing yet.
  const mark = finished ? (row.finish_position != null ? String(row.finish_position) : null) : row.code;
  const label = disabled
    ? `${teamName}: ${mark ?? "–"}`
    : !canBeTapped(row)
      ? t("tapLockedLabel", { code: row.code })
      : complete
        ? t("tapUndoLabel", { position: row.finish_position })
        : t("tapInProgressLabel", { boat: color.name });

  if (size === "sm") {
    return (
      <button
        type="button"
        onClick={() => tappable && onTap()}
        disabled={!tappable}
        aria-pressed={tappable ? complete : undefined}
        aria-label={label}
        data-testid={testId}
        className={`flex size-9 shrink-0 items-center justify-center rounded-md border border-transparent text-base text-white shadow-sm transition ${
          tappable ? "hover:brightness-110" : "cursor-default opacity-90"
        }`}
        style={{ backgroundColor: color.hex }}
      >
        <span aria-hidden className="[text-shadow:0_1px_2px_rgb(0_0_0_/_55%)]">
          {complete ? "🏁" : "⏳"}
        </span>
      </button>
    );
  }

  // Wet hands: the whole chip is the target, at least 64 px tall, and the team's name is
  // on it — on the water the committee thinks in boats and crews, not in numbers.
  return (
    <button
      type="button"
      onClick={onTap}
      disabled={disabled}
      aria-pressed={complete}
      aria-label={label}
      data-testid={testId}
      data-mark={mark ?? ""}
      className={`flex min-h-16 min-w-0 flex-col items-center justify-center gap-1 rounded-xl border-2 px-2 py-2 text-white shadow-sm transition ${
        complete ? "border-white ring-2 ring-slate-900/40" : "border-transparent"
      } ${disabled ? "cursor-default" : "active:scale-95"}`}
      style={{ backgroundColor: color.hex }}
    >
      <span className="w-full truncate text-xs font-medium [text-shadow:0_1px_2px_rgb(0_0_0_/_55%)]">
        {teamName}
      </span>
      <span className="text-2xl font-bold tabular-nums [text-shadow:0_1px_2px_rgb(0_0_0_/_55%)]">
        {mark ?? "·"}
      </span>
    </button>
  );
}

/** The pad: every boat of the race as a large chip, in boat order. */
export function FinishOrderPad({
  race,
  boats,
  order,
  overEarlyCode = null,
  disabled = false,
  testIdPrefix,
}: {
  race: AdminRace;
  boats: BoatOut[];
  order: FinishOrder;
  /** While flag X is up: the code a tapped boat gets instead of a finish position. */
  overEarlyCode?: string | null;
  disabled?: boolean;
  testIdPrefix: string;
}) {
  const byBoat = new Map(race.entries.map((entry) => [entry.boat_number, entry]));
  return (
    <div
      data-testid={`${testIdPrefix}-pad`}
      className="grid grid-cols-2 gap-3 sm:grid-cols-3"
    >
      {boats.map((boat) => {
        const entry = byBoat.get(boat.number);
        const row = order.rows[boat.number];
        if (!entry || !row) return null;
        return (
          <FinishChip
            key={boat.number}
            boat={boat}
            teamName={entry.team.club.short_name}
            row={row}
            size="lg"
            disabled={disabled}
            onTap={() => order.tap(boat.number, overEarlyCode)}
            testId={`${testIdPrefix}-chip-${boat.number}`}
          />
        );
      })}
    </div>
  );
}
