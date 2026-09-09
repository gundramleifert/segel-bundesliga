import { Button } from "@heroui/react";
import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { api, ApiError, type BoatSpec, type ClubAdmin, type SeriesAdmin } from "../api/client";
import { useApi, useInvalidate, useAccount } from "../api/useApi";
import { ErrorMessage, Loading, Empty, PageHeader } from "../components/Blocks";
import i18n from "../i18n";
import { BOAT_COLORS, boatColor } from "../lib/format";
import { AccountsAdmin } from "./AdminAccounts";
import { SailorsAdmin } from "./AdminSailors";
import { INPUT_CLASS, errorText, toggleSet } from "../lib/admin";
import { Section, Field, Message, ClubSelector } from "./adminBuildingBlocks";

/** Stories A-1, A-4, and A-6: Create clubs, create series, schedule events.
 *
 * The flow is deliberately top-to-bottom: **first clubs, then a series with their
 * clubs, then events for the series.** A series without clubs has no standings,
 * and an event without a series counts toward no scoring — that's why the three
 * sections are in this order, not alphabetically.
 */
export function Admin() {
  const { t } = useTranslation("admin");
  const { account, loading, hasRole } = useAccount();

  if (loading) return <Loading testId="admin-loading" />;
  if (!account) {
    return (
      <ErrorMessage text={t("auth.notSignedInError")} testId="admin-auth-error" />
    );
  }
  if (!hasRole("admin", "editor")) {
    return (
      <ErrorMessage text={t("auth.noAccessError")} testId="admin-access-error" />
    );
  }

  return (
    <>
      <PageHeader
        title={t("page.title")}
        subtitle={t("page.signedInAs", { displayName: account.display_name, roles: account.roles.join(", ") })}
        testId="admin-header"
      />
      <div className="grid gap-8">
        <Clubs />
        <Series editorOnly={!hasRole("admin")} />
        <Events />
        <SailorsAdmin />
        {hasRole("admin") && <AccountsAdmin />}
      </div>
    </>
  );
}

// ---------------------------------------------------------------------- Clubs

function Clubs() {
  const { t } = useTranslation("admin");
  const { data, error, loading } = useApi(["admin", "clubs"], (signal) =>
    api.admin.clubs(signal),
  );
  const invalidate = useInvalidate();
  const [name, setName] = useState("");
  const [shortName, setShortName] = useState("");
  const [city, setCity] = useState("");

  const create = useMutation({
    mutationFn: () =>
      api.admin.createClub({
        name: name.trim(),
        short_name: shortName.trim() || null,
        city: city.trim() || null,
      }),
    onSuccess: () => {
      setName("");
      setShortName("");
      setCity("");
      invalidate(["admin", "clubs"], ["clubs"]);
    },
  });

  return (
    <Section
      title={t("clubs.title")}
      hint={t("clubs.description")}
      testId="admin-clubs-section"
    >
      <form
        data-testid="admin-clubs-create-form"
        className="grid gap-3 sm:grid-cols-[2fr_1fr_1fr_auto] sm:items-end"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          create.mutate();
        }}
      >
        <Field label={t("clubs.nameLabel")}>
          <input
            className={INPUT_CLASS}
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            minLength={3}
            placeholder={t("clubs.namePlaceholder")}
            data-testid="admin-clubs-name-input"
          />
        </Field>
        <Field label={t("clubs.shortNameLabel")} hint={t("clubs.shortNameHint")}>
          <input
            className={INPUT_CLASS}
            value={shortName}
            onChange={(e) => setShortName(e.target.value)}
            placeholder={t("clubs.shortNamePlaceholder")}
            data-testid="admin-clubs-short-name-input"
          />
        </Field>
        <Field label={t("clubs.cityLabel")} hint={t("clubs.cityHint")}>
          <input
            className={INPUT_CLASS}
            value={city}
            onChange={(e) => setCity(e.target.value)}
            placeholder={t("clubs.cityPlaceholder")}
            data-testid="admin-clubs-city-input"
          />
        </Field>
        <Button
          type="submit"
          isDisabled={create.isPending || name.trim().length < 3}
          data-testid="admin-clubs-create-button"
        >
          {create.isPending ? t("clubs.creatingButton") : t("clubs.createButton")}
        </Button>
      </form>

      <Message
        testId="admin-clubs-create-message"
        error={create.isError ? errorText(create.error) : null}
        success={create.isSuccess ? t("clubs.createdMessage", { name: create.data?.name }) : null}
      />

      {loading && <Loading text={t("clubs.loadingText")} testId="admin-clubs-loading" />}
      {error && <ErrorMessage text={error} testId="admin-clubs-error" />}
      {data && (
        <p data-testid="admin-clubs-stats" className="text-sm text-slate-600">
          {t("clubs.statsText", { count: data.length, visible: data.filter((v) => v.visible).length })}
        </p>
      )}
    </Section>
  );
}

// ----------------------------------------------------------------------- Series

function Series({ editorOnly }: { editorOnly: boolean }) {
  const { t } = useTranslation("admin");
  const seriesList = useApi(["admin", "series"], (signal) => api.admin.series(signal));
  const clubs = useApi(["admin", "clubs"], (signal) => api.admin.clubs(signal));
  const invalidate = useInvalidate();

  const [name, setName] = useState("");
  // No default: the year is optional, not implicitly "this year". An admin planning
  // ahead should be able to leave it blank rather than having to clear a prefilled value.
  const [year, setYear] = useState("");
  const [startsOn, setStartsOn] = useState("");
  const [endsOn, setEndsOn] = useState("");
  const [selectedClubs, setSelectedClubs] = useState<Set<number>>(new Set());

  const toggle = toggleSet(setSelectedClubs);

  const create = useMutation({
    mutationFn: () =>
      api.admin.createSeries({
        name: name.trim(),
        year: year ? Number(year) : null,
        starts_on: startsOn || null,
        ends_on: endsOn || null,
        clubs: [...selectedClubs],
      }),
    onSuccess: () => {
      setName("");
      setYear("");
      setStartsOn("");
      setEndsOn("");
      setSelectedClubs(new Set());
      invalidate(["admin", "series"], ["series"], ["clubs"]);
    },
  });

  if (editorOnly) {
    return (
      <Section title={t("series.title")} testId="admin-series-section">
        <Empty testId="admin-series-editor-only">{t("series.editOnlyAdmin")}</Empty>
      </Section>
    );
  }

  return (
    <Section
      title={t("series.title")}
      hint={t("series.description")}
      testId="admin-series-section"
    >
      <form
        data-testid="admin-series-create-form"
        className="grid gap-3"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          create.mutate();
        }}
      >
        <div className="grid gap-3 sm:grid-cols-[2fr_1fr]">
          <Field label={t("series.nameLabel")}>
            <input
              className={INPUT_CLASS}
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              minLength={3}
              placeholder={t("series.namePlaceholder")}
              data-testid="admin-series-name-input"
            />
          </Field>
          <Field label={t("series.yearLabel")} hint={t("series.yearHint")}>
            <input
              className={INPUT_CLASS}
              type="number"
              value={year}
              onChange={(e) => setYear(e.target.value)}
              min={1900}
              max={2200}
              placeholder={String(new Date().getFullYear())}
              data-testid="admin-series-year-input"
            />
          </Field>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t("series.startsLabel")} hint={t("series.startsHint")}>
            <input
              className={INPUT_CLASS}
              type="date"
              value={startsOn}
              onChange={(e) => setStartsOn(e.target.value)}
              data-testid="admin-series-starts-input"
            />
          </Field>
          <Field label={t("series.endsLabel")} hint={t("series.endsHint")}>
            <input
              className={INPUT_CLASS}
              type="date"
              value={endsOn}
              onChange={(e) => setEndsOn(e.target.value)}
              data-testid="admin-series-ends-input"
            />
          </Field>
        </div>

        <Field label={t("series.clubsLabel")} hint={t("series.clubsHint", { count: selectedClubs.size })}>
          {clubs.loading && <Loading text={t("clubs.loadingText")} testId="admin-series-clubs-loading" />}
          {clubs.data && (
            <ClubSelector
              clubs={clubs.data}
              selectedIds={selectedClubs}
              toggle={toggle}
              testId="admin-series-clubs-select"
            />
          )}
        </Field>

        <div>
          <Button
            type="submit"
            isDisabled={create.isPending || name.trim().length < 3}
            data-testid="admin-series-create-button"
          >
            {create.isPending ? t("series.creatingButton") : t("series.createButton")}
          </Button>
        </div>
      </form>

      <Message
        testId="admin-series-create-message"
        error={create.isError ? errorText(create.error) : null}
        success={
          create.isSuccess
            ? t("series.createdMessage", { name: create.data?.name, count: create.data?.clubs?.length ?? 0 })
            : null
        }
      />

      {seriesList.loading && <Loading text={t("series.loadingText")} testId="admin-series-loading" />}
      {seriesList.error && <ErrorMessage text={seriesList.error} testId="admin-series-error" />}
      {seriesList.data &&
        (seriesList.data.length ? (
          <ul data-testid="admin-series-list" className="divide-y divide-slate-100 rounded-lg border border-slate-200">
            {seriesList.data.map((seriesId) => (
              <SeriesRow
                key={seriesId.id}
                seriesId={seriesId}
                clubs={clubs.data ?? []}
                onChanged={() => invalidate(["admin", "series"], ["series"], ["clubs"])}
              />
            ))}
          </ul>
        ) : (
          <Empty testId="admin-series-empty">{t("series.emptyText")}</Empty>
        ))}
    </Section>
  );
}

function SeriesRow({
  seriesId,
  clubs,
  onChanged,
}: {
  seriesId: SeriesAdmin;
  clubs: ClubAdmin[];
  onChanged: () => void;
}) {
  const { t } = useTranslation("admin");
  const [open, setOpen] = useState(false);
  const [selectedClubs, setSelectedClubs] = useState<Set<number>>(
    () => new Set((seriesId.clubs ?? []).map((c) => c.id)),
  );
  const [description, setDescription] = useState(seriesId.description ?? "");

  const save = useMutation({
    mutationFn: () => api.admin.setSeriesClubs(seriesId.id, [...selectedClubs]),
    onSuccess: () => {
      setOpen(false);
      onChanged();
    },
  });

  const saveDescription = useMutation({
    mutationFn: () =>
      api.admin.updateSeries(seriesId.id, { description: description.trim() || null }),
    onSuccess: () => onChanged(),
  });

  return (
    <li data-testid={`admin-series-row-${seriesId.id}`} className="px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link
            to={`/series/${seriesId.id}`}
            data-testid={`admin-series-link-${seriesId.id}`}
            className="font-medium underline-offset-2 hover:underline"
          >
            {seriesId.name}
          </Link>
          <p className="text-sm text-slate-600">
            {t("series.itemText", { count: seriesId.clubs?.length ?? 0, events: seriesId.event_count })}
          </p>
        </div>
        <Button
          size="sm"
          variant="ghost"
          onPress={() => setOpen((o) => !o)}
          data-testid={`admin-series-edit-button-${seriesId.id}`}
        >
          {open ? t("series.closeButton") : t("series.editButton")}
        </Button>
      </div>

      {open && (
        <div className="mt-3 grid gap-4">
          <div className="grid gap-3">
            <ClubSelector
              clubs={clubs}
              selectedIds={selectedClubs}
              toggle={toggleSet(setSelectedClubs)}
              testId={`admin-series-edit-clubs-${seriesId.id}`}
            />
            <div className="flex items-center gap-3">
              <Button
                size="sm"
                isDisabled={save.isPending}
                onPress={() => save.mutate()}
                data-testid={`admin-series-save-clubs-button-${seriesId.id}`}
              >
                {save.isPending ? t("series.savingButton") : t("series.saveButton", { count: selectedClubs.size })}
              </Button>
              <span className="text-sm text-slate-500">
                {t("series.saveHint")}
              </span>
            </div>
            {save.isError && (
              <ErrorMessage text={errorText(save.error)} testId={`admin-series-save-clubs-error-${seriesId.id}`} />
            )}
          </div>

          <Field label={t("series.descriptionLabel")} hint={t("series.descriptionHint")}>
            <textarea
              className={INPUT_CLASS}
              rows={4}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={t("series.descriptionPlaceholder")}
              data-testid={`admin-series-description-input-${seriesId.id}`}
            />
          </Field>
          <div className="flex items-center gap-3">
            <Button
              size="sm"
              isDisabled={saveDescription.isPending}
              onPress={() => saveDescription.mutate()}
              data-testid={`admin-series-save-description-button-${seriesId.id}`}
            >
              {saveDescription.isPending
                ? t("series.savingButton")
                : t("series.saveDescriptionButton")}
            </Button>
            {saveDescription.isSuccess && (
              <span
                data-testid={`admin-series-description-saved-${seriesId.id}`}
                className="text-sm text-emerald-700"
              >
                {t("series.descriptionSavedMessage")}
              </span>
            )}
          </div>
          {saveDescription.isError && (
            <ErrorMessage
              text={errorText(saveDescription.error)}
              testId={`admin-series-description-error-${seriesId.id}`}
            />
          )}
        </div>
      )}
    </li>
  );
}

// --------------------------------------------------------------- Events

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

/** Whether a failed draw is just "the clubs aren't in yet" rather than something wrong.
 *  A newly created event has no clubs — they are registered afterwards — so this is the
 *  expected outcome of the automatic draw, not a fault to report in red. */
function isTeamCountNotice(error: unknown): boolean {
  return error instanceof ApiError && error.code === "pairing-team-count-mismatch";
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

function Events() {
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
  });

  const create = useMutation({
    mutationFn: () =>
      api.admin.createEvent({
        title: title.trim(),
        starts_on: startsOn,
        ends_on: endsOn || null,
        series: seriesId ? Number(seriesId) : null,
        host_club_id: hostClubId ? Number(hostClubId) : null,
        team_count: Number(teams),
        boat_count: Number(boats),
        flight_count: Number(flights),
        boats: boatSpecs(boatRows),
      }),
    onSuccess: (event) => {
      setTitle("");
      setStartsOn("");
      setEndsOn("");
      setBoatRows(Array.from({ length: Number(boats) || 6 }, (_, i) => emptyBoatRow(i + 1)));
      invalidate(["admin", "series"], ["events"], ["series"]);
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
        className="grid gap-3"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          create.mutate();
        }}
      >
        <div className="grid gap-3 sm:grid-cols-[2fr_1fr_1fr]">
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
          <Field label={t("events.startsLabel")}>
            <input
              className={INPUT_CLASS}
              type="date"
              value={startsOn}
              onChange={(e) => setStartsOn(e.target.value)}
              required
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

        <div className="grid gap-3 sm:grid-cols-2">
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
          <Button
            type="submit"
            isDisabled={
              create.isPending ||
              title.trim().length < 3 ||
              !startsOn ||
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
       *  Having no clubs yet is the *normal* state right after creating an event — they are
       *  added afterwards — so the backend's `pairing-team-count-mismatch` is not an error
       *  here at all, it is the next step. Only a genuine failure is shown in red. */}
      {create.isSuccess && drawPairing.isError && (
        isTeamCountNotice(drawPairing.error) ? (
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
