import { Card } from "@heroui/react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import { useApi } from "../api/useApi";
import { Fehler, Laden, Leer, SpieltagKarte } from "../components/Bausteine";
import { zeitraum } from "../lib/format";

/** The home page shows two things: all events and all series.
 *
 * Events come first — that's what someone looks for around a matchday. The series below
 * link to their tables; without them, all but the first would be unreachable.
 */
export function Start() {
  const { t } = useTranslation("start");
  const termine = useApi(["events"], (signal) => api.events(signal));
  const serien = useApi(["series"], (signal) => api.series(signal));

  if (termine.loading || serien.loading) return <Laden />;
  if (termine.error) return <Fehler text={termine.error} />;

  const events = termine.data ?? [];
  // How many events belong to a series — already known from the events list, so no
  // second request is needed.
  const actsJeSerie = new Map<number, number>();
  for (const event of events) {
    if (event.series) {
      actsJeSerie.set(event.series.id, (actsJeSerie.get(event.series.id) ?? 0) + 1);
    }
  }

  return (
    <>
      <section className="mb-10 rounded-2xl bg-marke-600 px-6 py-10 text-white sm:px-10">
        <p className="text-sm font-medium uppercase tracking-wider text-marke-100">
          {t("hero.tagline")}
        </p>
        <img
          src="/marke/segelbundesliga-weiss.png"
          alt={t("hero.tagline")}
          className="mt-3 h-14 w-auto sm:h-16"
        />
        <p className="mt-3 max-w-2xl text-marke-100">
          {t("hero.description")}
        </p>
      </section>

      <section className="mb-12">
        <div className="mb-3 flex items-end justify-between gap-4">
          <h2 className="text-lg font-semibold">{t("eventsSection.heading")}</h2>
          <Link
            to="/events"
            className="text-sm text-marke-700 underline-offset-2 hover:underline"
          >
            {t("eventsSection.allLink")}
          </Link>
        </div>

        {events.length ? (
          <ul className="grid gap-4 sm:grid-cols-2">
            {events.map((event) => (
              <li key={event.id}>
                <SpieltagKarte event={event} />
              </li>
            ))}
          </ul>
        ) : (
          <Leer>{t("eventsSection.empty")}</Leer>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">{t("seriesSection.heading")}</h2>

        {serien.error && <Fehler text={serien.error} />}

        {!serien.error &&
          (serien.data?.length ? (
            <ul className="grid gap-4 sm:grid-cols-2">
              {serien.data.map((serie) => {
                const acts = actsJeSerie.get(serie.id) ?? 0;
                const zeitangabe =
                  serie.starts_on && serie.ends_on
                    ? zeitraum(serie.starts_on, serie.ends_on)
                    : null;

                return (
                  <li key={serie.id}>
                    <Link to={`/standings/${serie.id}`} className="block group">
                      <Card className="h-full transition-shadow group-hover:shadow-md">
                        <Card.Header>
                          <Card.Title>{serie.name}</Card.Title>
                          <Card.Description>
                            {t("seriesSection.eventCount", { count: acts })}
                            {zeitangabe && ` · ${zeitangabe}`}
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
            <Leer>{t("seriesSection.empty")}</Leer>
          ))}
      </section>
    </>
  );
}
