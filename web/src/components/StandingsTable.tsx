import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import type { EventSummary, SeriesTable } from "../api/types";
import { formatPoints } from "../lib/format";
import { TableFrame } from "./Blocks";
import { Tip } from "./Tip";

/** Where a table marks promotion, relegation and requalification — by rank. */
export type RankMarks = { promotion?: number; relegation?: number; requalify?: [number, number] };

type Mark = "promotion" | "relegation" | "requalify";

const MARK_STYLE: Record<Mark, string> = {
  promotion: "border-l-success",
  relegation: "border-l-danger",
  requalify: "border-l-warning",
};

function markOf(rank: number, count: number, marks: RankMarks): Mark | null {
  if (marks.promotion != null && rank <= marks.promotion) return "promotion";
  if (marks.relegation != null && rank > count - marks.relegation) return "relegation";
  if (marks.requalify && rank >= marks.requalify[0] && rank <= marks.requalify[1]) return "requalify";
  return null;
}

/** A series' standings as a table — Stories B-1, A-5: rank, club, points, and the place at
 *  each act, a missed act in italics with the rule in its tooltip.
 *
 *  One table for both places it is read: a series' own page (`/series/:id`, a series in no
 *  league) and each division on a league's standings page (Story B-14), where the
 *  league's rules mark the rows that go up, go down or must requalify — a coloured edge
 *  on the row, named in the legend below the table.
 */
export function StandingsTable({
  data,
  actHref,
  marks = {},
  testId = "standings",
}: {
  data: SeriesTable;
  /** Where an act's column heading leads. */
  actHref: (event: EventSummary) => string;
  marks?: RankMarks;
  /** Prefix of every testid: `${testId}-table`, `${testId}-row-<team>`, … */
  testId?: string;
}) {
  const { t } = useTranslation("standings");
  const count = data.rows.length;
  const used = new Set(data.rows.map((row) => markOf(row.rank, count, marks)).filter((m): m is Mark => m !== null));
  return (
    <>
      <TableFrame testId={`${testId}-table-frame`}>
        <table
          data-testid={`${testId}-table`}
          // Sized by its content, not stretched to the panel. Every column here is a rank,
          // an abbreviation or a number, so stretching only widened the club column.
          className="data-table border-collapse text-sm"
        >
          <caption className="sr-only">{t("caption", { seriesName: data.series.name })}</caption>
          <thead>
            <tr className="border-b border-separator bg-surface-secondary text-left">
              <th scope="col" className="w-14 font-medium text-muted">
                {t("table.rank")}
              </th>
              {/* Abbreviations only (the full name is the tooltip), so ten characters —
                  "BYC (BE)" — is the widest this ever has to be. */}
              <th scope="col" className="max-w-28 font-medium text-muted">
                {t("table.club")}
              </th>
              <th scope="col" className="w-24 text-right font-medium text-muted">
                {t("table.points")}
              </th>
              {data.events.map((event) => (
                <th key={event.id} scope="col" className="w-20 whitespace-nowrap text-center font-medium text-muted">
                  {/* The heading is the way into the matchday; the tooltip carries the
                      event's full name — the column fits only "Act 2". */}
                  <Tip text={event.title}>
                    <Link
                      to={actHref(event)}
                      data-testid={`${testId}-event-link-${event.id}`}
                      className="underline-offset-2 hover:text-foreground hover:underline"
                    >
                      {t("table.act", { matchday: event.matchday })}
                    </Link>
                  </Tip>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row) => {
              const mark = markOf(row.rank, count, marks);
              return (
                <tr
                  key={row.team.id}
                  data-testid={`${testId}-row-${row.team.id}`}
                  data-mark={mark ?? undefined}
                  className="border-b border-separator last:border-0 hover:bg-surface-secondary"
                >
                  <td className={`border-l-4 font-semibold tabular-nums text-foreground ${mark ? MARK_STYLE[mark] : "border-l-transparent"}`}>
                    {row.rank}
                  </td>
                  <td>
                    <Tip text={row.team.club.name}>
                      <Link
                        to={`/clubs/${row.team.club.id}`}
                        data-testid={`${testId}-club-link-${row.team.id}`}
                        className="font-medium text-foreground underline-offset-2 hover:underline"
                      >
                        {row.team.club.short_name}
                      </Link>
                    </Tip>
                  </td>
                  <td className="text-right font-semibold tabular-nums">{formatPoints(row.points)}</td>
                  {data.events.map((event) => {
                    const missed = row.missed_matchdays?.includes(event.matchday ?? 0);
                    return (
                      <td key={event.id} className="text-center tabular-nums text-muted">
                        {/* The rule lives on the cell that raises the question: a team that
                            missed this act has "field size + 1". */}
                        <Tip text={missed ? t("table.notSailed") : null}>
                          <span className={missed ? "italic text-faint" : ""}>
                            {row.ranks_by_matchday[String(event.matchday)] ?? "–"}
                          </span>
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
      {used.size > 0 && (
        <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted" data-testid={`${testId}-legend`}>
          {(["promotion", "relegation", "requalify"] as const)
            .filter((m) => used.has(m))
            .map((m) => (
              <li key={m} className="flex items-center gap-2">
                <span aria-hidden className={`h-3 w-1 rounded-sm border-l-4 ${MARK_STYLE[m]}`} />
                {t(`marks.${m}`)}
              </li>
            ))}
        </ul>
      )}
    </>
  );
}
