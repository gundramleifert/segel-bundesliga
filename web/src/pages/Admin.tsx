import { Button } from "@heroui/react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { CrestEditor } from "../components/CrestEditor";

import { Stack } from "../components/Layouts";
import {
  getListAllClubsQueryKey,
  getListAllSeriesQueryKey,
  useListAllClubs,
  useListAllSeries,
  usePublishSeries,
  useSetClubs,
  useUnpublishSeries,
  useUpdateSeries,
} from "../api/generated/sbl";
import type { ClubAdmin, SeriesAdmin } from "../api/types";
import { WHOLE_LIST, useAsyncRows, useInvalidate } from "../api/useApi";
import { ErrorMessage, Loading, Empty } from "../components/Blocks";
import { INPUT_CLASS, errorText, toggleSet } from "../lib/admin";
import { Section, Field, Message } from "../components/Form";
import { ClubSelector } from "../components/ClubSelector";
import { AddButton } from "../components/AddButton";
import { AccessPanel } from "../components/AccessPanel";

/** Stories A-1, A-4, A-6: the league office's clubs and series sections (Story A-11,
 *  `/office/<section>`, drawn by `pages/office/Office.tsx`). Until issue #32 this file
 *  was `/admin`, a page of tabs holding every object's administration; each object's own
 *  work now lives in its context in My space, and these panels are the office's. */

// ---------------------------------------------------------------------- Clubs

export function Clubs() {
  const { t } = useTranslation("admin");
  // Every club, not a page: this list is the master data screen and the source for the
  // selects below it (Story A-13).
  const { data, error, loading } = useAsyncRows(useListAllClubs({ limit: WHOLE_LIST }));
  const invalidate = useInvalidate();

  return (
    <Section
      title={t("clubs.title")}
      testId="admin-clubs-section"
      action={<AddButton label={t("clubs.newButton")} to="/office/clubs/new" testId="admin-clubs-new-button" />}
    >
      {loading && <Loading text={t("clubs.loadingText")} testId="admin-clubs-loading" />}
      {error && <ErrorMessage text={error} testId="admin-clubs-error" />}
      {data && (
        <p data-testid="admin-clubs-stats" className="text-sm text-muted">
          {t("clubs.statsText", { count: data.length, visible: data.filter((v) => v.visible).length })}
        </p>
      )}
      {data &&
        (data.length ? (
          <ul
            data-testid="admin-clubs-list"
            className="divide-y divide-separator rounded-lg border border-separator"
          >
            {data.map((club) => (
              <ClubRow key={club.id} club={club} onChanged={() => invalidate(getListAllClubsQueryKey(), "/api/clubs")} />
            ))}
          </ul>
        ) : (
          <Empty testId="admin-clubs-empty">{t("clubs.emptyText")}</Empty>
        ))}
    </Section>
  );
}

/** One club, with its crest — Story V-3, edited through `CrestEditor`. */
function ClubRow({ club, onChanged }: { club: ClubAdmin; onChanged: () => void }) {
  return (
    <li data-testid={`admin-club-row-${club.id}`} className="flex flex-wrap items-center gap-3 px-4 py-3">
      <CrestEditor club={club} onChanged={onChanged} testIdPrefix="admin-club-crest">
        <div className="min-w-0 flex-1">
          <Link
            to={`/clubs/${club.id}`}
            data-testid={`admin-club-link-${club.id}`}
            className="font-medium underline-offset-2 hover:underline"
          >
            {club.name}
          </Link>
          <p className="text-sm text-muted">
            {[club.short_name, club.city].filter(Boolean).join(" · ")}
          </p>
        </div>
      </CrestEditor>
    </li>
  );
}

// ----------------------------------------------------------------------- Series

/** Every series for the league office; a series manager's own (`GET /api/admin/series`
 *  narrows it), without the button that creates one — that stays the admin's (A-4). */
export function SeriesList({ mayCreate }: { mayCreate: boolean }) {
  const { t } = useTranslation("admin");
  const seriesList = useAsyncRows(useListAllSeries({ limit: WHOLE_LIST }));
  // The rows' club selectors have to offer every club, so this asks for the whole list.
  const clubs = useAsyncRows(useListAllClubs({ limit: WHOLE_LIST }));
  const invalidate = useInvalidate();

  return (
    <Section
      title={t("series.title")}
      testId="admin-series-section"
      action={
        mayCreate && <AddButton label={t("series.newButton")} to="/office/series/new" testId="admin-series-new-button" />
      }
    >
      {seriesList.loading && <Loading text={t("series.loadingText")} testId="admin-series-loading" />}
      {seriesList.error && <ErrorMessage text={seriesList.error} testId="admin-series-error" />}
      {seriesList.data &&
        (seriesList.data.length ? (
          <ul data-testid="admin-series-list" className="divide-y divide-separator rounded-lg border border-separator">
            {seriesList.data.map((series) => (
              <SeriesRow
                key={series.id}
                series={series}
                clubs={clubs.data ?? []}
                onChanged={() => invalidate(getListAllSeriesQueryKey(), "/api/series", "/api/clubs")}
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
  series,
  clubs,
  onChanged,
}: {
  series: SeriesAdmin;
  clubs: ClubAdmin[];
  onChanged: () => void;
}) {
  const { t } = useTranslation("admin");
  const [open, setOpen] = useState(false);
  const [selectedClubs, setSelectedClubs] = useState<Set<number>>(
    () => new Set((series.clubs ?? []).map((c) => c.id)),
  );
  const [description, setDescription] = useState(series.description ?? "");
  // Story V-1: how many people a club registers for this series. The maximum is enforced
  // when a squad is saved, the minimum shown on the club screen.
  const [squadMin, setSquadMin] = useState(String(series.squad_min));
  const [squadMax, setSquadMax] = useState(String(series.squad_max));
  const saveLimits = useUpdateSeries({ mutation: { onSuccess: () => onChanged() } });

  const save = useSetClubs({
    mutation: {
      onSuccess: () => {
        setOpen(false);
        onChanged();
      },
    },
  });

  const saveDescription = useUpdateSeries({ mutation: { onSuccess: () => onChanged() } });

  // Story VA-8: a series is planned long before anyone should read about it — clubs are
  // still being assigned, the name still argued over. Publishing changes only who can see
  // it and locks nothing, which is why this is a plain toggle and not a final step.
  // Two endpoints, not one with a flag — so the screen picks by what the row currently
  // is. `isPending` has to consider both, or the button stays live while the other is
  // in flight.
  const publish = usePublishSeries({ mutation: { onSuccess: () => onChanged() } });
  const unpublish = useUnpublishSeries({ mutation: { onSuccess: () => onChanged() } });
  const publication = series.published ? unpublish : publish;

  return (
    <li data-testid={`admin-series-row-${series.id}`} className="px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Link
              to={`/series/${series.id}`}
              data-testid={`admin-series-link-${series.id}`}
              className="font-medium underline-offset-2 hover:underline"
            >
              {series.name}
            </Link>
            <span
              data-testid={`admin-series-publication-${series.id}`}
              className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${
                series.published
                  ? "bg-accent-soft text-accent-soft-foreground ring-accent/30"
                  : "bg-warning-soft text-warning-soft-foreground ring-warning/50"
              }`}
            >
              {series.published ? t("series.publishedBadge") : t("series.draftBadge")}
            </span>
          </div>
          <p className="text-sm text-muted">
            {t("series.itemText", { count: series.clubs?.length ?? 0, events: series.event_count })}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="ghost"
            isDisabled={publication.isPending}
            onPress={() => publication.mutate({ seriesId: series.id })}
            data-testid={`admin-series-publish-button-${series.id}`}
          >
            {series.published ? t("series.unpublishButton") : t("series.publishButton")}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onPress={() => setOpen((o) => !o)}
            data-testid={`admin-series-edit-button-${series.id}`}
          >
            {open ? t("series.closeButton") : t("series.editButton")}
          </Button>
        </div>
      </div>
      {publication.isError && (
        <ErrorMessage
          text={errorText(publication.error)}
          testId={`admin-series-publish-error-${series.id}`}
        />
      )}

      {open && (
        <Stack className="mt-3">
          <AccessPanel object={`series:${series.id}`} testId={`admin-series-access-${series.id}`} />
          <Stack gap={3}>
            <ClubSelector
              clubs={clubs}
              selectedIds={selectedClubs}
              toggle={toggleSet(setSelectedClubs)}
              testId={`admin-series-edit-clubs-${series.id}`}
            />
            <div className="flex items-center gap-3">
              <Button
                size="sm"
                isDisabled={save.isPending}
                onPress={() => save.mutate({ seriesId: series.id, data: { clubs: [...selectedClubs] } })}
                data-testid={`admin-series-save-clubs-button-${series.id}`}
              >
                {save.isPending ? t("series.savingButton") : t("series.saveButton", { count: selectedClubs.size })}
              </Button>
              <span className="text-sm text-muted">
                {t("series.saveHint")}
              </span>
            </div>
            {save.isError && (
              <ErrorMessage text={errorText(save.error)} testId={`admin-series-save-clubs-error-${series.id}`} />
            )}
          </Stack>

          <div className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-[auto_auto_auto] sm:items-end">
            <Field label={t("series.squadMinLabel")} hint={t("series.squadMinHint")}>
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
            <Field label={t("series.squadMaxLabel")} hint={t("series.squadMaxHint")}>
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
              isDisabled={saveLimits.isPending || !squadMin || !squadMax}
              onPress={() =>
                saveLimits.mutate({
                  seriesId: series.id,
                  data: { squad_min: Number(squadMin), squad_max: Number(squadMax) },
                })
              }
              data-testid={`admin-series-save-squad-limits-${series.id}`}
            >
              {saveLimits.isPending ? t("series.savingButton") : t("series.saveSquadLimitsButton")}
            </Button>
          </div>
          <Message
            testId={`admin-series-squad-limits-message-${series.id}`}
            error={saveLimits.isError ? errorText(saveLimits.error) : null}
            success={saveLimits.isSuccess ? t("series.squadLimitsSavedMessage") : null}
          />

          <Field label={t("series.descriptionLabel")} hint={t("series.descriptionHint")}>
            <textarea
              className={INPUT_CLASS}
              rows={4}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={t("series.descriptionPlaceholder")}
              data-testid={`admin-series-description-input-${series.id}`}
            />
          </Field>
          <div className="flex items-center gap-3">
            <Button
              size="sm"
              isDisabled={saveDescription.isPending}
              onPress={() =>
                saveDescription.mutate({
                  seriesId: series.id,
                  data: { description: description.trim() || null },
                })
              }
              data-testid={`admin-series-save-description-button-${series.id}`}
            >
              {saveDescription.isPending
                ? t("series.savingButton")
                : t("series.saveDescriptionButton")}
            </Button>
            {saveDescription.isSuccess && (
              <span
                data-testid={`admin-series-description-saved-${series.id}`}
                className="text-sm text-success-soft-foreground"
              >
                {t("series.descriptionSavedMessage")}
              </span>
            )}
          </div>
          {saveDescription.isError && (
            <ErrorMessage
              text={errorText(saveDescription.error)}
              testId={`admin-series-description-error-${series.id}`}
            />
          )}
        </Stack>
      )}
    </li>
  );
}
