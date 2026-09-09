import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import { useApi } from "../api/useApi";
import { Fehler, Laden, Leer, Seitenkopf, SpieltagKarte } from "../components/Bausteine";

/** B-4: As a visitor, I want to find the events. */
export function Events() {
  const { t } = useTranslation("events");
  const { data, error, loading } = useApi(["events"], (signal) => api.events(signal));

  if (loading) return <Laden text={t("loading")} testId="events-loading" />;
  if (error) return <Fehler text={error} testId="events-error" />;
  if (!data?.length) return <Leer testId="events-empty">{t("noEvents")}</Leer>;

  return (
    <>
      <Seitenkopf
        titel={t("title")}
        unterzeile={t("eventCount", { count: data.length })}
        testId="events-header"
      />

      <ul data-testid="events-list" className="grid gap-4 sm:grid-cols-2">
        {data.map((spieltag) => (
          <li key={spieltag.id}>
            <SpieltagKarte event={spieltag} />
          </li>
        ))}
      </ul>
    </>
  );
}
