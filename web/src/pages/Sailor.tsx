import { Card } from "@heroui/react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import { useApi } from "../api/useApi";
import { ErrorMessage, Loading, Empty, PageHeader, StatusBadge } from "../components/Blocks";
import { locationText, roleText, eventDates } from "../lib/format";

/** B-8: The Sailor page — which teams someone is registered with and where they compete. */
export function Sailor() {
  const { t } = useTranslation("sailor");
  const { id = "" } = useParams();
  const { data, error, loading } = useApi(["sailor", id], (signal) =>
    api.sailor(Number(id), signal),
  );

  if (loading) return <Loading text={t("loading")} testId="sailor-loading" />;
  if (error) return <ErrorMessage text={error} testId="sailor-error" />;
  if (!data) return null;

  return (
    <>
      <PageHeader
        title={`${data.first_name} ${data.last_name}`}
        subtitle={
          data.teams?.length
            ? t("registeredFor", { clubs: data.teams.map((t) => t.club.short_name).join(", ") })
            : t("notRegistered")
        }
        testId="sailor-header"
      />

      <section data-testid="sailor-registrations-section" className="mb-8">
        <h2 className="mb-3 text-lg font-semibold">{t("registrations")}</h2>
        {data.teams?.length ? (
          <ul className="grid gap-3 sm:grid-cols-2">
            {data.teams.map((entry) => (
              <li key={entry.team_id} data-testid={`sailor-registration-card-${entry.team_id}`}>
                <Card>
                  <Card.Header>
                    <Card.Title className="text-base">
                      <Link
                        to={`/clubs/${entry.club.id}`}
                        data-testid={`sailor-registration-club-link-${entry.team_id}`}
                        className="underline-offset-2 hover:underline"
                      >
                        {entry.club.name}
                      </Link>
                    </Card.Title>
                    <Card.Description>
                      {entry.series.name} · {roleText(entry.role)}
                    </Card.Description>
                  </Card.Header>
                </Card>
              </li>
            ))}
          </ul>
        ) : (
          <Empty testId="sailor-registrations-empty">{t("noRegistrations")}</Empty>
        )}
      </section>

      <section data-testid="sailor-lineups-section">
        <h2 className="mb-3 text-lg font-semibold">{t("lineups")}</h2>
        {data.events?.length ? (
          <ul className="overflow-hidden rounded-xl border border-slate-200 bg-white">
            {data.events.map((entry) => (
              <li key={entry.event.id} className="border-b border-slate-100 last:border-0">
                <Link
                  to={`/events/${entry.event.id}`}
                  data-testid={`sailor-lineup-row-${entry.event.id}`}
                  className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-3 hover:bg-slate-50"
                >
                  <span className="font-medium">{entry.event.title}</span>
                  <StatusBadge status={entry.event.status} />
                  <span className="w-full text-sm text-slate-500">
                    {locationText(entry.event)} ·{" "}
                    {eventDates(entry.event)} ·{" "}
                    {roleText(entry.role)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <Empty testId="sailor-lineups-empty">{t("noLineups")}</Empty>
        )}
      </section>
    </>
  );
}
