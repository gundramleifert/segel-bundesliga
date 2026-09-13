import { useTranslation } from "react-i18next";

import { useListEvents } from "../api/generated/sbl";
import { useAsync } from "../api/useApi";
import { ErrorMessage, Loading, Empty, PageHeader, MatchdayCard } from "../components/Blocks";

/** B-4: As a visitor, I want to find the events. */
export function Events() {
  const { t } = useTranslation("events");
  const { data, error, loading } = useAsync(useListEvents());

  if (loading) return <Loading text={t("loading")} testId="events-loading" />;
  if (error) return <ErrorMessage text={error} testId="events-error" />;
  if (!data?.length) return <Empty testId="events-empty">{t("noEvents")}</Empty>;

  return (
    <>
      <PageHeader
        title={t("title")}
        subtitle={t("eventCount", { count: data.length })}
        testId="events-header"
      />

      <ul data-testid="events-list" className="grid gap-4 sm:grid-cols-2">
        {data.map((event) => (
          <li key={event.id}>
            <MatchdayCard event={event} />
          </li>
        ))}
      </ul>
    </>
  );
}
