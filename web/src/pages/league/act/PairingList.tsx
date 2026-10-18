import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Tip } from "../../../components/Tip";
import { getDownloadPairingPdfUrl, useGetPairing } from "../../../api/generated/sbl";
import { useAsync } from "../../../api/useApi";
import {
  ErrorMessage,
  Loading,
  Empty,
  TableFrame,
} from "../../../components/Blocks";
import { boatColor } from "../../../lib/format";

export function PairingList({ eventId }: { eventId: number }) {
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
          // Its own classes, not INPUT_CLASS plus overrides: that one carries `w-full` and
          // `py-2`, and a conflicting Tailwind class wins by its place in the stylesheet,
          // not in this list — `w-auto` lost, and the picker spanned the whole page.
          className={
            "w-auto max-w-full rounded-md border border-slate-300 px-2 py-1 text-sm outline-none " +
            "focus:border-brand-500 focus:ring-2 focus:ring-brand-200"
          }
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
