import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Tip } from "../../../components/Tip";
import { EventStatus, type EventSummary, type StandingRow } from "../../../api/types";
import { Empty, TableFrame } from "../../../components/Blocks";
import { formatPoints } from "../../../lib/format";

/** A team's points in one flight, or `null` when it has no result in that flight yet. The
 *  sums are the server's (`points_by_flight`, Story B-2), keyed by flight number — computed
 *  from each race's own flight, never from sequence numbers here. */
function pointsInFlight(row: StandingRow, flight: number): number | null {
  return row.points_by_flight?.[flight] ?? null;
}

/** Which flights have at least one recorded result, for *any* team — a flight nobody has
 *  raced in yet gets a plain "–" for everyone, not a grey estimate: an estimate only makes
 *  sense once the flight is actually under way (someone else's race in it already ran). */
function startedFlights(standings: StandingRow[]): Set<number> {
  const started = new Set<number>();
  for (const row of standings) {
    for (const flight of Object.keys(row.points_by_flight ?? {})) started.add(Number(flight));
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
function estimatedFlights(row: StandingRow, flights: number[], started: Set<number>): number[] {
  return flights.filter((flight) => started.has(flight) && pointsInFlight(row, flight) === null);
}

// The tabs of a matchday (Stories B-2, B-3, B-12, WL-2), mounted by the matchday page
// (`pages/league/Act.tsx`, Story B-15) — one division's event each.

export function DailyStandings({
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

  const flights = Array.from({ length: event.flight_count }, (_, i) => i + 1);

  return <EventStandingsTable standings={standings} event={event} flights={flights} t={t} />;
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

function EventStandingsTable({
  standings,
  event,
  flights,
  t,
}: {
  standings: StandingRow[];
  event: EventSummary;
  flights: number[];
  t: (key: string, options?: Record<string, unknown>) => string;
}) {
  const [chosenMode, setMode] = useState<PointsMode>("exact");
  // Extrapolation projects the flights that have not been sailed yet, so it only means
  // anything while the matchday is running. On a finished or cancelled day there is
  // nothing left to project and the "provisional" column would be the same numbers with
  // an italic face and a disclaimer — so the choice is not offered, and the mode is
  // pinned to `exact` rather than left wherever it happened to be when racing ended.
  const canProject = event.status === EventStatus.live;
  const mode: PointsMode = canProject ? chosenMode : "exact";
  const flightsStarted = startedFlights(standings);

  // Rows always keep the backend's own order — `rank`, official, fewer points ranking higher
  // (`app/services/standings.py`). There is deliberately no client-side sorting: the one
  // question a standings table answers is "who leads", and letting a *provisional* column
  // reorder the official table only ever made a projection look like a result.
  return (
    <>
      {canProject && (
      <div className="mb-3 flex items-center justify-end gap-2">
        <span className="text-sm text-muted">{t("pointsModeLabel")}</span>
        <div
          role="group"
          aria-label={t("pointsModeLabel")}
          data-testid="matchday-standings-mode"
          className="flex shrink-0 overflow-hidden rounded-md border border-border text-xs"
        >
          {(["exact", "extrapolate"] as const).map((value) => (
            <Tip
              key={value}
              text={t(value === "exact" ? "pointsModeExactHint" : "pointsModeExtrapolateHint")}
            >
              <button
                type="button"
                aria-pressed={mode === value}
                onClick={() => setMode(value)}
                data-testid={`matchday-standings-mode-${value}`}
                className={`px-2 py-1.5 transition-colors ${
                  mode === value
                    ? "bg-accent font-medium text-accent-foreground"
                    : "bg-surface text-muted hover:bg-surface-tertiary"
                }`}
              >
                {t(value === "exact" ? "pointsModeExact" : "pointsModeExtrapolate")}
              </button>
            </Tip>
          ))}
        </div>
      </div>
      )}
      <TableFrame testId="matchday-standings-table-frame">
      <table
        data-testid="matchday-standings-table"
        // Content-sized, like the series table: with `w-full` the leftover width went to
        // the club column, which holds an abbreviation.
        className="data-table border-collapse text-sm"
      >
        <caption className="sr-only">{t("standingsCaption")}</caption>
        <thead>
          <tr className="border-b border-separator bg-surface-secondary text-left">
            <th scope="col" className="w-14 font-medium text-muted">
              {t("placeHeader")}
            </th>
            <th scope="col" className="font-medium text-muted">
              {t("teamHeader")}
            </th>
            <Tip text={mode === "extrapolate" ? t("projectedTooltip") : undefined}>
              <th
                scope="col"
                className="w-32 text-right font-medium text-muted"
              >
                {/* Always "Points", in both modes: the column is about points either way, and
                    the toggle above already says how they are arrived at. A header that renamed
                    itself read as a different quantity rather than the same one computed
                    differently. */}
                {t("pointsHeader")}
              </th>
            </Tip>
            <th scope="col" className="w-16 text-right font-medium text-muted">
              {t("racesHeader")}
            </th>
            {flights.map((flight) => (
              <Tip key={flight} text={t("flightColumnHeader", { number: flight })}>
                <th
                  scope="col"
                  className="w-12 text-right font-medium text-muted"
                >
                  {flight}
                </th>
              </Tip>
            ))}
          </tr>
        </thead>
        <tbody>
          {standings.map((row) => {
            const average = expectedAverage(row, event.boat_count);
            const estimated = estimatedFlights(row, flights, flightsStarted);
            // The projected total is exactly the row's own cells added up: real flight sums
            // plus one expected average per greyed cell. Nothing is added that isn't shown.
            const extrapolated = row.total + estimated.length * average;
            return (
              <tr
                key={row.team.id}
                data-testid={`matchday-standings-row-${row.team.id}`}
                className="border-b border-separator last:border-0 hover:bg-surface-secondary"
              >
                <td className="font-semibold tabular-nums">{row.rank}</td>
                <td>
                  {/* The abbreviation, with the full name in the tooltip. Eighteen club
                      names set the width of this column on their own, and the people
                      reading a standings table know their abbreviations — that is what
                      abbreviations are for, and every pairing list already uses them. */}
                  <Tip text={row.team.club.name}>
                    <Link
                      to={`/clubs/${row.team.club.id}`}
                      data-testid={`matchday-standings-club-link-${row.team.id}`}
                      className="font-medium underline-offset-2 hover:underline"
                    >
                      {row.team.club.short_name}
                    </Link>
                  </Tip>
                </td>
                {mode === "extrapolate" ? (
                  <Tip text={t("projectedTooltip")}>
                    <td
                      data-testid={`matchday-standings-projected-${row.team.id}`}
                      className="text-right font-semibold italic tabular-nums text-foreground"
                    >
                      {formatPoints(extrapolated)}
                    </td>
                  </Tip>
                ) : (
                  <td
                    data-testid={`matchday-standings-points-${row.team.id}`}
                    className="text-right font-semibold tabular-nums"
                  >
                    {formatPoints(row.net)}
                    {row.net !== row.total && (
                      <span className="ml-1 text-xs font-normal text-faint">
                        ({formatPoints(row.total)} {t("gross")})
                      </span>
                    )}
                    {/* Story WL-4: a total that is not the sum of its races says why. */}
                    {(row.penalty_points ?? 0) > 0 && (
                      <Tip text={row.penalty_note || t("penaltyTooltip")}>
                        <span
                          data-testid={`matchday-standings-penalty-${row.team.id}`}
                          className="ml-1 text-xs font-normal text-danger"
                        >
                          {t("penaltyIncluded", { points: formatPoints(row.penalty_points ?? 0) })}
                        </span>
                      </Tip>
                    )}
                  </td>
                )}
                <td className="text-right tabular-nums text-muted">
                  {row.races_scored}
                </td>
                {flights.map((flight) => {
                  const value = pointsInFlight(row, flight);
                  if (value != null) {
                    return (
                      <td key={flight} className="text-right tabular-nums text-muted">
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
                      <td key={flight} className="text-right tabular-nums text-faint">
                        –
                      </td>
                    );
                  }
                  return (
                    <Tip key={flight} text={t("projectedFlightTooltip")}>
                      <td
                        data-testid={`matchday-standings-flight-projected-${row.team.id}-${flight}`}
                        className="text-right italic tabular-nums text-faint"
                      >
                        {formatPoints(average)}
                      </td>
                    </Tip>
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
