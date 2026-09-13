import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { useGetSeriesTable, useListSeries } from "../api/generated/sbl";
import { useAsync } from "../api/useApi";
import { ErrorMessage, Loading, Empty, PageHeader, TableFrame } from "../components/Blocks";
import { formatPoints } from "../lib/format";

/** B-1: As a fan, I want to see where my team stands in the series.
 *
 * With an id in the URL, the named series; without one, the first of the current year —
 * there are several at once (first, second, juniors, SCL).
 */
export function Standings() {
  const { t } = useTranslation("standings");
  const { id } = useParams();
  const named = id ? Number(id) : null;

  // Without an id in the URL this needs the list first, to learn which series is "the
  // first of the current year". Two dependent queries rather than one composite call:
  // the list is the same one the navigation and the overview page already hold, so with
  // a warm cache the extra request does not happen at all.
  const list = useAsync(useListSeries());
  const seriesId = named ?? list.data?.[0]?.id ?? null;
  const table = useAsync(
    useGetSeriesTable(seriesId ?? 0, { query: { enabled: seriesId !== null } }),
  );

  // A disabled query stays `isPending` forever, so "still loading" cannot simply be
  // `table.loading`: with no series this year there is no id to look up, and the page
  // would spin until someone reloaded it.
  const loading = (named === null && list.loading) || (seriesId !== null && table.loading);
  const error = table.error ?? list.error;
  const data = table.data;

  if (loading) return <Loading text={t("loading.text")} testId="standings-loading" />;
  if (error) return <ErrorMessage text={error} testId="standings-error" />;
  // No series at all this year: the list answered, it was empty, so there is nothing to
  // look up. Previously this threw a 404 from inside the composite call.
  if (!data) return <ErrorMessage text={t("common:errors.noSeriesThisYear")} testId="standings-error" />;

  return (
    <>
      <PageHeader
        title={data.series.name}
        testId="standings-header"
      />

      {/* The table is the page. The matchdays used to sit above it as a grid of cards and
          the series' free-text description above that, so the ranking — the one thing
          someone opens a league table for — started below the fold. The acts are not
          lost: every act column heading links to its matchday, which is where a reader
          looking at that column's numbers wants to go anyway. The description still has
          its home on the club and event pages; a standings page is not a place to read. */}
      {/* A series without a sailed event has no table — saying so plainly is clearer
          than showing an empty grid. */}
      {!data.rows.length ? (
        <Empty testId="standings-table-empty">
          {data.events.length
            ? t("empty.noRaces")
            : t("empty.noEvents")}
        </Empty>
      ) : (
      <>
      <TableFrame testId="standings-table-frame">
        <table data-testid="standings-table" className="data-table w-full min-w-[36rem] border-collapse text-sm">
          <caption className="sr-only">
            {t("caption", { seriesName: data.series.name })}
          </caption>
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-left">
              <th scope="col" className="w-14 font-medium text-slate-600">
                {t("table.rank")}
              </th>
              <th scope="col" className="font-medium text-slate-600">
                {t("table.club")}
              </th>
              <th scope="col" className="w-24 text-right font-medium text-slate-600">
                {t("table.points")}
              </th>
              {data.events.map((event) => (
                <th
                  key={event.id}
                  scope="col"
                  className="w-20 text-center font-medium text-slate-600"
                >
                  {/* The heading is the way into the matchday. `title` carries the event's
                      full name, because the column is only wide enough for "Act 2". */}
                  <Link
                    to={`/events/${event.id}`}
                    data-testid={`standings-event-link-${event.id}`}
                    title={event.title}
                    className="underline-offset-2 hover:text-slate-900 hover:underline"
                  >
                    {t("table.act", { matchday: event.matchday })}
                  </Link>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row) => (
              <tr
                key={row.team.id}
                data-testid={`standings-row-${row.team.id}`}
                className="border-b border-slate-100 last:border-0 hover:bg-slate-50"
              >
                <td className="font-semibold tabular-nums text-slate-900">
                  {row.rank}
                </td>
                <td>
                  <Link
                    to={`/clubs/${row.team.club.id}`}
                    data-testid={`standings-club-link-${row.team.id}`}
                    className="font-medium text-slate-900 underline-offset-2 hover:underline"
                  >
                    {row.team.club.name}
                  </Link>
                  <span className="ml-2 text-slate-500">{row.team.club.short_name}</span>
                </td>
                <td className="text-right font-semibold tabular-nums">
                  {formatPoints(row.points)}
                </td>
                {data.events.map((event) => (
                  <td
                    key={event.id}
                    className="text-center tabular-nums text-slate-500"
                  >
                    <span
                      className={
                        row.missed_matchdays?.includes(event.matchday ?? 0)
                          ? "italic text-slate-400"
                          : ""
                      }
                      title={
                        row.missed_matchdays?.includes(event.matchday ?? 0)
                          ? t("table.notSailed")
                          : undefined
                      }
                    >
                      {row.ranks_by_matchday[String(event.matchday)] ?? "–"}
                    </span>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </TableFrame>
      </>
      )}
    </>
  );
}
