import { Button } from "@heroui/react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  useEventCreateOptions,
  useGetReadiness,
  useListEventBoats,
  useListPairingCatalog,
  useUpdateEvent,
} from "../../../api/generated/sbl";
import type { EventSummary } from "../../../api/types";
import { useAsync } from "../../../api/useApi";
import { Field, Message } from "../../../components/Form";
import { Select } from "../../../components/Select";
import { INPUT_CLASS, errorText } from "../../../lib/admin";
import { boatColor } from "../../../lib/format";
import { BoatTable } from "../../admin/events/BoatTable";
import { useEventRefresh } from "../../admin/events/EventPanel";
import {
  CUSTOM_COLOR,
  PREDEFINED_COLORS,
  boatSpecs,
  sizeKey,
  sizeOptions,
  type BoatRow,
} from "../../admin/events/setup";

/** Story VA-8 (decided 2026-10-25): everything set at creation, changeable afterwards —
 *  title, series and matchday, host, venue, the size and the teams per club. Until the
 *  first race all of it; after it the configuration is frozen and only title, host and
 *  venue stay (the dates have their own block). A changed size discards a pairing list
 *  drawn for the old one — the form says so before saving. Only what changed is sent. */
export function EventGeneralForm({ event }: { event: EventSummary }) {
  const { t } = useTranslation("space");
  const { t: ta } = useTranslation("admin");
  const options = useAsync(useEventCreateOptions());
  const catalog = useAsync(useListPairingCatalog());
  const readiness = useAsync(useGetReadiness(event.id));
  const refresh = useEventRefresh(event.id);
  const save = useUpdateEvent({ mutation: { onSuccess: refresh } });

  const [title, setTitle] = useState(event.title);
  const [seriesId, setSeriesId] = useState(event.series ? String(event.series.id) : "");
  const [matchday, setMatchday] = useState(event.matchday ? String(event.matchday) : "");
  const [hostId, setHostId] = useState(event.host_club ? String(event.host_club.id) : "");
  const [venueId, setVenueId] = useState(event.venue ? String(event.venue.id) : "");
  const current = sizeKey({ teams: event.team_count, boats: event.boat_count });
  const [size, setSize] = useState(current);
  const [flights, setFlights] = useState(String(event.flight_count));
  const [teamsPerClub, setTeamsPerClub] = useState(String(event.teams_per_club ?? 1));

  const frozen = readiness.data?.configuration_frozen ?? false;
  const drawn = readiness.data?.has_pairing_list ?? false;

  // What may be chosen is the server's answer (Story VA-6), and what the event has now is
  // always among the choices — an organizer who could not pick it today keeps it.
  const series = [...(options.data?.series ?? [])];
  if (event.series && !series.some((s) => s.id === event.series!.id)) series.unshift({ ...event.series, registered: 0 });
  const hosts = [...(options.data?.hosts ?? [])];
  if (event.host_club && !hosts.some((c) => c.id === event.host_club!.id)) hosts.unshift(event.host_club);
  const venues = [...(options.data?.venues ?? [])];
  if (event.venue && !venues.some((v) => v.id === event.venue!.id)) venues.unshift(event.venue);
  const sizes = sizeOptions(catalog.data ?? []);
  if (!sizes.some((s) => sizeKey(s) === current)) {
    sizes.unshift({ teams: event.team_count, boats: event.boat_count, maxFlights: event.flight_count });
  }
  const chosen = sizes.find((s) => sizeKey(s) === size);
  const maxFlights = Math.max(chosen?.maxFlights ?? event.flight_count, Number(flights) || 1);
  const resized =
    (chosen && (chosen.teams !== event.team_count || chosen.boats !== event.boat_count)) ||
    Number(flights) !== event.flight_count;

  const changes: Record<string, unknown> = {};
  if (title.trim() !== event.title) changes.title = title.trim();
  if ((event.host_club ? String(event.host_club.id) : "") !== hostId) changes.host_club_id = hostId ? Number(hostId) : null;
  if ((event.venue ? String(event.venue.id) : "") !== venueId) changes.venue_id = venueId ? Number(venueId) : null;
  if (!frozen) {
    if ((event.series ? String(event.series.id) : "") !== seriesId || String(event.matchday ?? "") !== matchday) {
      changes.series = seriesId ? Number(seriesId) : null;
      changes.matchday = seriesId && matchday ? Number(matchday) : null;
    }
    if (chosen && chosen.teams !== event.team_count) changes.team_count = chosen.teams;
    if (chosen && chosen.boats !== event.boat_count) changes.boat_count = chosen.boats;
    if (Number(flights) !== event.flight_count) changes.flight_count = Number(flights);
    if (Number(teamsPerClub) !== (event.teams_per_club ?? 1)) changes.teams_per_club = Number(teamsPerClub);
  }
  const dirty = Object.keys(changes).length > 0;

  return (
    <form
      className="grid grid-cols-[minmax(0,1fr)] gap-3"
      data-testid="me-event-general-form"
      onSubmit={(e: FormEvent) => {
        e.preventDefault();
        save.mutate({ eventId: event.id, data: changes });
      }}
    >
      <Field label={ta("events.nameLabel")}>
        <input
          className={INPUT_CLASS}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          minLength={3}
          required
          data-testid="me-event-general-title"
        />
      </Field>
      <div className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-2">
        <Field label={ta("events.hostLabel")}>
          <Select value={hostId} onChange={(e) => setHostId(e.target.value)} testId="me-event-general-host">
            <option value="">{ta("events.hostNone")}</option>
            {hosts.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t("eventSections.factVenue")}>
          <Select value={venueId} onChange={(e) => setVenueId(e.target.value)} testId="me-event-general-venue">
            <option value="">{t("eventSections.notSet")}</option>
            {venues.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name}
              </option>
            ))}
          </Select>
        </Field>
      </div>

      <fieldset disabled={frozen} className="grid grid-cols-[minmax(0,1fr)] gap-3">
        {frozen && (
          <p className="text-sm text-muted" data-testid="me-event-general-frozen">
            {t("eventSections.configurationFrozen")}
          </p>
        )}
        <div className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-[2fr_1fr]">
          <Field label={ta("events.seriesLabel")}>
            <Select value={seriesId} onChange={(e) => setSeriesId(e.target.value)} testId="me-event-general-series">
              <option value="">{ta("events.seriesNone")}</option>
              {series.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("eventSections.matchday")}>
            <input
              className={INPUT_CLASS}
              type="number"
              min={1}
              value={matchday}
              disabled={!seriesId}
              onChange={(e) => setMatchday(e.target.value)}
              data-testid="me-event-general-matchday"
            />
          </Field>
        </div>
        <div className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-[2fr_1fr_1fr]">
          <Field label={ta("events.setupLabel")} hint={ta("events.setupHint")}>
            <Select value={size} onChange={(e) => setSize(e.target.value)} testId="me-event-general-size">
              {sizes.map((s) => (
                <option key={sizeKey(s)} value={sizeKey(s)}>
                  {ta("events.sizeOption", { teams: s.teams, boats: s.boats })}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={ta("events.flightsLabel")}>
            <Select value={flights} onChange={(e) => setFlights(e.target.value)} testId="me-event-general-flights">
              {Array.from({ length: maxFlights }, (_, i) => i + 1).map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("eventSections.teamsPerClub")}>
            <input
              className={INPUT_CLASS}
              type="number"
              min={1}
              value={teamsPerClub}
              onChange={(e) => setTeamsPerClub(e.target.value)}
              data-testid="me-event-general-teams-per-club"
            />
          </Field>
        </div>
        {resized && drawn && (
          <p className="text-sm text-warning-soft-foreground" data-testid="me-event-general-discards-draw">
            {t("eventSections.resizeDiscardsDraw")}
          </p>
        )}
      </fieldset>

      <div>
        <Button type="submit" isDisabled={!dirty || save.isPending || title.trim().length < 3} data-testid="me-event-general-save">
          {save.isPending ? ta("manage.savingButton") : t("eventSections.save")}
        </Button>
      </div>
      <Message
        testId="me-event-general-message"
        error={save.isError ? errorText(save.error) : null}
        success={save.isSuccess && !dirty ? t("eventSections.saved") : null}
      />
    </form>
  );
}

/** A boat as the table edits it: a league colour by name, or any other as its value. */
function rowOf(boat: { number: number; color?: string | null; name?: string | null }): BoatRow {
  const color = boat.color ?? "WHITE";
  const named = PREDEFINED_COLORS.includes(color);
  return {
    color: named ? color : CUSTOM_COLOR,
    customColor: named ? boatColor(color).hex : color,
    name: boat.name ?? "",
  };
}

/** Story VA-8: *Set up › Boats* — each boat's colour and name, kept by its number, so a
 *  renamed or recoloured boat keeps its place in a draw. How many there are is the size,
 *  set in *General*. Frozen by the first race, like the rest of the configuration. */
export function EventBoatsForm({ event }: { event: EventSummary }) {
  const { t } = useTranslation("space");
  const boats = useAsync(useListEventBoats(event.id));
  const readiness = useAsync(useGetReadiness(event.id));
  const frozen = readiness.data?.configuration_frozen ?? false;
  if (!boats.data) return null;
  return (
    <BoatsEditor
      key={event.id}
      eventId={event.id}
      initial={boats.data.map(rowOf)}
      frozen={frozen}
      labels={{ frozen: t("eventSections.configurationFrozen"), saved: t("eventSections.saved"), save: t("eventSections.save") }}
    />
  );
}

function BoatsEditor({
  eventId,
  initial,
  frozen,
  labels,
}: {
  eventId: number;
  initial: BoatRow[];
  frozen: boolean;
  labels: { frozen: string; saved: string; save: string };
}) {
  const [rows, setRows] = useState(initial);
  // What is stored, as far as this form knows: the boats it was opened with, then what it
  // last saved — so "Saved." stays until the next change.
  const [stored, setStored] = useState(initial);
  const refresh = useEventRefresh(eventId);
  const save = useUpdateEvent({
    mutation: {
      onSuccess: () => {
        setStored(rows);
        refresh();
      },
    },
  });
  const dirty = JSON.stringify(rows) !== JSON.stringify(stored);
  return (
    <form
      className="grid grid-cols-[minmax(0,1fr)] gap-3"
      data-testid="me-event-boats-form"
      onSubmit={(e: FormEvent) => {
        e.preventDefault();
        // An unnamed boat stays unnamed (it is printed as "Boat 3"): only the wizard asks
        // for every name, when the boats are first laid out.
        save.mutate({ eventId, data: { boats: boatSpecs(rows).map((b) => ({ ...b, name: b.name || null })) } });
      }}
    >
      {frozen && (
        <p className="text-sm text-muted" data-testid="me-event-boats-frozen">
          {labels.frozen}
        </p>
      )}
      <fieldset disabled={frozen}>
        <BoatTable rows={rows} onChange={setRows} namesRequired={false} />
      </fieldset>
      <div>
        <Button
          type="submit"
          isDisabled={frozen || !dirty || save.isPending}
          data-testid="me-event-boats-save"
        >
          {labels.save}
        </Button>
      </div>
      <Message testId="me-event-boats-message" error={save.isError ? errorText(save.error) : null} success={save.isSuccess && !dirty ? labels.saved : null} />
    </form>
  );
}
