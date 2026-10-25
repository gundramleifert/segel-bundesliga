import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { useListEvents } from "../../api/generated/sbl";
import { useAsync } from "../../api/useApi";
import { Async } from "../../components/Async";
import { Section } from "../../components/Form";
import { eventDates } from "../../lib/format";
import { contextPath, useMySpace } from "./shared";
import { ContextFrame, Door, MyTeams, waiverNotice } from "./ContextFrame";


/** `/me/series/:id` — my waiver and my team, the series' events, the organizer's door. */
export function SeriesPage() {
  const { t } = useTranslation("space");
  return (
    <ContextFrame
      kind="series"
      publicPath={(c) => (c.published ? `/series/${c.id}` : null)}
      sections={(c) => [
        waiverNotice(t, "series", c.id),
        {
          key: "team",
          label: t("context.tabs.team"),
          render: () => <MyTeams context={c} testId="me-series-teams" />,
        },
        { key: "events", label: t("context.tabs.events"), render: () => <SeriesEvents seriesId={c.id} /> },
        {
          key: "registrations",
          label: t("context.tabs.organize"),
          render: () => (
            <Door
              text={t("context.organizeSeries")}
              to="/admin?tab=series"
              label={t("context.organizeLink")}
              testId="me-series-organize"
            />
          ),
        },
      ]}
    />
  );
}

/** The series' events, each leading to my page for it when I am part of it. */
function SeriesEvents({ seriesId }: { seriesId: number }) {
  const { t } = useTranslation("space");
  const events = useAsync(useListEvents({ series: seriesId, limit: 100 }));
  const { space } = useMySpace();
  const mine = new Set((space.data?.contexts ?? []).filter((c) => c.kind === "event").map((c) => c.id));
  return (
    <Section title={t("context.tabs.events")} testId="me-series-events">
      <Async state={events} testId="me-series-events" empty={t("context.noEvents")} isEmpty={(page) => !page.items.length}>
        {(page) => (
          <ul className="flex flex-col gap-2" data-testid="me-series-events-list">
            {page.items.map((event) => (
              <li key={event.id} className="flex flex-wrap items-baseline gap-x-3 text-sm">
                <Link
                  to={mine.has(event.id) ? contextPath({ kind: "event", id: event.id }) : `/events/${event.id}`}
                  className="font-medium underline-offset-2 hover:underline"
                  data-testid={`me-series-event-${event.id}`}
                >
                  {event.title}
                </Link>
                <span className="text-muted">{eventDates(event)}</span>
              </li>
            ))}
          </ul>
        )}
      </Async>
    </Section>
  );
}
