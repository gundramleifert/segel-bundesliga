import { Button } from "@heroui/react";
import { keepPreviousData } from "@tanstack/react-query";
import { useState, type FormEvent, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { Stack } from "../components/Layouts";
import {
  getListAllEventsQueryKey,
  getGetReadinessQueryKey,
  getListParticipantsQueryKey,
  useCancelEvent,
  useCreateEvent,
  useEventWaivers,
  useFinishEvent,
  useGetPairing,
  useGetReadiness,
  useListAllClubs,
  useListAllEvents,
  useListAllSeries,
  useListPairingCatalog,
  useListParticipants,
  usePairingFromCatalog,
  usePublishEvent,
  useReopenEvent,
  useSetParticipants,
  useStartEvent,
  useUnpublishEvent,
  useUpdateEvent,
  getGetWaiverScanUrl,
  getDownloadPairingPdfUrl,
} from "../api/generated/sbl";
import type {
  BoatSpec,
  ClubAdmin,
  EventSummary,
  ReadinessReason,
  SeriesAdmin,
} from "../api/types";
import { WHOLE_LIST, useAsync, useAsyncRows, useInvalidate } from "../api/useApi";
import { Pager } from "../components/Pager";
import { useListParams } from "../lib/listParams";
import { ErrorMessage, Loading, Empty, StatusBadge, TableFrame } from "../components/Blocks";
import i18n from "../i18n";
import { BOAT_COLORS, boatColor, eventDates } from "../lib/format";
import { INPUT_CLASS, errorText, toggleSet } from "../lib/admin";
import { openFile } from "../lib/files";
import { Section, Field, Message } from "../components/Form";
import { ClubSelector } from "../components/ClubSelector";
import { Steps } from "../components/Steps";
import { AddButton } from "../components/AddButton";

/** Stories A-4, VA-6, VA-7 and VA-8: scheduling an event and taking it through its life.
 *
 * Two sections, because they are two different jobs. **Creating** an event is three steps
 * — general data, clubs, pairing list (Story VA-6) — of which only the first is required:
 * an event with no date, no clubs and the wrong boat count is the normal early state, not
 * an error (Story VA-8), so the first step deliberately gates almost nothing and the
 * other two can be skipped. **Managing** an event is where the rest arrives or changes:
 * the date once the host confirms it, the clubs, the draw, publication, and finally the
 * start. Those steps are ordered but not a
 * state machine — publication is orthogonal to status, validity is computed rather than
 * stored, and only the first race freezes anything.
 */

/** The league's predefined boat colors, in pairing-list order — the first six are the
 *  backend's own `BOAT_COLORS` (`app/models/racing.py`); `WHITE` is a UI-only addition on top
 *  (`lib/format.ts`), a real, sensible hull color and the fallback whenever a boat must have
 *  *some* color but none has been chosen — "no color" is deliberately not a choice here (the
 *  backend column is a free string either way, so this is a UI convention, not a schema one). */
const PREDEFINED_COLORS = Object.keys(BOAT_COLORS);

/** Sentinel select value for "type your own color" — distinct from every real color string. */
const CUSTOM_COLOR = "__custom__";

interface BoatRow {
  color: string;
  customColor: string;
  name: string;
}

/** The color the backend would assign by position if boats aren't configured explicitly:
 *  the predefined colors in order, `WHITE` beyond that — never "no color". */
function defaultColor(position: number): string {
  return position <= PREDEFINED_COLORS.length ? PREDEFINED_COLORS[position - 1] : "WHITE";
}

/** Default name for a freshly added row — "Boat 1".."Boat N" by position, unique by
 *  construction and a clearer starting point than an empty required field. Freely
 *  editable afterwards; a rename is never overwritten by a later resize. */
function defaultName(position: number): string {
  return i18n.t("admin:events.boatDefaultName", { number: position });
}

/** A fresh row's `customColor` starts out matching its predefined default, not empty — the
 *  picker and free-text field are always visible now (not just once "Custom" is chosen), so
 *  they need a real value to show from the very first render, not a black fallback. */
function emptyBoatRow(position: number): BoatRow {
  const color = defaultColor(position);
  return { color, customColor: boatColor(color).hex, name: defaultName(position) };
}

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

/** `<input type="color">` needs a well-formed 6-digit hex or it silently resets to black —
 *  falls back to black only for the picker's own value, the free-text field keeps showing
 *  whatever was actually typed. */
function hexForPicker(text: string): string {
  const trimmed = text.trim();
  return /^#[0-9a-f]{6}$/i.test(trimmed) ? trimmed.toLowerCase() : "#000000";
}

/** Resizes the boat rows to a new boat count — growing appends default rows, shrinking
 *  trims from the end, and rows in between keep whatever was already entered. Called from
 *  the size selector's `onChange`, not an effect: the boat count only ever changes because
 *  of that one event, so deriving it there avoids a redundant extra render. */
function resizedBoatRows(prev: BoatRow[], target: number): BoatRow[] {
  if (target === prev.length) return prev;
  if (target < prev.length) return prev.slice(0, target);
  const additional = Array.from({ length: target - prev.length }, (_, i) =>
    emptyBoatRow(prev.length + i + 1),
  );
  return [...prev, ...additional];
}

/** Builds the `boats` array position by position — `number` is the row's position, `color`
 *  resolves the custom-color sentinel to its free-text value. The name is required (the
 *  sail number is not collected here); `sail_number` stays null. */
function boatSpecs(rows: BoatRow[]): BoatSpec[] {
  return rows.map((row, index) => ({
    number: index + 1,
    color: row.color === CUSTOM_COLOR ? row.customColor.trim() || "#ffffff" : row.color || "WHITE",
    name: row.name.trim(),
    sail_number: null,
  }));
}

/** Whether every row has the name it now requires — gates the submit button. */
function boatNamesComplete(rows: BoatRow[]): boolean {
  return rows.every((row) => row.name.trim().length > 0);
}

/** Identifies a catalog size for the <select> — teams, boats and flights together. */
function catalogKey(entry: { teams: number; boats: number; flights: number }): string {
  return `${entry.teams}-${entry.boats}-${entry.flights}`;
}

export function EventsAdmin() {
  // The screen opens on the list; the "＋" top-right opens the wizard under the header,
  // above the list, only while an event is being created (Story VA-6).
  const [creating, setCreating] = useState(false);
  return (
    <ManageEvents
      creating={creating}
      onNew={() => setCreating(true)}
      onClose={() => setCreating(false)}
    />
  );
}

// ------------------------------------------------------------------ Creating

type WizardStep = 1 | 2 | 3 | "done";

/** The three steps a new event is created in, in the order the work happens (Story VA-6):
 *  general data, the clubs that enter, the pairing list. The event **exists after step 1**
 *  — the create request is that step's submit — so everything after it works on a saved
 *  event through the same endpoints the manage panel uses, and each later step can be
 *  skipped and finished there. The closing screen says whether the event is ready and
 *  offers publication, because the calendar entry often precedes the field. */
function CreateEventWizard({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation("admin");
  const [step, setStep] = useState<WizardStep>(1);
  const [event, setEvent] = useState<EventSummary | null>(null);

  return (
    <Stack
      gap={4}
      testId="admin-events-section"
      className="rounded-lg border border-brand-200 bg-brand-50/40 p-4"
    >
      <h3 className="text-base font-semibold">{t("events.wizardTitle")}</h3>
      <Steps
        testId="admin-events-steps"
        current={step === "done" ? 4 : step}
        steps={[t("events.stepGeneral"), t("events.stepClubs"), t("events.stepPairing")]}
      />
      {/* The creation message stays up through the later steps: the event is saved, and
          the steps that follow are refinements of it, not conditions on it. */}
      {event && (
        <Message
          testId="admin-events-create-message"
          error={null}
          success={t("events.createdMessage", { title: event.title })}
        />
      )}
      {step === 1 && (
        <GeneralDataStep
          onCreated={(created) => {
            setEvent(created);
            setStep(2);
          }}
          onCancel={onClose}
        />
      )}
      {step === 2 && event && (
        <ClubsStep event={event} onNext={() => setStep(3)} onSkip={() => setStep("done")} />
      )}
      {step === 3 && event && (
        <PairingStep
          event={event}
          onDone={() => setStep("done")}
          onBack={() => setStep(2)}
          onSkip={() => setStep("done")}
        />
      )}
      {step === "done" && event && (
        <ReadyStep
          event={event}
          onChanged={setEvent}
          onAnother={() => {
            setEvent(null);
            setStep(1);
          }}
          onClose={onClose}
        />
      )}
    </Stack>
  );
}

/** A row of the wizard's buttons: the way forward first, the ways out after it. */
function StepActions({ children }: { children: ReactNode }) {
  return <div className="flex flex-wrap items-center gap-3">{children}</div>;
}

/** Step 1: name, dates, series, host, size and boats — and the create request. Only the
 *  title and the boat names gate it: a missing date and the wrong number of clubs are the
 *  normal early state, which the next steps and the manage panel report and fix
 *  (Story VA-8). */
function GeneralDataStep({
  onCreated,
  onCancel,
}: {
  onCreated: (event: EventSummary) => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation("admin");
  // Selectors, so the whole list rather than a page: a dropdown offering the first
  // twenty-five series is one that cannot pick the twenty-sixth (Story A-13).
  const seriesList = useAsyncRows(useListAllSeries({ limit: WHOLE_LIST }));
  const clubs = useAsyncRows(useListAllClubs({ limit: WHOLE_LIST }));
  // Only pre-computed sizes are offered here — picking a free combination of teams,
  // boats and flights would mean drawing a pairing list from scratch later, an
  // optimization run that takes minutes, not seconds (see app/pairing/catalog.py).
  const catalog = useAsync(useListPairingCatalog());
  const invalidate = useInvalidate();

  const [title, setTitle] = useState("");
  const [startsOn, setStartsOn] = useState("");
  const [endsOn, setEndsOn] = useState("");
  const [seriesId, setSeriesId] = useState("");
  const [hostClubId, setHostClubId] = useState("");
  const [teams, setTeams] = useState("18");
  const [boats, setBoats] = useState("6");
  const [flights, setFlights] = useState("16");
  const [boatRows, setBoatRows] = useState<BoatRow[]>(() =>
    Array.from({ length: 6 }, (_, i) => emptyBoatRow(i + 1)),
  );

  const updateBoat = (index: number, patch: Partial<BoatRow>) =>
    setBoatRows((prev) =>
      prev.map((row, i) => (i === index ? { ...row, ...patch } : row)),
    );

  const create = useCreateEvent({
    mutation: {
      onSuccess: (event) => {
        invalidate("/api/admin/events", "/api/admin/series", "/api/events", "/api/series");
        onCreated(event);
      },
    },
  });

  return (
    <>
      <form
        data-testid="admin-events-create-form"
        className="grid grid-cols-[minmax(0,1fr)] gap-3"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          create.mutate({
            data: {
              title: title.trim(),
              // Empty means "not agreed with the host yet", which is savable — the date
              // is needed to *start* the event, not to write it down (Story VA-8).
              starts_on: startsOn || null,
              ends_on: endsOn || null,
              series: seriesId ? Number(seriesId) : null,
              host_club_id: hostClubId ? Number(hostClubId) : null,
              team_count: Number(teams),
              boat_count: Number(boats),
              flight_count: Number(flights),
              boats: boatSpecs(boatRows),
              // Saved as a draft. Publication is a separate, reversible decision on the
              // wizard's last screen and in the manage panel — it changes only who can
              // see the event (Story VA-8).
              published: false,
            },
          });
        }}
      >
        <div className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-[2fr_1fr_1fr]">
          <Field label={t("events.nameLabel")}>
            <input
              className={INPUT_CLASS}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              minLength={3}
              placeholder={t("events.namePlaceholder")}
              data-testid="admin-events-title-input"
            />
          </Field>
          <Field label={t("events.startsLabel")} hint={t("events.startsHint")}>
            <input
              className={INPUT_CLASS}
              type="date"
              value={startsOn}
              onChange={(e) => setStartsOn(e.target.value)}
              data-testid="admin-events-starts-input"
            />
          </Field>
          <Field label={t("events.endsLabel")} hint={t("events.endsHint")}>
            <input
              className={INPUT_CLASS}
              type="date"
              value={endsOn}
              onChange={(e) => setEndsOn(e.target.value)}
              min={startsOn || undefined}
              data-testid="admin-events-ends-input"
            />
          </Field>
        </div>

        <div className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-2">
          <Field label={t("events.seriesLabel")} hint={t("events.seriesHint")}>
            <select
              className={INPUT_CLASS}
              value={seriesId}
              onChange={(e) => setSeriesId(e.target.value)}
              data-testid="admin-events-series-select"
            >
              <option value="">{t("events.seriesNone")}</option>
              {seriesList.data?.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t("events.hostLabel")} hint={t("events.hostHint")}>
            <select
              className={INPUT_CLASS}
              value={hostClubId}
              onChange={(e) => setHostClubId(e.target.value)}
              data-testid="admin-events-host-select"
            >
              <option value="">{t("events.hostNone")}</option>
              {clubs.data?.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name}
                </option>
              ))}
            </select>
          </Field>
        </div>

        <Field label={t("events.setupLabel")} hint={t("events.setupHint")}>
          {catalog.loading && <Loading text={t("events.catalogLoadingText")} testId="admin-events-catalog-loading" />}
          {catalog.error && <ErrorMessage text={catalog.error} testId="admin-events-catalog-error" />}
          {catalog.data && catalog.data.length > 0 && (
            <select
              className={INPUT_CLASS}
              value={catalogKey({ teams: Number(teams), boats: Number(boats), flights: Number(flights) })}
              onChange={(e) => {
                const entry = catalog.data?.find(
                  (candidate) => catalogKey(candidate) === e.target.value,
                );
                if (!entry) return;
                setTeams(String(entry.teams));
                setBoats(String(entry.boats));
                setFlights(String(entry.flights));
                setBoatRows((prev) => resizedBoatRows(prev, entry.boats));
              }}
              data-testid="admin-events-catalog-select"
            >
              {catalog.data.map((entry) => (
                <option key={catalogKey(entry)} value={catalogKey(entry)}>
                  {t("events.catalogOption", {
                    teams: entry.teams,
                    boats: entry.boats,
                    flights: entry.flights,
                  })}
                </option>
              ))}
            </select>
          )}
          {catalog.data && catalog.data.length === 0 && (
            <ErrorMessage text={t("events.catalogEmptyText")} testId="admin-events-catalog-empty" />
          )}
        </Field>

        <p className="text-sm text-slate-500">
          {t("events.formatText", { teams, boats, races: Math.ceil(Number(teams) / Number(boats)) || 0 })}
        </p>

        <p className="text-sm text-slate-500">
          {t("events.catalogContactHint")}{" "}
          <a
            href="https://github.com/gundramleifert"
            target="_blank"
            rel="noreferrer"
            className="underline"
          >
            github.com/gundramleifert
          </a>
        </p>

        <Field label={t("events.boatSetupLabel")}>
          <div className="overflow-x-auto rounded-md border border-slate-200">
            <table data-testid="admin-events-boat-table" className="data-table w-full min-w-[44rem] text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
                  <th scope="col" className="font-medium">
                    {t("events.boatNumberLabel")}
                  </th>
                  <th scope="col" className="font-medium">
                    {t("events.boatColorLabel")}
                  </th>
                  <th scope="col" className="font-medium">
                    {t("events.boatNameLabel")}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {boatRows.map((row, index) => (
                  <tr key={index}>
                    <td className="text-slate-500">{index + 1}</td>
                    <td>
                      {/* `INPUT_CLASS` is `w-full` by default — every control here overrides that
                       *  to a fixed or growing-but-bounded width instead, so all three
                       *  controls stay on one line; the table's own `overflow-x-auto` wrapper
                       *  is the fallback on narrow screens, not wrapping within the row.
                       *
                       *  All three are always shown, not just once "Custom" is picked: the
                       *  select is the plain named choice, the picker is the only place the
                       *  color itself is actually visible, and the text field is the same
                       *  value as typable text. Picking a named color in the select copies its
                       *  hex into the picker/text (so "the dropdown sets the picker"); editing
                       *  the picker or the text field the other way switches the select to
                       *  "Custom" (so a hand-picked color never sits silently under a named
                       *  option it no longer matches). */}
                      <div className="flex flex-nowrap items-center gap-2">
                        <select
                          className={`${INPUT_CLASS.replace("w-full", "w-32")} shrink-0`}
                          aria-label={`${t("events.boatColorLabel")} ${index + 1}`}
                          value={row.color}
                          onChange={(e) => {
                            const nextColor = e.target.value;
                            updateBoat(index, {
                              color: nextColor,
                              customColor:
                                nextColor === CUSTOM_COLOR
                                  ? row.customColor
                                  : boatColor(nextColor).hex,
                            });
                          }}
                          data-testid={`admin-events-boat-color-select-${index}`}
                        >
                          {PREDEFINED_COLORS.map((code) => (
                            <option key={code} value={code}>
                              {t(`common:boatColor.${code}`)}
                            </option>
                          ))}
                          <option value={CUSTOM_COLOR}>{t("events.boatColorCustom")}</option>
                        </select>
                        <input
                          type="color"
                          className="h-9 w-9 shrink-0 cursor-pointer rounded border border-slate-300 p-0.5"
                          value={hexForPicker(row.customColor)}
                          onChange={(e) =>
                            updateBoat(index, { color: CUSTOM_COLOR, customColor: e.target.value })
                          }
                          aria-label={t("events.boatColorPickerLabel")}
                          data-testid={`admin-events-boat-color-picker-${index}`}
                        />
                        <input
                          className={`${INPUT_CLASS.replace("w-full", "min-w-[6rem]")} flex-1`}
                          value={row.customColor}
                          onChange={(e) =>
                            updateBoat(index, { color: CUSTOM_COLOR, customColor: e.target.value })
                          }
                          placeholder={t("events.boatColorCustomPlaceholder")}
                          aria-label={t("events.boatColorCustomPlaceholder")}
                          data-testid={`admin-events-boat-color-custom-input-${index}`}
                        />
                      </div>
                    </td>
                    <td>
                      <input
                        className={INPUT_CLASS}
                        value={row.name}
                        onChange={(e) => updateBoat(index, { name: e.target.value })}
                        required
                        placeholder={t("events.boatNamePlaceholder")}
                        aria-label={`${t("events.boatNameLabel")} ${index + 1}`}
                        data-testid={`admin-events-boat-name-input-${index}`}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Field>

        <StepActions>
          {/* Only the title and the boat names gate saving. A missing date, no clubs and a
              boat count that doesn't match are all things the next steps and the manage
              panel report and fix — refusing to save them would mean nothing could be
              written down until everything was known (Story VA-8). */}
          <Button
            type="submit"
            isDisabled={
              create.isPending ||
              title.trim().length < 3 ||
              !catalog.data?.length ||
              !boatNamesComplete(boatRows)
            }
            data-testid="admin-events-create-button"
          >
            {create.isPending ? t("events.creatingButton") : t("events.createButton")}
          </Button>
          <Button size="sm" variant="ghost" onPress={onCancel} data-testid="admin-events-cancel-button">
            {t("events.cancelButton")}
          </Button>
        </StepActions>
      </form>

      <Message
        testId="admin-events-create-message"
        error={create.isError ? errorText(create.error) : null}
        success={null}
      />
    </>
  );
}

/** Step 2: who enters. The candidates are the series' registered clubs when the event
 *  belongs to one — the backend enforces exactly that (`app/services/participation.py`) —
 *  and every club when it stands alone. A series' registrations were adopted at creation,
 *  so they arrive pre-selected; the step is then a confirmation, not a search. */
function ClubsStep({
  event,
  onNext,
  onSkip,
}: {
  event: EventSummary;
  onNext: () => void;
  onSkip: () => void;
}) {
  const { t } = useTranslation("admin");
  const invalidate = useInvalidate();
  const seriesList = useAsyncRows(useListAllSeries({ limit: WHOLE_LIST }));
  const clubs = useAsyncRows(useListAllClubs({ limit: WHOLE_LIST }));
  const participants = useAsync(useListParticipants(event.id));
  const [selectedClubs, setSelectedClubs] = useState<Set<number> | null>(null);

  const series = event.series ? seriesList.data?.find((s) => s.id === event.series?.id) : undefined;
  const candidates = event.series ? (series?.clubs ?? []) : (clubs.data ?? []);
  const loading = participants.loading || (event.series ? seriesList.loading : clubs.loading);

  // Server state until the first click, the local set afterwards (see `EventPanel`).
  const entered = new Set((participants.data ?? []).map((p) => p.club.id));
  const selection = selectedClubs ?? entered;
  const toggle = toggleSet((updater) => setSelectedClubs((prev) => updater(prev ?? entered)));

  const save = useSetParticipants({
    mutation: {
      onSuccess: () => {
        invalidate("/api/admin/events", "/api/events");
        onNext();
      },
    },
  });

  return (
    <Stack gap={3}>
      <h3 className="text-sm font-semibold text-slate-700" data-testid="admin-events-clubs-count">
        {t("manage.clubsTitle", { count: selection.size, configured: event.team_count })}
      </h3>
      <p className="text-sm text-slate-600">
        {event.series
          ? t("manage.clubsFromSeriesHint", { series: event.series.name })
          : t("manage.clubsStandaloneHint")}
      </p>
      {loading && <Loading text={t("manage.clubsLoadingText")} testId="admin-events-clubs-loading" />}
      {participants.error && <ErrorMessage text={participants.error} testId="admin-events-clubs-error" />}
      {!loading && !candidates.length ? (
        <Empty testId="admin-events-clubs-empty">
          {event.series ? t("manage.seriesHasNoClubs") : t("manage.noClubsAtAll")}
        </Empty>
      ) : (
        !loading && (
          <ClubSelector
            clubs={candidates}
            selectedIds={selection}
            toggle={toggle}
            testId="admin-events-clubs"
          />
        )
      )}
      {selection.size !== event.team_count && (
        <p className="text-sm text-amber-800" data-testid="admin-events-clubs-mismatch">
          {t("events.clubsCountHint", { expected: event.team_count, actual: selection.size })}
        </p>
      )}
      <StepActions>
        <Button
          size="sm"
          isDisabled={save.isPending || loading}
          onPress={() => save.mutate({ eventId: event.id, data: { clubs: [...selection] } })}
          data-testid="admin-events-clubs-next-button"
        >
          {save.isPending
            ? t("manage.savingButton")
            : t("events.clubsNextButton", { count: selection.size })}
        </Button>
        {/* The field can be entered later — a standalone regatta collects its clubs over
            weeks, and the manage panel has the same selector. */}
        <Button size="sm" variant="ghost" onPress={onSkip} data-testid="admin-events-clubs-skip-button">
          {t("events.skipButton")}
        </Button>
      </StepActions>
      <Message
        testId="admin-events-clubs-message"
        error={save.isError ? errorText(save.error) : null}
        success={null}
      />
    </Stack>
  );
}

/** Step 3: the draw (Story VA-7). Refused visibly while the setup is incomplete — the
 *  same readiness reasons the server would answer with — rather than fired blind the
 *  way the old automatic draw was, which for a new event without clubs failed every time
 *  and made that failure the first thing the organizer read. */
function PairingStep({
  event,
  onDone,
  onBack,
  onSkip,
}: {
  event: EventSummary;
  onDone: () => void;
  onBack: () => void;
  onSkip: () => void;
}) {
  const { t } = useTranslation("admin");
  const invalidate = useInvalidate();
  const readiness = useAsync(useGetReadiness(event.id));
  // Default matches the backend's own default seed (`PairingJobRequest.seed` in
  // app/schemas/admin.py) — same seed, same draw, reproducible if it ever needs proving.
  const [seed, setSeed] = useState("1240");
  const ready = readiness.data?.ready ?? false;

  const draw = usePairingFromCatalog({
    mutation: {
      onSuccess: () => {
        invalidate("/api/admin/events", "/api/events", getGetReadinessQueryKey(event.id));
        onDone();
      },
    },
  });

  return (
    <Stack gap={3}>
      <h3 className="text-sm font-semibold text-slate-700">{t("manage.pairingTitle")}</h3>
      <p className="text-sm text-slate-600">{t("manage.pairingMissingHint")}</p>
      {readiness.loading && (
        <Loading text={t("manage.readinessLoadingText")} testId="admin-events-draw-readiness-loading" />
      )}
      {readiness.error && <ErrorMessage text={readiness.error} testId="admin-events-draw-readiness-error" />}
      {readiness.data && !ready && (
        <div data-testid="admin-events-draw-blocked" className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
          <p>{t("events.drawBlockedHint")}</p>
          <ul data-testid="admin-events-draw-reasons" className="mt-1 grid grid-cols-[minmax(0,1fr)] gap-1">
            {(readiness.data.reasons ?? []).map((reason) => (
              <li key={reason.code} data-testid={`admin-events-draw-reason-${reason.code}`}>
                · {reasonText(reason)}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="flex flex-wrap items-end gap-3">
        <Field label={t("events.seedLabel")} hint={t("events.seedHint")} testId="admin-events-draw-seed-field">
          <input
            className={`${INPUT_CLASS.replace("w-full", "w-28")}`}
            type="number"
            value={seed}
            onChange={(e) => setSeed(e.target.value)}
            data-testid="admin-events-draw-seed-input"
          />
        </Field>
      </div>
      <StepActions>
        <Button
          size="sm"
          isDisabled={draw.isPending || !ready}
          onPress={() => draw.mutate({ eventId: event.id, data: { seed: Number(seed) || 1240 } })}
          data-testid="admin-events-draw-button"
        >
          {draw.isPending ? t("manage.drawingButton") : t("manage.drawButton")}
        </Button>
        <Button size="sm" variant="ghost" onPress={onBack} data-testid="admin-events-draw-back-button">
          {t("events.backButton")}
        </Button>
        <Button size="sm" variant="ghost" onPress={onSkip} data-testid="admin-events-draw-skip-button">
          {t("events.skipButton")}
        </Button>
      </StepActions>
      <Message
        testId="admin-events-draw-message"
        error={draw.isError ? errorText(draw.error) : null}
        success={null}
      />
    </Stack>
  );
}

/** The closing screen: ready 🚀, or what is still missing and where it is finished. It
 *  offers publication here because the calendar entry often precedes the field (Story
 *  VA-8), and — once published with a list — the pairing list and its PDF, which are
 *  public pages and therefore exist only for a published event. */
function ReadyStep({
  event,
  onChanged,
  onAnother,
  onClose,
}: {
  event: EventSummary;
  onChanged: (event: EventSummary) => void;
  onAnother: () => void;
  onClose: () => void;
}) {
  const { t } = useTranslation("admin");
  const invalidate = useInvalidate();
  const readiness = useAsync(useGetReadiness(event.id));
  const ready = readiness.data?.ready ?? false;
  const hasPairing = readiness.data?.has_pairing_list ?? false;
  const complete = ready && hasPairing;
  const published = event.published ?? false;
  // The public pairing endpoint: a draft answers 404 there, so it is asked only once the
  // event is published — and it is what says whether this server can print (Story B-3).
  const pairing = useGetPairing(event.id, { query: { enabled: published && hasPairing } });
  const pdfAvailable = pairing.data?.pdf_available ?? false;

  const refresh = () => invalidate("/api/admin/events", "/api/events", "/api/series");
  const publishEvent = usePublishEvent({
    mutation: { onSuccess: (updated) => { refresh(); onChanged(updated); } },
  });
  const unpublishEvent = useUnpublishEvent({
    mutation: { onSuccess: (updated) => { refresh(); onChanged(updated); } },
  });
  const publish = published ? unpublishEvent : publishEvent;

  return (
    <Stack gap={3}>
      <div data-testid="admin-events-ready" data-ready={complete ? "true" : "false"}>
        {readiness.loading && (
          <Loading text={t("manage.readinessLoadingText")} testId="admin-events-ready-loading" />
        )}
        {readiness.error && <ErrorMessage text={readiness.error} testId="admin-events-ready-error" />}
        {readiness.data && (
          <>
            <h3
              data-testid="admin-events-ready-title"
              className={`text-base font-semibold ${complete ? "text-emerald-700" : "text-slate-800"}`}
            >
              {complete ? t("events.readyTitle") : t("events.notReadyTitle")}
            </h3>
            {!complete && (
              <>
                <ul
                  data-testid="admin-events-ready-reasons"
                  className="mt-1 grid grid-cols-[minmax(0,1fr)] gap-1 text-sm text-amber-800"
                >
                  {(readiness.data.reasons ?? []).map((reason) => (
                    <li key={reason.code} data-testid={`admin-events-ready-reason-${reason.code}`}>
                      · {reasonText(reason)}
                    </li>
                  ))}
                  {!hasPairing && (
                    <li data-testid="admin-events-ready-missing-pairing">· {t("events.missingPairing")}</li>
                  )}
                </ul>
                <p className="mt-2 text-sm text-slate-600">{t("events.finishLaterHint")}</p>
              </>
            )}
          </>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <PublicationBadge published={published} eventId={event.id} testId="admin-events-publication" />
        <Button
          size="sm"
          variant={published ? "ghost" : "primary"}
          isDisabled={publish.isPending}
          onPress={() => publish.mutate({ eventId: event.id })}
          data-testid="admin-events-publish-button"
        >
          {published ? t("manage.unpublishButton") : t("manage.publishButton")}
        </Button>
        {published && hasPairing && (
          <Link
            to={`/events/${event.id}`}
            data-testid="admin-events-pairing-link"
            className="text-sm underline underline-offset-2"
          >
            {t("manage.openPairingLink")}
          </Link>
        )}
        {/* A plain anchor, not a generated hook: the answer is a PDF, and `api/http.ts`
            parses everything it handles as JSON (see `Matchday.tsx`). Shown only where the
            server can print, because a link whose only answer is 503 is worse than none. */}
        {published && hasPairing && pdfAvailable && (
          <a
            href={getDownloadPairingPdfUrl(event.id)}
            download
            data-testid="admin-events-pairing-pdf-link"
            className="text-sm font-medium text-brand-700 underline-offset-2 hover:underline"
          >
            {t("events.pairingPdfLink")}
          </a>
        )}
      </div>
      <p className="text-sm text-slate-600">
        {!published && hasPairing ? t("events.publishToShareHint") : t("manage.publishHint")}
      </p>
      <Message
        testId="admin-events-publish-message"
        error={publish.isError ? errorText(publish.error) : null}
        success={null}
      />

      <StepActions>
        <Button size="sm" onPress={onClose} data-testid="admin-events-close-button">
          {t("events.closeButton")}
        </Button>
        <Button size="sm" variant="ghost" onPress={onAnother} data-testid="admin-events-another-button">
          {t("events.anotherButton")}
        </Button>
      </StepActions>
    </Stack>
  );
}

// ------------------------------------------------------------------ Managing

function ManageEvents({
  creating,
  onNew,
  onClose,
}: {
  creating: boolean;
  onNew: () => void;
  onClose: () => void;
}) {
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
  // Both feed selectors inside each row's panel, so both want the whole list.
  const seriesList = useAsyncRows(useListAllSeries({ limit: WHOLE_LIST }));
  const clubs = useAsyncRows(useListAllClubs({ limit: WHOLE_LIST }));

  return (
    <Section
      title={t("manage.title")}
      testId="admin-manage-events-section"
      action={
        !creating && (
          <AddButton
            label={t("events.wizardTitle")}
            onPress={onNew}
            testId="admin-events-new-button"
          />
        )
      }
    >
      {creating && <CreateEventWizard onClose={onClose} />}
      <Field label={t("manage.searchLabel")} hint={t("manage.searchHint")}>
        <input
          className={INPUT_CLASS}
          value={list.q}
          onChange={(e) => list.setQuery(e.target.value)}
          placeholder={t("manage.searchPlaceholder")}
          data-testid="admin-manage-events-search-input"
        />
      </Field>

      {events.loading && <Loading text={t("manage.loadingText")} testId="admin-manage-events-loading" />}
      {events.error && <ErrorMessage text={events.error} testId="admin-manage-events-error" />}
      {events.data &&
        (events.data.items.length ? (
          <ul
            data-testid="admin-manage-events-list"
            className="divide-y divide-slate-100 rounded-lg border border-slate-200"
          >
            {events.data.items.map((event) => (
              <EventRow
                key={event.id}
                event={event}
                seriesList={seriesList.data ?? []}
                clubs={clubs.data ?? []}
              />
            ))}
          </ul>
        ) : (
          <Empty testId="admin-manage-events-empty">{t("manage.emptyText")}</Empty>
        ))}
      <Pager
        page={events.data}
        current={list.page}
        onPage={list.setPage}
        testId="admin-manage-events"
      />
    </Section>
  );
}

function EventRow({
  event,
  seriesList,
  clubs,
}: {
  event: EventSummary;
  seriesList: SeriesAdmin[];
  clubs: ClubAdmin[];
}) {
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
            <PublicationBadge published={event.published ?? false} eventId={event.id} />
          </div>
          <p className="text-sm text-slate-600">
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
      {open && <EventPanel event={event} seriesList={seriesList} clubs={clubs} />}
    </li>
  );
}

function PublicationBadge({
  published,
  eventId,
  testId,
}: {
  published: boolean;
  eventId: number;
  testId?: string;
}) {
  const { t } = useTranslation("admin");
  return (
    <span
      data-testid={testId ?? `admin-manage-event-publication-${eventId}`}
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${
        published
          ? "bg-brand-50 text-brand-800 ring-brand-200"
          : "bg-amber-50 text-amber-800 ring-amber-200"
      }`}
    >
      {published ? t("manage.publishedBadge") : t("manage.draftBadge")}
    </span>
  );
}

/** Everything an organizer still has to do to this event, in the order they do it.
 *
 * The panel deliberately mirrors `app/services/event_readiness.py` rather than inventing
 * its own rules: the reasons listed here are the same ones the draw and the start refuse
 * with, so the screen can never promise something the server then rejects.
 */
function EventPanel({
  event,
  seriesList,
  clubs,
}: {
  event: EventSummary;
  seriesList: SeriesAdmin[];
  clubs: ClubAdmin[];
}) {
  const { t } = useTranslation("admin");
  const invalidate = useInvalidate();
  const readiness = useAsync(useGetReadiness(event.id));
  const participants = useAsync(useListParticipants(event.id));

  const [startsOn, setStartsOn] = useState(event.starts_on ?? "");
  const [endsOn, setEndsOn] = useState(event.ends_on ?? "");
  const [seed, setSeed] = useState("1240");
  // Print settings for the pairing list (Story B-3). Empty font size means "whatever the
  // configuration implies" — the backend derives it, and that is the normal case.
  const stored = printSettings(event);
  const [fontSize, setFontSize] = useState(stored.fontSize === null ? "" : String(stored.fontSize));
  const [landscape, setLandscape] = useState(stored.landscape);
  const [teamPages, setTeamPages] = useState(stored.teamPages);
  // Story L-1: the live view is the internal map unless the event names an external one.
  const [liveUrl, setLiveUrl] = useState(event.live_url ?? "");
  // Story V-1: a stand-alone event carries its own squad size; a series event uses its
  // series' limits, so the block below appears only without a series.
  const [squadMin, setSquadMin] = useState(String(event.squad_min));
  const [squadMax, setSquadMax] = useState(String(event.squad_max));
  const saveSquadLimits = useUpdateEvent({
    mutation: { onSuccess: () => invalidate("/api/admin/events", "/api/events", "/api/clubs") },
  });
  const [selectedClubs, setSelectedClubs] = useState<Set<number> | null>(null);

  // Which clubs may be entered at all: the series' registered clubs when the event belongs
  // to one — the backend enforces exactly that (`app/services/participation.py`) — and
  // every club when it stands alone, which is the case that makes this site a service to
  // clubs outside the association's own series.
  const series = event.series ? seriesList.find((s) => s.id === event.series?.id) : undefined;
  const candidates = event.series ? (series?.clubs ?? []) : clubs;

  // Server state until the first click, the local set afterwards. Seeding `useState` from
  // the query instead would freeze whatever the first render happened to see — the query
  // is still pending then, so it would freeze an empty selection.
  const entered = new Set((participants.data ?? []).map((p) => p.club.id));
  const selection = selectedClubs ?? entered;
  const toggle = toggleSet((updater) =>
    setSelectedClubs((prev) => updater(prev ?? entered)),
  );

  const refresh = () =>
    invalidate(
      getListAllEventsQueryKey(),
      getGetReadinessQueryKey(event.id),
      getListParticipantsQueryKey(event.id),
      // The public side too: this event's own page and the calendar both show what just
      // changed, and a prefix covers `/api/events` as well as `/api/events/7/pairing`.
      "/api/events",
    );

  const saveDates = useUpdateEvent({ mutation: { onSuccess: refresh } });

  // Its own mutation rather than sharing `saveDates`: two save buttons that report into one
  // message would each claim the other's success.
  const savePrint = useUpdateEvent({ mutation: { onSuccess: refresh } });
  const saveLive = useUpdateEvent({ mutation: { onSuccess: refresh } });

  const saveClubs = useSetParticipants({
    mutation: {
      onSuccess: () => {
        setSelectedClubs(null);
        refresh();
      },
    },
  });

  const draw = usePairingFromCatalog({ mutation: { onSuccess: refresh } });

  // Publishing and withdrawing are two endpoints, so the screen picks by what the event
  // currently is rather than passing a flag.
  const publishEvent = usePublishEvent({ mutation: { onSuccess: refresh } });
  const unpublishEvent = useUnpublishEvent({ mutation: { onSuccess: refresh } });
  const publish = event.published ? unpublishEvent : publishEvent;

  const start = useStartEvent({ mutation: { onSuccess: refresh } });

  // Story VA-10. Three endpoints, but one decision from the screen's point of view —
  // this day is over, one way or the other — and only one of them is ever offered at a
  // time, so the block reads them as a single `closing`.
  const finish = useFinishEvent({ mutation: { onSuccess: refresh } });
  const cancel = useCancelEvent({ mutation: { onSuccess: refresh } });
  const reopen = useReopenEvent({ mutation: { onSuccess: refresh } });
  const closing = [finish, cancel, reopen];
  const closingPending = closing.some((m) => m.isPending);
  const closingError = closing.find((m) => m.isError)?.error ?? null;

  const frozen = readiness.data?.configuration_frozen ?? false;
  const ready = readiness.data?.ready ?? false;
  const hasPairing = readiness.data?.has_pairing_list ?? false;
  // Closed as in "declared over", not as in "locked": results stay editable forever and
  // both closings undo with one press (Story VA-10). This only decides which buttons the
  // closing block offers.
  const closed = event.status === "final" || event.status === "cancelled";

  return (
    <Stack gap={5} className="mt-4  border-t border-slate-100 pt-4">
      {/* 1. What's missing --------------------------------------------------- */}
      <div>
        <h3 className="text-sm font-semibold text-slate-700">{t("manage.readinessTitle")}</h3>
        {readiness.loading && (
          <Loading text={t("manage.readinessLoadingText")} testId={`admin-readiness-loading-${event.id}`} />
        )}
        {readiness.error && (
          <ErrorMessage text={readiness.error} testId={`admin-readiness-error-${event.id}`} />
        )}
        {readiness.data &&
          (ready ? (
            <p
              data-testid={`admin-readiness-ready-${event.id}`}
              className="mt-1 text-sm text-emerald-700"
            >
              {t("manage.readyMessage")}
            </p>
          ) : (
            <ul
              data-testid={`admin-readiness-reasons-${event.id}`}
              className="mt-1 grid grid-cols-[minmax(0,1fr)] gap-1 text-sm text-amber-800"
            >
              {(readiness.data.reasons ?? []).map((reason) => (
                <li key={reason.code} data-testid={`admin-readiness-reason-${reason.code}`}>
                  · {reasonText(reason)}
                </li>
              ))}
            </ul>
          ))}
        {frozen && (
          <p
            data-testid={`admin-readiness-frozen-${event.id}`}
            className="mt-2 rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-600"
          >
            {t("manage.frozenMessage", {
              races: readiness.data?.races_started ?? 0,
              results: readiness.data?.results_recorded ?? 0,
            })}
          </p>
        )}
      </div>

      {/* 2. The date, once the host confirms it ----------------------------- */}
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

      {/* 3. Who enters ------------------------------------------------------ */}
      <Stack gap={3}>
        <h3 className="text-sm font-semibold text-slate-700">
          {t("manage.clubsTitle", { count: selection.size, configured: event.team_count })}
        </h3>
        <p className="text-sm text-slate-600">
          {event.series
            ? t("manage.clubsFromSeriesHint", { series: event.series.name })
            : t("manage.clubsStandaloneHint")}
        </p>
        {participants.loading && (
          <Loading text={t("manage.clubsLoadingText")} testId={`admin-manage-event-clubs-loading-${event.id}`} />
        )}
        {participants.error && (
          <ErrorMessage
            text={participants.error}
            testId={`admin-manage-event-clubs-error-${event.id}`}
          />
        )}
        {!candidates.length ? (
          <Empty testId={`admin-manage-event-clubs-empty-${event.id}`}>
            {event.series ? t("manage.seriesHasNoClubs") : t("manage.noClubsAtAll")}
          </Empty>
        ) : (
          <>
            <ClubSelector
              clubs={candidates}
              selectedIds={selection}
              toggle={toggle}
              testId={`admin-manage-event-clubs-${event.id}`}
            />
            <div className="flex flex-wrap items-center gap-3">
              <Button
                size="sm"
                isDisabled={saveClubs.isPending || frozen}
                onPress={() => saveClubs.mutate({ eventId: event.id, data: { clubs: [...selection] } })}
                data-testid={`admin-manage-event-save-clubs-${event.id}`}
              >
                {saveClubs.isPending
                  ? t("manage.savingButton")
                  : t("manage.saveClubsButton", { count: selection.size })}
              </Button>
              {frozen && (
                <span className="text-sm text-slate-500">{t("manage.frozenClubsHint")}</span>
              )}
            </div>
          </>
        )}
        <Message
          testId={`admin-manage-event-clubs-message-${event.id}`}
          error={saveClubs.isError ? errorText(saveClubs.error) : null}
          success={saveClubs.isSuccess ? t("manage.clubsSavedMessage") : null}
        />
      </Stack>

      {/* 4. The draw -------------------------------------------------------- */}
      <Stack gap={3}>
        <h3 className="text-sm font-semibold text-slate-700">{t("manage.pairingTitle")}</h3>
        <p className="text-sm text-slate-600">
          {hasPairing ? t("manage.pairingExistsHint") : t("manage.pairingMissingHint")}
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <Field label={t("events.seedLabel")} testId={`admin-manage-event-seed-field-${event.id}`}>
            <input
              className={`${INPUT_CLASS.replace("w-full", "w-28")}`}
              type="number"
              value={seed}
              onChange={(e) => setSeed(e.target.value)}
              data-testid={`admin-manage-event-seed-${event.id}`}
            />
          </Field>
          <Button
            size="sm"
            isDisabled={draw.isPending || frozen || !ready}
            onPress={() => draw.mutate({ eventId: event.id, data: { seed: Number(seed) || 1240 } })}
            data-testid={`admin-manage-event-draw-${event.id}`}
          >
            {draw.isPending
              ? t("manage.drawingButton")
              : hasPairing
                ? t("manage.redrawButton")
                : t("manage.drawButton")}
          </Button>
          {hasPairing && (
            <Link
              to={`/events/${event.id}`}
              data-testid={`admin-manage-event-pairing-link-${event.id}`}
              className="text-sm underline underline-offset-2"
            >
              {t("manage.openPairingLink")}
            </Link>
          )}
        </div>
        {!ready && !frozen && (
          <p className="text-sm text-slate-500">{t("manage.drawNeedsReadyHint")}</p>
        )}
        <Message
          testId={`admin-manage-event-draw-message-${event.id}`}
          error={draw.isError ? errorText(draw.error) : null}
          success={draw.isSuccess ? t("manage.drawSuccessMessage") : null}
        />
      </Stack>

      {/* 5. How it prints ---------------------------------------------------- */}
      <Stack gap={3}>
        <h3 className="text-sm font-semibold text-slate-700">{t("manage.printTitle")}</h3>
        <p className="text-sm text-slate-600">{t("manage.printHint")}</p>
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

      {/* 5b. Where the live view is ------------------------------------------ */}
      <Stack gap={3}>
        <h3 className="text-sm font-semibold text-slate-700">{t("manage.liveTitle")}</h3>
        <p className="text-sm text-slate-600">{t("manage.liveHint")}</p>
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
            onPress={() =>
              saveLive.mutate({ eventId: event.id, data: { live_url: liveUrl.trim() || null } })
            }
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

      {/* 5b'. Squad size, stand-alone events only (Story V-1) ------------------- */}
      {!event.series && (
        <Stack gap={3}>
          <h3 className="text-sm font-semibold text-slate-700">{t("manage.squadLimitsTitle")}</h3>
          <p className="text-sm text-slate-600">{t("manage.squadLimitsHint")}</p>
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
      )}

      {/* 5c. Liability waivers (Stories VA-5, S-1) --------------------------- */}
      <WaiverChecklist eventId={event.id} />

      {/* 6. Publication and start ------------------------------------------- */}
      <Stack gap={3}>
        <h3 className="text-sm font-semibold text-slate-700">{t("manage.lifecycleTitle")}</h3>
        <p className="text-sm text-slate-600">{t("manage.publishHint")}</p>
        <div className="flex flex-wrap items-center gap-3">
          <Button
            size="sm"
            variant={event.published ? "ghost" : "primary"}
            isDisabled={publish.isPending}
            onPress={() => publish.mutate({ eventId: event.id })}
            data-testid={`admin-manage-event-publish-${event.id}`}
          >
            {event.published ? t("manage.unpublishButton") : t("manage.publishButton")}
          </Button>
          <Button
            size="sm"
            isDisabled={start.isPending || !ready || !hasPairing || event.status === "live"}
            onPress={() => start.mutate({ eventId: event.id })}
            data-testid={`admin-manage-event-start-${event.id}`}
          >
            {event.status === "live" ? t("manage.startedButton") : t("manage.startButton")}
          </Button>
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
        </div>
        {event.status !== "live" && (!ready || !hasPairing) && (
          <p className="text-sm text-slate-500">{t("manage.startNeedsHint")}</p>
        )}
        <Message
          testId={`admin-manage-event-lifecycle-message-${event.id}`}
          error={
            publish.isError
              ? errorText(publish.error)
              : start.isError
                ? errorText(start.error)
                : null
          }
          success={start.isSuccess ? t("manage.startedMessage") : null}
        />
      </Stack>

      {/* 7. Closing it ------------------------------------------------------ */}
      {/* Story VA-10. Last, because it is the last thing done to an event — and because
          putting "Call off" next to "Publish" invites the wrong press.

          Only the transitions that apply are rendered. A permanently visible, permanently
          disabled "Reopen" under every planned event would be noise on a screen that has
          to stay usable at 412 px (Story A-10), and a disabled button explains nothing
          here: the reason it is disabled is simply that the event is not closed, which the
          status badge already says.

          Neither closing asks for confirmation. Both undo with one press and neither
          deletes anything — not the pairing list, not a single result — so a dialog would
          buy nothing and cost a tap on a rocking boat. */}
      <Stack gap={3}>
        <h3 className="text-sm font-semibold text-slate-700">{t("manage.closingTitle")}</h3>
        <p className="text-sm text-slate-600">
          {closed
            ? t(
                event.status === "final"
                  ? "manage.finishedHint"
                  : "manage.cancelledHint",
              )
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
              {t(
                event.status === "final"
                  ? "manage.reopenFinishedButton"
                  : "manage.reopenCancelledButton",
              )}
            </Button>
          ) : (
            <>
              {/* Finishing needs a live event — a day that never started cannot be over,
                  and the server says so with `event-not-started`. It deliberately does
                  **not** need complete results: demanding all 48 races would disable this
                  exactly on the day the wind died after flight 13. */}
              <Button
                size="sm"
                isDisabled={closingPending || event.status !== "live"}
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
        {!closed && event.status !== "live" && (
          <p className="text-sm text-slate-500">{t("manage.finishNeedsLiveHint")}</p>
        )}
        <Message
          testId={`admin-manage-event-closing-message-${event.id}`}
          error={closingError ? errorText(closingError) : null}
        />
      </Stack>
    </Stack>
  );
}

/** One readiness reason as a sentence.
 *
 * The backend sends a code plus the numbers involved and deliberately no English text, so
 * the wording lives in the `errors` namespace — the same key the matching API error uses.
 * A code this build doesn't know yet still reads as something rather than vanishing.
 */
/** Story VA-5: the organizer's check-in list — who in the participating squads is cleared,
 * and the guardian's uploaded form for a minor, opened with the token (Story S-1). */
function WaiverChecklist({ eventId }: { eventId: number }) {
  const { t } = useTranslation("admin");
  const list = useAsync(useEventWaivers(eventId));
  const [scanError, setScanError] = useState<string | null>(null);

  return (
    <Stack gap={3}>
      <h3 className="text-sm font-semibold text-slate-700">{t("manage.waiversTitle")}</h3>
      <p className="text-sm text-slate-600">{t("manage.waiversHint")}</p>
      {list.loading ? (
        <Loading text={t("manage.waiversLoadingText")} testId={`admin-manage-event-waivers-loading-${eventId}`} />
      ) : list.error ? (
        <ErrorMessage text={list.error} testId={`admin-manage-event-waivers-error-${eventId}`} />
      ) : list.data ? (
        list.data.sailors.length === 0 ? (
          <p className="text-sm text-slate-600" data-testid={`admin-manage-event-waivers-empty-${eventId}`}>
            {t("manage.waiversEmpty")}
          </p>
        ) : (
          <>
            <p className="text-sm" data-testid={`admin-manage-event-waivers-summary-${eventId}`}>
              {list.data.required_version == null
                ? t("manage.waiversNoVersion")
                : t("manage.waiversSummary", {
                    cleared: list.data.cleared,
                    outstanding: list.data.outstanding,
                    version: list.data.required_version,
                  })}
            </p>
            <TableFrame testId={`admin-manage-event-waivers-${eventId}`}>
              <table className="data-table w-full border-collapse text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
                    <th className="px-3 py-2">{t("manage.waiverColSailor")}</th>
                    <th className="px-3 py-2">{t("manage.waiverColClub")}</th>
                    <th className="px-3 py-2">{t("manage.waiverColStatus")}</th>
                  </tr>
                </thead>
                <tbody>
                  {list.data.sailors.map((row) => (
                    <tr
                      key={row.sailor_id}
                      className="border-t border-slate-100"
                      data-testid={`admin-manage-event-waiver-row-${eventId}-${row.sailor_id}`}
                      data-status={row.status}
                    >
                      <td className="px-3 py-2">
                        {row.first_name} {row.last_name}
                        {row.minor && (
                          <span className="ml-2 text-xs text-slate-500">{t("manage.waiverMinor")}</span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-slate-600">{row.club ?? "—"}</td>
                      <td className="px-3 py-2">
                        <span
                          className={
                            row.status === "cleared" ? "text-emerald-700" : "font-medium text-amber-700"
                          }
                        >
                          {t(`manage.waiverStatus.${row.status}`)}
                        </span>
                        {row.scan_available && row.confirmation_id != null && (
                          <button
                            type="button"
                            className="ml-2 text-xs underline underline-offset-2"
                            onClick={() => {
                              setScanError(null);
                              openFile(getGetWaiverScanUrl(row.confirmation_id!)).catch((err) =>
                                setScanError(errorText(err)),
                              );
                            }}
                            data-testid={`admin-manage-event-waiver-scan-${eventId}-${row.sailor_id}`}
                          >
                            {t("manage.waiverOpenScan")}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableFrame>
            {scanError && <ErrorMessage text={scanError} />}
          </>
        )
      ) : null}
    </Stack>
  );
}

function reasonText(reason: ReadinessReason): string {
  return i18n.t(`errors:${reason.code}`, {
    ...reason.details,
    defaultValue: reason.code,
  });
}
