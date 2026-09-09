import { Button } from "@heroui/react";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import {
  api,
  type AdminRace,
  type BoatOut,
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

      {ansicht === "wertung" && <DailyStandings standings={standings} />}
      {ansicht === "pairing" && <PairingList eventId={Number(id)} />}
      {ansicht === "ergebnisse" && kannErfassen && (
        <ResultsEntry eventId={Number(id)} eventIdParam={id} />
      )}
    </>
  );
}

function DailyStandings({ standings }: { standings: StandingRow[] }) {
  const { t } = useTranslation("matchday");

  if (!standings.length) return <Leer testId="matchday-standings-empty">{t("noResultsYet")}</Leer>;

  const gesegelt = standings.some((zeile) => zeile.races_scored > 0);
  if (!gesegelt) {
    return <Leer testId="matchday-standings-not-sailed">{t("notSailedYet")}</Leer>;
  }

  return (
    <TabellenRahmen testId="matchday-standings-table-frame">
      <table data-testid="matchday-standings-table" className="w-full min-w-[32rem] border-collapse text-sm">
        <caption className="sr-only">{t("standingsCaption")}</caption>
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50 text-left">
            <th scope="col" className="w-14 px-4 py-3 font-medium text-slate-600">
              {t("placeHeader")}
            </th>
            <th scope="col" className="px-4 py-3 font-medium text-slate-600">
              {t("teamHeader")}
            </th>
            <th scope="col" className="w-28 px-4 py-3 text-right font-medium text-slate-600">
              {t("pointsHeader")}
            </th>
            <th scope="col" className="w-28 px-4 py-3 text-right font-medium text-slate-600">
              {t("racesHeader")}
            </th>
          </tr>
        </thead>
        <tbody>
          {standings.map((zeile) => (
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
              </td>
              <td className="px-4 py-3 text-right tabular-nums text-slate-500">
                {zeile.races_scored}
              </td>
            </tr>
          ))}
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

/** Only `admin`/`race_officer` can reach this (gated in `Matchday`) — the race committee's
 *  entry screen: the same pairing grid as the "pairing" tab, but editable and including
 *  unfinished races. A row PUTs its whole race on save; results are the raw
 *  `code`/`finish_position`/`redress_points` — `points` are always derived
 *  (`app/services/standings.py`), never entered here.
 */
function ResultsEntry({
  eventId,
  eventIdParam,
}: {
  eventId: number;
  eventIdParam: string;
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

function RaceResultRow({
  race,
  boats,
  eventId,
  eventIdParam,
}: {
  race: AdminRace;
  boats: BoatOut[];
  eventId: number;
  eventIdParam: string;
}) {
  const { t } = useTranslation("matchday");
  const invalidieren = useInvalidieren();
  const byBoat = new Map(race.entries.map((eintrag) => [eintrag.boat_number, eintrag]));

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
        return (
          <td key={boot.number} className="min-w-[9rem] px-3 py-2.5">
            <div className="mb-1 truncate text-xs font-medium text-slate-600">
              {bestehend.team.club.short_name}
            </div>
            {bestehend.points != null && (
              <div className="mb-1 text-[11px] text-slate-400">
                {t("currentResultNote", { points: punkte(bestehend.points) })}
                {bestehend.is_discarded && ` (${t("discardedNote")})`}
              </div>
            )}
            <select
              aria-label={t("codeHeader")}
              className={EINGABE}
              value={zeile.code}
              onChange={(e) => setzeFeld(boot.number, { code: e.target.value })}
              data-testid={`matchday-results-code-select-${race.id}-${boot.number}`}
            >
              {RESULT_CODES.map((code) => (
                <option key={code} value={code}>
                  {code}
                </option>
              ))}
            </select>
            {brauchtPlatz(zeile.code) && (
              <input
                type="number"
                min={1}
                className={`${EINGABE} mt-1`}
                value={zeile.finish_position ?? ""}
                placeholder={t("positionPlaceholder")}
                onChange={(e) =>
                  setzeFeld(boot.number, {
                    finish_position: e.target.value ? Number(e.target.value) : null,
                  })
                }
                data-testid={`matchday-results-position-input-${race.id}-${boot.number}`}
              />
            )}
            {zeile.code === "RDG" && (
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
            )}
          </td>
        );
      })}
      <td className="px-3 py-2.5">
        <Button
          size="sm"
          onPress={() => speichern.mutate()}
          isDisabled={speichern.isPending}
          data-testid={`matchday-results-save-button-${race.id}`}
        >
          {speichern.isPending ? t("savingButton") : t("saveButton")}
        </Button>
        <div className="mt-1">
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
