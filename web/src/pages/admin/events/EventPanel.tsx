import { Button } from "@heroui/react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import {
  getGetAdminEventQueryKey,
  getGetReadinessQueryKey,
  getListAllEventsQueryKey,
  getListCandidateClubsQueryKey,
  getListParticipantsQueryKey,
  useCancelEvent,
  useFinishEvent,
  useGetReadiness,
  usePublishEvent,
  useReopenEvent,
  useStartEvent,
  useUnpublishEvent,
  useUpdateEvent,
} from "../../../api/generated/sbl";
import { EventStatus, type EventSummary } from "../../../api/types";
import { useAsync, useInvalidate } from "../../../api/useApi";
import { AccessPanel } from "../../../components/AccessPanel";
import { Async } from "../../../components/Async";
import { Field, Message } from "../../../components/Form";
import { Stack } from "../../../components/Layouts";
import { INPUT_CLASS, errorText } from "../../../lib/admin";
import { DrawControl } from "./DrawControl";
import { EventClubsEditor } from "./EventClubsEditor";
import { ReadinessReasons } from "./ReadinessReasons";
import { WaiverChecklist } from "./WaiverChecklist";

/** What the organizer stored about printing this event's pairing list (Story B-3).
 *
 *  The column is free-form JSON, so this reads defensively and falls back to what the
 *  backend itself falls back to: no font size means "derived from the configuration",
 *  and team pages are on unless someone turned them off.
 */
function printSettings(event: EventSummary): {
  fontSize: number | null;
  landscape: boolean;
  teamPages: boolean;
} {
  const raw = (event.print_settings ?? {}) as Record<string, unknown>;
  return {
    fontSize: typeof raw.font_size === "number" ? raw.font_size : null,
    landscape: raw.landscape === true,
    teamPages: raw.team_pages !== false,
  };
}

/** Everything a change to one event may have changed, refetched: the administration's
 *  list, the event as its own context reads it (Story Z-10), its readiness, its clubs,
 *  the public side — this event's own page and the calendar, a prefix covering
 *  `/api/events` as well as `/api/events/7/pairing` — and my space, whose to-dos
 *  (`event_not_ready`, `event_unpublished`) follow the set-up. */
export function useEventRefresh(eventId: number): () => void {
  const invalidate = useInvalidate();
  return () =>
    invalidate(
      getListAllEventsQueryKey(),
      getGetAdminEventQueryKey(eventId),
      getGetReadinessQueryKey(eventId),
      getListParticipantsQueryKey(eventId),
      getListCandidateClubsQueryKey(eventId),
      "/api/events",
      "/api/me/contexts",
    );
}

/** The event's readiness — one request, shared: every block below asks it, and the query
 *  cache answers them all from one response. */
function useReadiness(eventId: number) {
  const readiness = useAsync(useGetReadiness(eventId));
  return {
    readiness,
    frozen: readiness.data?.configuration_frozen ?? false,
    ready: readiness.data?.ready ?? false,
    hasPairing: readiness.data?.has_pairing_list ?? false,
  };
}

/** Everything an organizer still has to do to this event, in the order they do it.
 *
 * The panel deliberately mirrors `app/services/event_readiness.py` rather than inventing
 * its own rules: the reasons listed here are the same ones the draw and the start refuse
 * with, so the screen can never promise something the server then rejects.
 *
 * Each step is a block of its own, exported: the event's own context in the workspace
 * (Story Z-10, `pages/me/event/`) shows the same blocks as its *Set up* and *Race day*
 * sections, so the two screens cannot drift apart while both exist.
 */
export function EventPanel({ event }: { event: EventSummary }) {
  return (
    <Stack gap={5} className="mt-4  border-t border-separator pt-4" testId={`admin-manage-event-panel-${event.id}`}>
      {/* 1. What's missing */}
      <EventReadiness event={event} />
      {/* 2. The date, once the host confirms it */}
      <EventDates event={event} />
      {/* 3. Who enters */}
      <EventClubs event={event} />
      {/* 4. The draw */}
      <EventDraw event={event} />
      {/* 5. How it prints */}
      <EventPrint event={event} />
      {/* 5b. Where the live view is */}
      <EventLiveUrl event={event} />
      {/* 5b'. Squad size, stand-alone events only (Story V-1) */}
      <EventSquadLimits event={event} />
      {/* 5c. Liability waivers (Stories VA-5, S-1) */}
      <WaiverChecklist eventId={event.id} />
      <AccessPanel object={`event:${event.id}`} testId={`admin-event-access-${event.id}`} />
      {/* 6. Publication and start */}
      <EventLifecycle event={event} />
      {/* 7. Closing it */}
      <EventClosing event={event} />
    </Stack>
  );
}

/** Step 1: what still keeps the event from its draw and start (VA-8), and whether racing
 *  has frozen its configuration. */
export function EventReadiness({ event }: { event: EventSummary }) {
  const { t } = useTranslation("admin");
  const { readiness, frozen } = useReadiness(event.id);
  return (
    <div>
      <h3 className="text-sm font-semibold text-foreground">{t("manage.readinessTitle")}</h3>
      <Async
        state={readiness}
        testId={`admin-readiness-${event.id}`}
        loadingText={t("manage.readinessLoadingText")}
      >
        {(data) =>
          data.ready ? (
            <p data-testid={`admin-readiness-ready-${event.id}`} className="mt-1 text-sm text-success-soft-foreground">
              {t("manage.readyMessage")}
            </p>
          ) : (
            <ReadinessReasons
              reasons={data.reasons ?? []}
              testId={`admin-readiness-reasons-${event.id}`}
              reasonTestId="admin-readiness-reason"
              className="text-sm text-warning-soft-foreground"
            />
          )
        }
      </Async>
      {frozen && (
        <p
          data-testid={`admin-readiness-frozen-${event.id}`}
          className="mt-2 rounded-md bg-surface-secondary px-3 py-2 text-sm text-muted"
        >
          {t("manage.frozenMessage", {
            races: readiness.data?.races_started ?? 0,
            results: readiness.data?.results_recorded ?? 0,
          })}
        </p>
      )}
    </div>
  );
}

/** Step 2: the dates, once the host confirms them. */
export function EventDates({ event }: { event: EventSummary }) {
  const { t } = useTranslation("admin");
  const refresh = useEventRefresh(event.id);
  const [startsOn, setStartsOn] = useState(event.starts_on ?? "");
  const [endsOn, setEndsOn] = useState(event.ends_on ?? "");
  const saveDates = useUpdateEvent({ mutation: { onSuccess: refresh } });
  return (
    <Stack gap={3}>
      <div className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
        <Field label={t("events.startsLabel")}>
          <input
            className={INPUT_CLASS}
            type="date"
            value={startsOn}
            onChange={(e) => setStartsOn(e.target.value)}
            data-testid={`admin-manage-event-starts-${event.id}`}
          />
        </Field>
        <Field label={t("events.endsLabel")} hint={t("events.endsHint")}>
          <input
            className={INPUT_CLASS}
            type="date"
            value={endsOn}
            min={startsOn || undefined}
            onChange={(e) => setEndsOn(e.target.value)}
            data-testid={`admin-manage-event-ends-${event.id}`}
          />
        </Field>
        <Button
          size="sm"
          isDisabled={saveDates.isPending}
          onPress={() =>
            saveDates.mutate({
              eventId: event.id,
              data: { starts_on: startsOn || null, ends_on: endsOn || startsOn || null },
            })
          }
          data-testid={`admin-manage-event-save-dates-${event.id}`}
        >
          {saveDates.isPending ? t("manage.savingButton") : t("manage.saveDatesButton")}
        </Button>
      </div>
      <Message
        testId={`admin-manage-event-dates-message-${event.id}`}
        error={saveDates.isError ? errorText(saveDates.error) : null}
        success={saveDates.isSuccess ? t("manage.datesSavedMessage") : null}
      />
    </Stack>
  );
}

/** Step 3: who enters. */
export function EventClubs({ event }: { event: EventSummary }) {
  const { t } = useTranslation("admin");
  const refresh = useEventRefresh(event.id);
  const { frozen } = useReadiness(event.id);
  return (
    <EventClubsEditor
      event={event}
      testId={`admin-manage-event-clubs-${event.id}`}
      saveTestId={`admin-manage-event-save-clubs-${event.id}`}
      saveLabel={(count) => t("manage.saveClubsButton", { count })}
      messageTestId={`admin-manage-event-clubs-message-${event.id}`}
      savedText={t("manage.clubsSavedMessage")}
      frozen={frozen}
      onSaved={refresh}
    />
  );
}

/** Step 4: the draw from the catalog (VA-7). */
export function EventDraw({ event }: { event: EventSummary }) {
  const { t } = useTranslation("admin");
  const refresh = useEventRefresh(event.id);
  const { frozen, ready, hasPairing } = useReadiness(event.id);
  return (
    <Stack gap={3}>
      <h3 className="text-sm font-semibold text-foreground">{t("manage.pairingTitle")}</h3>
      <p className="text-sm text-muted">
        {hasPairing ? t("manage.pairingExistsHint") : t("manage.pairingMissingHint")}
      </p>
      <DrawControl
        eventId={event.id}
        ready={ready}
        frozen={frozen}
        hasPairing={hasPairing}
        testIds={{
          field: `admin-manage-event-seed-field-${event.id}`,
          seed: `admin-manage-event-seed-${event.id}`,
          button: `admin-manage-event-draw-${event.id}`,
          message: `admin-manage-event-draw-message-${event.id}`,
        }}
        hint={
          !ready && !frozen && <p className="text-sm text-muted">{t("manage.drawNeedsReadyHint")}</p>
        }
        successText={t("manage.drawSuccessMessage")}
        onDrawn={refresh}
      >
        {hasPairing && (
          <Link
            to={`/events/${event.id}`}
            data-testid={`admin-manage-event-pairing-link-${event.id}`}
            className="text-sm underline underline-offset-2"
          >
            {t("manage.openPairingLink")}
          </Link>
        )}
      </DrawControl>
    </Stack>
  );
}

/** Step 5: how the pairing list prints (Story B-3). Empty font size means "whatever the
 *  configuration implies" — the backend derives it, and that is the normal case. */
export function EventPrint({ event }: { event: EventSummary }) {
  const { t } = useTranslation("admin");
  const refresh = useEventRefresh(event.id);
  const stored = printSettings(event);
  const [fontSize, setFontSize] = useState(stored.fontSize === null ? "" : String(stored.fontSize));
  const [landscape, setLandscape] = useState(stored.landscape);
  const [teamPages, setTeamPages] = useState(stored.teamPages);
  // Its own mutation rather than sharing one with the dates: two save buttons that report
  // into one message would each claim the other's success.
  const savePrint = useUpdateEvent({ mutation: { onSuccess: refresh } });
  return (
    <Stack gap={3}>
      <h3 className="text-sm font-semibold text-foreground">{t("manage.printTitle")}</h3>
      <p className="text-sm text-muted">{t("manage.printHint")}</p>
      <div className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-[1fr_auto_auto_auto] sm:items-end">
        <Field label={t("manage.printFontLabel")} hint={t("manage.printFontHint")}>
          <input
            className={INPUT_CLASS}
            type="number"
            min={5}
            max={16}
            value={fontSize}
            placeholder={t("manage.printFontAuto")}
            onChange={(e) => setFontSize(e.target.value)}
            data-testid={`admin-manage-event-print-font-${event.id}`}
          />
        </Field>
        <label className="flex items-center gap-1.5 text-sm sm:pb-2">
          <input
            type="checkbox"
            checked={landscape}
            onChange={(e) => setLandscape(e.target.checked)}
            data-testid={`admin-manage-event-print-landscape-${event.id}`}
          />
          {t("manage.printLandscapeLabel")}
        </label>
        <label className="flex items-center gap-1.5 text-sm sm:pb-2">
          <input
            type="checkbox"
            checked={teamPages}
            onChange={(e) => setTeamPages(e.target.checked)}
            data-testid={`admin-manage-event-print-team-pages-${event.id}`}
          />
          {t("manage.printTeamPagesLabel")}
        </label>
        <Button
          size="sm"
          isDisabled={savePrint.isPending}
          onPress={() =>
            savePrint.mutate({
              eventId: event.id,
              data: {
                print_settings: {
                  font_size: fontSize ? Number(fontSize) : null,
                  landscape,
                  team_pages: teamPages,
                },
              },
            })
          }
          data-testid={`admin-manage-event-save-print-${event.id}`}
        >
          {savePrint.isPending ? t("manage.savingButton") : t("manage.savePrintButton")}
        </Button>
      </div>
      <Message
        testId={`admin-manage-event-print-message-${event.id}`}
        error={savePrint.isError ? errorText(savePrint.error) : null}
        success={savePrint.isSuccess ? t("manage.printSavedMessage") : null}
      />
    </Stack>
  );
}

/** Step 5b: where the live view is — the internal map unless the event names an external
 *  one (Story L-1). */
export function EventLiveUrl({ event }: { event: EventSummary }) {
  const { t } = useTranslation("admin");
  const refresh = useEventRefresh(event.id);
  const [liveUrl, setLiveUrl] = useState(event.live_url ?? "");
  const saveLive = useUpdateEvent({ mutation: { onSuccess: refresh } });
  return (
    <Stack gap={3}>
      <h3 className="text-sm font-semibold text-foreground">{t("manage.liveTitle")}</h3>
      <p className="text-sm text-muted">{t("manage.liveHint")}</p>
      <div className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
        <Field label={t("manage.liveUrlLabel")} hint={t("manage.liveUrlHint")}>
          <input
            className={INPUT_CLASS}
            type="url"
            value={liveUrl}
            placeholder={t("manage.liveInternal")}
            onChange={(e) => setLiveUrl(e.target.value)}
            data-testid={`admin-manage-event-live-url-${event.id}`}
          />
        </Field>
        <Button
          size="sm"
          isDisabled={saveLive.isPending}
          onPress={() => saveLive.mutate({ eventId: event.id, data: { live_url: liveUrl.trim() || null } })}
          data-testid={`admin-manage-event-save-live-${event.id}`}
        >
          {saveLive.isPending ? t("manage.savingButton") : t("manage.saveLiveButton")}
        </Button>
      </div>
      <Message
        testId={`admin-manage-event-live-message-${event.id}`}
        error={saveLive.isError ? errorText(saveLive.error) : null}
        success={saveLive.isSuccess ? t(liveUrl.trim() ? "manage.liveSavedExternal" : "manage.liveSavedInternal") : null}
      />
    </Stack>
  );
}

/** Step 5b': the squad's size (Story V-1) — a stand-alone event carries its own; a series
 *  event uses its series' limits, so nothing renders for one. */
export function EventSquadLimits({ event }: { event: EventSummary }) {
  const { t } = useTranslation("admin");
  const invalidate = useInvalidate();
  const [squadMin, setSquadMin] = useState(String(event.squad_min));
  const [squadMax, setSquadMax] = useState(String(event.squad_max));
  // A prefix: the administration's list and the event as its context reads it alike.
  const saveSquadLimits = useUpdateEvent({
    mutation: { onSuccess: () => invalidate("/api/admin/events", "/api/events", "/api/clubs") },
  });
  if (event.series) return null;
  return (
    <Stack gap={3}>
      <h3 className="text-sm font-semibold text-foreground">{t("manage.squadLimitsTitle")}</h3>
      <p className="text-sm text-muted">{t("manage.squadLimitsHint")}</p>
      <div className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-[auto_auto_auto] sm:items-end">
        <Field label={t("manage.squadMinLabel")}>
          <input
            type="number"
            min={1}
            max={50}
            className={INPUT_CLASS}
            value={squadMin}
            onChange={(e) => setSquadMin(e.target.value)}
            data-testid={`admin-manage-event-squad-min-${event.id}`}
          />
        </Field>
        <Field label={t("manage.squadMaxLabel")}>
          <input
            type="number"
            min={1}
            max={50}
            className={INPUT_CLASS}
            value={squadMax}
            onChange={(e) => setSquadMax(e.target.value)}
            data-testid={`admin-manage-event-squad-max-${event.id}`}
          />
        </Field>
        <Button
          size="sm"
          isDisabled={saveSquadLimits.isPending || !squadMin || !squadMax}
          onPress={() =>
            saveSquadLimits.mutate({
              eventId: event.id,
              data: { squad_min: Number(squadMin), squad_max: Number(squadMax) },
            })
          }
          data-testid={`admin-manage-event-save-squad-limits-${event.id}`}
        >
          {saveSquadLimits.isPending ? t("manage.savingButton") : t("manage.saveSquadLimitsButton")}
        </Button>
      </div>
      <Message
        testId={`admin-manage-event-squad-limits-message-${event.id}`}
        error={saveSquadLimits.isError ? errorText(saveSquadLimits.error) : null}
        success={saveSquadLimits.isSuccess ? t("manage.squadLimitsSavedMessage") : null}
      />
    </Stack>
  );
}

/** Which parts of the publication-and-start block a screen shows. The administration's
 *  panel shows all; the workspace splits them — publishing is *Set up › Publication*, the
 *  start and the race committee's screen *Race day › Race control* (Story Z-10). */
export type LifecycleParts = { publish?: boolean; start?: boolean; links?: boolean };

/** Step 6: publication and start. Publishing and withdrawing are two endpoints, so the
 *  screen picks by what the event currently is rather than passing a flag. */
export function EventLifecycle({
  event,
  parts = { publish: true, start: true, links: true },
}: {
  event: EventSummary;
  parts?: LifecycleParts;
}) {
  const { t } = useTranslation("admin");
  const refresh = useEventRefresh(event.id);
  const { ready, hasPairing } = useReadiness(event.id);
  const publishEvent = usePublishEvent({ mutation: { onSuccess: refresh } });
  const unpublishEvent = useUnpublishEvent({ mutation: { onSuccess: refresh } });
  const publish = event.published ? unpublishEvent : publishEvent;
  const start = useStartEvent({ mutation: { onSuccess: refresh } });
  return (
    <Stack gap={3}>
      <h3 className="text-sm font-semibold text-foreground">{t("manage.lifecycleTitle")}</h3>
      {parts.publish && <p className="text-sm text-muted">{t("manage.publishHint")}</p>}
      <div className="flex flex-wrap items-center gap-3">
        {parts.publish && (
          <Button
            size="sm"
            variant={event.published ? "ghost" : "primary"}
            isDisabled={publish.isPending}
            onPress={() => publish.mutate({ eventId: event.id })}
            data-testid={`admin-manage-event-publish-${event.id}`}
          >
            {event.published ? t("manage.unpublishButton") : t("manage.publishButton")}
          </Button>
        )}
        {parts.start && (
          <Button
            size="sm"
            isDisabled={start.isPending || !ready || !hasPairing || event.status === EventStatus.live}
            onPress={() => start.mutate({ eventId: event.id })}
            data-testid={`admin-manage-event-start-${event.id}`}
          >
            {event.status === EventStatus.live ? t("manage.startedButton") : t("manage.startButton")}
          </Button>
        )}
        {parts.links && (
          <>
            <Link
              to={`/events/${event.id}`}
              data-testid={`admin-manage-event-results-link-${event.id}`}
              className="text-sm underline underline-offset-2"
            >
              {t("manage.openResultsLink")}
            </Link>
            {/* Story WL-3: the committee's screen on the water, a page of its own. */}
            <Link
              to={`/events/${event.id}/race-control`}
              data-testid={`admin-manage-event-race-control-link-${event.id}`}
              className="text-sm underline underline-offset-2"
            >
              {t("manage.openRaceControlLink")}
            </Link>
          </>
        )}
      </div>
      {parts.start && event.status !== EventStatus.live && (!ready || !hasPairing) && (
        <p className="text-sm text-muted">{t("manage.startNeedsHint")}</p>
      )}
      <Message
        testId={`admin-manage-event-lifecycle-message-${event.id}`}
        error={publish.isError ? errorText(publish.error) : start.isError ? errorText(start.error) : null}
        success={start.isSuccess ? t("manage.startedMessage") : null}
      />
    </Stack>
  );
}

/** Step 7: closing it (Story VA-10). Last, because it is the last thing done to an event —
 *  and because putting "Call off" next to "Publish" invites the wrong press.
 *
 *  Three endpoints, but one decision from the screen's point of view — this day is over,
 *  one way or the other — and only one of them is ever offered at a time, so the block
 *  reads them as a single `closing`. Only the transitions that apply are rendered: a
 *  permanently disabled "Reopen" under every planned event would be noise on a screen that
 *  has to stay usable at 412 px (Story A-10), and its reason is simply that the event is
 *  not closed, which the status badge already says.
 *
 *  Neither closing asks for confirmation. Both undo with one press and neither deletes
 *  anything — not the pairing list, not a single result — so a dialog would buy nothing
 *  and cost a tap on a rocking boat. */
export function EventClosing({ event }: { event: EventSummary }) {
  const { t } = useTranslation("admin");
  const refresh = useEventRefresh(event.id);
  const finish = useFinishEvent({ mutation: { onSuccess: refresh } });
  const cancel = useCancelEvent({ mutation: { onSuccess: refresh } });
  const reopen = useReopenEvent({ mutation: { onSuccess: refresh } });
  const closing = [finish, cancel, reopen];
  const closingPending = closing.some((m) => m.isPending);
  const closingError = closing.find((m) => m.isError)?.error ?? null;
  // Closed as in "declared over", not as in "locked": results stay editable forever and
  // both closings undo with one press. This only decides which buttons are offered.
  const closed = event.status === EventStatus.final || event.status === EventStatus.cancelled;
  return (
    <Stack gap={3} testId={`admin-manage-event-closing-${event.id}`}>
      <h3 className="text-sm font-semibold text-foreground">{t("manage.closingTitle")}</h3>
      <p className="text-sm text-muted">
        {closed
          ? t(event.status === EventStatus.final ? "manage.finishedHint" : "manage.cancelledHint")
          : t("manage.closingHint")}
      </p>
      <div className="flex flex-wrap items-center gap-3">
        {closed ? (
          <Button
            size="sm"
            isDisabled={closingPending}
            onPress={() => reopen.mutate({ eventId: event.id })}
            data-testid={`admin-manage-event-reopen-${event.id}`}
          >
            {t(event.status === EventStatus.final ? "manage.reopenFinishedButton" : "manage.reopenCancelledButton")}
          </Button>
        ) : (
          <>
            {/* Finishing needs a live event — a day that never started cannot be over, and
                the server says so with `event-not-started`. It deliberately does **not**
                need complete results: demanding all 48 races would disable this exactly on
                the day the wind died after flight 13. */}
            <Button
              size="sm"
              isDisabled={closingPending || event.status !== EventStatus.live}
              onPress={() => finish.mutate({ eventId: event.id })}
              data-testid={`admin-manage-event-finish-${event.id}`}
            >
              {t("manage.finishButton")}
            </Button>
            {/* Available from `planned` as well as `live`: a day is called off before
                anyone leaves the dock at least as often as halfway through. */}
            <Button
              size="sm"
              variant="ghost"
              isDisabled={closingPending}
              onPress={() => cancel.mutate({ eventId: event.id })}
              data-testid={`admin-manage-event-cancel-${event.id}`}
            >
              {t("manage.cancelButton")}
            </Button>
          </>
        )}
      </div>
      {!closed && event.status !== EventStatus.live && (
        <p className="text-sm text-muted">{t("manage.finishNeedsLiveHint")}</p>
      )}
      <Message
        testId={`admin-manage-event-closing-message-${event.id}`}
        error={closingError ? errorText(closingError) : null}
      />
    </Stack>
  );
}
