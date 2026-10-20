import { Button } from "@heroui/react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  useCreateEvent,
  useListAllClubs,
  useListAllSeries,
  useListPairingCatalog,
} from "../../../api/generated/sbl";
import type { EventSummary } from "../../../api/types";
import { WHOLE_LIST, useAsync, useAsyncRows, useInvalidate } from "../../../api/useApi";
import { Async } from "../../../components/Async";
import { Field, Message } from "../../../components/Form";
import { INPUT_CLASS, errorText } from "../../../lib/admin";
import { boatColor } from "../../../lib/format";
import { racesPerFlight } from "../../../lib/results";
import {
  CUSTOM_COLOR,
  PREDEFINED_COLORS,
  boatNamesComplete,
  boatSpecs,
  defaultSize,
  hexForPicker,
  resizedBoatRows,
  sizeKey,
  sizeOptions,
  sizedInput,
  type BoatRow,
  type Size,
} from "./setup";
import { StepActions } from "./StepActions";
import { Select } from "../../../components/Select";

/** Step 1: name, dates, series, host, size and boats — and the create request. Only the
 *  title and the boat names gate it: a missing date and the wrong number of clubs are the
 *  normal early state, which the next steps and the manage panel report and fix
 *  (Story VA-8). */
export function GeneralDataStep({
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
  // Each `null` until the organizer chooses: until then the size follows the series (its
  // registered clubs) or the catalog's first entry, the flights its full length, and the
  // boat rows its boat count — never a league's "18 on 6 in 16" written into the screen.
  const [chosenSize, setChosenSize] = useState<Size | null>(null);
  const [chosenFlights, setChosenFlights] = useState<string | null>(null);
  const [chosenRows, setChosenRows] = useState<BoatRow[]>([]);

  const sizes = sizeOptions(catalog.data ?? []);
  const series = seriesList.data?.find((s) => String(s.id) === seriesId);
  const size = chosenSize ?? defaultSize(sizes, series ? (series.clubs?.length ?? 0) : null);
  const teams = size?.teams ?? 0;
  const boats = size?.boats ?? 0;
  const maxFlights = size?.maxFlights ?? 0;
  // A choice made for another size (the series changed under it) falls back to the full day.
  const flights =
    chosenFlights !== null && Number(chosenFlights) <= maxFlights ? chosenFlights : String(maxFlights);
  const boatRows = resizedBoatRows(chosenRows, boats);
  const perFlight = racesPerFlight({ team_count: teams, boat_count: boats });

  const updateBoat = (index: number, patch: Partial<BoatRow>) =>
    setChosenRows(boatRows.map((row, i) => (i === index ? { ...row, ...patch } : row)));

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
              team_count: teams,
              boat_count: boats,
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
            <Select
              value={seriesId}
              onChange={(e) => setSeriesId(e.target.value)}
              testId="admin-events-series-select"
            >
              <option value="">{t("events.seriesNone")}</option>
              {seriesList.data?.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("events.hostLabel")} hint={t("events.hostHint")}>
            <Select
              value={hostClubId}
              onChange={(e) => setHostClubId(e.target.value)}
              testId="admin-events-host-select"
            >
              <option value="">{t("events.hostNone")}</option>
              {clubs.data?.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name}
                </option>
              ))}
            </Select>
          </Field>
        </div>

        <div className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-[2fr_1fr]">
          <Field label={t("events.setupLabel")} hint={t("events.setupHint")}>
            <Async
              state={catalog}
              testId="admin-events-catalog"
              loadingText={t("events.catalogLoadingText")}
              empty={t("events.catalogEmptyText")}
            >
              {() => (
                <Select
                  value={size ? sizeKey(size) : ""}
                  onChange={(e) => {
                    const picked = sizes.find((candidate) => sizeKey(candidate) === e.target.value);
                    if (!picked) return;
                    setChosenSize(picked);
                    // A new combination starts at its full length; the flights are then
                    // shortened on purpose, never left over from the previous size.
                    setChosenFlights(null);
                    setChosenRows(resizedBoatRows(boatRows, picked.boats));
                  }}
                  testId="admin-events-catalog-select"
                >
                  {sizes.map((option) => (
                    <option key={sizeKey(option)} value={sizeKey(option)}>
                      {t("events.sizeOption", { teams: option.teams, boats: option.boats })}
                    </option>
                  ))}
                </Select>
              )}
            </Async>
          </Field>
          {/* Flights are a choice of their own: the stored list is the longest day, and a
              shorter one is its first flights (Story VA-7). */}
          {maxFlights > 0 && (
            <Field label={t("events.flightsLabel")} hint={t("events.flightsHint", { max: maxFlights })}>
              <Select
                value={flights}
                onChange={(e) => setChosenFlights(e.target.value)}
                testId="admin-events-flights-select"
              >
                {Array.from({ length: maxFlights }, (_, i) => i + 1).map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </Select>
            </Field>
          )}
        </div>

        <p className="text-sm text-muted" data-testid="admin-events-format-text">
          {t("events.formatText", {
            teams,
            boats,
            races: perFlight,
            flights,
            total: perFlight * (Number(flights) || 0),
          })}
        </p>

        <p className="text-sm text-muted">
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
          <div className="overflow-x-auto rounded-md border border-separator">
            <table data-testid="admin-events-boat-table" className="data-table w-full min-w-[44rem] text-sm">
              <thead>
                <tr className="border-b border-separator bg-surface-secondary text-left text-xs font-medium uppercase tracking-wide text-muted">
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
              <tbody className="divide-y divide-separator">
                {boatRows.map((row, index) => (
                  <tr key={index}>
                    <td className="text-muted">{index + 1}</td>
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
                        <Select
                          size="inline"
                          className="w-32 shrink-0"
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
                          testId={`admin-events-boat-color-select-${index}`}
                        >
                          {PREDEFINED_COLORS.map((code) => (
                            <option key={code} value={code}>
                              {t(`common:boatColor.${code}`)}
                            </option>
                          ))}
                          <option value={CUSTOM_COLOR}>{t("events.boatColorCustom")}</option>
                        </Select>
                        <input
                          type="color"
                          className="h-9 w-9 shrink-0 cursor-pointer rounded border border-border p-0.5"
                          value={hexForPicker(row.customColor)}
                          onChange={(e) =>
                            updateBoat(index, { color: CUSTOM_COLOR, customColor: e.target.value })
                          }
                          aria-label={t("events.boatColorPickerLabel")}
                          data-testid={`admin-events-boat-color-picker-${index}`}
                        />
                        <input
                          className={`${sizedInput("min-w-[6rem]")} flex-1`}
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
              !size ||
              !boatNamesComplete(boatRows)
            }
            data-testid="admin-events-create-button"
          >
            {create.isPending ? t("events.creatingButton") : t("events.createButton")}
          </Button>
          <Button size="sm" variant="ghost" onPress={onCancel} data-testid="admin-events-cancel-button">
            {t("page.cancelButton")}
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
