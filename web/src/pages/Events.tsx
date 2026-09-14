import { keepPreviousData } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { CardGrid } from "../components/Layouts";

import { useListEvents } from "../api/generated/sbl";
import { useAsync } from "../api/useApi";
import { Empty, PageHeader, MatchdayCard } from "../components/Blocks";
import { Async } from "../components/Async";
import { Pager } from "../components/Pager";
import { useListParams } from "../lib/listParams";

/** B-4: As a visitor, I want to find the events. */
export function Events() {
  const { t } = useTranslation("events");
  // The calendar grows by a dozen events a season and never shrinks, so it is paged, with
  // the page in the URL (Story A-13). `keepPreviousData` holds the current page on screen
  // while the next one loads — without it every step replaces the cards with a spinner.
  const list = useListParams();
  const query = useListEvents(
    { ...list.request, q: list.q || undefined },
    { query: { placeholderData: keepPreviousData } },
  );
  const events = useAsync(query);

  return (
    <Async
      state={events}
      testId="events"
      loadingText={t("loading")}
    >
      {(page) => (
        <>
          <PageHeader
            title={t("title")}
            testId="events-header"
          />

          <input
            type="search"
            value={list.q}
            onChange={(e) => list.setQuery(e.target.value)}
            placeholder={t("searchPlaceholder")}
            aria-label={t("searchPlaceholder")}
            data-testid="events-search-input"
            className="mb-4 w-full max-w-sm rounded border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-200"
          />

          {!page.items.length && (
            <Empty testId={list.q ? "events-no-matches" : "events-empty"}>
              {list.q ? t("noMatches") : t("noEvents")}
            </Empty>
          )}

          <CardGrid testId="events-list">
            {page.items.map((event) => (
              <li key={event.id}>
                <MatchdayCard event={event} />
              </li>
            ))}
          </CardGrid>
          <Pager page={page} current={list.page} onPage={list.setPage} testId="events" />
        </>
      )}
    </Async>
  );
}
