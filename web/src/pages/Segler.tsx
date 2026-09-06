import { Card } from "@heroui/react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import { useApi } from "../api/useApi";
import { Fehler, Laden, Leer, Seitenkopf, StatusMarke } from "../components/Bausteine";
import { ortText, rolle, zeitraum } from "../lib/format";

/** B-8: The Sailor page — which teams someone is registered with and where they compete. */
export function Sailor() {
  const { t } = useTranslation("sailor");
  const { id = "" } = useParams();
  const { data, error, loading } = useApi(["sailor", id], (signal) =>
    api.sailor(Number(id), signal),
  );

  if (loading) return <Laden text={t("loading")} />;
  if (error) return <Fehler text={error} />;
  if (!data) return null;

  return (
    <>
      <Seitenkopf
        titel={`${data.first_name} ${data.last_name}`}
        unterzeile={
          data.teams?.length
            ? t("registeredFor", { clubs: data.teams.map((t) => t.club.short_name).join(", ") })
            : t("notRegistered")
        }
      />

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-semibold">{t("registrations")}</h2>
        {data.teams?.length ? (
          <ul className="grid gap-3 sm:grid-cols-2">
            {data.teams.map((eintrag) => (
              <li key={eintrag.team_id}>
                <Card>
                  <Card.Header>
                    <Card.Title className="text-base">
                      <Link
                        to={`/clubs/${eintrag.club.id}`}
                        className="underline-offset-2 hover:underline"
                      >
                        {eintrag.club.name}
                      </Link>
                    </Card.Title>
                    <Card.Description>
                      {eintrag.series.name} · {rolle(eintrag.role)}
                    </Card.Description>
                  </Card.Header>
                </Card>
              </li>
            ))}
          </ul>
        ) : (
          <Leer>{t("noRegistrations")}</Leer>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">{t("lineups")}</h2>
        {data.events?.length ? (
          <ul className="overflow-hidden rounded-xl border border-slate-200 bg-white">
            {data.events.map((eintrag) => (
              <li key={eintrag.event.id} className="border-b border-slate-100 last:border-0">
                <Link
                  to={`/events/${eintrag.event.id}`}
                  className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-3 hover:bg-slate-50"
                >
                  <span className="font-medium">{eintrag.event.title}</span>
                  <StatusMarke status={eintrag.event.status} />
                  <span className="w-full text-sm text-slate-500">
                    {ortText(eintrag.event)} ·{" "}
                    {zeitraum(eintrag.event.starts_on, eintrag.event.ends_on)} ·{" "}
                    {rolle(eintrag.role)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <Leer>{t("noLineups")}</Leer>
        )}
      </section>
    </>
  );
}
