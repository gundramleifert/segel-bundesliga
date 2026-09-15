import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Card } from "@heroui/react";
import { useTranslation } from "react-i18next";

import { Tip } from "../components/Tip";

import {
  getDownloadPairingPdfUrl,
  getGetAdminRacesQueryKey,
  getGetEventQueryKey,
  useGetAdminRaces,
  useGetEvent,
  useGetEventCrew,
  useGetPairing,
  usePutRaceResult,
} from "../api/generated/sbl";
import type { AdminRace, BoatOut, EventSummary, StandingRow, TeamCrew } from "../api/types";
import { useAsync, useInvalidate, useAccount } from "../api/useApi";
import { useLive } from "../api/useLive";
import { TabbedView, type TabDef } from "../components/Tabs";
import { Async } from "../components/Async";
import { FinishChip, useFinishOrder } from "../components/FinishOrderPad";
import { CardGrid } from "../components/Layouts";
import {
  NOT_FINISHED_CODES,
  SPECIAL_CODES,
  needsOwnInput,
  redressSuggestion,
} from "../lib/results";
import {
  ErrorMessage,
  LiveBadge,
  Loading,
  Empty,
  PageHeader,
  StatusBadge,
  TableFrame,
} from "../components/Blocks";
import {
  boatColor,
  locationText,
  formatPoints,
  matchdaySubtitle,
  eventDates,
  roleText,
} from "../lib/format";
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
  const { hasRole } = useAccount();
  const canEnterResults = hasRole("admin", "race_officer");

  const matchday = useAsync(useGetEvent(Number(id)));

  // Story B-5: hear about results and transitions while the page is open. Only for a
  // published event — a draft has no stream (the server answers 404) and the hook would
  // otherwise fall back to polling for nothing. The prefixes end in a slash on purpose:
  // "/api/events/1" would also match "/api/events/12".
  const live = useLive(matchday.data?.event.published ? `event:${id}` : null, [
    getGetEventQueryKey(Number(id)),
    `/api/events/${id}/`,
    `/api/admin/events/${id}/`,
  ]);

  if (matchday.loading) return <Loading text={t("loading")} testId="matchday-loading" />;
  if (matchday.error) return <ErrorMessage text={matchday.error} testId="matchday-error" />;
  if (!matchday.data) return null;

  const { event, standings, races_scored, races_total } = matchday.data;

  // The same strip as the admin screen and the club screen. It was hand-rolled here
  // first; `TabbedView` grew out of it (Story A-11) and owns the parts that get forgotten
  // when a strip is copied — the roving tabindex, the arrow keys, the scroll guard — and
  // it puts the selection in the URL, so a matchday's results tab can be linked.
  const tabs: TabDef<"standings" | "pairing" | "crew" | "results">[] = [
    {
      key: "standings",
      label: t("standingsTab"),
      render: () => <DailyStandings standings={standings} event={event} />,
    },
    {
      key: "pairing",
      label: t("pairingTab"),
      render: () => <PairingList eventId={Number(id)} />,
    },
    {
      key: "crew",
      label: t("crewTab"),
      render: () => <Crew eventId={Number(id)} />,
    },
  ];
  if (canEnterResults) {
    tabs.push({
      key: "results",
      label: t("resultsTab"),
      render: () => <ResultsEntry eventId={Number(id)} standings={standings} />,
    });
  }

  return (
    <>
      <PageHeader title={event.title} testId="matchday-header" />

      {/* The matchday's own facts — not a page subtitle, the breadcrumb names the page,
          but the only place on this page these appear.
          Three lines rather than one, because they are three kinds of fact and as a
          single dot-separated run they were a hundred and forty characters that wrapped
          mid-phrase: which competition this is, where and when it is sailed, and how far
          along it is. Each line is short enough to survive a phone. */}
      <div data-testid="matchday-meta" className="mb-6 space-y-0.5 text-sm">
        {/* The state belongs on the identity line, not on a row of its own above it —
            "which matchday is this, and where does it stand" is one question. */}
        <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
          <p className="font-medium text-slate-900">{matchdaySubtitle(event) ?? event.title}</p>
          <StatusBadge status={event.status} testId="matchday-status-badge" />
        </div>
        <p className="text-slate-600">
          {[locationText(event), eventDates(event)].filter(Boolean).join(" · ")}
        </p>
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-slate-500">
          <span data-testid="matchday-races-count">
            {t("racesCount", { scored: races_scored, total: races_total })}
          </span>
          {/* The badge only while racing: a finished day is not "live", and a planned one
              has nothing to stream yet. The stream itself is open regardless, so the page
              hears the start. */}
          {event.status === "live" && <LiveBadge state={live} testId="matchday-live-badge" />}
          {/* Stories L-1, L-2: the boats on the map, for a published event. */}
          {event.published && (
            <Link
              to={`/events/${id}/live`}
              data-testid="matchday-live-map-link"
              className="font-medium text-brand-700 underline-offset-2 hover:underline"
            >
              {t("liveMap")}
            </Link>
          )}
        </p>
      </div>

      <TabbedView tabs={tabs} param="view" testIdPrefix="matchday" label={t("viewLabel")} />
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
  const [chosenMode, setMode] = useState<PointsMode>("exact");
  // Extrapolation projects the flights that have not been sailed yet, so it only means
  // anything while the matchday is running. On a finished or cancelled day there is
  // nothing left to project and the "provisional" column would be the same numbers with
  // an italic face and a disclaimer — so the choice is not offered, and the mode is
  // pinned to `exact` rather than left wherever it happened to be when racing ended.
  const canProject = event.status === "live";
  const mode: PointsMode = canProject ? chosenMode : "exact";
  const flightsStarted = startedFlights(standings, perFlight);

  // Rows always keep the backend's own order — `rank`, official, fewer points ranking higher
  // (`app/services/standings.py`). There is deliberately no client-side sorting: the one
  // question a standings table answers is "who leads", and letting a *provisional* column
  // reorder the official table only ever made a projection look like a result.
  return (
    <>
      {canProject && (
      <div className="mb-3 flex items-center justify-end gap-2">
        <span className="text-sm text-slate-600">{t("pointsModeLabel")}</span>
        <div
          role="group"
          aria-label={t("pointsModeLabel")}
          data-testid="matchday-standings-mode"
          className="flex shrink-0 overflow-hidden rounded-md border border-slate-300 text-xs"
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
                    ? "bg-brand-600 font-medium text-white"
                    : "bg-white text-slate-600 hover:bg-slate-100"
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
          <tr className="border-b border-slate-200 bg-slate-50 text-left">
            <th scope="col" className="w-14 font-medium text-slate-600">
              {t("placeHeader")}
            </th>
            <th scope="col" className="font-medium text-slate-600">
              {t("teamHeader")}
            </th>
            <Tip text={mode === "extrapolate" ? t("projectedTooltip") : undefined}>
              <th
                scope="col"
                className="w-32 text-right font-medium text-slate-600"
              >
                {/* Always "Points", in both modes: the column is about points either way, and
                    the toggle above already says how they are arrived at. A header that renamed
                    itself read as a different quantity rather than the same one computed
                    differently. */}
                {t("pointsHeader")}
              </th>
            </Tip>
            <th scope="col" className="w-16 text-right font-medium text-slate-600">
              {t("racesHeader")}
            </th>
            {flights.map((flight) => (
              <Tip key={flight} text={t("flightColumnHeader", { number: flight })}>
                <th
                  scope="col"
                  className="w-12 text-right font-medium text-slate-600"
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
                      className="text-right font-semibold italic tabular-nums text-slate-700"
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
                      <span className="ml-1 text-xs font-normal text-slate-400">
                        ({formatPoints(row.total)} {t("gross")})
                      </span>
                    )}
                  </td>
                )}
                <td className="text-right tabular-nums text-slate-500">
                  {row.races_scored}
                </td>
                {flights.map((flight) => {
                  const value = pointsInFlight(row, flight, perFlight);
                  if (value != null) {
                    return (
                      <td key={flight} className="text-right tabular-nums text-slate-500">
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
                      <td key={flight} className="text-right tabular-nums text-slate-400">
                        –
                      </td>
                    );
                  }
                  return (
                    <Tip key={flight} text={t("projectedFlightTooltip")}>
                      <td
                        data-testid={`matchday-standings-flight-projected-${row.team.id}-${flight}`}
                        className="text-right italic tabular-nums text-slate-400"
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

/** B-12: who sails for each team at this matchday.
 *
 *  Public with no login, and no name is ever hidden: whoever is entered here is already on
 *  the pairing list, the results and the standings. Club *membership* is the private thing
 *  (V-10), and this is not that.
 *
 *  Deliberately **not** a `LinkCard`, which is one anchor around the whole card: each name
 *  is its own link to a sailor page, and an anchor inside an anchor is invalid HTML that
 *  browsers silently unnest. The club link therefore sits in the card header on its own. */
function Crew({ eventId }: { eventId: number }) {
  const { t } = useTranslation("matchday");
  const crew = useAsync(useGetEventCrew(eventId));

  return (
    <Async
      state={crew}
      testId="matchday-crew"
      loadingText={t("crewLoading")}
      empty={t("noTeamsEntered")}
      isEmpty={(data) => !data.teams?.length}
    >
      {(data) => (
        <CardGrid columns={3} testId="matchday-crew-list">
          {(data.teams ?? []).map((entry) => (
            <li key={entry.team.id} data-testid={`matchday-crew-team-${entry.team.id}`}>
              <TeamCrewCard entry={entry} />
            </li>
          ))}
        </CardGrid>
      )}
    </Async>
  );
}

function TeamCrewCard({ entry }: { entry: TeamCrew }) {
  const { t } = useTranslation("matchday");
  const { team, crew } = entry;

  return (
    <Card className="h-full">
      <Card.Header>
        <div className="flex items-start gap-3">
          {team.club.logo_url && (
            <img src={team.club.logo_url} alt="" className="size-8 shrink-0 object-contain" />
          )}
          {/* `min-w-0` so a long club name truncates instead of widening the grid track
              and zooming the page out on a phone (Story A-10). */}
          <div className="min-w-0 flex-1">
            <Card.Title className="truncate text-base">
              <Tip text={team.club.name}>
                <Link
                  to={`/clubs/${team.club.id}`}
                  data-testid={`matchday-crew-club-link-${team.id}`}
                  className="underline-offset-2 hover:underline"
                >
                  {team.name}
                </Link>
              </Tip>
            </Card.Title>
            {team.club.city && <Card.Description>{team.club.city}</Card.Description>}
          </div>
        </div>
      </Card.Header>
      <Card.Content>
        {crew?.length ? (
          <ul className="divide-y divide-slate-100 text-sm">
            {crew.map((member) => (
              <li
                key={member.id}
                data-testid={`matchday-crew-row-${team.id}-${member.id}`}
                className="flex items-center justify-between gap-3 py-2"
              >
                <Link
                  to={`/sailors/${member.id}`}
                  data-testid={`matchday-crew-sailor-link-${team.id}-${member.id}`}
                  className="truncate font-medium underline-offset-2 hover:underline"
                >
                  {member.first_name} {member.last_name}
                </Link>
                <span className="shrink-0 text-slate-500">{roleText(member.role)}</span>
              </li>
            ))}
          </ul>
        ) : (
          /* Entered but nobody named yet — said out loud, because an empty card reads as
             a page that failed to load. */
          <p
            data-testid={`matchday-crew-unnamed-${team.id}`}
            className="text-sm text-slate-400"
          >
            {t("crewNotNamed")}
          </p>
        )}
      </Card.Content>
    </Card>
  );
}

function PairingList({ eventId }: { eventId: number }) {
  const { t } = useTranslation("matchday");
  // "" is the whole sheet; a club id is that crew's own page. Before the guards below,
  // because a hook cannot sit after a conditional return.
  const [club, setClub] = useState("");
  const { data, error, loading } = useAsync(useGetPairing(eventId));

  if (loading) return <Loading text={t("pairingLoading")} testId="matchday-pairing-loading" />;
  if (error) return <ErrorMessage text={error} testId="matchday-pairing-error" />;
  if (!data?.races.length) return <Empty testId="matchday-pairing-empty">{t("noRacesDrawn")}</Empty>;

  // The teams of this draw, from the draw itself — the same set the PDF is built from, so
  // the picker can never offer a club the printed sheet does not know.
  const teams = [
    ...new Map(
      data.races.flatMap((race) => Object.values(race.teams_by_boat)).map((team) => [team.id, team]),
    ).values(),
  ].sort((a, b) => a.name.localeCompare(b.name));

  return (
    <>
      {/* The list is also read off paper: printed for the notice board, handed out at
          registration, carried to the boat. The link is a plain anchor, not a generated
          hook — the response is a PDF, and `api/http.ts` parses every response it handles
          as JSON. The picker narrows it to one crew's own page, which is what a crew at
          the dock wants; "all clubs" stays the default because the notice board wants the
          whole thing.

          Shown only where the server can actually print: the renderer is a Java tool, and
          a deployment may carry no JRE (the free test image did for a while). The server
          says so in `pdf_available`, because a button whose only possible answer is 503 is
          worse than no button. */}
      {data.pdf_available && (
      <div className="mb-3 flex flex-wrap items-center justify-end gap-2">
        <label className="sr-only" htmlFor="pairing-pdf-club">
          {t("pairingPdfForClub")}
        </label>
        <select
          id="pairing-pdf-club"
          value={club}
          onChange={(event) => setClub(event.target.value)}
          data-testid="matchday-pairing-pdf-club"
          className={`${INPUT_CLASS} w-auto py-1 text-sm`}
        >
          <option value="">{t("pairingPdfAllClubs")}</option>
          {teams.map((team) => (
            <option key={team.id} value={team.id}>
              {team.name}
            </option>
          ))}
        </select>
        <a
          href={getDownloadPairingPdfUrl(eventId, club ? { team: Number(club) } : undefined)}
          download
          data-testid="matchday-pairing-pdf-link"
          className="text-sm font-medium text-brand-700 underline-offset-2 hover:underline"
        >
          {t("pairingPdf")}
        </a>
      </div>
      )}
      <TableFrame testId="matchday-pairing-table-frame">
        {/* Centred throughout, heading over cell. Every column holds one short token — a
            race number, a flight number, a club abbreviation — so left alignment left each
            one pinned to the edge of a column much wider than its content, and which
            abbreviation belonged under which boat was a matter of tracing a ragged line.
            Centring makes the grid read as a grid. */}
        <table data-testid="matchday-pairing-table" className="data-table w-full min-w-[44rem] border-collapse text-center text-sm">
          <caption className="sr-only">{t("pairingCaption")}</caption>
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50">
              <th scope="col" className="w-24 font-medium text-slate-600">
                {t("numberHeader")}
              </th>
              <th scope="col" className="w-20 font-medium text-slate-600">
                {t("flightHeader")}
              </th>
              {data.boats.map((boat) => {
                const color = boatColor(boat.color);
                return (
                  <th key={boat.number} scope="col" className="font-medium">
                    <span className="flex items-center justify-center gap-1.5">
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
            {data.races.map((race, index) => {
              // A flight is the unit this list is actually read in — every team sails
              // exactly once in it, and a crew looks up "our flight", not "our race". 48
              // evenly-ruled rows hid that structure completely. Each flight is now a
              // banded block: a rule where one starts, and every second one tinted, so
              // the three races that belong together are one shape on the page.
              const startsFlight = data.races[index - 1]?.flight !== race.flight;
              const banded = race.flight % 2 === 0;
              return (
              <tr
                key={race.sequence}
                data-testid={`matchday-pairing-row-${race.sequence}`}
                className={`last:border-0 ${
                  startsFlight && index > 0
                    ? "border-t-2 border-t-slate-300"
                    : "border-t border-t-slate-100"
                } ${banded ? "bg-slate-50/70 hover:bg-slate-100" : "hover:bg-slate-50"}`}
              >
                <td className="font-semibold tabular-nums">{race.sequence}</td>
                {/* Named once per block rather than on all three of its rows: repeating
                    the same number down a group is what made the grouping invisible in
                    the first place. */}
                <td className="font-semibold tabular-nums text-slate-600">
                  {startsFlight ? race.flight : ""}
                </td>
                {data.boats.map((boat) => {
                  const team = race.teams_by_boat[String(boat.number)];
                  // Same treatment as every other club in the site: the abbreviation is
                  // what fits, the full name is the tooltip, and the name is the way to
                  // that club — a pairing list is read by someone looking for one club's
                  // races, and "which club is BYC (BE)?" was a question the table refused
                  // to answer.
                  if (!team) {
                    return (
                      <td key={boat.number} className="text-slate-400">
                        –
                      </td>
                    );
                  }
                  return (
                    <td key={boat.number}>
                      <Tip text={team.club.name}>
                        <Link
                          to={`/clubs/${team.club.id}`}
                          data-testid={`matchday-pairing-club-link-${race.sequence}-${boat.number}`}
                          className="font-medium underline-offset-2 hover:underline"
                        >
                          {team.club.short_name}
                        </Link>
                      </Tip>
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
/** A race not yet finished (or abandoned) — races run strictly one at a time in sequence,
 *  so at most one race in the whole matchday is ever actually "open" at once. */
function stillOpen(race: AdminRace): boolean {
  return race.status !== "finished" && race.status !== "abandoned";
}

function ResultsEntry({
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
        <div className="flex flex-wrap items-center gap-3">
          {/* Story WL-3: on the water the committee runs races from their own page; this
              tab is the correction screen. */}
          <Link
            to={`/events/${eventId}/race-control`}
            data-testid="matchday-results-race-control-link"
            className="text-sm font-medium text-brand-700 underline-offset-2 hover:underline"
          >
            {t("openRaceControl")}
          </Link>
          <button
            type="button"
            onClick={() => setShowAll((prev) => !prev)}
            data-testid="matchday-results-show-all-toggle"
            className="text-sm font-medium text-brand-700 underline-offset-2 hover:underline"
          >
            {showAll ? t("resultsShowFocused") : t("resultsShowAll")}
          </button>
        </div>
      </div>
      <TableFrame testId="matchday-results-table-frame">
        <table data-testid="matchday-results-table" className="data-table w-full min-w-[64rem] border-collapse text-sm">
          <caption className="sr-only">{t("resultsCaption")}</caption>
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-left">
              <th scope="col" className="w-16 font-medium text-slate-600">
                {t("numberHeader")}
              </th>
              <th scope="col" className="w-20 font-medium text-slate-600">
                {t("flightHeader")}
              </th>
              {data.boats.map((boat) => {
                const color = boatColor(boat.color);
                return (
                  <th key={boat.number} scope="col" className="font-medium">
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
              <th scope="col" className="w-28 font-medium text-slate-600" />
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
    </>
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

  function codeTitle(code: string): string {
    if (code === "FINISHED") return t("codeTooltip.FINISHED");
    if (NOT_FINISHED_CODES.has(code)) return t(`codeTooltip.${code}`, { points: dnfPoints });
    if (code === "ZFP" || code === "SCP") {
      return t(`codeTooltip.${code}`, { cap: dnfPoints, penalty: zfpPenalty });
    }
    if (code === "RDG") return t("codeTooltip.RDG");
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
  // <select> and position <input> below just read it back, so tap-assignment and manual
  // entry can never drift apart.
  const order = useFinishOrder(race, standings, {
    onChange: (body) => save.mutate({ eventId, raceId: race.id, data: body }),
  });
  const { rows, setField, duplicateBoats } = order;
  const hasDuplicates = duplicateBoats.size > 0;

  return (
    <tr
      data-testid={`matchday-results-row-${race.id}`}
      className={`border-b border-slate-100 align-top last:border-0 ${
        raceRole === "current" ? "bg-brand-50" : ""
      }`}
    >
      <td className="px-3 py-2.5 font-semibold tabular-nums">
        {race.sequence}
        {raceRole && (
          <span
            data-testid={`matchday-results-role-${race.id}`}
            className={`ml-1.5 block text-[10px] font-normal uppercase tracking-wide ${
              raceRole === "current" ? "text-brand-700" : "text-slate-400"
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
              <Tip text={codeTitle(row.code)}>
                <select
                  aria-label={t("codeHeader")}
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
              </Tip>
              <FinishChip
                boat={boat}
                teamName={existing.team.club.short_name}
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
                          ? "border-brand-600 bg-brand-50 text-brand-700"
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
