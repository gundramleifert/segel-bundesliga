import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { useGetAdminEvent, useGetReadiness } from "../../../api/generated/sbl";
import { ContextRelation, EventStatus, type EventSummary, type MyContext } from "../../../api/types";
import { useAsync } from "../../../api/useApi";
import { AccessPanel } from "../../../components/AccessPanel";
import { Async } from "../../../components/Async";
import { Section } from "../../../components/Form";
import { Stack } from "../../../components/Layouts";
import { eventDates } from "../../../lib/format";
import { sectionPath } from "../../../lib/workspace";
import {
  EventClosing,
  EventClubs,
  EventDates,
  EventDraw,
  EventLifecycle,
  EventLiveUrl,
  EventPrint,
  EventReadiness,
  EventSquadLimits,
} from "../../admin/events/EventPanel";
import { ReadinessReasons } from "../../admin/events/ReadinessReasons";
import { WaiverChecklist } from "../../admin/events/WaiverChecklist";
import { NoticeBoard } from "../../league/act/NoticeBoard";
import { Door } from "../ContextFrame";
import type { WorkspaceSection } from "../Workspace";

/** Story Z-10 (#32): an event's own administration, as the sections of its context —
 *  *Set up* and *Race day* (`docs/PLAN_NAVIGATION.md` §3).
 *
 * **The blocks are the administration's, not copies.** Each section is assembled from the
 * blocks the event panel of `/admin?tab=events` is made of (`admin/events/EventPanel.tsx`),
 * with their test ids, so the two screens cannot drift apart while both exist. Who sees a
 * section is the declaration's business (`lib/workspace.ts`); the server asks the model
 * again on every request.
 *
 * Built only what has a screen today: *Boats* (no way to change an event's boats after it
 * is created), *Trackers* (no screen for the trackers yet) and the editorial *News* wait,
 * and the declaration leaves them out until they come. */

type T = (key: string, values?: Record<string, unknown>) => string;

/** The event as the administration reads it — drafts included, the configuration and the
 *  print settings with it (`GET /api/admin/events/{id}`, for its organizers and race
 *  committee). */
function WithEvent({ id, testId, children }: { id: number; testId: string; children: (event: EventSummary) => ReactNode }) {
  const event = useAsync(useGetAdminEvent(id));
  return (
    <Async state={event} testId={testId}>
      {children}
    </Async>
  );
}

/** A section's panel: its title and one block of the work. */
function Panel({ title, testId, children }: { title: string; testId: string; children: ReactNode }) {
  return (
    <Section title={title} testId={testId}>
      <Stack gap={5}>{children}</Stack>
    </Section>
  );
}

/** Title, series, host, venue and size, as they are — set when the event is created. */
function Facts({ event }: { event: EventSummary }) {
  const { t } = useTranslation("space");
  const { t: ta } = useTranslation("admin");
  const none = t("eventSections.notSet");
  const rows: [string, string, ReactNode][] = [
    ["title", t("eventSections.factTitle"), event.title],
    ["dates", t("eventSections.factDates"), eventDates(event) || none],
    ["series", t("eventSections.factSeries"), event.series?.name ?? t("eventSections.standalone")],
    ["host", t("eventSections.factHost"), event.host_club?.name ?? none],
    ["venue", t("eventSections.factVenue"), event.venue?.name ?? none],
    [
      "size",
      t("eventSections.factSize"),
      ta("manage.sizeText", { teams: event.team_count, boats: event.boat_count, flights: event.flight_count }),
    ],
  ];
  return (
    <dl className="grid grid-cols-[minmax(0,1fr)] gap-x-6 gap-y-2 text-sm sm:grid-cols-[auto_minmax(0,1fr)]" data-testid="me-event-facts">
      {rows.map(([key, label, value]) => (
        <div key={key} className="contents">
          <dt className="text-muted">{label}</dt>
          <dd className="font-medium" data-testid={`me-event-fact-${key}`}>
            {value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

/** *Set up* — general, clubs, pairing list, publication, people. */
export function setupSections(t: T, c: MyContext): WorkspaceSection[] {
  const id = c.id;
  return [
    {
      key: "general",
      label: t("eventSections.general"),
      render: () => (
        <Panel title={t("eventSections.general")} testId="me-event-general">
          <WithEvent id={id} testId="me-event-general">
            {(event) => (
              <>
                <Facts event={event} />
                <EventDates event={event} />
                <EventSquadLimits event={event} />
              </>
            )}
          </WithEvent>
        </Panel>
      ),
    },
    {
      key: "clubs",
      label: t("eventSections.clubs"),
      needs: ["registrations_open"],
      render: () => (
        <Panel title={t("eventSections.clubs")} testId="me-event-clubs">
          <WithEvent id={id} testId="me-event-clubs">
            {(event) => <EventClubs event={event} />}
          </WithEvent>
        </Panel>
      ),
    },
    {
      key: "pairing",
      label: t("eventSections.pairing"),
      render: () => (
        <Panel title={t("eventSections.pairing")} testId="me-event-pairing">
          <WithEvent id={id} testId="me-event-pairing">
            {(event) => (
              <>
                <EventDraw event={event} />
                <EventPrint event={event} />
              </>
            )}
          </WithEvent>
        </Panel>
      ),
    },
    {
      key: "publication",
      label: t("eventSections.publication"),
      needs: ["event_unpublished"],
      render: () => (
        <Panel title={t("eventSections.publication")} testId="me-event-publication">
          <WithEvent id={id} testId="me-event-publication">
            {(event) => (
              <>
                <EventReadiness event={event} />
                <EventLifecycle event={event} parts={{ publish: true }} />
                <EventLiveUrl event={event} />
              </>
            )}
          </WithEvent>
        </Panel>
      ),
    },
    {
      key: "people",
      label: t("eventSections.people"),
      render: () => (
        <Panel title={t("eventSections.people")} testId="me-event-people">
          <p className="text-sm text-muted">{t("eventSections.peopleHint")}</p>
          <AccessPanel object={`event:${id}`} testId={`me-event-access-${id}`} />
        </Panel>
      ),
    },
  ];
}

/** *Race day* — check-in, race control, results, notice board. */
export function raceDaySections(t: T, c: MyContext): WorkspaceSection[] {
  const id = c.id;
  return [
    {
      key: "check-in",
      label: t("eventSections.checkIn"),
      needs: ["checkin_waivers_missing"],
      render: () => (
        <Panel title={t("eventSections.checkIn")} testId="me-event-check-in">
          <WaiverChecklist eventId={id} />
        </Panel>
      ),
    },
    {
      key: "race-control",
      label: t("eventSections.raceControl"),
      render: () => (
        <Panel title={t("eventSections.raceControl")} testId="me-event-race-control">
          <Door
            text={t("eventSections.raceControlScreen")}
            to={`/events/${id}/race-control`}
            label={t("eventSections.raceControlLink")}
            testId="me-event-race-control-screen"
          />
          <WithEvent id={id} testId="me-event-race-control">
            {(event) => (
              <>
                <EventLifecycle event={event} parts={{ start: true }} />
                <EventClosing event={event} />
              </>
            )}
          </WithEvent>
        </Panel>
      ),
    },
    {
      key: "results",
      label: t("eventSections.results"),
      needs: ["results_missing"],
      render: () => (
        <Panel title={t("eventSections.results")} testId="me-event-results">
          {c.published ? (
            <Door
              text={t("eventSections.resultsText")}
              to={`/events/${id}/entry`}
              label={t("eventSections.resultsLink")}
              testId="me-event-results-entry"
            />
          ) : (
            <p className="text-sm text-muted" data-testid="me-event-results-draft">
              {t("eventSections.resultsDraft")}
            </p>
          )}
        </Panel>
      ),
    },
    {
      key: "notice-board",
      label: t("eventSections.noticeBoard"),
      render: () => (
        <Panel title={t("eventSections.noticeBoard")} testId="me-event-notice-board">
          <NoticeBoard event={{ id }} />
        </Panel>
      ),
    },
  ];
}

/** The overview's own part for the event's organizers: what still keeps a planned event
 *  from its draw and start (VA-8) — where the `event_not_ready` to-do leads — each reason
 *  one line, and the way to the set-up. Nothing while it is ready, or once it sails. */
export function EventOverview({ context }: { context: MyContext }) {
  const organizes = context.relations.some((r) => r === ContextRelation.admin || r === ContextRelation.manager);
  if (!organizes || context.status !== EventStatus.planned) return null;
  return <NotReady context={context} />;
}

function NotReady({ context }: { context: MyContext }) {
  const { t } = useTranslation("space");
  const readiness = useAsync(useGetReadiness(context.id));
  if (!readiness.data || readiness.data.ready) return null;
  return (
    <section className="flex flex-col gap-2 rounded-lg border border-separator p-4" data-testid="me-event-readiness">
      <h2 className="text-sm font-semibold text-foreground">{t("eventSections.notReadyTitle")}</h2>
      <ReadinessReasons
        reasons={readiness.data.reasons ?? []}
        testId="me-event-readiness-reasons"
        reasonTestId="me-event-readiness-reason"
        className="text-sm text-warning-soft-foreground"
      />
      <Link
        to={sectionPath({ kind: "event", id: context.id }, "general")}
        className="w-fit text-sm font-medium text-link underline-offset-2 hover:underline"
        data-testid="me-event-readiness-setup"
      >
        {t("eventSections.notReadyLink")} →
      </Link>
    </section>
  );
}
