import { Button } from "@heroui/react";
import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import {
  api,
  ApiError,
  type BoatSpec,
  type ClubAdmin,
  type EventSummary,
  type ReadinessReason,
  type SeriesAdmin,
} from "../api/client";
import { useApi, useInvalidate } from "../api/useApi";
import { ErrorMessage, Loading, Empty, StatusBadge } from "../components/Blocks";
import i18n from "../i18n";
import { BOAT_COLORS, boatColor, eventDates } from "../lib/format";
import { INPUT_CLASS, errorText, toggleSet } from "../lib/admin";
import { Section, Field, Message, ClubSelector } from "./adminBuildingBlocks";

/** Stories A-4, VA-7 and VA-8: scheduling an event and taking it through its life.
 *
 * Two sections, because they are two different jobs. **Creating** an event asks only for a
 * name — an event with no date, no clubs and the wrong boat count is the normal early
 * state, not an error (Story VA-8), so the form deliberately gates almost nothing.
 * **Managing** an event is where the rest arrives: the date once the host confirms it, the
 * clubs, the draw, publication, and finally the start. Those steps are ordered but not a
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

/** Whether a failed draw is just "the setup isn't finished yet" rather than something wrong.
 *
 *  A newly created event has no clubs and often no date — they arrive afterwards — so this
 *  is the *expected* outcome of the automatic draw, not a fault to report in red.
 *
 *  Both codes have to be accepted. `pairing-team-count-mismatch` is what the draw refuses
 *  with when that is the **only** thing missing; as soon as a second reason applies — and
 *  for an event saved with a title alone, the missing date always does — readiness answers
 *  with `event-not-ready` carrying the reasons instead (see
 *  `app/services/event_readiness.py::require_ready`). Checking only the single-reason code
 *  meant the normal case, creating an event and filling it in later, reported a red error
 *  every time. */
function isSetupIncompleteNotice(error: unknown): boolean {
  return (
    error instanceof ApiError &&
    (error.code === "pairing-team-count-mismatch" || error.code === "event-not-ready")
  );
}

/** A fresh row's `customColor` starts out matching its predefined default, not empty — the
 *  picker and free-text field are always visible now (not just once "Custom" is chosen), so
 *  they need a real value to show from the very first render, not a black fallback. */
function emptyBoatRow(position: number): BoatRow {
  const color = defaultColor(position);
  return { color, customColor: boatColor(color).hex, name: defaultName(position) };
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
  return (
    <>
      <CreateEvent />
      <ManageEvents />
    </>
  );
}

// ------------------------------------------------------------------ Creating

function CreateEvent() {
  const { t } = useTranslation("admin");
  const seriesList = useApi(["admin", "series"], (signal) => api.admin.series(signal));
  const clubs = useApi(["admin", "clubs"], (signal) => api.admin.clubs(signal));
  // Only pre-computed sizes are offered here — picking a free combination of teams,
  // boats and flights would mean drawing a pairing list from scratch later, an
  // optimization run that takes minutes, not seconds (see app/pairing/catalog.py).
  // What can still be varied per event without recomputing is the seed that shuffles
  // starting positions — that's a separate step once the event exists, not part of
  // creating it.
  const catalog = useApi(["admin", "pairingCatalog"], (signal) => api.admin.pairingCatalog(signal));
  const invalidate = useInvalidate();

  const [title, setTitle] = useState("");
  const [startsOn, setStartsOn] = useState("");
  const [endsOn, setEndsOn] = useState("");
  const [seriesId, setSeriesId] = useState("");
  const [hostClubId, setHostClubId] = useState("");
  const [teams, setTeams] = useState("18");
  const [boats, setBoats] = useState("6");
  const [flights, setFlights] = useState("16");
  // Default matches the backend's own default seed (`PairingJobRequest.seed` in
  // app/schemas/admin.py) — same seed, same draw, reproducible if it ever needs proving.
  const [seed, setSeed] = useState("1240");
  const [boatRows, setBoatRows] = useState<BoatRow[]>(() =>
    Array.from({ length: 6 }, (_, i) => emptyBoatRow(i + 1)),
  );

  const updateBoat = (index: number, patch: Partial<BoatRow>) =>
    setBoatRows((prev) =>
      prev.map((row, i) => (i === index ? { ...row, ...patch } : row)),
    );

  // Separate from event creation on purpose: the event exists either way, so a failed draw
  // (e.g. a standalone event with no teams registered yet) must not read as "creation failed."
  const drawPairing = useMutation({
    mutationFn: (eventId: number) => api.admin.pairingFromCatalog(eventId, Number(seed) || 1240),
    onSuccess: () => invalidate(["admin", "readiness"]),
  });

  const create = useMutation({
    mutationFn: () =>
      api.admin.createEvent({
        title: title.trim(),
        // Empty means "not agreed with the host yet", which is savable — the date is
        // needed to *start* the event, not to write it down (Story VA-8).
        starts_on: startsOn || null,
        ends_on: endsOn || null,
        series: seriesId ? Number(seriesId) : null,
        host_club_id: hostClubId ? Number(hostClubId) : null,
        team_count: Number(teams),
        boat_count: Number(boats),
        flight_count: Number(flights),
        boats: boatSpecs(boatRows),
        // Saved as a draft. Publication is a separate, reversible decision in the manage
        // panel below — it changes only who can see the event (Story VA-8).
        published: false,
      }),
    onSuccess: (event) => {
      setTitle("");
      setStartsOn("");
      setEndsOn("");
      setBoatRows(Array.from({ length: Number(boats) || 6 }, (_, i) => emptyBoatRow(i + 1)));
      invalidate(["admin", "series"], ["admin", "events"], ["events"], ["series"]);
      drawPairing.mutate(event.id);
    },
  });

  return (
    <Section
      title={t("events.title")}
      hint={t("events.description")}
      testId="admin-events-section"
    >
      <form
        data-testid="admin-events-create-form"
        className="grid grid-cols-[minmax(0,1fr)] gap-3"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          create.mutate();
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

        <Field label={t("events.seedLabel")} hint={t("events.seedHint")}>
          <input
            className={INPUT_CLASS}
            type="number"
            value={seed}
            onChange={(e) => setSeed(e.target.value)}
            data-testid="admin-events-seed-input"
          />
        </Field>

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
            <table data-testid="admin-events-boat-table" className="w-full min-w-[44rem] text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
                  <th scope="col" className="px-3 py-2 font-medium">
                    {t("events.boatNumberLabel")}
                  </th>
                  <th scope="col" className="px-3 py-2 font-medium">
                    {t("events.boatColorLabel")}
                  </th>
                  <th scope="col" className="px-3 py-2 font-medium">
                    {t("events.boatNameLabel")}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {boatRows.map((row, index) => (
                  <tr key={index}>
                    <td className="px-3 py-2 text-slate-500">{index + 1}</td>
                    <td className="px-3 py-2">
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
                    <td className="px-3 py-2">
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

        <div>
          {/* Only the title and the boat names gate saving. A missing date, no clubs and a
              boat count that doesn't match are all things the manage panel below reports
              and fixes — refusing to save them would mean nothing could be written down
              until everything was known (Story VA-8). */}
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
        </div>
      </form>

      <Message
        testId="admin-events-create-message"
        error={create.isError ? errorText(create.error) : null}
        success={create.isSuccess ? t("events.createdMessage", { title: create.data?.title }) : null}
      />

      {/* Distinct from event-creation success/failure above: the event exists either way,
       *  so a failed draw is reported as its own, clearly-labeled notice rather than looking
       *  like creation itself failed.
       *
       *  Having no clubs and no date yet is the *normal* state right after creating an
       *  event — both arrive afterwards — so a readiness refusal is not an error here at
       *  all, it is the next step. Only a genuine failure is shown in red. */}
      {create.isSuccess && drawPairing.isError && (
        isSetupIncompleteNotice(drawPairing.error) ? (
          <p data-testid="admin-events-pairing-draw-pending" className="text-sm text-slate-600">
            {t("events.pairingDrawPendingMessage")}
          </p>
        ) : (
          <ErrorMessage
            text={t("events.pairingDrawFailedMessage", { error: errorText(drawPairing.error) })}
            testId="admin-events-pairing-draw-error"
          />
        )
      )}
      {create.isSuccess && drawPairing.isSuccess && (
        <p data-testid="admin-events-pairing-draw-success" className="text-sm text-emerald-700">
          {t("events.pairingDrawSuccessMessage")}
        </p>
      )}
    </Section>
  );
}

// ------------------------------------------------------------------ Managing

function ManageEvents() {
  const { t } = useTranslation("admin");
  // The admin list, not the public one: a draft has to appear on the very screen whose
  // job is to finish and publish it.
  const events = useApi(["admin", "events"], (signal) => api.admin.events(signal));
  const seriesList = useApi(["admin", "series"], (signal) => api.admin.series(signal));
  const clubs = useApi(["admin", "clubs"], (signal) => api.admin.clubs(signal));

  return (
    <Section
      title={t("manage.title")}
      hint={t("manage.description")}
      testId="admin-manage-events-section"
    >
      {events.loading && <Loading text={t("manage.loadingText")} testId="admin-manage-events-loading" />}
      {events.error && <ErrorMessage text={events.error} testId="admin-manage-events-error" />}
      {events.data &&
        (events.data.length ? (
          <ul
            data-testid="admin-manage-events-list"
            className="divide-y divide-slate-100 rounded-lg border border-slate-200"
          >
            {events.data.map((event) => (
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
            <PublicationBadge published={event.published} eventId={event.id} />
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

function PublicationBadge({ published, eventId }: { published: boolean; eventId: number }) {
  const { t } = useTranslation("admin");
  return (
    <span
      data-testid={`admin-manage-event-publication-${eventId}`}
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
  const readiness = useApi(["admin", "readiness", event.id], (signal) =>
    api.admin.eventReadiness(event.id, signal),
  );
  const participants = useApi(["admin", "eventClubs", event.id], (signal) =>
    api.admin.eventClubs(event.id, signal),
  );

  const [startsOn, setStartsOn] = useState(event.starts_on ?? "");
  const [endsOn, setEndsOn] = useState(event.ends_on ?? "");
  const [seed, setSeed] = useState("1240");
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
      ["admin", "events"],
      ["admin", "readiness", event.id],
      ["admin", "eventClubs", event.id],
      ["events"],
      ["event", event.id],
    );

  const saveDates = useMutation({
    mutationFn: () =>
      api.admin.updateEvent(event.id, {
        starts_on: startsOn || null,
        ends_on: endsOn || startsOn || null,
      }),
    onSuccess: refresh,
  });

  const saveClubs = useMutation({
    mutationFn: () => api.admin.setEventClubs(event.id, [...selection]),
    onSuccess: () => {
      setSelectedClubs(null);
      refresh();
    },
  });

  const draw = useMutation({
    mutationFn: () => api.admin.pairingFromCatalog(event.id, Number(seed) || 1240),
    onSuccess: refresh,
  });

  const publish = useMutation({
    mutationFn: (published: boolean) => api.admin.publishEvent(event.id, published),
    onSuccess: refresh,
  });

  const start = useMutation({
    mutationFn: () => api.admin.startEvent(event.id),
    onSuccess: refresh,
  });

  const frozen = readiness.data?.configuration_frozen ?? false;
  const ready = readiness.data?.ready ?? false;
  const hasPairing = readiness.data?.has_pairing_list ?? false;

  return (
    <div className="mt-4 grid grid-cols-[minmax(0,1fr)] gap-5 border-t border-slate-100 pt-4">
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
      <div className="grid grid-cols-[minmax(0,1fr)] gap-3">
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
            onPress={() => saveDates.mutate()}
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
      </div>

      {/* 3. Who enters ------------------------------------------------------ */}
      <div className="grid grid-cols-[minmax(0,1fr)] gap-3">
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
                onPress={() => saveClubs.mutate()}
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
      </div>

      {/* 4. The draw -------------------------------------------------------- */}
      <div className="grid grid-cols-[minmax(0,1fr)] gap-3">
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
            onPress={() => draw.mutate()}
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
      </div>

      {/* 5. Publication and start ------------------------------------------- */}
      <div className="grid grid-cols-[minmax(0,1fr)] gap-3">
        <h3 className="text-sm font-semibold text-slate-700">{t("manage.lifecycleTitle")}</h3>
        <p className="text-sm text-slate-600">{t("manage.publishHint")}</p>
        <div className="flex flex-wrap items-center gap-3">
          <Button
            size="sm"
            variant={event.published ? "ghost" : "primary"}
            isDisabled={publish.isPending}
            onPress={() => publish.mutate(!event.published)}
            data-testid={`admin-manage-event-publish-${event.id}`}
          >
            {event.published ? t("manage.unpublishButton") : t("manage.publishButton")}
          </Button>
          <Button
            size="sm"
            isDisabled={start.isPending || !ready || !hasPairing || event.status === "live"}
            onPress={() => start.mutate()}
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
      </div>
    </div>
  );
}

/** One readiness reason as a sentence.
 *
 * The backend sends a code plus the numbers involved and deliberately no English text, so
 * the wording lives in the `errors` namespace — the same key the matching API error uses.
 * A code this build doesn't know yet still reads as something rather than vanishing.
 */
function reasonText(reason: ReadinessReason): string {
  return i18n.t(`errors:${reason.code}`, {
    ...reason.details,
    defaultValue: reason.code,
  });
}
