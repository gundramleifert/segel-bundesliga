import { Button } from "@heroui/react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { useCreateEvent, useEventCreateOptions, useListPairingCatalog } from "../../../api/generated/sbl";
import type { EventSummary } from "../../../api/types";
import { useAsync, useInvalidate } from "../../../api/useApi";
import { Async } from "../../../components/Async";
import { Field, Message } from "../../../components/Form";
import { INPUT_CLASS, errorText } from "../../../lib/admin";
import { racesPerFlight } from "../../../lib/results";
import {
  boatNamesComplete,
  boatSpecs,
  defaultSize,
  resizedBoatRows,
  sizeKey,
  sizeOptions,
  type BoatRow,
  type Size,
} from "./setup";
import { BoatTable } from "./BoatTable";
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
  // What this person may pick, asked of the server (Story VA-6): the league office any
  // series and host, a series' organizer its acts with any host, a club's organizer an
  // event their own club hosts outside a series. Whole lists, never a page of them.
  const options = useAsync(useEventCreateOptions());
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

  const seriesChoices = options.data?.series ?? [];
  const ownHosts = options.data?.own_hosts;
  // Outside a series only the site's people may leave the host open; a club's organizer
  // names their own club, and someone who organizes no club adds acts to a series only.
  const standalone = ownHosts === null || (ownHosts?.length ?? 0) > 0;
  const seriesValue = seriesId || (standalone ? "" : String(seriesChoices[0]?.id ?? ""));
  const series = seriesChoices.find((s) => String(s.id) === seriesValue);
  const hosts = (options.data?.hosts ?? []).filter(
    (club) => series || ownHosts == null || ownHosts.includes(club.id),
  );
  const hostRequired = !series && ownHosts != null;
  const hostValue = hosts.some((club) => String(club.id) === hostClubId)
    ? hostClubId
    : hostRequired && hosts.length === 1
      ? String(hosts[0].id)
      : "";
  const sizes = sizeOptions(catalog.data ?? []);
  const size = chosenSize ?? defaultSize(sizes, series ? series.registered : null);
  const teams = size?.teams ?? 0;
  const boats = size?.boats ?? 0;
  const maxFlights = size?.maxFlights ?? 0;
  // A choice made for another size (the series changed under it) falls back to the full day.
  const flights =
    chosenFlights !== null && Number(chosenFlights) <= maxFlights ? chosenFlights : String(maxFlights);
  const boatRows = resizedBoatRows(chosenRows, boats);
  const perFlight = racesPerFlight({ team_count: teams, boat_count: boats });

  const create = useCreateEvent({
    mutation: {
      onSuccess: (event) => {
        invalidate("/api/admin/events", "/api/admin/series", "/api/events", "/api/series");
        onCreated(event);
      },
    },
  });

  if (options.data && !options.data.may_create) {
    return <Message testId="admin-events-create-message" error={t("events.createNotAllowed")} success={null} />;
  }

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
              series: seriesValue ? Number(seriesValue) : null,
              host_club_id: hostValue ? Number(hostValue) : null,
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
              value={seriesValue}
              onChange={(e) => setSeriesId(e.target.value)}
              testId="admin-events-series-select"
            >
              {standalone && <option value="">{t("events.seriesNone")}</option>}
              {seriesChoices.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("events.hostLabel")} hint={t("events.hostHint")}>
            <Select
              value={hostValue}
              onChange={(e) => setHostClubId(e.target.value)}
              testId="admin-events-host-select"
            >
              {!hostRequired && <option value="">{t("events.hostNone")}</option>}
              {hosts.map((v) => (
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
          <BoatTable rows={boatRows} onChange={setChosenRows} />
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
              (hostRequired && !hostValue) ||
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
