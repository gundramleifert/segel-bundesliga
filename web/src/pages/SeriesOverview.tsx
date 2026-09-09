import { Card } from "@heroui/react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import { useApi } from "../api/useApi";
import { Fehler, Laden, Leer, Seitenkopf } from "../components/Bausteine";
import { zeitraum } from "../lib/format";

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
  const serien = useApi(["series"], (signal) => api.series(signal));
  // The event counts come out of the events list, which is loaded anyway — one request
  // instead of one per series. Same approach as the home page's series section.
  const termine = useApi(["events"], (signal) => api.events(signal));

  if (serien.loading) return <Laden testId="series-loading" />;
  if (serien.error) return <Fehler text={serien.error} testId="series-error" />;

  const actsJeSerie = new Map<number, number>();
  for (const event of termine.data ?? []) {
    if (event.series) {
      actsJeSerie.set(event.series.id, (actsJeSerie.get(event.series.id) ?? 0) + 1);
    }
  }

  return (
    <>
      <Seitenkopf titel={t("seriesOverview.title")} unterzeile={t("seriesOverview.subtitle")} testId="series-header" />

      {!serien.data?.length ? (
        <Leer testId="series-empty">{t("seriesOverview.empty")}</Leer>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2" data-testid="series-list">
          {serien.data.map((serie) => {
            const acts = actsJeSerie.get(serie.id) ?? 0;
            const zeitangabe =
              serie.starts_on && serie.ends_on ? zeitraum(serie.starts_on, serie.ends_on) : null;

            return (
              <li key={serie.id}>
                <Link
                  to={`/series/${serie.id}`}
                  data-testid={`series-card-${serie.id}`}
                  className="block group"
                >
                  <Card className="h-full transition-shadow group-hover:shadow-md">
                    <Card.Header>
                      <Card.Title>{serie.name}</Card.Title>
                      <Card.Description>
                        {t("seriesOverview.eventCount", { count: acts })}
                        {zeitangabe && ` · ${zeitangabe}`}
                      </Card.Description>
                    </Card.Header>
                    {serie.description && (
                      <Card.Content>
                        {/* Deliberately the plain first line, not rendered Markdown: the
                            series' own page renders the full description, and a card is not
                            the place for headings and links. */}
                        <p className="line-clamp-2 text-sm text-slate-600">
                          {serie.description}
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
