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
import { useApi, useInvalidieren, useKonto } from "../api/useApi";
import {
  Fehler,
  Laden,
  Leer,
  Seitenkopf,
  StatusMarke,
  TabellenRahmen,
} from "../components/Bausteine";
import { bootsfarbe, ortText, punkte, spieltagUntertitel, zeitraum } from "../lib/format";
import { EINGABE, fehlertext } from "../lib/verwaltung";

/** `races_per_flight = ceil(team_count / boat_count)` — same formula as
 *  `Verwaltung.tsx`'s `events.formatText` (`CLAUDE.md`: "The Event defines the
 *  configuration"). Guarded against `boat_count === 0` while an event is still being set up. */
function racesProFlight(event: Pick<EventSummary, "team_count" | "boat_count">): number {
  return event.boat_count > 0 ? Math.ceil(event.team_count / event.boat_count) : 0;
}

/** Sum of a team's `points_by_race` for the races that belong to one flight, or `null` when
 *  none of that flight's races have a result yet for this team. Keys of `points_by_race` are
 *  JSON object keys (always strings) even though the backend type is `dict[int, float]`. */
function punkteImFlight(zeile: StandingRow, flight: number, proFlight: number): number | null {
  const start = (flight - 1) * proFlight + 1;
  const end = flight * proFlight;
  let summe = 0;
  let vorhanden = false;
  for (const [sequenzText, wert] of Object.entries(zeile.points_by_race)) {
    const sequenz = Number(sequenzText);
    if (sequenz >= start && sequenz <= end) {
      summe += wert;
      vorhanden = true;
    }
  }
  return vorhanden ? summe : null;
}

/** Which flights have at least one recorded result, for *any* team — a flight nobody has
 *  raced in yet gets a plain "–" for everyone, not a grey estimate: an estimate only makes
 *  sense once the flight is actually under way (someone else's race in it already ran). */
function begonneneFlights(standings: StandingRow[], proFlight: number): Set<number> {
  const begonnen = new Set<number>();
  for (const zeile of standings) {
    for (const sequenzText of Object.keys(zeile.points_by_race)) {
      begonnen.add(Math.ceil(Number(sequenzText) / proFlight));
    }
  }
  return begonnen;
}

/** A team's own average points per sailed race — or, before it has sailed anything, the fair
 *  expected value of a single low-point result: the mean of places 1..N is (N+1)/2 (e.g. in a
 *  6-boat race, a still-unraced result is "expected" to be worth 3.5 points). This single
 *  number both fills a not-yet-sailed flight's cell (shown greyed, clearly an estimate, never
 *  a real result) and builds the projected total below — never persisted, purely a display
 *  computation. */
function erwarteterDurchschnitt(zeile: StandingRow, boatCount: number): number {
  return zeile.races_scored > 0 ? zeile.total / zeile.races_scored : (boatCount + 1) / 2;
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
function geschaetzteFlights(
  zeile: StandingRow,
  flights: number[],
  proFlight: number,
  begonnen: Set<number>,
): number[] {
  return flights.filter(
    (flight) => begonnen.has(flight) && punkteImFlight(zeile, flight, proFlight) === null,
  );
}

/** B-2 and B-3: Daily standings and pairing list of a matchday. */
export function Matchday() {
  const { t } = useTranslation("matchday");
  const { id = "" } = useParams();
  const [ansicht, setAnsicht] = useState<"wertung" | "pairing" | "ergebnisse">("wertung");
  const { hatRolle } = useKonto();
  const kannErfassen = hatRolle("admin", "race_officer");

  const spieltag = useApi(["event", id], (signal) => api.event(Number(id), signal));

  if (spieltag.loading) return <Laden text={t("loading")} testId="matchday-loading" />;
  if (spieltag.error) return <Fehler text={spieltag.error} testId="matchday-error" />;
  if (!spieltag.data) return null;

  const { event, standings, races_scored, races_total } = spieltag.data;

  const tabs: Array<["wertung" | "pairing" | "ergebnisse", string]> = [
    ["wertung", t("standingsTab")],
    ["pairing", t("pairingTab")],
  ];
  if (kannErfassen) tabs.push(["ergebnisse", t("resultsTab")]);

  return (
    <>
      <Seitenkopf
        titel={event.title}
        unterzeile={
          <>
            {[
              spieltagUntertitel(event),
              ortText(event),
              zeitraum(event.starts_on, event.ends_on),
            ]
              .filter(Boolean)
              .join(" · ")}
          </>
        }
        testId="matchday-header"
        rechts={<StatusMarke status={event.status} testId="matchday-status-badge" />}
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
            aria-selected={ansicht === value}
            onClick={() => setAnsicht(value)}
            data-testid={`matchday-${value}-tab`}
            className={`rounded-md px-4 py-1.5 text-sm transition-colors ${
              ansicht === value
                ? "bg-marke-600 font-medium text-white"
                : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            {text}
          </button>
        ))}
      </div>

      {ansicht === "wertung" && (
        <DailyStandings standings={standings} event={event} />
      )}
      {ansicht === "pairing" && <PairingList eventId={Number(id)} />}
      {ansicht === "ergebnisse" && kannErfassen && (
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

  if (!standings.length) return <Leer testId="matchday-standings-empty">{t("noResultsYet")}</Leer>;

  const gesegelt = standings.some((zeile) => zeile.races_scored > 0);
  if (!gesegelt) {
    return <Leer testId="matchday-standings-not-sailed">{t("notSailedYet")}</Leer>;
  }

  const proFlight = racesProFlight(event);
  const flights = Array.from({ length: event.flight_count }, (_, i) => i + 1);

  return <StandingsTable standings={standings} event={event} flights={flights} proFlight={proFlight} t={t} />;
}

/** How the one points column reads a team that hasn't sailed every started flight yet.
 *
 *  "exact" shows only what was actually sailed — a flight with no result is a plain dash and
 *  contributes nothing. "extrapolate" fills a flight that is already under way with this
 *  team's expected average, greyed, and counts it in the total. Deliberately a display
 *  toggle over one column rather than two columns side by side: the two numbers answer the
 *  same question ("how does this team stand?") under different assumptions, and showing both
 *  at once invited reading the provisional one as official. */
type PunkteModus = "exact" | "extrapolate";

function StandingsTable({
  standings,
  event,
  flights,
  proFlight,
  t,
}: {
  standings: StandingRow[];
  event: EventSummary;
  flights: number[];
  proFlight: number;
  t: (key: string, options?: Record<string, unknown>) => string;
}) {
  const [modus, setModus] = useState<PunkteModus>("exact");
  const flightsBegonnen = begonneneFlights(standings, proFlight);

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
          {(["exact", "extrapolate"] as const).map((wert) => (
            <button
              key={wert}
              type="button"
              aria-pressed={modus === wert}
              onClick={() => setModus(wert)}
              title={t(wert === "exact" ? "pointsModeExactHint" : "pointsModeExtrapolateHint")}
              data-testid={`matchday-standings-mode-${wert}`}
              className={`px-2 py-1.5 transition-colors ${
                modus === wert
                  ? "bg-marke-600 font-medium text-white"
                  : "bg-white text-slate-600 hover:bg-slate-100"
              }`}
            >
              {t(wert === "exact" ? "pointsModeExact" : "pointsModeExtrapolate")}
            </button>
          ))}
        </div>
      </div>
      <TabellenRahmen testId="matchday-standings-table-frame">
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
              title={modus === "extrapolate" ? t("projectedTooltip") : undefined}
              className="w-32 px-4 py-3 text-right font-medium text-slate-600"
            >
              {modus === "extrapolate" ? t("projectedColumnHeader") : t("pointsHeader")}
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
          {standings.map((zeile) => {
            const durchschnitt = erwarteterDurchschnitt(zeile, event.boat_count);
            const geschaetzt = geschaetzteFlights(zeile, flights, proFlight, flightsBegonnen);
            // The projected total is exactly the row's own cells added up: real flight sums
            // plus one expected average per greyed cell. Nothing is added that isn't shown.
            const hochgerechnet = zeile.total + geschaetzt.length * durchschnitt;
            return (
              <tr
                key={zeile.team.id}
                data-testid={`matchday-standings-row-${zeile.team.id}`}
                className="border-b border-slate-100 last:border-0 hover:bg-slate-50"
              >
                <td className="px-4 py-3 font-semibold tabular-nums">{zeile.rank}</td>
                <td className="px-4 py-3">
                  <Link
                    to={`/clubs/${zeile.team.club.id}`}
                    data-testid={`matchday-standings-club-link-${zeile.team.id}`}
                    className="font-medium underline-offset-2 hover:underline"
                  >
                    {zeile.team.club.name}
                  </Link>
                </td>
                {modus === "extrapolate" ? (
                  <td
                    title={t("projectedTooltip")}
                    data-testid={`matchday-standings-projected-${zeile.team.id}`}
                    className="px-4 py-3 text-right font-semibold italic tabular-nums text-slate-700"
                  >
                    {punkte(hochgerechnet)}
                  </td>
                ) : (
                  <td
                    data-testid={`matchday-standings-points-${zeile.team.id}`}
                    className="px-4 py-3 text-right font-semibold tabular-nums"
                  >
                    {punkte(zeile.net)}
                    {zeile.net !== zeile.total && (
                      <span className="ml-1 text-xs font-normal text-slate-400">
                        ({punkte(zeile.total)} {t("gross")})
                      </span>
                    )}
                  </td>
                )}
                <td className="px-4 py-3 text-right tabular-nums text-slate-500">
                  {zeile.races_scored}
                </td>
                {flights.map((flight) => {
                  const wert = punkteImFlight(zeile, flight, proFlight);
                  if (wert != null) {
                    return (
                      <td key={flight} className="px-2 py-3 text-right tabular-nums text-slate-500">
                        {punkte(wert)}
                      </td>
                    );
                  }
                  // In "exact" mode an unsailed flight is always a plain dash. In
                  // "extrapolate" it carries the expected average — but only where the flight
                  // is already under way, i.e. someone has a result in it. A flight nobody
                  // has reached yet is never estimated, even mid-matchday.
                  if (modus === "exact" || !geschaetzt.includes(flight)) {
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
                      data-testid={`matchday-standings-flight-projected-${zeile.team.id}-${flight}`}
                      className="px-2 py-3 text-right italic tabular-nums text-slate-400"
                    >
                      {punkte(durchschnitt)}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
      </TabellenRahmen>
    </>
  );
}

function PairingList({ eventId }: { eventId: number }) {
  const { t } = useTranslation("matchday");
  const { data, error, loading } = useApi(["pairing", eventId], (signal) =>
    api.pairing(eventId, signal),
  );

  if (loading) return <Laden text={t("pairingLoading")} testId="matchday-pairing-loading" />;
  if (error) return <Fehler text={error} testId="matchday-pairing-error" />;
  if (!data?.races.length) return <Leer testId="matchday-pairing-empty">{t("noRacesDrawn")}</Leer>;

  return (
    <>
      <TabellenRahmen testId="matchday-pairing-table-frame">
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
              {data.boats.map((boot) => {
                const farbe = bootsfarbe(boot.color);
                return (
                  <th key={boot.number} scope="col" className="px-3 py-3 font-medium">
                    <span className="flex items-center gap-1.5">
                      <span
                        aria-hidden
                        className="size-3 shrink-0 rounded-full ring-1 ring-slate-300"
                        style={{ backgroundColor: farbe.hex }}
                      />
                      <span className="text-slate-600">{farbe.name}</span>
                    </span>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {data.races.map((wettfahrt) => (
              <tr
                key={wettfahrt.sequence}
                data-testid={`matchday-pairing-row-${wettfahrt.sequence}`}
                className="border-b border-slate-100 last:border-0 hover:bg-slate-50"
              >
                <td className="px-3 py-2.5 font-semibold tabular-nums">{wettfahrt.sequence}</td>
                <td className="px-3 py-2.5 tabular-nums text-slate-500">{wettfahrt.flight}</td>
                {data.boats.map((boot) => (
                  <td key={boot.number} className="px-3 py-2.5">
                    {wettfahrt.teams_by_boat[String(boot.number)]?.club.short_name ?? "–"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </TabellenRahmen>
    </>
  );
}

// ---------------------------------------------------------------- Story WL-2: results

/** Every code except FINISHED — that one is picked as a finish position number directly in
 *  the merged dropdown (see `RaceResultRow`), not as its own entry in this list. */
const SPEZIAL_CODES = ["DNS", "DNF", "OCS", "DSQ", "DNE", "RET", "RDG", "ZFP", "SCP"] as const;

function brauchtPlatz(code: string): boolean {
  return code === "FINISHED" || code === "ZFP" || code === "SCP";
}

/** Only ZFP/SCP still need their own position input — FINISHED's position comes directly
 *  from picking a number in the merged dropdown, so showing a second input for it would just
 *  be two controls for the same value. */
function brauchtEigeneEingabe(code: string): boolean {
  return code === "ZFP" || code === "SCP";
}

/** Whether this row already carries a complete result: a finish position for
 *  FINISHED/ZFP/SCP, redress points for RDG, or — for the rest — simply having chosen the
 *  code at all. Drives the tap icon's in-progress/done flip: a boat that hasn't finished this
 *  race yet still reads "in progress" even once other boats in the same race already have a
 *  result recorded. */
function ergebnisVollstaendig(zeile: EingabeZeile): boolean {
  if (brauchtPlatz(zeile.code)) return zeile.finish_position != null;
  if (zeile.code === "RDG") return zeile.redress_points != null;
  return true;
}

/** The tap fast-path only ever assigns/undoes a *FINISHED* position — once a special code has
 *  been chosen via the dropdown, tapping the icon would silently overwrite it back to a
 *  numbered finish, so it's disabled (still shown, just not clickable) for those rows. */
function kannGetipptWerden(zeile: EingabeZeile): boolean {
  return zeile.code === "FINISHED";
}

/** `DID_NOT_FINISH_CODES` in `api/app/scoring/low_point.py`: all scored identically —
 *  starters + 1 points, worse than finishing last. Frontend copy of that fact for the
 *  tooltip text; the backend file is the source of truth and isn't touched here. */
const NICHT_BEENDET_CODES = new Set(["DNS", "DNF", "OCS", "DSQ", "DNE", "RET"]);

/** RRS Appendix A10: nearest tenth, 0.05 rounds up — `Math.round` already rounds half away
 *  from zero for these non-negative point values, so this is exact for the RDG suggestion. */
function rundeAufZehntel(wert: number): number {
  return Math.round(wert * 10) / 10;
}

/** RRS A10's suggested redress convention: the average of the team's points in this event's
 *  other already-scored races (this race's own sequence excluded). A suggestion the race
 *  officer can override, not something the app enforces — A10 allows alternatives too. */
function redressVorschlag(
  teamId: number,
  ausgeschlosseneSequenz: number,
  standings: StandingRow[],
): number | null {
  const zeile = standings.find((z) => z.team.id === teamId);
  if (!zeile) return null;
  const werte = Object.entries(zeile.points_by_race)
    .filter(([sequenzText]) => Number(sequenzText) !== ausgeschlosseneSequenz)
    .map(([, wert]) => wert);
  if (!werte.length) return null;
  return rundeAufZehntel(werte.reduce((summe, wert) => summe + wert, 0) / werte.length);
}

/** Only `admin`/`race_officer` can reach this (gated in `Matchday`) — the race committee's
 *  entry screen: the same pairing grid as the "pairing" tab, but editable and including
 *  unfinished races. A row PUTs its whole race on save; results are the raw
 *  `code`/`finish_position`/`redress_points` — `points` are always derived
 *  (`app/services/standings.py`), never entered here.
 */
/** A race not yet finished (or abandoned) — races run strictly one at a time in sequence,
 *  so at most one race in the whole matchday is ever actually "open" at once. */
function nochOffen(race: AdminRace): boolean {
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
  const [alleAnzeigen, setAlleAnzeigen] = useState(false);

  if (loading) return <Laden text={t("resultsLoading")} testId="matchday-results-loading" />;
  if (error) return <Fehler text={error} testId="matchday-results-error" />;
  if (!data?.races.length) return <Leer testId="matchday-results-empty">{t("noRacesDrawn")}</Leer>;

  // Captured as its own const so TS keeps `races` narrowed to non-null inside the closures
  // below — narrowing on `data` itself doesn't survive into a nested function body.
  const races = data.races;

  // Everything before the first still-open race is already finished, everything after it
  // can't have started yet — so there's never more than one "current" race, one "previous"
  // (just finished) and one "next" (drawn but not run) worth focusing on at a time. Default
  // to that neighborhood instead of all 48 rows; "show all" stays available for correcting
  // an older result later (a protest decision isn't limited to the most recent race).
  const aktuellerIndex = races.findIndex(nochOffen);
  const angezeigt = alleAnzeigen
    ? races
    : aktuellerIndex === -1
      ? races.slice(-3)
      : races.slice(Math.max(0, aktuellerIndex - 1), aktuellerIndex + 2);

  function rolle(race: AdminRace): "previous" | "current" | "next" | null {
    if (alleAnzeigen) return null;
    const index = races.indexOf(race);
    if (aktuellerIndex === -1) return null;
    if (index === aktuellerIndex) return "current";
    if (index === aktuellerIndex - 1) return "previous";
    if (index === aktuellerIndex + 1) return "next";
    return null;
  }

  return (
    <>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-slate-600" data-testid="matchday-results-focus-hint">
          {alleAnzeigen ? t("resultsAllHint") : t("resultsFocusHint")}
        </p>
        <button
          type="button"
          onClick={() => setAlleAnzeigen((vorher) => !vorher)}
          data-testid="matchday-results-show-all-toggle"
          className="text-sm font-medium text-marke-700 underline-offset-2 hover:underline"
        >
          {alleAnzeigen ? t("resultsShowFocused") : t("resultsShowAll")}
        </button>
      </div>
      <TabellenRahmen testId="matchday-results-table-frame">
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
              {data.boats.map((boot) => {
                const farbe = bootsfarbe(boot.color);
                return (
                  <th key={boot.number} scope="col" className="px-3 py-3 font-medium">
                    <span className="flex items-center gap-1.5">
                      <span
                        aria-hidden
                        className="size-3 shrink-0 rounded-full ring-1 ring-slate-300"
                        style={{ backgroundColor: farbe.hex }}
                      />
                      <span className="text-slate-600">{farbe.name}</span>
                    </span>
                  </th>
                );
              })}
              <th scope="col" className="w-28 px-3 py-3 font-medium text-slate-600" />
            </tr>
          </thead>
          <tbody>
            {angezeigt.map((race) => (
              // Keyed on the version too: after a save, the row re-mounts with the fresh
              // server state instead of quietly keeping the pre-save form values.
              <RaceResultRow
                key={`${race.id}-${race.version}`}
                race={race}
                boats={data.boats}
                eventId={eventId}
                eventIdParam={eventIdParam}
                standings={standings}
                rolle={rolle(race)}
              />
            ))}
          </tbody>
        </table>
      </TabellenRahmen>
    </>
  );
}

interface EingabeZeile {
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
function naechsteFreiePosition(zeilen: Record<number, EingabeZeile>): number {
  const belegt = new Set(
    Object.values(zeilen)
      .filter((zeile) => zeile.code === "FINISHED" && zeile.finish_position != null)
      .map((zeile) => zeile.finish_position as number),
  );
  let position = 1;
  while (belegt.has(position)) position += 1;
  return position;
}

function RaceResultRow({
  race,
  boats,
  eventId,
  eventIdParam,
  standings,
  rolle,
}: {
  race: AdminRace;
  boats: BoatOut[];
  eventId: number;
  eventIdParam: string;
  standings: StandingRow[];
  rolle: "previous" | "current" | "next" | null;
}) {
  const { t } = useTranslation("matchday");
  const invalidieren = useInvalidieren();
  const byBoat = new Map(race.entries.map((eintrag) => [eintrag.boat_number, eintrag]));

  // RRS A9: the DNF family scores as starters + 1; ZFP/SCP add a 20%-of-starters penalty
  // capped at that value. `race.entries.length` is this race's starter count.
  const starter = race.entries.length;
  const dnfPunkte = starter + 1;
  const zfpStrafe = Math.max(1, Math.round(starter * 0.2));

  function codeTitel(code: string): string {
    if (code === "FINISHED") return t("codeTooltip.FINISHED");
    if (NICHT_BEENDET_CODES.has(code)) return t(`codeTooltip.${code}`, { points: dnfPunkte });
    if (code === "ZFP" || code === "SCP") {
      return t(`codeTooltip.${code}`, { cap: dnfPunkte, penalty: zfpStrafe });
    }
    if (code === "RDG") return t("codeTooltip.RDG");
    return code;
  }

  const [zeilen, setZeilen] = useState<Record<number, EingabeZeile>>(() =>
    Object.fromEntries(
      race.entries.map((eintrag) => {
        const code = eintrag.code ?? "FINISHED";
        const redress_points = eintrag.redress_points ?? null;
        // No backend field says whether a stored RDG value was the auto-average or a jury's
        // own figure — guess "auto" when it still matches today's average, "fixed" otherwise
        // (e.g. the average has since shifted, or it never matched to begin with).
        let redress_mode: "auto" | "fixed" = "auto";
        if (code === "RDG" && redress_points != null) {
          const vorschlag = redressVorschlag(eintrag.team.id, race.sequence, standings);
          redress_mode = vorschlag != null && Math.abs(vorschlag - redress_points) < 0.05 ? "auto" : "fixed";
        }
        return [
          eintrag.boat_number,
          {
            boat_number: eintrag.boat_number,
            code,
            finish_position: eintrag.finish_position ?? null,
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
  function effektiverRedressWert(zeile: EingabeZeile): number | null {
    if (zeile.code !== "RDG") return null;
    if (zeile.redress_mode === "fixed") return zeile.redress_points;
    const teamId = byBoat.get(zeile.boat_number)?.team.id;
    if (teamId == null) return zeile.redress_points;
    return redressVorschlag(teamId, race.sequence, standings) ?? zeile.redress_points;
  }

  // No Save button: every change writes straight through to the backend (still guarded by
  // the same duplicate check that used to just disable Save — an in-progress duplicate
  // simply doesn't save yet, rather than blocking a click that no longer exists).
  const speichern = useMutation({
    mutationFn: (naechsteZeilen: Record<number, EingabeZeile>) =>
      api.admin.setRaceResult(eventId, race.id, {
        results: Object.values(naechsteZeilen).map((zeile) => ({
          boat_number: zeile.boat_number,
          code: zeile.code,
          finish_position: brauchtPlatz(zeile.code) ? zeile.finish_position : null,
          redress_points: effektiverRedressWert(zeile),
        })),
      }),
    onSuccess: () => {
      invalidieren(["admin", "races", eventId], ["event", eventIdParam]);
    },
  });

  function duplikateIn(kandidat: Record<number, EingabeZeile>): Set<number> {
    const positionsAnzahl = new Map<number, number>();
    for (const zeile of Object.values(kandidat)) {
      if (brauchtPlatz(zeile.code) && zeile.finish_position != null) {
        positionsAnzahl.set(zeile.finish_position, (positionsAnzahl.get(zeile.finish_position) ?? 0) + 1);
      }
    }
    return new Set(
      Object.values(kandidat)
        .filter(
          (zeile) =>
            brauchtPlatz(zeile.code) &&
            zeile.finish_position != null &&
            (positionsAnzahl.get(zeile.finish_position) ?? 0) > 1,
        )
        .map((zeile) => zeile.boat_number),
    );
  }

  function anwenden(naechsteZeilen: Record<number, EingabeZeile>) {
    setZeilen(naechsteZeilen);
    if (duplikateIn(naechsteZeilen).size === 0) {
      speichern.mutate(naechsteZeilen);
    }
  }

  const setzeFeld = (boatNumber: number, patch: Partial<EingabeZeile>) =>
    anwenden({ ...zeilen, [boatNumber]: { ...zeilen[boatNumber], ...patch } });

  // Fast path (Story WL-2): tapping a boat assigns it FINISHED + the next unused finish
  // position; tapping an already-assigned boat undoes just that one. `zeilen` stays the
  // single source of truth — the <select> and position <input> below just read it back, so
  // tap-assignment and manual entry can never drift apart.
  function tippen(boatNumber: number) {
    const zeile = zeilen[boatNumber];
    const naechsteZeile =
      zeile.code === "FINISHED" && zeile.finish_position != null
        ? { ...zeile, finish_position: null }
        : { ...zeile, code: "FINISHED", finish_position: naechsteFreiePosition(zeilen) };
    anwenden({ ...zeilen, [boatNumber]: naechsteZeile });
  }

  const duplikatBoote = duplikateIn(zeilen);
  const hatDuplikate = duplikatBoote.size > 0;

  return (
    <tr
      data-testid={`matchday-results-row-${race.id}`}
      className={`border-b border-slate-100 align-top last:border-0 ${
        rolle === "current" ? "bg-marke-50" : ""
      }`}
    >
      <td className="px-3 py-2.5 font-semibold tabular-nums">
        {race.sequence}
        {rolle && (
          <span
            data-testid={`matchday-results-role-${race.id}`}
            className={`ml-1.5 block text-[10px] font-normal uppercase tracking-wide ${
              rolle === "current" ? "text-marke-700" : "text-slate-400"
            }`}
          >
            {t(`raceRole.${rolle}`)}
          </span>
        )}
      </td>
      <td className="px-3 py-2.5 tabular-nums text-slate-500">{race.flight}</td>
      {boats.map((boot) => {
        const bestehend = byBoat.get(boot.number);
        const zeile = zeilen[boot.number];
        if (!bestehend || !zeile) {
          return (
            <td key={boot.number} className="px-3 py-2.5 text-slate-400">
              –
            </td>
          );
        }
        const farbe = bootsfarbe(boot.color);
        const vollstaendig = ergebnisVollstaendig(zeile);
        const tippbar = kannGetipptWerden(zeile);
        const vorschlag =
          zeile.code === "RDG" ? redressVorschlag(bestehend.team.id, race.sequence, standings) : null;
        // The merged dropdown's own value: a finish position shows as its number, every
        // other code shows as itself, and "FINISHED with nothing picked yet" shows as the
        // empty placeholder rather than a bare "FINISHED" that isn't a real option anymore.
        const auswahlWert =
          zeile.code === "FINISHED"
            ? zeile.finish_position != null
              ? String(zeile.finish_position)
              : ""
            : zeile.code;
        return (
          <td key={boot.number} className="min-w-[9.5rem] px-3 py-2.5">
            <div className="mb-1 flex items-center gap-1.5 truncate text-xs font-medium text-slate-600">
              <span
                aria-hidden
                className="size-2.5 shrink-0 rounded-full ring-1 ring-slate-300"
                style={{ backgroundColor: farbe.hex }}
              />
              <span className="truncate">{bestehend.team.club.short_name}</span>
            </div>
            {bestehend.is_discarded && (
              <div className="mb-1 text-[11px] text-slate-400">{t("discardedNote")}</div>
            )}
            <div className="flex items-center gap-1.5">
              <select
                aria-label={t("codeHeader")}
                title={codeTitel(zeile.code)}
                className={`${EINGABE} flex-1 ${
                  duplikatBoote.has(boot.number) ? "border-red-500 ring-2 ring-red-200" : ""
                }`}
                value={auswahlWert}
                aria-invalid={duplikatBoote.has(boot.number)}
                onChange={(e) => {
                  const neuerWert = e.target.value;
                  const alsPosition = Number(neuerWert);
                  if (neuerWert !== "" && Number.isInteger(alsPosition) && alsPosition > 0) {
                    setzeFeld(boot.number, { code: "FINISHED", finish_position: alsPosition });
                    return;
                  }
                  if (neuerWert === "RDG") {
                    const vorschlagBeiUmschaltung = redressVorschlag(
                      bestehend.team.id,
                      race.sequence,
                      standings,
                    );
                    setzeFeld(boot.number, {
                      code: neuerWert,
                      // Most redress cases are the plain A10 average — default to "auto"
                      // whenever one can actually be computed, "fixed" only when there's
                      // nothing yet to average (this team hasn't scored another race).
                      redress_mode: vorschlagBeiUmschaltung != null ? "auto" : "fixed",
                      redress_points: vorschlagBeiUmschaltung,
                    });
                    return;
                  }
                  setzeFeld(boot.number, { code: neuerWert });
                }}
                data-testid={`matchday-results-code-select-${race.id}-${boot.number}`}
              >
                <option value="" disabled hidden>
                  {t("resultPlaceholder")}
                </option>
                {Array.from({ length: starter }, (_, i) => i + 1).map((position) => (
                  <option key={position} value={position} title={codeTitel("FINISHED")}>
                    {position}
                  </option>
                ))}
                {SPEZIAL_CODES.map((code) => (
                  <option key={code} value={code} title={codeTitel(code)}>
                    {code}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => tippbar && tippen(boot.number)}
                disabled={!tippbar}
                aria-pressed={tippbar ? vollstaendig : undefined}
                title={
                  !tippbar
                    ? t("tapLockedLabel", { code: zeile.code })
                    : vollstaendig
                      ? t("tapUndoLabel", { position: zeile.finish_position })
                      : t("tapInProgressLabel", { boat: farbe.name })
                }
                data-testid={`matchday-results-tap-${race.id}-${boot.number}`}
                className={`flex size-9 shrink-0 items-center justify-center rounded-md border border-transparent text-base text-white shadow-sm transition ${
                  tippbar ? "hover:brightness-110" : "cursor-default opacity-90"
                }`}
                style={{ backgroundColor: farbe.hex }}
              >
                <span aria-hidden className="[text-shadow:0_1px_2px_rgb(0_0_0_/_55%)]">
                  {vollstaendig ? "🏁" : "⏳"}
                </span>
              </button>
            </div>
            {brauchtEigeneEingabe(zeile.code) && (
              <input
                type="number"
                min={1}
                className={`${EINGABE} mt-1 ${
                  duplikatBoote.has(boot.number) ? "border-red-500 ring-2 ring-red-200" : ""
                }`}
                value={zeile.finish_position ?? ""}
                placeholder={t("positionPlaceholder")}
                aria-invalid={duplikatBoote.has(boot.number)}
                onChange={(e) =>
                  setzeFeld(boot.number, {
                    finish_position: e.target.value ? Number(e.target.value) : null,
                  })
                }
                data-testid={`matchday-results-position-input-${race.id}-${boot.number}`}
              />
            )}
            {zeile.code === "RDG" && (
              <div className="mt-1 space-y-1">
                <div className="flex gap-1" role="group" aria-label={t("redressModeLabel")}>
                  {(["auto", "fixed"] as const).map((modus) => (
                    <button
                      key={modus}
                      type="button"
                      onClick={() =>
                        setzeFeld(boot.number, {
                          redress_mode: modus,
                          // Switching to "auto" snaps the value to today's average right
                          // away; switching to "fixed" just unlocks the field and keeps
                          // whatever number is currently showing as the starting point.
                          redress_points: modus === "auto" ? vorschlag : zeile.redress_points,
                        })
                      }
                      aria-pressed={zeile.redress_mode === modus}
                      data-testid={`matchday-results-redress-mode-${modus}-${race.id}-${boot.number}`}
                      className={`flex-1 rounded-md border px-1.5 py-1 text-[11px] font-medium transition ${
                        zeile.redress_mode === modus
                          ? "border-marke-600 bg-marke-50 text-marke-700"
                          : "border-slate-300 text-slate-500 hover:bg-slate-50"
                      }`}
                    >
                      {t(`redress${modus === "auto" ? "Auto" : "Fixed"}Label`)}
                    </button>
                  ))}
                </div>
                {zeile.redress_mode === "auto" ? (
                  <p
                    className="text-[11px] italic text-slate-500"
                    data-testid={`matchday-results-redress-auto-value-${race.id}-${boot.number}`}
                  >
                    {vorschlag != null
                      ? t("redressAutoValue", { value: punkte(vorschlag) })
                      : t("redressAutoUnavailable")}
                  </p>
                ) : (
                  <input
                    type="number"
                    step="0.1"
                    className={EINGABE}
                    value={zeile.redress_points ?? ""}
                    placeholder={t("redressPlaceholder")}
                    onChange={(e) =>
                      setzeFeld(boot.number, {
                        redress_points: e.target.value ? Number(e.target.value) : null,
                      })
                    }
                    data-testid={`matchday-results-redress-input-${race.id}-${boot.number}`}
                  />
                )}
              </div>
            )}
          </td>
        );
      })}
      <td className="px-3 py-2.5">
        {hatDuplikate && (
          <p
            role="alert"
            data-testid={`matchday-results-duplicate-warning-${race.id}`}
            className="mb-1 text-xs text-red-700"
          >
            {t("duplicatePositionWarning")}
          </p>
        )}
        {!hatDuplikate && speichern.isPending && (
          <p className="text-xs text-slate-400" data-testid={`matchday-results-save-message-${race.id}`}>
            {t("savingButton")}
          </p>
        )}
        {!hatDuplikate && speichern.isError && (
          <Fehler text={fehlertext(speichern.error)} testId={`matchday-results-save-message-${race.id}`} />
        )}
      </td>
    </tr>
  );
}
