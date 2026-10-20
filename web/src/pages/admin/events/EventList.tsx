import { Button } from "@heroui/react";
import { keepPreviousData } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { useListAllEvents } from "../../../api/generated/sbl";
import type { EventSummary } from "../../../api/types";
import { useAsync } from "../../../api/useApi";
import { AddButton } from "../../../components/AddButton";
import { Async } from "../../../components/Async";
import { StatusBadge } from "../../../components/Blocks";
import { Field, Section } from "../../../components/Form";
import { Pager } from "../../../components/Pager";
import { INPUT_CLASS } from "../../../lib/admin";
import { eventDates } from "../../../lib/format";
import { useListParams } from "../../../lib/listParams";
import { EventPanel } from "./EventPanel";
import { PublicationBadge } from "./PublicationBadge";

/** Stories A-4, VA-6, VA-7 and VA-8: scheduling an event and taking it through its life.
 *
 * Two jobs, two places. **Creating** an event is three steps — general data, clubs,
 * pairing list (Story VA-6, `Wizard.tsx`) — of which only the first is required: an event
 * with no date, no clubs and the wrong boat count is the normal early state, not an error
 * (Story VA-8). **Managing** an event, this list, is where the rest arrives or changes:
 * the date once the host confirms it, the clubs, the draw, publication, and finally the
 * start. Those steps are ordered but not a state machine — publication is orthogonal to
 * status, validity is computed rather than stored, and only the first race freezes
 * anything.
 *
 * The tab is the list; creating is its own page, `/admin/events/new`, reached from the
 * "＋" top-right of it (`AdminEventNew`).
 */
export function EventsAdmin() {
  const { t } = useTranslation("admin");
  // The admin list, not the public one: a draft has to appear on the very screen whose
  // job is to finish and publish it.
  // Paged with the page in the URL (Story A-13). Deliberately **not** the shared
  // `DataTable`: every row here opens an editor — readiness, clubs, the draw, publication,
  // closing — so this is a list of panels, not a table of values.
  const list = useListParams();
  const events = useAsync(
    useListAllEvents(
      { ...list.request, q: list.q || undefined },
      { query: { placeholderData: keepPreviousData } },
    ),
  );

  return (
    <Section
      title={t("manage.title")}
      testId="admin-manage-events-section"
      action={
        <AddButton label={t("events.wizardTitle")} to="/admin/events/new" testId="admin-events-new-button" />
      }
    >
      <Field label={t("manage.searchLabel")} hint={t("manage.searchHint")}>
        <input
          className={INPUT_CLASS}
          value={list.q}
          onChange={(e) => list.setQuery(e.target.value)}
          placeholder={t("manage.searchPlaceholder")}
          data-testid="admin-manage-events-search-input"
        />
      </Field>

      <Async
        state={events}
        testId="admin-manage-events"
        loadingText={t("manage.loadingText")}
        empty={t("manage.emptyText")}
        isEmpty={(page) => page.items.length === 0}
      >
        {(page) => (
          <ul
            data-testid="admin-manage-events-list"
            className="divide-y divide-separator rounded-lg border border-separator"
          >
            {page.items.map((event) => (
              <EventRow key={event.id} event={event} />
            ))}
          </ul>
        )}
      </Async>
      <Pager
        page={events.data}
        current={list.page}
        onPage={list.setPage}
        testId="admin-manage-events"
      />
    </Section>
  );
}

function EventRow({ event }: { event: EventSummary }) {
  const { t } = useTranslation("admin");
  const [open, setOpen] = useState(false);

  return (
    <li data-testid={`admin-manage-event-row-${event.id}`} className="px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Link
              to={`/events/${event.id}`}
              data-testid={`admin-manage-event-link-${event.id}`}
              className="font-medium underline-offset-2 hover:underline"
            >
              {event.title}
            </Link>
            <StatusBadge status={event.status} testId={`admin-manage-event-status-${event.id}`} />
            <PublicationBadge published={event.published ?? false} testId={`admin-manage-event-publication-${event.id}`} />
          </div>
          <p className="text-sm text-muted">
            {[
              event.series ? event.series.name : t("manage.standaloneLabel"),
              eventDates(event),
              t("manage.sizeText", {
                teams: event.team_count,
                boats: event.boat_count,
                flights: event.flight_count,
              }),
            ].join(" · ")}
          </p>
        </div>
        <Button
          size="sm"
          variant="ghost"
          onPress={() => setOpen((o) => !o)}
          data-testid={`admin-manage-event-toggle-${event.id}`}
        >
          {open ? t("manage.closeButton") : t("manage.manageButton")}
        </Button>
      </div>

      {/* Mounted only while open: the readiness of every event is a request each, and the
          list can be long. One click is a fair price for not firing them all at once. */}
      {open && <EventPanel event={event} />}
    </li>
  );
}
