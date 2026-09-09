import { Card } from "@heroui/react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import { useApi } from "../api/useApi";
import { ErrorMessage, Loading, Empty, PageHeader } from "../components/Blocks";
import { dateRange } from "../lib/format";

/** The series of the current year, as an overview.
 *
 *  The association runs several series at once — 1. Liga, 2. Liga, Junioren-Liga, DSL-Pokal
 *  — so there is no single "the standings" to link to. This page is the way in: it lists the
 *  series, and each one leads to its own table. Before this existed, the navigation went
 *  straight to whichever series happened to be first for the year and the others were
 *  reachable only by editing the URL.
 */
export function SeriesOverview() {
  const { t } = useTranslation("standings");
  const seriesList = useApi(["series"], (signal) => api.series(signal));
  // The event counts come out of the events list, which is loaded anyway — one request
  // instead of one per series. Same approach as the home page's series section.
  const eventsQuery = useApi(["events"], (signal) => api.events(signal));

  if (seriesList.loading) return <Loading testId="series-loading" />;
  if (seriesList.error) return <ErrorMessage text={seriesList.error} testId="series-error" />;

  const actsPerSeries = new Map<number, number>();
  for (const event of eventsQuery.data ?? []) {
    if (event.series) {
      actsPerSeries.set(event.series.id, (actsPerSeries.get(event.series.id) ?? 0) + 1);
    }
  }

  return (
    <>
      <PageHeader title={t("seriesOverview.title")} subtitle={t("seriesOverview.subtitle")} testId="series-header" />

      {!seriesList.data?.length ? (
        <Empty testId="series-empty">{t("seriesOverview.empty")}</Empty>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2" data-testid="series-list">
          {seriesList.data.map((series) => {
            const acts = actsPerSeries.get(series.id) ?? 0;
            const dateRangeText =
              series.starts_on && series.ends_on ? dateRange(series.starts_on, series.ends_on) : null;

            return (
              <li key={series.id}>
                <Link
                  to={`/series/${series.id}`}
                  data-testid={`series-card-${series.id}`}
                  className="block group"
                >
                  <Card className="h-full transition-shadow group-hover:shadow-md">
                    <Card.Header>
                      <Card.Title>{series.name}</Card.Title>
                      <Card.Description>
                        {t("seriesOverview.eventCount", { count: acts })}
                        {dateRangeText && ` · ${dateRangeText}`}
                      </Card.Description>
                    </Card.Header>
                    {series.description && (
                      <Card.Content>
                        {/* Deliberately the plain first line, not rendered Markdown: the
                            series' own page renders the full description, and a card is not
                            the place for headings and links. */}
                        <p className="line-clamp-2 text-sm text-slate-600">
                          {series.description}
                        </p>
                      </Card.Content>
                    )}
                  </Card>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}
