import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { Stack } from "../../components/Layouts";
import { EventClaimsTab } from "./Money";
import { ClaimsTab } from "./Papers";
import { ContextFrame, MyTeams, waiverNotice } from "./ContextFrame";
import { RegattaNews } from "./RegattaNews";
import { EventOverview, raceDaySections, setupSections } from "./event/EventSections";


/** `/me/event/:id` — my crew and waiver; the event's set-up and its race day for those
 *  who organize or run it (Story Z-10, #32); my claims, and the claims to decide. */
export function EventPage() {
  const { t } = useTranslation("space");
  return (
    <ContextFrame
      kind="event"
      publicPath={(c) => (c.published ? `/events/${c.id}` : null)}
      overview={(c) => <EventOverview context={c} />}
      sections={(c) => [
        c.series_id != null ? waiverNotice(t, "series", c.series_id) : waiverNotice(t, "event", c.id),
        {
          key: "crew",
          render: () => (
            <Stack gap={3}>
              <MyTeams context={c} testId="me-event-teams" />
              {c.published && (
                <Link to={`/events/${c.id}`} className="w-fit text-sm underline underline-offset-2" data-testid="me-event-crews-link">
                  {t("context.crewsAndPairings")}
                </Link>
              )}
            </Stack>
          ),
        },
        ...setupSections(t, c),
        ...raceDaySections(t, c),
        {
          // Those who work the event file claims on it (Story F-2); sailing is not work.
          key: "my-claims",
          needs: ["claim_rejected"],
          render: () => <ClaimsTab target={{ kind: "event", id: c.id }} />,
        },
        {
          key: "decide-claims",
          needs: ["claims"],
          render: () => <EventClaimsTab eventId={c.id} />,
        },
        { key: "news", render: () => <RegattaNews kind="event" id={c.id} /> },
      ]}
    />
  );
}
