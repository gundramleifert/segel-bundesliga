import { Card } from "@heroui/react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import { useApi } from "../api/useApi";
import { ErrorMessage, Loading, Empty, MatchdayCard } from "../components/Blocks";
import { dateRange } from "../lib/format";

/** The home page shows two things: all events and all series.
 *
 * Events come first — that's what someone looks for around a matchday. The series below
 * link to their tables; without them, all but the first would be unreachable.
 */
export function Start() {
  const { t } = useTranslation("start");
  const eventsQuery = useApi(["events"], (signal) => api.events(signal));
  const seriesList = useApi(["series"], (signal) => api.series(signal));

  if (eventsQuery.loading || seriesList.loading) return <Loading testId="start-loading" />;
  if (eventsQuery.error) return <ErrorMessage text={eventsQuery.error} testId="start-events-error" />;

  const events = eventsQuery.data ?? [];
  // How many events belong to a series — already known from the events list, so no
  // second request is needed.
  const actsPerSeries = new Map<number, number>();
  for (const event of events) {
    if (event.series) {
      actsPerSeries.set(event.series.id, (actsPerSeries.get(event.series.id) ?? 0) + 1);
    }
  }

  return (
    <>
      <section className="mb-10 rounded-2xl bg-marke-600 px-6 py-10 text-white sm:px-10">
        <p className="text-sm font-medium uppercase tracking-wider text-marke-100">
          {t("hero.tagline")}
        </p>
        {/* The real logo (see Layout.tsx) is a photograph with a white background baked
            in, not a white-on-transparent mark like the old placeholder asset this
            replaces — dropped straight onto this dark bg-marke-600 hero it would show a
            stray white rectangle. Framing it in its own white card keeps that white
            edge deliberate instead of looking like a rendering bug. */}
        <div className="mt-3 inline-block rounded-lg bg-white p-2 shadow-sm sm:p-3">
          <img
            src="/marke/deutsche-segelliga-logo.jpg"
            alt="Deutsche Segel-Liga"
            className="h-12 w-auto sm:h-14"
            width={600}
            height={173}
          />
        </div>
        <p className="mt-3 max-w-2xl text-marke-100">
          {t("hero.description")}
        </p>
      </section>

      <section data-testid="start-events-section" className="mb-12">
        <div className="mb-3 flex items-end justify-between gap-4">
          <h2 className="text-lg font-semibold">{t("eventsSection.heading")}</h2>
          <Link
            to="/events"
            data-testid="start-events-all-link"
            className="text-sm text-marke-700 underline-offset-2 hover:underline"
          >
            {t("eventsSection.allLink")}
          </Link>
        </div>

        {events.length ? (
          <ul className="grid gap-4 sm:grid-cols-2">
            {events.map((event) => (
              <li key={event.id}>
                <MatchdayCard event={event} />
              </li>
            ))}
          </ul>
        ) : (
          <Empty testId="start-events-empty">{t("eventsSection.empty")}</Empty>
        )}
      </section>

      <section data-testid="start-series-section">
        <h2 className="mb-3 text-lg font-semibold">{t("seriesSection.heading")}</h2>

        {seriesList.error && <ErrorMessage text={seriesList.error} testId="start-series-error" />}

        {!seriesList.error &&
          (seriesList.data?.length ? (
            <ul className="grid gap-4 sm:grid-cols-2">
              {seriesList.data.map((series) => {
                const acts = actsPerSeries.get(series.id) ?? 0;
                const dateRangeText =
                  series.starts_on && series.ends_on
                    ? dateRange(series.starts_on, series.ends_on)
                    : null;

                return (
                  <li key={series.id}>
                    <Link
                      to={`/series/${series.id}`}
                      data-testid={`start-series-card-${series.id}`}
                      className="block group"
                    >
                      <Card className="h-full transition-shadow group-hover:shadow-md">
                        <Card.Header>
                          <Card.Title>{series.name}</Card.Title>
                          <Card.Description>
                            {t("seriesSection.eventCount", { count: acts })}
                            {dateRangeText && ` · ${dateRangeText}`}
                          </Card.Description>
                        </Card.Header>
                        <Card.Content>
                          <p className="text-sm text-marke-700">{t("seriesCard.linkText")}</p>
                        </Card.Content>
                      </Card>
                    </Link>
                  </li>
                );
              })}
            </ul>
          ) : (
            <Empty testId="start-series-empty">{t("seriesSection.empty")}</Empty>
          ))}
      </section>
    </>
  );
}
