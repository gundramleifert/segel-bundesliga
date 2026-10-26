import { Card } from "@heroui/react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CardGrid } from "../components/Layouts";

import { useGetPerson } from "../api/generated/sbl";
import { useAsync } from "../api/useApi";
import { ErrorMessage, Loading, Empty, PageHeader, StatusBadge } from "../components/Blocks";
import { locationText, roleText, eventDates } from "../lib/format";

/** B-8: The Sailor page — which teams someone is registered with and where they compete. */
export function Sailor() {
  const { t } = useTranslation("sailor");
  const { id = "" } = useParams();
  const { data, error, loading } = useAsync(useGetPerson(Number(id)));

  if (loading) return <Loading text={t("loading")} testId="sailor-loading" />;
  if (error) return <ErrorMessage text={error} testId="sailor-error" />;
  if (!data) return null;

  return (
    <>
      <PageHeader
        title={`${data.first_name} ${data.last_name}`}
        testId="sailor-header"
      />
      {/* Story S-4: only a connected viewer reaches a hidden page — say so, so they do
          not take it for what a guest sees. */}
      {data.profile_public === false && (
        <p data-testid="sailor-not-public" className="mb-6 text-sm text-muted">
          {t("notPublic")}
        </p>
      )}

      <section data-testid="sailor-registrations-section" className="mb-8">
        <h2 className="mb-3 text-lg font-semibold">{t("registrations")}</h2>
        {data.teams?.length ? (
          <CardGrid gap={3}>
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
          </CardGrid>
        ) : (
          <Empty testId="sailor-registrations-empty">{t("noRegistrations")}</Empty>
        )}
      </section>

      <section data-testid="sailor-lineups-section">
        <h2 className="mb-3 text-lg font-semibold">{t("lineups")}</h2>
        {data.events?.length ? (
          <ul className="overflow-hidden rounded-xl border border-separator bg-surface">
            {data.events.map((entry) => (
              <li key={entry.event.id} className="border-b border-separator last:border-0">
                <Link
                  to={`/events/${entry.event.id}`}
                  data-testid={`sailor-lineup-row-${entry.event.id}`}
                  className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-3 hover:bg-surface-secondary"
                >
                  <span className="font-medium">{entry.event.title}</span>
                  <StatusBadge status={entry.event.status} />
                  <span className="w-full text-sm text-muted">
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
