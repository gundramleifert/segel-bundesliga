import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import type { EventSummary } from "../../api/types";
import { Badge, StatusBadge } from "../../components/Blocks";
import { eventDates } from "../../lib/format";
import { sectionPath } from "../../lib/workspace";

/** Events as rows, each opening the event's own context (`/me/event/<id>`) — a club's
 *  *Hosting* and a series' *Events* for its organizers (Story Z-10): an object's admin work
 *  is done in its own context, so a list of them is a way there, not an editor. The
 *  matchday stands before the title when the event has one; a draft says so. */
export function EventLinks({ events, testId }: { events: EventSummary[]; testId: string }) {
  const { t } = useTranslation("space");
  return (
    <ul className="flex flex-col divide-y divide-separator" data-testid={`${testId}-list`}>
      {events.map((event) => (
        <li key={event.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2 text-sm" data-testid={`${testId}-${event.id}`}>
          <Link
            to={sectionPath({ kind: "event", id: event.id })}
            className="min-w-0 flex-1 font-medium underline-offset-2 hover:underline"
            data-testid={`${testId}-${event.id}-link`}
          >
            {event.matchday != null && <span className="mr-1 text-muted">{t("clubSections.matchday", { n: event.matchday })}</span>}
            {event.title}
          </Link>
          <span className="text-muted">{eventDates(event)}</span>
          <StatusBadge status={event.status} testId={`${testId}-${event.id}-status`} />
          {!event.published && (
            <Badge tone="warning" testId={`${testId}-${event.id}-draft`}>
              {t("clubSections.draft")}
            </Badge>
          )}
        </li>
      ))}
    </ul>
  );
}
