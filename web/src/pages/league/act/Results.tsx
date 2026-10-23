import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Tip } from "../../../components/Tip";
import {
  getGetAdminRacesQueryKey,
  getGetEventQueryKey,
  useGetAdminRaces,
  usePutRaceResult,
  usePutTeamPenalty,
} from "../../../api/generated/sbl";
import { ResultCode, type AdminRace, type BoatOut, type StandingRow } from "../../../api/types";
import { useAsync, useInvalidate } from "../../../api/useApi";
import { FinishChip, useFinishOrder } from "../../../components/FinishOrderPad";
import {
  NOT_FINISHED_CODES,
  SPECIAL_CODES,
  needsOwnInput,
  parseResultCode,
  redressSuggestion,
} from "../../../lib/results";
import {
  ErrorMessage,
  Loading,
  Empty,
  TableFrame,
} from "../../../components/Blocks";
import { boatColor, formatPoints, teamLabel } from "../../../lib/format";
import { INPUT_CLASS, errorText } from "../../../lib/admin";
import { Select } from "../../../components/Select";

// ---------------------------------------------------------------- Story WL-2: results

// The codes, what "complete" means and the redress suggestion live in `lib/results.ts`, and
// the tap state in `components/FinishOrderPad.tsx` — shared with the race-control page
// (Story WL-3), so the two screens cannot drift apart on what a tap means.

/** Only `admin`/`race_officer` can reach this (gated in `Matchday`) — the race committee's
 *  entry screen: the same pairing grid as the "pairing" tab, but editable and including
 *  unfinished races. A row PUTs its whole race on save; results are the raw
 *  `code`/`finish_position`/`redress_points` — `points` are always derived
 *  (`app/services/standings.py`), never entered here.
 */
export function ResultsEntry({
  eventId,
  standings,
}: {
  eventId: number;
  standings: StandingRow[];
}) {
  const { t } = useTranslation("matchday");
  const { data, error, loading } = useAsync(useGetAdminRaces(eventId));
  const [showAll, setShowAll] = useState(false);

  if (loading) return <Loading text={t("resultsLoading")} testId="matchday-results-loading" />;
  if (error) return <ErrorMessage text={error} testId="matchday-results-error" />;
  if (!data?.races.length) return <Empty testId="matchday-results-empty">{t("noRacesDrawn")}</Empty>;

  // Captured as its own const so TS keeps `races` narrowed to non-null inside the closures
  // below — narrowing on `data` itself doesn't survive into a nested function body.
  const races = data.races;

  // The current race is the server's (`current_sequence`, Story WL-3): races run one at a
  // time, so there's never more than one "current" race, one "previous" (just finished) and
  // one "next" (drawn but not run) worth focusing on at a time. Default to that
  // neighborhood instead of all 48 rows; "show all" stays available for correcting an older
  // result later (a protest decision isn't limited to the most recent race).
  const currentIndex = races.findIndex((race) => race.sequence === data.current_sequence);
  const displayed = showAll
    ? races
    : currentIndex === -1
      ? races.slice(-3)
      : races.slice(Math.max(0, currentIndex - 1), currentIndex + 2);

  function raceRole(race: AdminRace): "previous" | "current" | "next" | null {
    if (showAll) return null;
    const index = races.indexOf(race);
    if (currentIndex === -1) return null;
    if (index === currentIndex) return "current";
    if (index === currentIndex - 1) return "previous";
    if (index === currentIndex + 1) return "next";
    return null;
  }

  return (
    <>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted" data-testid="matchday-results-focus-hint">
          {showAll ? t("resultsAllHint") : t("resultsFocusHint")}
        </p>
        <div className="flex flex-wrap items-center gap-3">
          {/* Story WL-3: on the water the committee runs races from their own page; this
              tab is the correction screen. */}
          <Link
            to={`/events/${eventId}/race-control`}
            data-testid="matchday-results-race-control-link"
            className="text-sm font-medium text-link underline-offset-2 hover:underline"
          >
            {t("openRaceControl")}
          </Link>
          <button
            type="button"
            onClick={() => setShowAll((prev) => !prev)}
            data-testid="matchday-results-show-all-toggle"
            className="text-sm font-medium text-link underline-offset-2 hover:underline"
          >
            {showAll ? t("resultsShowFocused") : t("resultsShowAll")}
          </button>
        </div>
      </div>
      <TableFrame testId="matchday-results-table-frame">
        <table data-testid="matchday-results-table" className="data-table w-full min-w-[64rem] border-collapse text-sm">
          <caption className="sr-only">{t("resultsCaption")}</caption>
          <thead>
            <tr className="border-b border-separator bg-surface-secondary text-left">
              <th scope="col" className="w-16 font-medium text-muted">
                {t("numberHeader")}
              </th>
              <th scope="col" className="w-20 font-medium text-muted">
                {t("flightHeader")}
              </th>
              {data.boats.map((boat) => {
                const color = boatColor(boat.color);
                return (
                  <th key={boat.number} scope="col" className="font-medium">
                    <span className="flex items-center gap-1.5">
                      <span
                        aria-hidden
                        className="size-3 shrink-0 rounded-full ring-1 ring-border"
                        style={{ backgroundColor: color.hex }}
                      />
                      <span className="text-muted">{color.name}</span>
                    </span>
                  </th>
                );
              })}
              <th scope="col" className="w-28 font-medium text-muted" />
            </tr>
          </thead>
          <tbody>
            {displayed.map((race) => (
              // Keyed on the version too: after a save, the row re-mounts with the fresh
              // server state instead of quietly keeping the pre-save form values.
              <RaceResultRow
                key={`${race.id}-${race.version}`}
                race={race}
                boats={data.boats}
                eventId={eventId}
                standings={standings}
                raceRole={raceRole(race)}
              />
            ))}
          </tbody>
        </table>
      </TableFrame>
      <PenaltyEntry eventId={eventId} standings={standings} />
    </>
  );
}

/** Story WL-4: penalty points for a team on the matchday as a whole — counted once, never
 *  discarded. One row per team; saving an empty field removes the penalty. */
function PenaltyEntry({ eventId, standings }: { eventId: number; standings: StandingRow[] }) {
  const { t } = useTranslation("matchday");
  if (!standings.length) return null;
  const rows = [...standings].sort((a, b) =>
    teamLabel(a.team).localeCompare(teamLabel(b.team)),
  );
  return (
    <details className="mt-4" data-testid="matchday-penalties">
      <summary className="cursor-pointer text-sm font-medium text-foreground">
        {t("penaltiesTitle")}
      </summary>
      <p className="mt-2 text-sm text-muted">{t("penaltiesHint")}</p>
      <ul className="mt-2 flex flex-col gap-2">
        {rows.map((row) => (
          <PenaltyRow key={`${row.team.id}-${row.penalty_points}-${row.penalty_note}`} eventId={eventId} row={row} />
        ))}
      </ul>
    </details>
  );
}

function PenaltyRow({ eventId, row }: { eventId: number; row: StandingRow }) {
  const { t } = useTranslation("matchday");
  const invalidate = useInvalidate();
  const [points, setPoints] = useState(row.penalty_points ? String(row.penalty_points) : "");
  const [note, setNote] = useState(row.penalty_note ?? "");
  const save = usePutTeamPenalty({
    mutation: { onSuccess: () => invalidate(getGetEventQueryKey(eventId)) },
  });
  const parsed = points.trim() === "" ? null : Number(points.replace(",", "."));
  const invalid = parsed !== null && !(parsed > 0 && parsed <= 100);
  return (
    <li
      data-testid={`matchday-penalty-row-${row.team.id}`}
      className="flex flex-wrap items-center gap-2 text-sm"
    >
      <span className="w-20 font-medium">{teamLabel(row.team)}</span>
      <input
        type="text"
        inputMode="decimal"
        aria-label={t("penaltyPointsLabel", { club: teamLabel(row.team) })}
        data-testid={`matchday-penalty-points-${row.team.id}`}
        className={`${INPUT_CLASS} w-20`}
        value={points}
        onChange={(e) => setPoints(e.target.value)}
      />
      <input
        type="text"
        aria-label={t("penaltyNoteLabel", { club: teamLabel(row.team) })}
        placeholder={t("penaltyNotePlaceholder")}
        data-testid={`matchday-penalty-note-${row.team.id}`}
        className={`${INPUT_CLASS} min-w-0 flex-1`}
        value={note}
        maxLength={300}
        onChange={(e) => setNote(e.target.value)}
      />
      <button
        type="button"
        disabled={invalid || save.isPending}
        data-testid={`matchday-penalty-save-${row.team.id}`}
        className="text-sm font-medium text-link underline-offset-2 hover:underline disabled:text-faint"
        onClick={() =>
          save.mutate({
            eventId,
            teamId: row.team.id,
            data: { points: parsed, note: parsed === null ? null : note.trim() || null },
          })
        }
      >
        {t("penaltySave")}
      </button>
      {invalid && <span className="text-danger">{t("penaltyInvalid")}</span>}
      {save.error && <span className="text-danger">{errorText(save.error)}</span>}
    </li>
  );
}

function RaceResultRow({
  race,
  boats,
  eventId,
  standings,
  raceRole,
}: {
  race: AdminRace;
  boats: BoatOut[];
  eventId: number;
  standings: StandingRow[];
  raceRole: "previous" | "current" | "next" | null;
}) {
  const { t } = useTranslation("matchday");
  const invalidate = useInvalidate();
  const byBoat = new Map(race.entries.map((entry) => [entry.boat_number, entry]));

  // RRS A9: the DNF family scores as starters + 1; ZFP/SCP add a 20%-of-starters penalty
  // capped at that value. `race.entries.length` is this race's starter count.
  const starter = race.entries.length;
  const dnfPoints = starter + 1;
  const zfpPenalty = Math.max(1, Math.round(starter * 0.2));

  function codeTitle(code: ResultCode): string {
    if (code === ResultCode.FINISHED) return t("codeTooltip.FINISHED");
    if (NOT_FINISHED_CODES.has(code)) return t(`codeTooltip.${code}`, { points: dnfPoints });
    if (code === ResultCode.ZFP || code === ResultCode.SCP) {
      return t(`codeTooltip.${code}`, { cap: dnfPoints, penalty: zfpPenalty });
    }
    if (code === ResultCode.RDG) return t("codeTooltip.RDG");
    return code;
  }

  // No Save button: every change writes straight through to the backend (still guarded by
  // the same duplicate check that used to just disable Save — an in-progress duplicate
  // simply doesn't save yet, rather than blocking a click that no longer exists).
  const save = usePutRaceResult({
    mutation: {
      onSuccess: () => {
        // The keys come from the generated getters, so they cannot drift away from the
        // queries they are meant to clear. Both matter: the race list this screen reads,
        // and the event, whose standings the backend just recomputed.
        invalidate(getGetAdminRacesQueryKey(eventId), getGetEventQueryKey(eventId));
      },
    },
  });

  // The taps and codes of this race, shared with the race-control page (Story WL-3). This
  // screen writes through on every change; `rows` stays the single source of truth — the
  // <Select> and position <input> below just read it back, so tap-assignment and manual
  // entry can never drift apart.
  const order = useFinishOrder(race, standings, {
    onChange: (body) => save.mutate({ eventId, raceId: race.id, data: body }),
  });
  const { rows, setField, duplicateBoats } = order;
  const hasDuplicates = duplicateBoats.size > 0;

  return (
    <tr
      data-testid={`matchday-results-row-${race.id}`}
      className={`border-b border-separator align-top last:border-0 ${
        raceRole === "current" ? "bg-accent-soft" : ""
      }`}
    >
      <td className="px-3 py-2.5 font-semibold tabular-nums">
        {race.sequence}
        {raceRole && (
          <span
            data-testid={`matchday-results-role-${race.id}`}
            className={`ml-1.5 block text-[10px] font-normal uppercase tracking-wide ${
              raceRole === "current" ? "text-link" : "text-faint"
            }`}
          >
            {t(`raceRole.${raceRole}`)}
          </span>
        )}
      </td>
      <td className="px-3 py-2.5 tabular-nums text-muted">{race.flight}</td>
      {boats.map((boat) => {
        const existing = byBoat.get(boat.number);
        const row = rows[boat.number];
        if (!existing || !row) {
          return (
            <td key={boat.number} className="px-3 py-2.5 text-faint">
              –
            </td>
          );
        }
        const color = boatColor(boat.color);
        const suggestion =
          row.code === ResultCode.RDG ? redressSuggestion(existing.team.id, race.sequence, standings) : null;
        // The merged dropdown's own value: a finish position shows as its number, every
        // other code shows as itself, and "FINISHED with nothing picked yet" shows as the
        // empty placeholder rather than a bare "FINISHED" that isn't a real option anymore.
        const selectValue =
          row.code === ResultCode.FINISHED
            ? row.finish_position != null
              ? String(row.finish_position)
              : ""
            : row.code;
        return (
          <td key={boat.number} className="min-w-[9.5rem] px-3 py-2.5">
            <div className="mb-1 flex items-center gap-1.5 truncate text-xs font-medium text-muted">
              <span
                aria-hidden
                className="size-2.5 shrink-0 rounded-full ring-1 ring-border"
                style={{ backgroundColor: color.hex }}
              />
              <span className="truncate">{teamLabel(existing.team)}</span>
            </div>
            {existing.is_discarded && (
              <div className="mb-1 text-[11px] text-faint">{t("discardedNote")}</div>
            )}
            <div className="flex items-center gap-1.5">
              <Tip text={codeTitle(row.code)}>
                <Select
                  aria-label={t("codeHeader")}
                  className="flex-1"
                  value={selectValue}
                  invalid={duplicateBoats.has(boat.number)}
                  onChange={(e) => {
                    const nextValue = e.target.value;
                    const asPosition = Number(nextValue);
                    if (nextValue !== "" && Number.isInteger(asPosition) && asPosition > 0) {
                      setField(boat.number, { code: ResultCode.FINISHED, finish_position: asPosition });
                      return;
                    }
                    const code = parseResultCode(nextValue);
                    if (code === ResultCode.RDG) {
                      const suggestionOnSwitch = redressSuggestion(
                        existing.team.id,
                        race.sequence,
                        standings,
                      );
                      setField(boat.number, {
                        code,
                        // Most redress cases are the plain A10 average — default to "auto"
                        // whenever one can actually be computed, "fixed" only when there's
                        // nothing yet to average (this team hasn't scored another race).
                        redress_mode: suggestionOnSwitch != null ? "auto" : "fixed",
                        redress_points: suggestionOnSwitch,
                      });
                      return;
                    }
                    if (code) setField(boat.number, { code });
                  }}
                  testId={`matchday-results-code-select-${race.id}-${boat.number}`}
                >
                  <option value="" disabled hidden>
                    {t("resultPlaceholder")}
                  </option>
                  {Array.from({ length: starter }, (_, i) => i + 1).map((position) => (
                    <option key={position} value={position} title={codeTitle(ResultCode.FINISHED)}>
                      {position}
                    </option>
                  ))}
                  {SPECIAL_CODES.map((code) => (
                    <option key={code} value={code} title={codeTitle(code)}>
                      {code}
                    </option>
                  ))}
                </Select>
              </Tip>
              <FinishChip
                boat={boat}
                teamName={teamLabel(existing.team)}
                row={row}
                onTap={() => order.tap(boat.number)}
                testId={`matchday-results-tap-${race.id}-${boat.number}`}
              />
            </div>
            {needsOwnInput(row.code) && (
              <input
                type="number"
                min={1}
                className={`${INPUT_CLASS} mt-1 ${
                  duplicateBoats.has(boat.number) ? "border-danger ring-2 ring-danger/40" : ""
                }`}
                value={row.finish_position ?? ""}
                placeholder={t("positionPlaceholder")}
                aria-invalid={duplicateBoats.has(boat.number)}
                onChange={(e) =>
                  setField(boat.number, {
                    finish_position: e.target.value ? Number(e.target.value) : null,
                  })
                }
                data-testid={`matchday-results-position-input-${race.id}-${boat.number}`}
              />
            )}
            {row.code === ResultCode.RDG && (
              <div className="mt-1 space-y-1">
                <div className="flex gap-1" role="group" aria-label={t("redressModeLabel")}>
                  {(["auto", "fixed"] as const).map((mode) => (
                    <button
                      key={mode}
                      type="button"
                      onClick={() =>
                        setField(boat.number, {
                          redress_mode: mode,
                          // Switching to "auto" snaps the value to today's average right
                          // away; switching to "fixed" just unlocks the field and keeps
                          // whatever number is currently showing as the starting point.
                          redress_points: mode === "auto" ? suggestion : row.redress_points,
                        })
                      }
                      aria-pressed={row.redress_mode === mode}
                      data-testid={`matchday-results-redress-mode-${mode}-${race.id}-${boat.number}`}
                      className={`flex-1 rounded-md border px-1.5 py-1 text-[11px] font-medium transition ${
                        row.redress_mode === mode
                          ? "border-accent bg-accent-soft text-link"
                          : "border-border text-muted hover:bg-surface-secondary"
                      }`}
                    >
                      {t(`redress${mode === "auto" ? "Auto" : "Fixed"}Label`)}
                    </button>
                  ))}
                </div>
                {row.redress_mode === "auto" ? (
                  <p
                    className="text-[11px] italic text-muted"
                    data-testid={`matchday-results-redress-auto-value-${race.id}-${boat.number}`}
                  >
                    {suggestion != null
                      ? t("redressAutoValue", { value: formatPoints(suggestion) })
                      : t("redressAutoUnavailable")}
                  </p>
                ) : (
                  <input
                    type="number"
                    step="0.1"
                    className={INPUT_CLASS}
                    value={row.redress_points ?? ""}
                    placeholder={t("redressPlaceholder")}
                    onChange={(e) =>
                      setField(boat.number, {
                        redress_points: e.target.value ? Number(e.target.value) : null,
                      })
                    }
                    data-testid={`matchday-results-redress-input-${race.id}-${boat.number}`}
                  />
                )}
              </div>
            )}
          </td>
        );
      })}
      <td className="px-3 py-2.5">
        {hasDuplicates && (
          <p
            role="alert"
            data-testid={`matchday-results-duplicate-warning-${race.id}`}
            className="mb-1 text-xs text-danger"
          >
            {t("duplicatePositionWarning")}
          </p>
        )}
        {!hasDuplicates && save.isPending && (
          <p className="text-xs text-faint" data-testid={`matchday-results-save-message-${race.id}`}>
            {t("savingButton")}
          </p>
        )}
        {!hasDuplicates && save.isError && (
          <ErrorMessage text={errorText(save.error)} testId={`matchday-results-save-message-${race.id}`} />
        )}
      </td>
    </tr>
  );
}
