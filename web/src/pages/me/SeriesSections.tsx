import { Button } from "@heroui/react";
import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import {
  getListAllSeriesQueryKey,
  useAcceptApplication,
  useEventCreateOptions,
  useListAllEvents,
  useListAllSeries,
  useListPendingApplications,
  usePublishSeries,
  useRejectApplication,
  useSetClubs,
  useUnpublishSeries,
  useUpdateSeries,
} from "../../api/generated/sbl";
import type { ApplicationOut } from "../../api/generated/model/applicationOut";
import type { MyContext, SeriesAdmin } from "../../api/types";
import { WHOLE_LIST, useAsync, useAsyncRows, useInvalidate } from "../../api/useApi";
import { AccessPanel } from "../../components/AccessPanel";
import { Async } from "../../components/Async";
import { Badge, ErrorMessage, Loading } from "../../components/Blocks";
import { ClubSelector } from "../../components/ClubSelector";
import { Field, Message, Section } from "../../components/Form";
import { Stack } from "../../components/Layouts";
import { INPUT_CLASS, errorText, toggleSet } from "../../lib/admin";
import { EventLinks } from "./EventLinks";

/** Story Z-10: a series' *Organize* and *Officials* sections — what the administration's
 * series row did (clubs, publication, squad size, description, people), each in the
 * series' own context now (#32). The series manager and the league office see them; the
 * model decides (`lib/workspace.ts`), and every write asks it again on the server.
 */

/** The series as its organizers' list answers it (`GET /api/admin/series`, narrowed to
 *  theirs) — the one read that carries its clubs and its drafts. */
function WithSeries({ seriesId, children }: { seriesId: number; children: (series: SeriesAdmin) => ReactNode }) {
  const { t } = useTranslation("space");
  const list = useAsyncRows(useListAllSeries({ limit: WHOLE_LIST }));
  if (list.loading) return <Loading testId="me-series-loading" />;
  if (list.error) return <ErrorMessage text={list.error} testId="me-series-error" />;
  const series = list.data?.find((s) => s.id === seriesId);
  if (!series) return <ErrorMessage text={t("seriesSections.notFound")} testId="me-series-not-found" />;
  return <>{children(series)}</>;
}

function useSeriesRefresh() {
  const invalidate = useInvalidate();
  return () => invalidate(getListAllSeriesQueryKey(), "/api/series", "/api/clubs", "/api/me/contexts", "/api/admin/applications");
}

// ------------------------------------------------------------------ Clubs & registrations

/** The clubs registered for the series (Story A-4, A-9): set directly — accepted at once —
 *  and the clubs' applications still waiting for a decision (V-5). */
export function SeriesRegistrations({ seriesId }: { seriesId: number }) {
  return (
    <WithSeries seriesId={seriesId}>
      {(series) => (
        <Stack>
          <Applications seriesId={series.id} />
          <SeriesClubs key={(series.clubs ?? []).map((c) => c.id).join(",")} series={series} />
        </Stack>
      )}
    </WithSeries>
  );
}

function SeriesClubs({ series }: { series: SeriesAdmin }) {
  const { t } = useTranslation("space");
  const { t: ta } = useTranslation("admin");
  const refresh = useSeriesRefresh();
  // The clubs a series' organizer may choose from: the event wizard's hosts are every club
  // for them (an act's host is theirs to name), and the league office's club list is the
  // site admin's alone.
  const options = useAsync(useEventCreateOptions());
  const registered = series.clubs ?? [];
  const shortOf = new Map(registered.map((c) => [c.id, c.short_name]));
  const clubs = (options.data?.hosts ?? registered).map((c) => ({ id: c.id, name: c.name, short_name: shortOf.get(c.id) ?? "" }));
  const [selected, setSelected] = useState<Set<number>>(() => new Set(registered.map((c) => c.id)));
  const save = useSetClubs({ mutation: { onSuccess: refresh } });

  return (
    <Section title={t("seriesSections.clubsTitle")} testId={`me-series-clubs-${series.id}`}>
      <Stack gap={3}>
        <p className="text-sm text-muted">{t("seriesSections.clubsHint")}</p>
        {options.loading ? (
          <Loading testId="me-series-clubs-loading" />
        ) : (
          <ClubSelector
            clubs={clubs}
            selectedIds={selected}
            toggle={toggleSet(setSelected)}
            testId={`admin-series-edit-clubs-${series.id}`}
          />
        )}
        <div className="flex flex-wrap items-center gap-3">
          <Button
            size="sm"
            isDisabled={save.isPending || options.loading}
            onPress={() => save.mutate({ seriesId: series.id, data: { clubs: [...selected] } })}
            data-testid={`admin-series-save-clubs-button-${series.id}`}
          >
            {save.isPending ? ta("series.savingButton") : ta("series.saveButton", { count: selected.size })}
          </Button>
          <span className="text-sm text-muted">{ta("series.saveHint")}</span>
        </div>
        <Message
          testId={`admin-series-save-clubs-message-${series.id}`}
          error={save.isError ? errorText(save.error) : null}
          success={save.isSuccess ? t("seriesSections.saved") : null}
        />
      </Stack>
    </Section>
  );
}

/** Applications to the series, each accepted or rejected with a reason (Story A-9). */
function Applications({ seriesId }: { seriesId: number }) {
  const { t } = useTranslation("space");
  const rows = useAsync(useListPendingApplications({ series_id: seriesId }));
  if (!rows.data?.length) return null;
  return (
    <Section title={t("seriesSections.applicationsTitle")} testId={`me-series-applications-${seriesId}`}>
      <ul className="flex flex-col divide-y divide-separator">
        {rows.data.map((row) => (
          <Application key={row.team_id} row={row} />
        ))}
      </ul>
    </Section>
  );
}

function Application({ row }: { row: ApplicationOut }) {
  const { t } = useTranslation("space");
  const refresh = useSeriesRefresh();
  const [note, setNote] = useState("");
  const accept = useAcceptApplication({ mutation: { onSuccess: refresh } });
  const reject = useRejectApplication({ mutation: { onSuccess: refresh } });
  const id = `me-series-application-${row.team_id}`;
  const busy = accept.isPending || reject.isPending;
  const failed = accept.error ?? reject.error;
  return (
    <li className="flex flex-col gap-2 py-3" data-testid={id}>
      <span className="font-medium">{row.club.name}</span>
      <div className="flex flex-wrap items-center gap-2">
        <div className="min-w-0 flex-1">
          <input
            className={INPUT_CLASS}
            value={note}
            maxLength={500}
            onChange={(e) => setNote(e.target.value)}
            placeholder={t("seriesSections.rejectNote")}
            aria-label={t("seriesSections.rejectNote")}
            data-testid={`${id}-note`}
          />
        </div>
        <Button size="sm" isDisabled={busy} onPress={() => accept.mutate({ teamId: row.team_id, data: null })} data-testid={`${id}-accept`}>
          {t("seriesSections.accept")}
        </Button>
        <Button
          size="sm"
          variant="danger"
          isDisabled={busy}
          onPress={() => reject.mutate({ teamId: row.team_id, data: { note: note.trim() || null } })}
          data-testid={`${id}-reject`}
        >
          {t("seriesSections.reject")}
        </Button>
      </div>
      {failed && <ErrorMessage text={errorText(failed)} testId={`${id}-error`} />}
    </li>
  );
}

// ------------------------------------------------------------------ Dates & publication

/** When the series sails, whether the public site shows it (VA-8: publishing locks
 *  nothing), and the text its public page carries. */
export function SeriesDates({ seriesId }: { seriesId: number }) {
  return <WithSeries seriesId={seriesId}>{(series) => <DatesForm key={series.id} series={series} />}</WithSeries>;
}

function DatesForm({ series }: { series: SeriesAdmin }) {
  const { t } = useTranslation("space");
  const { t: ta } = useTranslation("admin");
  const refresh = useSeriesRefresh();
  const [startsOn, setStartsOn] = useState(series.starts_on ?? "");
  const [endsOn, setEndsOn] = useState(series.ends_on ?? "");
  const [description, setDescription] = useState(series.description ?? "");
  const saveDates = useUpdateSeries({ mutation: { onSuccess: refresh } });
  const saveDescription = useUpdateSeries({ mutation: { onSuccess: refresh } });
  // Two endpoints, picked by what the series currently is (as on the series row before).
  const publish = usePublishSeries({ mutation: { onSuccess: refresh } });
  const unpublish = useUnpublishSeries({ mutation: { onSuccess: refresh } });
  const publication = series.published ? unpublish : publish;
  const id = `me-series-dates-${series.id}`;

  return (
    <Stack>
      <Section title={t("seriesSections.publicationTitle")} testId={`${id}-publication`}>
        <div className="flex flex-wrap items-center gap-3">
          <Badge tone={series.published ? "brand" : "warning"} testId={`admin-series-publication-${series.id}`}>
            {series.published ? ta("series.publishedBadge") : ta("series.draftBadge")}
          </Badge>
          <Button
            size="sm"
            variant="outline"
            isDisabled={publication.isPending}
            onPress={() => publication.mutate({ seriesId: series.id })}
            data-testid={`admin-series-publish-button-${series.id}`}
          >
            {series.published ? ta("series.unpublishButton") : ta("series.publishButton")}
          </Button>
        </div>
        <p className="mt-2 text-sm text-muted">{t("seriesSections.publicationHint")}</p>
        {publication.isError && (
          <ErrorMessage text={errorText(publication.error)} testId={`admin-series-publish-error-${series.id}`} />
        )}
      </Section>

      <Section title={t("seriesSections.datesTitle")} testId={id}>
        <div className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-[auto_auto_auto] sm:items-end">
          <Field label={t("seriesSections.startsOn")}>
            <input type="date" className={INPUT_CLASS} value={startsOn} onChange={(e) => setStartsOn(e.target.value)} data-testid={`${id}-starts-on`} />
          </Field>
          <Field label={t("seriesSections.endsOn")}>
            <input type="date" className={INPUT_CLASS} value={endsOn} onChange={(e) => setEndsOn(e.target.value)} data-testid={`${id}-ends-on`} />
          </Field>
          <Button
            size="sm"
            isDisabled={saveDates.isPending}
            onPress={() => saveDates.mutate({ seriesId: series.id, data: { starts_on: startsOn || null, ends_on: endsOn || null } })}
            data-testid={`${id}-save`}
          >
            {saveDates.isPending ? ta("series.savingButton") : t("seriesSections.saveDates")}
          </Button>
        </div>
        <Message testId={`${id}-message`} error={saveDates.isError ? errorText(saveDates.error) : null} success={saveDates.isSuccess ? t("seriesSections.saved") : null} />
      </Section>

      <Section title={ta("series.descriptionLabel")} testId={`${id}-description`}>
        <Field label={ta("series.descriptionLabel")} hint={ta("series.descriptionHint")}>
          <textarea
            className={INPUT_CLASS}
            rows={4}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder={ta("series.descriptionPlaceholder")}
            data-testid={`admin-series-description-input-${series.id}`}
          />
        </Field>
        <div className="mt-3 flex items-center gap-3">
          <Button
            size="sm"
            isDisabled={saveDescription.isPending}
            onPress={() => saveDescription.mutate({ seriesId: series.id, data: { description: description.trim() || null } })}
            data-testid={`admin-series-save-description-button-${series.id}`}
          >
            {saveDescription.isPending ? ta("series.savingButton") : ta("series.saveDescriptionButton")}
          </Button>
          {saveDescription.isSuccess && (
            <span data-testid={`admin-series-description-saved-${series.id}`} className="text-sm text-success-soft-foreground">
              {ta("series.descriptionSavedMessage")}
            </span>
          )}
        </div>
        {saveDescription.isError && (
          <ErrorMessage text={errorText(saveDescription.error)} testId={`admin-series-description-error-${series.id}`} />
        )}
      </Section>
    </Stack>
  );
}

// ------------------------------------------------------------------ Squad size & scoring

/** How many people a club registers (Story V-1): the maximum enforced when a squad is
 *  saved, the minimum shown on the club's screen. The scoring rules have no editor yet. */
export function SeriesScoring({ seriesId }: { seriesId: number }) {
  return <WithSeries seriesId={seriesId}>{(series) => <SquadLimits key={series.id} series={series} />}</WithSeries>;
}

function SquadLimits({ series }: { series: SeriesAdmin }) {
  const { t } = useTranslation("space");
  const { t: ta } = useTranslation("admin");
  const refresh = useSeriesRefresh();
  const [squadMin, setSquadMin] = useState(String(series.squad_min));
  const [squadMax, setSquadMax] = useState(String(series.squad_max));
  const save = useUpdateSeries({ mutation: { onSuccess: refresh } });
  return (
    <Section title={t("seriesSections.squadTitle")} testId={`me-series-scoring-${series.id}`}>
      <div className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-[auto_auto_auto] sm:items-end">
        <Field label={ta("series.squadMinLabel")} hint={ta("series.squadMinHint")}>
          <input
            type="number"
            min={1}
            max={50}
            className={INPUT_CLASS}
            value={squadMin}
            onChange={(e) => setSquadMin(e.target.value)}
            data-testid={`admin-series-squad-min-${series.id}`}
          />
        </Field>
        <Field label={ta("series.squadMaxLabel")} hint={ta("series.squadMaxHint")}>
          <input
            type="number"
            min={1}
            max={50}
            className={INPUT_CLASS}
            value={squadMax}
            onChange={(e) => setSquadMax(e.target.value)}
            data-testid={`admin-series-squad-max-${series.id}`}
          />
        </Field>
        <Button
          size="sm"
          isDisabled={save.isPending || !squadMin || !squadMax}
          onPress={() => save.mutate({ seriesId: series.id, data: { squad_min: Number(squadMin), squad_max: Number(squadMax) } })}
          data-testid={`admin-series-save-squad-limits-${series.id}`}
        >
          {save.isPending ? ta("series.savingButton") : ta("series.saveSquadLimitsButton")}
        </Button>
      </div>
      <Message
        testId={`admin-series-squad-limits-message-${series.id}`}
        error={save.isError ? errorText(save.error) : null}
        success={save.isSuccess ? ta("series.squadLimitsSavedMessage") : null}
      />
    </Section>
  );
}

// ------------------------------------------------------------------ Officials, standings, events

/** Who holds what on the series — its race committee and jury, its managers and editors
 *  (Story Z-2): held here, they reach every event of it. */
export function SeriesOfficials({ seriesId }: { seriesId: number }) {
  const { t } = useTranslation("space");
  return (
    <Stack gap={3}>
      <p className="text-sm text-muted">{t("seriesSections.officialsHint")}</p>
      <AccessPanel object={`series:${seriesId}`} testId={`me-series-officials-${seriesId}`} />
    </Stack>
  );
}

/** The table lives on the public page; a draft has none to show yet. */
export function SeriesStandings({ context }: { context: MyContext }) {
  const { t } = useTranslation("space");
  return context.published ? (
    <div className="flex flex-col gap-2" data-testid="me-series-standings">
      <p className="text-sm text-muted">{t("seriesSections.standingsHint")}</p>
      <Link to={`/series/${context.id}`} className="w-fit font-medium text-link underline-offset-2 hover:underline" data-testid="me-series-standings-link">
        {t("seriesSections.standingsLink")} →
      </Link>
    </div>
  ) : (
    <p className="text-sm text-muted" data-testid="me-series-standings-draft">
      {t("seriesSections.standingsDraft")}
    </p>
  );
}

/** Every act of the series, drafts included, each opening the event's context — for its
 *  organizers, who organize them there. The server narrows the list to the series
 *  (`series_id`, Story A-13). */
export function OrganizerSeriesEvents({ seriesId }: { seriesId: number }) {
  const { t } = useTranslation("space");
  const events = useAsync(useListAllEvents({ series_id: seriesId, limit: WHOLE_LIST }));
  const ours = [...(events.data?.items ?? [])]
    .sort((a, b) => (a.matchday ?? 99) - (b.matchday ?? 99) || (a.starts_on ?? "9999").localeCompare(b.starts_on ?? "9999"));
  return (
    <Async state={events} testId="me-series-events" empty={t("context.noEvents")} isEmpty={() => !ours.length}>
      {() => <EventLinks events={ours} testId="me-series-event" />}
    </Async>
  );
}
