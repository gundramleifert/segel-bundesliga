import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { api, type StandingRow } from "../api/client";
import { useApi } from "../api/useApi";
import {
  Fehler,
  Laden,
  Leer,
  Seitenkopf,
  StatusMarke,
  TabellenRahmen,
} from "../components/Bausteine";
import { bootsfarbe, ortText, punkte, spieltagUntertitel, zeitraum } from "../lib/format";

/** B-2 and B-3: Daily standings and pairing list of a matchday. */
export function Matchday() {
  const { t } = useTranslation("matchday");
  const { id = "" } = useParams();
  const [ansicht, setAnsicht] = useState<"wertung" | "pairing">("wertung");

  const spieltag = useApi(["event", id], (signal) => api.event(Number(id), signal));

  if (spieltag.loading) return <Laden text={t("loading")} />;
  if (spieltag.error) return <Fehler text={spieltag.error} />;
  if (!spieltag.data) return null;

  const { event, standings, races_scored, races_total } = spieltag.data;

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
        rechts={<StatusMarke status={event.status} />}
      />

      <p className="mb-6 text-sm text-slate-600">
        {t("racesCount", { scored: races_scored, total: races_total })}
        {event.status === "live" && ` · ${t("liveUpdate")}`}
      </p>

      <div
        role="tablist"
        aria-label={t("viewLabel")}
        className="mb-4 inline-flex rounded-lg border border-slate-200 bg-white p-1"
      >
        {(
          [
            ["wertung", t("standingsTab")],
            ["pairing", t("pairingTab")],
          ] as const
        ).map(([wert, text]) => (
          <button
            key={wert}
            role="tab"
            aria-selected={ansicht === wert}
            onClick={() => setAnsicht(wert)}
            className={`rounded-md px-4 py-1.5 text-sm transition-colors ${
              ansicht === wert
                ? "bg-marke-600 font-medium text-white"
                : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            {text}
          </button>
        ))}
      </div>

      {ansicht === "wertung" ? (
        <DailyStandings standings={standings} />
      ) : (
        <PairingList eventId={Number(id)} />
      )}
    </>
  );
}

function DailyStandings({ standings }: { standings: StandingRow[] }) {
  const { t } = useTranslation("matchday");

  if (!standings.length) return <Leer>{t("noResultsYet")}</Leer>;

  const gesegelt = standings.some((zeile) => zeile.races_scored > 0);
  if (!gesegelt) {
    return <Leer>{t("notSailedYet")}</Leer>;
  }

  return (
    <TabellenRahmen>
      <table className="w-full min-w-[32rem] border-collapse text-sm">
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
              className="border-b border-slate-100 last:border-0 hover:bg-slate-50"
            >
              <td className="px-4 py-3 font-semibold tabular-nums">{zeile.rank}</td>
              <td className="px-4 py-3">
                <Link
                  to={`/clubs/${zeile.team.club.id}`}
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

  if (loading) return <Laden text={t("pairingLoading")} />;
  if (error) return <Fehler text={error} />;
  if (!data?.races.length) return <Leer>{t("noRacesDrawn")}</Leer>;

  return (
    <>
      <TabellenRahmen>
        <table className="w-full min-w-[44rem] border-collapse text-sm">
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
