import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { useListEvents } from "../../api/generated/sbl";
import { useAsync } from "../../api/useApi";
import { Async } from "../../components/Async";
import { Section } from "../../components/Form";
import { eventDates } from "../../lib/format";
import { ORGANIZERS } from "../../lib/workspace";
import { contextPath, useMySpace } from "./shared";
import { RegattaNews } from "./RegattaNews";
import { ContextFrame, MyTeams, waiverNotice } from "./ContextFrame";
import {
  OrganizerSeriesEvents,
  SeriesDates,
  SeriesOfficials,
  SeriesRegistrations,
  SeriesScoring,
  SeriesStandings,
} from "./SeriesSections";

/** `/me/series/:id` — Story Z-10: my waiver and my team; the series' events and standings;
 * for its organizers *Organize* (clubs & registrations, dates & publication, squad size &
 * scoring) and *Officials* — the series' administration in its own context (#32).
 * *News & pictures* for its editors is declared and not built yet. */
export function SeriesPage() {
  const { t } = useTranslation("space");
  return (
    <ContextFrame
      kind="series"
      publicPath={(c) => (c.published ? `/series/${c.id}` : null)}
      sections={(c) => {
        const organizer = ORGANIZERS.some((r) => c.relations.includes(r));
        return [
          waiverNotice(t, "series", c.id),
          {
            key: "team",
            label: t("context.tabs.team"),
            render: () => <MyTeams context={c} testId="me-series-teams" />,
          },
          {
            key: "events",
            label: t("seriesSections.events"),
            render: () => (organizer ? <OrganizerSeriesEvents seriesId={c.id} /> : <SeriesEvents seriesId={c.id} />),
          },
          { key: "standings", label: t("seriesSections.standings"), render: () => <SeriesStandings context={c} /> },
          {
            key: "registrations",
            label: t("seriesSections.registrations"),
            needs: ["registrations_open"],
            render: () => <SeriesRegistrations seriesId={c.id} />,
          },
          {
            key: "dates",
            label: t("seriesSections.dates"),
            needs: ["event_unpublished"],
            render: () => <SeriesDates seriesId={c.id} />,
          },
          { key: "scoring", label: t("seriesSections.scoring"), render: () => <SeriesScoring seriesId={c.id} /> },
          { key: "officials", label: t("seriesSections.officials"), render: () => <SeriesOfficials seriesId={c.id} /> },
          { key: "news", label: t("workspace.sectionLabels.series.news"), render: () => <RegattaNews kind="series" id={c.id} /> },
        ];
      }}
    />
  );
}

/** The series' published events, each leading to my page for it when I am part of it. */
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
