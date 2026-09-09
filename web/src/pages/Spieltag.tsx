import { Button } from "@heroui/react";
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
import { Meldung } from "./verwaltungBausteine";

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

/** Average gross points per sailed race across every team that has sailed at least one race —
 *  the fallback for a team that itself hasn't sailed yet, so it still gets a sensible
 *  projection instead of none. */
function durchschnittProWettfahrtGesamt(standings: StandingRow[]): number {
  let punkteSumme = 0;
  let wettfahrtenSumme = 0;
  for (const zeile of standings) {
    if (zeile.races_scored > 0) {
      punkteSumme += zeile.total;
      wettfahrtenSumme += zeile.races_scored;
    }
  }
  return wettfahrtenSumme > 0 ? punkteSumme / wettfahrtenSumme : 0;
}

/** Provisional final total: gross so far, plus the team's own (or, failing that, the
 *  event-wide) average points per race, extrapolated over the still-unsailed flights.
 *  Purely a display computation — never persisted, never used for `rank`. */
function projizierterGesamtwert(
  zeile: StandingRow,
  flightCount: number,
  durchschnittGesamt: number,
): number {
  const verbleibend = Math.max(0, flightCount - zeile.races_scored);
  const durchschnitt = zeile.races_scored > 0 ? zeile.total / zeile.races_scored : durchschnittGesamt;
  return zeile.total + durchschnitt * verbleibend;
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
        <DailyStandings standings={standings} event={event} racesScored={races_scored} />
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
  racesScored,
}: {
  standings: StandingRow[];
  event: EventSummary;
  racesScored: number;
}) {
  const { t } = useTranslation("matchday");

  if (!standings.length) return <Leer testId="matchday-standings-empty">{t("noResultsYet")}</Leer>;

  const gesegelt = standings.some((zeile) => zeile.races_scored > 0);
  if (!gesegelt) {
    return <Leer testId="matchday-standings-not-sailed">{t("notSailedYet")}</Leer>;
  }

  const proFlight = racesProFlight(event);
  const flights = Array.from({ length: event.flight_count }, (_, i) => i + 1);
  // B-2: "a running matchday shows an interim standing" — once anything has been sailed
  // anywhere in the event, a team with 0 races so far would otherwise show net=0 and look
  // like it's winning outright. The projected total makes that provisional, never the sort.
  const zeigeProjektion = racesScored > 0;
  const durchschnittGesamt = zeigeProjektion ? durchschnittProWettfahrtGesamt(standings) : 0;

  return (
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
            <th scope="col" className="w-32 px-4 py-3 text-right font-medium text-slate-600">
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
          {standings.map((zeile) => {
            const projektion = zeigeProjektion
              ? projizierterGesamtwert(zeile, event.flight_count, durchschnittGesamt)
              : null;
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
                <td className="px-4 py-3 text-right font-semibold tabular-nums">
                  {punkte(zeile.net)}
                  {zeile.net !== zeile.total && (
                    <span className="ml-1 text-xs font-normal text-slate-400">
                      ({punkte(zeile.total)} {t("gross")})
                    </span>
                  )}
                  {projektion != null && (
                    <span
                      title={t("projectedTooltip")}
                      data-testid={`matchday-standings-projected-${zeile.team.id}`}
                      className="ml-1.5 block text-xs font-normal italic text-slate-400"
                    >
                      {t("projectedLabel", { value: punkte(projektion) })}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-slate-500">
                  {zeile.races_scored}
                </td>
                {flights.map((flight) => {
                  const wert = punkteImFlight(zeile, flight, proFlight);
                  return (
                    <td
                      key={flight}
                      className="px-2 py-3 text-right tabular-nums text-slate-500"
                    >
                      {wert == null ? "–" : punkte(wert)}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </TabellenRahmen>
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

/** RRS Appendix A scoring codes, in the order they're most often needed. */
const RESULT_CODES = [
  "FINISHED",
  "DNS",
  "DNF",
  "OCS",
  "DSQ",
  "DNE",
  "RDG",
  "ZFP",
  "SCP",
  "RET",
] as const;

function brauchtPlatz(code: string): boolean {
  return code === "FINISHED" || code === "ZFP" || code === "SCP";
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

  if (loading) return <Laden text={t("resultsLoading")} testId="matchday-results-loading" />;
  if (error) return <Fehler text={error} testId="matchday-results-error" />;
  if (!data?.races.length) return <Leer testId="matchday-results-empty">{t("noRacesDrawn")}</Leer>;

  return (
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
          {data.races.map((race) => (
            // Keyed on the version too: after a save, the row re-mounts with the fresh
            // server state instead of quietly keeping the pre-save form values.
            <RaceResultRow
              key={`${race.id}-${race.version}`}
              race={race}
              boats={data.boats}
              eventId={eventId}
              eventIdParam={eventIdParam}
              standings={standings}
            />
          ))}
        </tbody>
      </table>
    </TabellenRahmen>
  );
}

interface EingabeZeile {
  boat_number: number;
  code: string;
  finish_position: number | null;
  redress_points: number | null;
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
}: {
  race: AdminRace;
  boats: BoatOut[];
  eventId: number;
  eventIdParam: string;
  standings: StandingRow[];
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
      race.entries.map((eintrag) => [
        eintrag.boat_number,
        {
          boat_number: eintrag.boat_number,
          code: eintrag.code ?? "FINISHED",
          finish_position: eintrag.finish_position ?? null,
          redress_points: eintrag.redress_points ?? null,
        },
      ]),
    ),
  );

  const speichern = useMutation({
    mutationFn: () =>
      api.admin.setRaceResult(eventId, race.id, {
        results: Object.values(zeilen).map((zeile) => ({
          boat_number: zeile.boat_number,
          code: zeile.code,
          finish_position: brauchtPlatz(zeile.code) ? zeile.finish_position : null,
          redress_points: zeile.code === "RDG" ? zeile.redress_points : null,
        })),
      }),
    onSuccess: () => {
      invalidieren(["admin", "races", eventId], ["event", eventIdParam]);
    },
  });

  const setzeFeld = (boatNumber: number, patch: Partial<EingabeZeile>) =>
    setZeilen((vorher) => ({
      ...vorher,
      [boatNumber]: { ...vorher[boatNumber], ...patch },
    }));

  // Fast path (Story WL-2): tapping a boat assigns it FINISHED + the next unused finish
  // position; tapping an already-assigned boat undoes just that one. `zeilen` stays the
  // single source of truth — the <select> and position <input> below just read it back, so
  // tap-assignment and manual entry can never drift apart.
  const tippen = (boatNumber: number) =>
    setZeilen((vorher) => {
      const zeile = vorher[boatNumber];
      if (zeile.code === "FINISHED" && zeile.finish_position != null) {
        return { ...vorher, [boatNumber]: { ...zeile, finish_position: null } };
      }
      return {
        ...vorher,
        [boatNumber]: {
          ...zeile,
          code: "FINISHED",
          finish_position: naechsteFreiePosition(vorher),
        },
      };
    });

  const alleZuruecksetzen = () =>
    setZeilen((vorher) =>
      Object.fromEntries(
        Object.entries(vorher).map(([nummer, zeile]) => [
          nummer,
          zeile.code === "FINISHED" ? { ...zeile, finish_position: null } : zeile,
        ]),
      ),
    );

  // Client-side duplicate check (tap-assignment can't produce one by construction — only
  // manual position entry can): flags every boat sharing a position so Save is blocked
  // before the round trip to the typed `/errors/race-result-duplicate-position` response.
  const positionsAnzahl = new Map<number, number>();
  for (const zeile of Object.values(zeilen)) {
    if (brauchtPlatz(zeile.code) && zeile.finish_position != null) {
      positionsAnzahl.set(zeile.finish_position, (positionsAnzahl.get(zeile.finish_position) ?? 0) + 1);
    }
  }
  const duplikatBoote = new Set(
    Object.values(zeilen)
      .filter(
        (zeile) =>
          brauchtPlatz(zeile.code) &&
          zeile.finish_position != null &&
          (positionsAnzahl.get(zeile.finish_position) ?? 0) > 1,
      )
      .map((zeile) => zeile.boat_number),
  );
  const hatDuplikate = duplikatBoote.size > 0;

  return (
    <tr data-testid={`matchday-results-row-${race.id}`} className="border-b border-slate-100 align-top last:border-0">
      <td className="px-3 py-2.5 font-semibold tabular-nums">{race.sequence}</td>
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
        const zugewiesen = zeile.code === "FINISHED" && zeile.finish_position != null;
        const vorschlag =
          zeile.code === "RDG" ? redressVorschlag(bestehend.team.id, race.sequence, standings) : null;
        return (
          <td key={boot.number} className="min-w-[9.5rem] px-3 py-2.5">
            <div className="mb-1 truncate text-xs font-medium text-slate-600">
              {bestehend.team.club.short_name}
            </div>
            {bestehend.points != null && (
              <div className="mb-1 text-[11px] text-slate-400">
                {t("currentResultNote", { points: punkte(bestehend.points) })}
                {bestehend.is_discarded && ` (${t("discardedNote")})`}
              </div>
            )}
            <button
              type="button"
              onClick={() => tippen(boot.number)}
              aria-pressed={zugewiesen}
              title={
                zugewiesen
                  ? t("tapUndoLabel", { position: zeile.finish_position })
                  : t("tapAssignLabel", { boat: farbe.name })
              }
              data-testid={`matchday-results-tap-${race.id}-${boot.number}`}
              className="mb-1.5 flex w-full items-center justify-between gap-2 rounded-md px-2.5 py-1.5 text-xs font-semibold text-white shadow-sm transition hover:brightness-110"
              style={{ backgroundColor: farbe.hex }}
            >
              <span className="truncate">{farbe.name}</span>
              {zugewiesen ? (
                <span
                  data-testid={`matchday-results-tap-badge-${race.id}-${boot.number}`}
                  className="flex size-5 shrink-0 items-center justify-center rounded-full bg-white text-[11px] font-bold text-slate-900"
                >
                  {zeile.finish_position}
                </span>
              ) : (
                <span aria-hidden className="shrink-0 text-[10px] font-normal text-white/80">
                  {t("tapChipHint")}
                </span>
              )}
            </button>
            <select
              aria-label={t("codeHeader")}
              title={codeTitel(zeile.code)}
              className={EINGABE}
              value={zeile.code}
              onChange={(e) => {
                const neuerCode = e.target.value;
                if (neuerCode === "RDG" && zeile.redress_points == null) {
                  setzeFeld(boot.number, {
                    code: neuerCode,
                    redress_points: redressVorschlag(bestehend.team.id, race.sequence, standings),
                  });
                } else {
                  setzeFeld(boot.number, { code: neuerCode });
                }
              }}
              data-testid={`matchday-results-code-select-${race.id}-${boot.number}`}
            >
              {RESULT_CODES.map((code) => (
                <option key={code} value={code} title={codeTitel(code)}>
                  {code}
                </option>
              ))}
            </select>
            {brauchtPlatz(zeile.code) && (
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
              <>
                <input
                  type="number"
                  step="0.1"
                  className={`${EINGABE} mt-1`}
                  value={zeile.redress_points ?? ""}
                  placeholder={t("redressPlaceholder")}
                  onChange={(e) =>
                    setzeFeld(boot.number, {
                      redress_points: e.target.value ? Number(e.target.value) : null,
                    })
                  }
                  data-testid={`matchday-results-redress-input-${race.id}-${boot.number}`}
                />
                {vorschlag != null && (
                  <p className="mt-0.5 text-[11px] italic text-slate-400">
                    {t("redressSuggested", { value: punkte(vorschlag) })}
                  </p>
                )}
              </>
            )}
          </td>
        );
      })}
      <td className="px-3 py-2.5">
        <div className="flex flex-wrap gap-1.5">
          <Button
            size="sm"
            onPress={() => speichern.mutate()}
            isDisabled={speichern.isPending || hatDuplikate}
            data-testid={`matchday-results-save-button-${race.id}`}
          >
            {speichern.isPending ? t("savingButton") : t("saveButton")}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onPress={alleZuruecksetzen}
            data-testid={`matchday-results-reset-button-${race.id}`}
          >
            {t("resetRaceButton")}
          </Button>
        </div>
        <div className="mt-1">
          {hatDuplikate && (
            <p
              role="alert"
              data-testid={`matchday-results-duplicate-warning-${race.id}`}
              className="mb-1 text-xs text-red-700"
            >
              {t("duplicatePositionWarning")}
            </p>
          )}
          <Meldung
            testId={`matchday-results-save-message-${race.id}`}
            fehler={speichern.isError ? fehlertext(speichern.error) : null}
            erfolg={speichern.isSuccess ? t("savedMessage") : null}
          />
        </div>
      </td>
    </tr>
  );
}
