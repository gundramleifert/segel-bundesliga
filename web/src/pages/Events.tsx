import { useTranslation } from "react-i18next";
import { CardGrid } from "../components/Layouts";

import { useListEvents } from "../api/generated/sbl";
import { useAsync } from "../api/useApi";
import { PageHeader, MatchdayCard } from "../components/Blocks";
import { Async } from "../components/Async";

/** B-4: As a visitor, I want to find the events. */
export function Events() {
  const { t } = useTranslation("events");
  const events = useAsync(useListEvents());

  return (
    <Async
      state={events}
      testId="events"
      loadingText={t("loading")}
      empty={t("noEvents")}
    >
      {(data) => (
        <>
          <PageHeader
            title={t("title")}
            subtitle={t("eventCount", { count: data.length })}
            testId="events-header"
          />

          <CardGrid testId="events-list">
            {data.map((event) => (
              <li key={event.id}>
                <MatchdayCard event={event} />
              </li>
            ))}
          </CardGrid>
        </>
      )}
    </Async>
  );
}
