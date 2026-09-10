import type { ComponentProps } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import ReactMarkdown from "react-markdown";

import { api } from "../api/client";
import { useApi } from "../api/useApi";
import {
  ErrorMessage,
  Loading,
  Empty,
  PageHeader,
  MatchdayCard,
  TableFrame,
} from "../components/Blocks";
import { formatPoints } from "../lib/format";

/** Minimal Tailwind styling for the series' Markdown description — this project has no
 *  typography plugin, so headings, emphasis and paragraphs are styled element by element
 *  rather than through a `prose` class. */
const MARKDOWN_COMPONENTS = {
  h1: (props: ComponentProps<"h2">) => (
    <h2 className="mb-2 text-lg font-semibold text-slate-900" {...props} />
  ),
  h2: (props: ComponentProps<"h3">) => (
    <h3 className="mb-2 text-base font-semibold text-slate-900" {...props} />
  ),
  h3: (props: ComponentProps<"h4">) => (
    <h4 className="mb-2 text-sm font-semibold text-slate-900" {...props} />
  ),
  p: (props: ComponentProps<"p">) => (
    <p className="mb-2 text-sm text-slate-600 last:mb-0" {...props} />
  ),
  ul: (props: ComponentProps<"ul">) => (
    <ul className="mb-2 list-disc pl-5 text-sm text-slate-600 last:mb-0" {...props} />
  ),
  ol: (props: ComponentProps<"ol">) => (
    <ol className="mb-2 list-decimal pl-5 text-sm text-slate-600 last:mb-0" {...props} />
  ),
  a: (props: ComponentProps<"a">) => (
    <a className="underline underline-offset-2 hover:text-brand-700" {...props} />
  ),
};

/** B-1: As a fan, I want to see where my team stands in the series.
 *
 * With an id in the URL, the named series; without one, the first of the current year —
 * there are several at once (first, second, juniors, SCL).
 */
export function Standings() {
  const { t } = useTranslation("standings");
  const { id } = useParams();
  const seriesId = id ? Number(id) : null;
  const { data, error, loading } = useApi(["series-table", seriesId], (signal) =>
    seriesId ? api.table(seriesId, signal) : api.firstSeries(signal),
  );

  if (loading) return <Loading text={t("loading.text")} testId="standings-loading" />;
  if (error) return <ErrorMessage text={error} testId="standings-error" />;
  if (!data) return null;

  return (
    <>
      <PageHeader
        title={data.series.name}
        subtitle={t("subtitle", {
          teamCount: data.rows.length,
          actCount: data.events.length
        })}
        testId="standings-header"
      />

      {/* The series' events, front and center — same card as the home page and the
          events list, so a matchday looks the same everywhere it appears. */}
      <section data-testid="standings-events-section" className="mb-8">
        <h2 className="mb-3 text-lg font-semibold">{t("eventsSection.heading")}</h2>
        {data.events.length ? (
          <ul className="grid gap-4 sm:grid-cols-2">
            {data.events.map((event) => (
              <li key={event.id}>
                <MatchdayCard event={event} />
              </li>
            ))}
          </ul>
        ) : (
          <Empty testId="standings-events-empty">{t("eventsSection.empty")}</Empty>
        )}
      </section>

      {/* Free-text, Markdown, written by the admin — nothing shown when absent. */}
      {data.series.description && (
        <div data-testid="standings-description" className="mb-6">
          <ReactMarkdown components={MARKDOWN_COMPONENTS}>
            {data.series.description}
          </ReactMarkdown>
        </div>
      )}

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
        <table data-testid="standings-table" className="w-full min-w-[36rem] border-collapse text-sm">
          <caption className="sr-only">
            {t("caption", { seriesName: data.series.name })}
          </caption>
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-left">
              <th scope="col" className="w-14 px-4 py-3 font-medium text-slate-600">
                {t("table.rank")}
              </th>
              <th scope="col" className="px-4 py-3 font-medium text-slate-600">
                {t("table.club")}
              </th>
              <th scope="col" className="w-24 px-4 py-3 text-right font-medium text-slate-600">
                {t("table.points")}
              </th>
              {data.events.map((event) => (
                <th
                  key={event.id}
                  scope="col"
                  className="w-20 px-3 py-3 text-center font-medium text-slate-600"
                  title={event.title}
                >
                  {t("table.act", { matchday: event.matchday })}
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
                <td className="px-4 py-3 font-semibold tabular-nums text-slate-900">
                  {row.rank}
                </td>
                <td className="px-4 py-3">
                  <Link
                    to={`/clubs/${row.team.club.id}`}
                    data-testid={`standings-club-link-${row.team.id}`}
                    className="font-medium text-slate-900 underline-offset-2 hover:underline"
                  >
                    {row.team.club.name}
                  </Link>
                  <span className="ml-2 text-slate-500">{row.team.club.short_name}</span>
                </td>
                <td className="px-4 py-3 text-right font-semibold tabular-nums">
                  {formatPoints(row.points)}
                </td>
                {data.events.map((event) => (
                  <td
                    key={event.id}
                    className="px-3 py-3 text-center tabular-nums text-slate-500"
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
      {/* The scoring rule itself is short and unconditional — it stays here as a
          permanent legend, independent of whatever the series' own description says. */}
      <p className="mt-3 text-sm text-slate-500">{t("scoringNote")}</p>
      </>
      )}
    </>
  );
}
