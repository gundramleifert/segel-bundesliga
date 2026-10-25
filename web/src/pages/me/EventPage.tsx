import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { Stack } from "../../components/Layouts";
import { EventClaimsTab } from "./Money";
import { ClaimsTab } from "./Papers";
import { ContextFrame, Door, MyTeams, waiverNotice } from "./ContextFrame";


/** `/me/event/:id` — my crew and waiver, my claims, claims to decide, race control. */
export function EventPage() {
  const { t } = useTranslation("space");
  return (
    <ContextFrame
      kind="event"
      publicPath={(c) => (c.published ? `/events/${c.id}` : null)}
      sections={(c) => [
        c.series_id != null ? waiverNotice(t, "series", c.series_id) : waiverNotice(t, "event", c.id),
        {
          key: "crew",
          label: t("context.tabs.crew"),
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
        {
          // Those who work the event file claims on it (Story F-2); sailing is not work.
          key: "my-claims",
          label: t("context.tabs.myClaims"),
          needs: ["claim_rejected"],
          render: () => <ClaimsTab target={{ kind: "event", id: c.id }} />,
        },
        {
          key: "decide-claims",
          label: t("context.tabs.toDecide"),
          needs: ["claims"],
          render: () => <EventClaimsTab eventId={c.id} />,
        },
        {
          key: "race-control",
          label: t("context.tabs.raceControl"),
          render: () => (
            <Door
              text={t("context.raceControl")}
              to={`/events/${c.id}/race-control`}
              label={t("context.raceControlLink")}
              testId="me-event-race-control"
            />
          ),
        },
        {
          key: "general",
          label: t("context.tabs.organize"),
          render: () => (
            <Door
              text={t("context.organizeEvent")}
              to="/admin?tab=events"
              label={t("context.organizeLink")}
              testId="me-event-organize"
            />
          ),
        },
      ]}
    />
  );
}
