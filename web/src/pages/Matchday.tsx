import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import {
  api,
  type AdminRace,
  type BoatOut,
  type EventSummary,
  type StandingRow,
} from "../api/client";
import { useApi, useInvalidate, useAccount } from "../api/useApi";
import {
  ErrorMessage,
  Loading,
  Empty,
  PageHeader,
  StatusBadge,
  TableFrame,
} from "../components/Blocks";
import { boatColor, locationText, formatPoints, matchdaySubtitle, dateRange } from "../lib/format";
import { INPUT_CLASS, errorText } from "../lib/admin";

/** `races_per_flight = ceil(team_count / boat_count)` — same formula as
 *  `Verwaltung.tsx`'s `events.formatText` (`CLAUDE.md`: "The Event defines the
 *  configuration"). Guarded against `boat_count === 0` while an event is still being set up. */
function racesPerFlight(event: Pick<EventSummary, "team_count" | "boat_count">): number {
  return event.boat_count > 0 ? Math.ceil(event.team_count / event.boat_count) : 0;
}

/** Sum of a team's `points_by_race` for the races that belong to one flight, or `null` when
 *  none of that flight's races have a result yet for this team. Keys of `points_by_race` are
 *  JSON object keys (always strings) even though the backend type is `dict[int, float]`. */
function pointsInFlight(row: StandingRow, flight: number, perFlight: number): number | null {
  const start = (flight - 1) * perFlight + 1;
  const end = flight * perFlight;
  let sum = 0;
  let present = false;
  for (const [sequenceText, value] of Object.entries(row.points_by_race)) {
    const sequence = Number(sequenceText);
    if (sequence >= start && sequence <= end) {
      sum += value;
      present = true;
    }
  }
  return present ? sum : null;
}

/** Which flights have at least one recorded result, for *any* team — a flight nobody has
 *  raced in yet gets a plain "–" for everyone, not a grey estimate: an estimate only makes
 *  sense once the flight is actually under way (someone else's race in it already ran). */
function startedFlights(standings: StandingRow[], perFlight: number): Set<number> {
  const started = new Set<number>();
  for (const row of standings) {
    for (const sequenceText of Object.keys(row.points_by_race)) {
      started.add(Math.ceil(Number(sequenceText) / perFlight));
    }
  }
  return started;
}

/** A team's own average points per sailed race — or, before it has sailed anything, the fair
 *  expected value of a single low-point result: the mean of places 1..N is (N+1)/2 (e.g. in a
 *  6-boat race, a still-unraced result is "expected" to be worth 3.5 points). This single
 *  number both fills a not-yet-sailed flight's cell (shown greyed, clearly an estimate, never
 *  a real result) and builds the projected total below — never persisted, purely a display
 *  computation. */
function expectedAverage(row: StandingRow, boatCount: number): number {
  return row.races_scored > 0 ? row.total / row.races_scored : (boatCount + 1) / 2;
}

/** The flights this team has no result in *yet* which are nevertheless already under way —
 *  someone else has sailed a race in them. Exactly the cells that carry a greyed estimate in
 *  "extrapolate" mode, so the projected total is precisely the sum of what the row shows,
 *  with nothing added that isn't visible somewhere.
 *
 *  Because races run in sequence, in practice this is at most one flight — which is what
 *  keeps a projection from ever drifting more than a single race's worth above the real
 *  total, without needing a separate cap to enforce it. A flight nobody has reached yet is
 *  never estimated: there is no evidence it is under way. */
function estimatedFlights(
  row: StandingRow,
  flights: number[],
  perFlight: number,
  started: Set<number>,
): number[] {
  return flights.filter(
    (flight) => started.has(flight) && pointsInFlight(row, flight, perFlight) === null,
  );
}

/** B-2 and B-3: Daily standings and pairing list of a matchday. */
export function Matchday() {
  const { t } = useTranslation("matchday");
  const { id = "" } = useParams();
  const [view, setView] = useState<"standings" | "pairing" | "results">("standings");
  const { hasRole } = useAccount();
  const canEnterResults = hasRole("admin", "race_officer");

  const matchday = useApi(["event", id], (signal) => api.event(Number(id), signal));

  if (matchday.loading) return <Loading text={t("loading")} testId="matchday-loading" />;
  if (matchday.error) return <ErrorMessage text={matchday.error} testId="matchday-error" />;
  if (!matchday.data) return null;

  const { event, standings, races_scored, races_total } = matchday.data;

  const tabs: Array<["standings" | "pairing" | "results", string]> = [
    ["standings", t("standingsTab")],
    ["pairing", t("pairingTab")],
  ];
  if (canEnterResults) tabs.push(["results", t("resultsTab")]);

  return (
    <>
      <PageHeader
        title={event.title}
        subtitle={
          <>
            {[
              matchdaySubtitle(event),
              locationText(event),
              dateRange(event.starts_on, event.ends_on),
            ]
              .filter(Boolean)
              .join(" · ")}
          </>
        }
        testId="matchday-header"
        right={<StatusBadge status={event.status} testId="matchday-status-badge" />}
      />

      <p className="mb-6 text-sm text-slate-600">
        {t("racesCount", { scored: races_scored, total: races_total })}
        {event.status === "live" && ` · ${t("liveUpdate")}`}
      </p>

      <div
        role="tablist"
        aria-label={t("viewLabel")}
        data-testid="matchday-tabs"
        className="mb-4 inline-flex rounded-lg border border-slate-200 bg-white p-1"
      >
        {tabs.map(([value, text]) => (
          <button
            key={value}
            role="tab"
            aria-selected={view === value}
            onClick={() => setView(value)}
            data-testid={`matchday-${value}-tab`}
            className={`rounded-md px-4 py-1.5 text-sm transition-colors ${
              view === value
                ? "bg-marke-600 font-medium text-white"
                : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            {text}
          </button>
        ))}
      </div>

      {view === "standings" && (
        <DailyStandings standings={standings} event={event} />
      )}
      {view === "pairing" && <PairingList eventId={Number(id)} />}
      {view === "results" && canEnterResults && (
        <ResultsEntry eventId={Number(id)} eventIdParam={id} standings={standings} />
      )}
    </>
  );
}

function DailyStandings({
  standings,
  event,
}: {
  standings: StandingRow[];
  event: EventSummary;
}) {
  const { t } = useTranslation("matchday");

  if (!standings.length) return <Empty testId="matchday-standings-empty">{t("noResultsYet")}</Empty>;

  const hasSailed = standings.some((row) => row.races_scored > 0);
  if (!hasSailed) {
    return <Empty testId="matchday-standings-not-sailed">{t("notSailedYet")}</Empty>;
  }

  const perFlight = racesPerFlight(event);
  const flights = Array.from({ length: event.flight_count }, (_, i) => i + 1);

  return <StandingsTable standings={standings} event={event} flights={flights} perFlight={perFlight} t={t} />;
}

/** How the one points column reads a team that hasn't sailed every started flight yet.
 *
 *  "exact" shows only what was actually sailed — a flight with no result is a plain dash and
 *  contributes nothing. "extrapolate" fills a flight that is already under way with this
 *  team's expected average, greyed, and counts it in the total. Deliberately a display
 *  toggle over one column rather than two columns side by side: the two numbers answer the
 *  same question ("how does this team stand?") under different assumptions, and showing both
 *  at once invited reading the provisional one as official. */
type PointsMode = "exact" | "extrapolate";

function StandingsTable({
  standings,
  event,
  flights,
  perFlight,
  t,
}: {
  standings: StandingRow[];
  event: EventSummary;
  flights: number[];
  perFlight: number;
  t: (key: string, options?: Record<string, unknown>) => string;
}) {
  const [mode, setMode] = useState<PointsMode>("exact");
  const flightsStarted = startedFlights(standings, perFlight);

  // Rows always keep the backend's own order — `rank`, official, fewer points ranking higher
  // (`app/services/standings.py`). There is deliberately no client-side sorting: the one
  // question a standings table answers is "who leads", and letting a *provisional* column
  // reorder the official table only ever made a projection look like a result.
  return (
    <>
      <div className="mb-3 flex items-center justify-end gap-2">
        <span className="text-sm text-slate-600">{t("pointsModeLabel")}</span>
        <div
          role="group"
          aria-label={t("pointsModeLabel")}
          data-testid="matchday-standings-mode"
          className="flex shrink-0 overflow-hidden rounded-md border border-slate-300 text-xs"
        >
          {(["exact", "extrapolate"] as const).map((value) => (
            <button
              key={value}
              type="button"
              aria-pressed={mode === value}
              onClick={() => setMode(value)}
              title={t(value === "exact" ? "pointsModeExactHint" : "pointsModeExtrapolateHint")}
              data-testid={`matchday-standings-mode-${value}`}
              className={`px-2 py-1.5 transition-colors ${
                mode === value
                  ? "bg-marke-600 font-medium text-white"
                  : "bg-white text-slate-600 hover:bg-slate-100"
              }`}
            >
              {t(value === "exact" ? "pointsModeExact" : "pointsModeExtrapolate")}
            </button>
          ))}
        </div>
      </div>
      <TableFrame testId="matchday-standings-table-frame">
      <table
        data-testid="matchday-standings-table"
        className="w-full border-collapse text-sm"
        style={{ minWidth: `${30 + flights.length * 3.25}rem` }}
      >
        <caption className="sr-only">{t("standingsCaption")}</caption>
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50 text-left">
            <th scope="col" className="w-14 px-4 py-3 font-medium text-slate-600">
              {t("placeHeader")}
            </th>
            <th scope="col" className="px-4 py-3 font-medium text-slate-600">
              {t("teamHeader")}
            </th>
            <th
              scope="col"
              title={mode === "extrapolate" ? t("projectedTooltip") : undefined}
              className="w-32 px-4 py-3 text-right font-medium text-slate-600"
            >
              {/* Always "Points", in both modes: the column is about points either way, and
                  the toggle above already says how they are arrived at. A header that renamed
                  itself read as a different quantity rather than the same one computed
                  differently. */}
              {t("pointsHeader")}
            </th>
            <th scope="col" className="w-16 px-4 py-3 text-right font-medium text-slate-600">
              {t("racesHeader")}
            </th>
            {flights.map((flight) => (
              <th
                key={flight}
                scope="col"
                title={t("flightColumnHeader", { number: flight })}
                className="w-12 px-2 py-3 text-right font-medium text-slate-600"
              >
                {flight}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {standings.map((row) => {
            const average = expectedAverage(row, event.boat_count);
            const estimated = estimatedFlights(row, flights, perFlight, flightsStarted);
            // The projected total is exactly the row's own cells added up: real flight sums
            // plus one expected average per greyed cell. Nothing is added that isn't shown.
            const extrapolated = row.total + estimated.length * average;
            return (
              <tr
                key={row.team.id}
                data-testid={`matchday-standings-row-${row.team.id}`}
                className="border-b border-slate-100 last:border-0 hover:bg-slate-50"
              >
                <td className="px-4 py-3 font-semibold tabular-nums">{row.rank}</td>
                <td className="px-4 py-3">
                  <Link
                    to={`/clubs/${row.team.club.id}`}
                    data-testid={`matchday-standings-club-link-${row.team.id}`}
                    className="font-medium underline-offset-2 hover:underline"
                  >
                    {row.team.club.name}
                  </Link>
                </td>
                {mode === "extrapolate" ? (
                  <td
                    title={t("projectedTooltip")}
                    data-testid={`matchday-standings-projected-${row.team.id}`}
                    className="px-4 py-3 text-right font-semibold italic tabular-nums text-slate-700"
                  >
                    {formatPoints(extrapolated)}
                  </td>
                ) : (
                  <td
                    data-testid={`matchday-standings-points-${row.team.id}`}
                    className="px-4 py-3 text-right font-semibold tabular-nums"
                  >
                    {formatPoints(row.net)}
                    {row.net !== row.total && (
                      <span className="ml-1 text-xs font-normal text-slate-400">
                        ({formatPoints(row.total)} {t("gross")})
                      </span>
                    )}
                  </td>
                )}
                <td className="px-4 py-3 text-right tabular-nums text-slate-500">
                  {row.races_scored}
                </td>
                {flights.map((flight) => {
                  const value = pointsInFlight(row, flight, perFlight);
                  if (value != null) {
                    return (
                      <td key={flight} className="px-2 py-3 text-right tabular-nums text-slate-500">
                        {formatPoints(value)}
                      </td>
                    );
                  }
                  // In "exact" mode an unsailed flight is always a plain dash. In
                  // "extrapolate" it carries the expected average — but only where the flight
                  // is already under way, i.e. someone has a result in it. A flight nobody
                  // has reached yet is never estimated, even mid-matchday.
                  if (mode === "exact" || !estimated.includes(flight)) {
                    return (
                      <td key={flight} className="px-2 py-3 text-right tabular-nums text-slate-400">
                        –
                      </td>
                    );
                  }
                  return (
                    <td
                      key={flight}
                      title={t("projectedFlightTooltip")}
                      data-testid={`matchday-standings-flight-projected-${row.team.id}-${flight}`}
                      className="px-2 py-3 text-right italic tabular-nums text-slate-400"
                    >
                      {formatPoints(average)}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
      </TableFrame>
    </>
  );
}

function PairingList({ eventId }: { eventId: number }) {
  const { t } = useTranslation("matchday");
  const { data, error, loading } = useApi(["pairing", eventId], (signal) =>
    api.pairing(eventId, signal),
  );

  if (loading) return <Loading text={t("pairingLoading")} testId="matchday-pairing-loading" />;
  if (error) return <ErrorMessage text={error} testId="matchday-pairing-error" />;
  if (!data?.races.length) return <Empty testId="matchday-pairing-empty">{t("noRacesDrawn")}</Empty>;

  return (
    <>
      <TableFrame testId="matchday-pairing-table-frame">
        <table data-testid="matchday-pairing-table" className="w-full min-w-[44rem] border-collapse text-sm">
          <caption className="sr-only">{t("pairingCaption")}</caption>
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-left">
              <th scope="col" className="w-16 px-3 py-3 font-medium text-slate-600">
                {t("numberHeader")}
              </th>
              <th scope="col" className="w-20 px-3 py-3 font-medium text-slate-600">
                {t("flightHeader")}
              </th>
              {data.boats.map((boat) => {
                const color = boatColor(boat.color);
                return (
                  <th key={boat.number} scope="col" className="px-3 py-3 font-medium">
                    <span className="flex items-center gap-1.5">
                      <span
                        aria-hidden
                        className="size-3 shrink-0 rounded-full ring-1 ring-slate-300"
                        style={{ backgroundColor: color.hex }}
                      />
                      <span className="text-slate-600">{color.name}</span>
                    </span>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {data.races.map((race) => (
              <tr
                key={race.sequence}
                data-testid={`matchday-pairing-row-${race.sequence}`}
                className="border-b border-slate-100 last:border-0 hover:bg-slate-50"
              >
                <td className="px-3 py-2.5 font-semibold tabular-nums">{race.sequence}</td>
                <td className="px-3 py-2.5 tabular-nums text-slate-500">{race.flight}</td>
                {data.boats.map((boat) => (
                  <td key={boat.number} className="px-3 py-2.5">
                    {race.teams_by_boat[String(boat.number)]?.club.short_name ?? "–"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </TableFrame>
    </>
  );
}

// ---------------------------------------------------------------- Story WL-2: results

/** Every code except FINISHED — that one is picked as a finish position number directly in
 *  the merged dropdown (see `RaceResultRow`), not as its own entry in this list. */
const SPECIAL_CODES = ["DNS", "DNF", "OCS", "DSQ", "DNE", "RET", "RDG", "ZFP", "SCP"] as const;

function needsPosition(code: string): boolean {
  return code === "FINISHED" || code === "ZFP" || code === "SCP";
}

/** Only ZFP/SCP still need their own position input — FINISHED's position comes directly
 *  from picking a number in the merged dropdown, so showing a second input for it would just
 *  be two controls for the same value. */
function needsOwnInput(code: string): boolean {
  return code === "ZFP" || code === "SCP";
}

/** Whether this row already carries a complete result: a finish position for
 *  FINISHED/ZFP/SCP, redress points for RDG, or — for the rest — simply having chosen the
 *  code at all. Drives the tap icon's in-progress/done flip: a boat that hasn't finished this
 *  race yet still reads "in progress" even once other boats in the same race already have a
 *  result recorded. */
function resultComplete(row: ResultRow): boolean {
  if (needsPosition(row.code)) return row.finish_position != null;
  if (row.code === "RDG") return row.redress_points != null;
  return true;
}

/** The tap fast-path only ever assigns/undoes a *FINISHED* position — once a special code has
 *  been chosen via the dropdown, tapping the icon would silently overwrite it back to a
 *  numbered finish, so it's disabled (still shown, just not clickable) for those rows. */
function canBeTapped(row: ResultRow): boolean {
  return row.code === "FINISHED";
}

/** `DID_NOT_FINISH_CODES` in `api/app/scoring/low_point.py`: all scored identically —
 *  starters + 1 points, worse than finishing last. Frontend copy of that fact for the
 *  tooltip text; the backend file is the source of truth and isn't touched here. */
const NOT_FINISHED_CODES = new Set(["DNS", "DNF", "OCS", "DSQ", "DNE", "RET"]);

/** RRS Appendix A10: nearest tenth, 0.05 rounds up — `Math.round` already rounds half away
 *  from zero for these non-negative point values, so this is exact for the RDG suggestion. */
function roundToTenth(value: number): number {
  return Math.round(value * 10) / 10;
}

/** RRS A10's suggested redress convention: the average of the team's points in this event's
 *  other already-scored races (this race's own sequence excluded). A suggestion the race
 *  officer can override, not something the app enforces — A10 allows alternatives too. */
function redressSuggestion(
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

/** Only `admin`/`race_officer` can reach this (gated in `Matchday`) — the race committee's
 *  entry screen: the same pairing grid as the "pairing" tab, but editable and including
 *  unfinished races. A row PUTs its whole race on save; results are the raw
 *  `code`/`finish_position`/`redress_points` — `points` are always derived
 *  (`app/services/standings.py`), never entered here.
 */
/** A race not yet finished (or abandoned) — races run strictly one at a time in sequence,
 *  so at most one race in the whole matchday is ever actually "open" at once. */
function stillOpen(race: AdminRace): boolean {
  return race.status !== "finished" && race.status !== "abandoned";
}

function ResultsEntry({
  eventId,
  eventIdParam,
  standings,
}: {
  eventId: number;
  eventIdParam: string;
  standings: StandingRow[];
}) {
  const { t } = useTranslation("matchday");
  const { data, error, loading } = useApi(["admin", "races", eventId], (signal) =>
    api.admin.races(eventId, signal),
  );
  const [showAll, setShowAll] = useState(false);

  if (loading) return <Loading text={t("resultsLoading")} testId="matchday-results-loading" />;
  if (error) return <ErrorMessage text={error} testId="matchday-results-error" />;
  if (!data?.races.length) return <Empty testId="matchday-results-empty">{t("noRacesDrawn")}</Empty>;

  // Captured as its own const so TS keeps `races` narrowed to non-null inside the closures
  // below — narrowing on `data` itself doesn't survive into a nested function body.
  const races = data.races;

  // Everything before the first still-open race is already finished, everything after it
  // can't have started yet — so there's never more than one "current" race, one "previous"
  // (just finished) and one "next" (drawn but not run) worth focusing on at a time. Default
  // to that neighborhood instead of all 48 rows; "show all" stays available for correcting
  // an older result later (a protest decision isn't limited to the most recent race).
  const currentIndex = races.findIndex(stillOpen);
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
        <p className="text-sm text-slate-600" data-testid="matchday-results-focus-hint">
          {showAll ? t("resultsAllHint") : t("resultsFocusHint")}
        </p>
        <button
          type="button"
          onClick={() => setShowAll((prev) => !prev)}
          data-testid="matchday-results-show-all-toggle"
          className="text-sm font-medium text-marke-700 underline-offset-2 hover:underline"
        >
          {showAll ? t("resultsShowFocused") : t("resultsShowAll")}
        </button>
      </div>
      <TableFrame testId="matchday-results-table-frame">
        <table data-testid="matchday-results-table" className="w-full min-w-[64rem] border-collapse text-sm">
          <caption className="sr-only">{t("resultsCaption")}</caption>
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-left">
              <th scope="col" className="w-16 px-3 py-3 font-medium text-slate-600">
                {t("numberHeader")}
              </th>
              <th scope="col" className="w-20 px-3 py-3 font-medium text-slate-600">
                {t("flightHeader")}
              </th>
              {data.boats.map((boat) => {
                const color = boatColor(boat.color);
                return (
                  <th key={boat.number} scope="col" className="px-3 py-3 font-medium">
                    <span className="flex items-center gap-1.5">
                      <span
                        aria-hidden
                        className="size-3 shrink-0 rounded-full ring-1 ring-slate-300"
                        style={{ backgroundColor: color.hex }}
                      />
                      <span className="text-slate-600">{color.name}</span>
                    </span>
                  </th>
                );
              })}
              <th scope="col" className="w-28 px-3 py-3 font-medium text-slate-600" />
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
                eventIdParam={eventIdParam}
                standings={standings}
                raceRole={raceRole(race)}
              />
            ))}
          </tbody>
        </table>
      </TableFrame>
    </>
  );
}

interface ResultRow {
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

/** Smallest finish position not currently occupied by a tap-assigned (or manually entered)
 *  `FINISHED` boat — so the tap flow always continues 1, 2, 3, … even across a single-boat
 *  undo, without needing to renumber everyone else. */
function nextFreePosition(rows: Record<number, ResultRow>): number {
  const taken = new Set(
    Object.values(rows)
      .filter((row) => row.code === "FINISHED" && row.finish_position != null)
      .map((row) => row.finish_position as number),
  );
  let position = 1;
  while (taken.has(position)) position += 1;
  return position;
}

function RaceResultRow({
  race,
  boats,
  eventId,
  eventIdParam,
  standings,
  raceRole,
}: {
  race: AdminRace;
  boats: BoatOut[];
  eventId: number;
  eventIdParam: string;
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

  function codeTitle(code: string): string {
    if (code === "FINISHED") return t("codeTooltip.FINISHED");
    if (NOT_FINISHED_CODES.has(code)) return t(`codeTooltip.${code}`, { points: dnfPoints });
    if (code === "ZFP" || code === "SCP") {
      return t(`codeTooltip.${code}`, { cap: dnfPoints, penalty: zfpPenalty });
    }
    if (code === "RDG") return t("codeTooltip.RDG");
    return code;
  }

  const [rows, setRows] = useState<Record<number, ResultRow>>(() =>
    Object.fromEntries(
      race.entries.map((entry) => {
        const code = entry.code ?? "FINISHED";
        const redress_points = entry.redress_points ?? null;
        // No backend field says whether a stored RDG value was the auto-average or a jury's
        // own figure — guess "auto" when it still matches today's average, "fixed" otherwise
        // (e.g. the average has since shifted, or it never matched to begin with).
        let redress_mode: "auto" | "fixed" = "auto";
        if (code === "RDG" && redress_points != null) {
          const suggestion = redressSuggestion(entry.team.id, race.sequence, standings);
          redress_mode = suggestion != null && Math.abs(suggestion - redress_points) < 0.05 ? "auto" : "fixed";
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
    ),
  );

  // In "auto" mode the stored `redress_points` can be stale (the average moves as other
  // races get scored) — recompute fresh from the current `standings` at save time instead of
  // trusting whatever was last written into state.
  function effectiveRedressValue(row: ResultRow): number | null {
    if (row.code !== "RDG") return null;
    if (row.redress_mode === "fixed") return row.redress_points;
    const teamId = byBoat.get(row.boat_number)?.team.id;
    if (teamId == null) return row.redress_points;
    return redressSuggestion(teamId, race.sequence, standings) ?? row.redress_points;
  }

  // No Save button: every change writes straight through to the backend (still guarded by
  // the same duplicate check that used to just disable Save — an in-progress duplicate
  // simply doesn't save yet, rather than blocking a click that no longer exists).
  const save = useMutation({
    mutationFn: (nextRows: Record<number, ResultRow>) =>
      api.admin.setRaceResult(eventId, race.id, {
        results: Object.values(nextRows).map((row) => ({
          boat_number: row.boat_number,
          code: row.code,
          finish_position: needsPosition(row.code) ? row.finish_position : null,
          redress_points: effectiveRedressValue(row),
        })),
      }),
    onSuccess: () => {
      invalidate(["admin", "races", eventId], ["event", eventIdParam]);
    },
  });

  function duplicatesIn(candidate: Record<number, ResultRow>): Set<number> {
    const positionCounts = new Map<number, number>();
    for (const row of Object.values(candidate)) {
      if (needsPosition(row.code) && row.finish_position != null) {
        positionCounts.set(row.finish_position, (positionCounts.get(row.finish_position) ?? 0) + 1);
      }
    }
    return new Set(
      Object.values(candidate)
        .filter(
          (row) =>
            needsPosition(row.code) &&
            row.finish_position != null &&
            (positionCounts.get(row.finish_position) ?? 0) > 1,
        )
        .map((row) => row.boat_number),
    );
  }

  function apply(nextRows: Record<number, ResultRow>) {
    setRows(nextRows);
    if (duplicatesIn(nextRows).size === 0) {
      save.mutate(nextRows);
    }
  }

  const setField = (boatNumber: number, patch: Partial<ResultRow>) =>
    apply({ ...rows, [boatNumber]: { ...rows[boatNumber], ...patch } });

  // Fast path (Story WL-2): tapping a boat assigns it FINISHED + the next unused finish
  // position; tapping an already-assigned boat undoes just that one. `rows` stays the
  // single source of truth — the <select> and position <input> below just read it back, so
  // tap-assignment and manual entry can never drift apart.
  function tap(boatNumber: number) {
    const row = rows[boatNumber];
    const nextRow =
      row.code === "FINISHED" && row.finish_position != null
        ? { ...row, finish_position: null }
        : { ...row, code: "FINISHED", finish_position: nextFreePosition(rows) };
    apply({ ...rows, [boatNumber]: nextRow });
  }

  const duplicateBoats = duplicatesIn(rows);
  const hasDuplicates = duplicateBoats.size > 0;

  return (
    <tr
      data-testid={`matchday-results-row-${race.id}`}
      className={`border-b border-slate-100 align-top last:border-0 ${
        raceRole === "current" ? "bg-marke-50" : ""
      }`}
    >
      <td className="px-3 py-2.5 font-semibold tabular-nums">
        {race.sequence}
        {raceRole && (
          <span
            data-testid={`matchday-results-role-${race.id}`}
            className={`ml-1.5 block text-[10px] font-normal uppercase tracking-wide ${
              raceRole === "current" ? "text-marke-700" : "text-slate-400"
            }`}
          >
            {t(`raceRole.${raceRole}`)}
          </span>
        )}
      </td>
      <td className="px-3 py-2.5 tabular-nums text-slate-500">{race.flight}</td>
      {boats.map((boat) => {
        const existing = byBoat.get(boat.number);
        const row = rows[boat.number];
        if (!existing || !row) {
          return (
            <td key={boat.number} className="px-3 py-2.5 text-slate-400">
              –
            </td>
          );
        }
        const color = boatColor(boat.color);
        const complete = resultComplete(row);
        const tappable = canBeTapped(row);
        const suggestion =
          row.code === "RDG" ? redressSuggestion(existing.team.id, race.sequence, standings) : null;
        // The merged dropdown's own value: a finish position shows as its number, every
        // other code shows as itself, and "FINISHED with nothing picked yet" shows as the
        // empty placeholder rather than a bare "FINISHED" that isn't a real option anymore.
        const selectValue =
          row.code === "FINISHED"
            ? row.finish_position != null
              ? String(row.finish_position)
              : ""
            : row.code;
        return (
          <td key={boat.number} className="min-w-[9.5rem] px-3 py-2.5">
            <div className="mb-1 flex items-center gap-1.5 truncate text-xs font-medium text-slate-600">
              <span
                aria-hidden
                className="size-2.5 shrink-0 rounded-full ring-1 ring-slate-300"
                style={{ backgroundColor: color.hex }}
              />
              <span className="truncate">{existing.team.club.short_name}</span>
            </div>
            {existing.is_discarded && (
              <div className="mb-1 text-[11px] text-slate-400">{t("discardedNote")}</div>
            )}
            <div className="flex items-center gap-1.5">
              <select
                aria-label={t("codeHeader")}
                title={codeTitle(row.code)}
                className={`${INPUT_CLASS} flex-1 ${
                  duplicateBoats.has(boat.number) ? "border-red-500 ring-2 ring-red-200" : ""
                }`}
                value={selectValue}
                aria-invalid={duplicateBoats.has(boat.number)}
                onChange={(e) => {
                  const nextValue = e.target.value;
                  const asPosition = Number(nextValue);
                  if (nextValue !== "" && Number.isInteger(asPosition) && asPosition > 0) {
                    setField(boat.number, { code: "FINISHED", finish_position: asPosition });
                    return;
                  }
                  if (nextValue === "RDG") {
                    const suggestionOnSwitch = redressSuggestion(
                      existing.team.id,
                      race.sequence,
                      standings,
                    );
                    setField(boat.number, {
                      code: nextValue,
                      // Most redress cases are the plain A10 average — default to "auto"
                      // whenever one can actually be computed, "fixed" only when there's
                      // nothing yet to average (this team hasn't scored another race).
                      redress_mode: suggestionOnSwitch != null ? "auto" : "fixed",
                      redress_points: suggestionOnSwitch,
                    });
                    return;
                  }
                  setField(boat.number, { code: nextValue });
                }}
                data-testid={`matchday-results-code-select-${race.id}-${boat.number}`}
              >
                <option value="" disabled hidden>
                  {t("resultPlaceholder")}
                </option>
                {Array.from({ length: starter }, (_, i) => i + 1).map((position) => (
                  <option key={position} value={position} title={codeTitle("FINISHED")}>
                    {position}
                  </option>
                ))}
                {SPECIAL_CODES.map((code) => (
                  <option key={code} value={code} title={codeTitle(code)}>
                    {code}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => tappable && tap(boat.number)}
                disabled={!tappable}
                aria-pressed={tappable ? complete : undefined}
                title={
                  !tappable
                    ? t("tapLockedLabel", { code: row.code })
                    : complete
                      ? t("tapUndoLabel", { position: row.finish_position })
                      : t("tapInProgressLabel", { boat: color.name })
                }
                data-testid={`matchday-results-tap-${race.id}-${boat.number}`}
                className={`flex size-9 shrink-0 items-center justify-center rounded-md border border-transparent text-base text-white shadow-sm transition ${
                  tappable ? "hover:brightness-110" : "cursor-default opacity-90"
                }`}
                style={{ backgroundColor: color.hex }}
              >
                <span aria-hidden className="[text-shadow:0_1px_2px_rgb(0_0_0_/_55%)]">
                  {complete ? "🏁" : "⏳"}
                </span>
              </button>
            </div>
            {needsOwnInput(row.code) && (
              <input
                type="number"
                min={1}
                className={`${INPUT_CLASS} mt-1 ${
                  duplicateBoats.has(boat.number) ? "border-red-500 ring-2 ring-red-200" : ""
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
            {row.code === "RDG" && (
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
                          ? "border-marke-600 bg-marke-50 text-marke-700"
                          : "border-slate-300 text-slate-500 hover:bg-slate-50"
                      }`}
                    >
                      {t(`redress${mode === "auto" ? "Auto" : "Fixed"}Label`)}
                    </button>
                  ))}
                </div>
                {row.redress_mode === "auto" ? (
                  <p
                    className="text-[11px] italic text-slate-500"
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
            className="mb-1 text-xs text-red-700"
          >
            {t("duplicatePositionWarning")}
          </p>
        )}
        {!hasDuplicates && save.isPending && (
          <p className="text-xs text-slate-400" data-testid={`matchday-results-save-message-${race.id}`}>
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
