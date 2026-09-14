import type { ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { Tip } from "../components/Tip";

import {
  getGetSeriesTableQueryKey,
  useGetSeriesTable,
  useListSeries,
} from "../api/generated/sbl";
import { useAsync } from "../api/useApi";
import { useLive } from "../api/useLive";
import {
  ErrorMessage,
  LiveBadge,
  Loading,
  Empty,
  MatchdayCard,
  PageHeader,
  TableFrame,
} from "../components/Blocks";
import { CardGrid, Stack } from "../components/Layouts";
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

  // Story B-5: live is an event, never a series. The table changes because one of its
  // events does, so this page listens on the running event — or, with none running, on
  // the next planned one, so it hears the start — and refetches its own table.
  const runningEvent = data?.events.find((event) => event.status === "live");
  const liveTopicEvent = runningEvent ?? data?.events.find((event) => event.status === "planned");
  const live = useLive(
    liveTopicEvent ? `event:${liveTopicEvent.id}` : null,
    seriesId !== null ? [getGetSeriesTableQueryKey(seriesId)] : [],
  );

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

      {/* Two blocks, in the order they are wanted: the ranking, then the matchdays it is
          made of. The matchdays used to sit *above* the table, together with the series'
          free-text description, so the ranking — the one thing someone opens a league
          table for — started below the fold. Below it they are the natural next step, and
          the reader has already seen the numbers each one contributed. The description
          keeps its home on the club and event pages; a standings page is not a place to
          read. */}
      <Stack gap={8}>
      <section data-testid="standings-results-section">
      <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
        <SectionHeading>{t("resultsHeading")}</SectionHeading>
        {/* Only while one of the series' events is being sailed: that is when this table
            moves, and the only time "live" is true of anything here. */}
        {runningEvent && (
          <span className="mb-3">
            <LiveBadge state={live} testId="standings-live-badge" />
          </span>
        )}
      </div>
      {/* A series without a sailed event has no table — saying so plainly is clearer
          than showing an empty grid. */}
      {!data.rows.length ? (
        <Empty testId="standings-table-empty">
          {data.events.length
            ? t("empty.noRaces")
            : t("empty.noEvents")}
        </Empty>
      ) : (
      <TableFrame testId="standings-table-frame">
        <table
          data-testid="standings-table"
          // Sized by its content, not stretched to the panel. Every column here is a rank,
          // an abbreviation or a number, so stretching only widened the club column — with
          // `w-full` the browser hands the leftover width to whichever column has no
          // explicit one, and "BYC (BE)" then sat in a column three times its width.
          className="data-table border-collapse text-sm"
        >
          <caption className="sr-only">
            {t("caption", { seriesName: data.series.name })}
          </caption>
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-left">
              <th scope="col" className="w-14 font-medium text-slate-600">
                {t("table.rank")}
              </th>
              {/* Abbreviations only (the full name is the row's tooltip), so ten
                  characters — "BYC (BE)" — is the widest this ever has to be. */}
              <th scope="col" className="max-w-28 font-medium text-slate-600">
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
                  {/* The heading is the way into the matchday. The tooltip carries the
                      event's full name — the column fits only "Act 2". */}
                  <Tip text={event.title}>
                    <Link
                      to={`/events/${event.id}`}
                      data-testid={`standings-event-link-${event.id}`}
                      className="underline-offset-2 hover:text-slate-900 hover:underline"
                    >
                      {t("table.act", { matchday: event.matchday })}
                    </Link>
                  </Tip>
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
                  {/* The abbreviation carries the row, the full name is the tooltip. It
                      used to be both side by side, which set this column's width from the
                      longest of eighteen club names. */}
                  <Tip text={row.team.club.name}>
                    <Link
                      to={`/clubs/${row.team.club.id}`}
                      data-testid={`standings-club-link-${row.team.id}`}
                      className="font-medium text-slate-900 underline-offset-2 hover:underline"
                    >
                      {row.team.club.short_name}
                    </Link>
                  </Tip>
                </td>
                <td className="text-right font-semibold tabular-nums">
                  {formatPoints(row.points)}
                </td>
                {data.events.map((event) => (
                  <td
                    key={event.id}
                    className="text-center tabular-nums text-slate-500"
                  >
                    {/* The rule lives here, on the cell that raises the question — a boat
                        that missed this act shows "field size + 1", and that is where
                        someone asks why. It used to be a paragraph under the table. */}
                    <Tip
                      text={
                        row.missed_matchdays?.includes(event.matchday ?? 0)
                          ? t("table.notSailed")
                          : null
                      }
                    >
                      <span
                        className={
                          row.missed_matchdays?.includes(event.matchday ?? 0)
                            ? "italic text-slate-400"
                            : ""
                        }
                      >
                        {row.ranks_by_matchday[String(event.matchday)] ?? "–"}
                      </span>
                    </Tip>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </TableFrame>
      )}
      </section>

      {/* The events of the series, in the order they are sailed. An act column in the
          table above already links to its matchday, but that link is a number in a grid —
          it answers "how did we do there", not "where and when is the next one". */}
      {data.events.length > 0 && (
        <section data-testid="standings-events-section">
          <SectionHeading>{t("eventsHeading")}</SectionHeading>
          <CardGrid testId="standings-events-list">
            {data.events.map((event) => (
              <li key={event.id}>
                <MatchdayCard event={event} />
              </li>
            ))}
          </CardGrid>
        </section>
      )}
      </Stack>
    </>
  );
}

/** The name of a block within a page. The page's own name is the breadcrumb's (Story
 *  A-12), so these are deliberately quieter than an `h1` would be — but they are real
 *  headings, and a page of two unlabelled blocks has no outline at all. */
function SectionHeading({ children }: { children: ReactNode }) {
  return <h2 className="mb-3 text-base font-semibold text-slate-900">{children}</h2>;
}
