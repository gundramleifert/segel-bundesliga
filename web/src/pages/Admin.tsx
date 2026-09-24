import { Button, Spinner } from "@heroui/react";
import { useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { Tip } from "../components/Tip";

import { Stack } from "../components/Layouts";
import {
  getListAllClubsQueryKey,
  getListAllSeriesQueryKey,
  useDeleteClubLogo,
  useListAllClubs,
  useListAllSeries,
  usePublishSeries,
  useSetClubs,
  useUnpublishSeries,
  useUpdateSeries,
  useUploadClubLogo,
} from "../api/generated/sbl";
import type { ClubAdmin, SeriesAdmin } from "../api/types";
import { WHOLE_LIST, useAsyncRows, useInvalidate, useAccount } from "../api/useApi";
import { ErrorMessage, Loading, Empty, PageHeader } from "../components/Blocks";
import { TabbedView, type TabDef } from "../components/Tabs";
import { AccountsAdmin } from "./AdminAccounts";
import { EventsAdmin } from "./AdminEvents";
import { SailorsAdmin } from "./AdminSailors";
import { INPUT_CLASS, errorText, toggleSet } from "../lib/admin";
import { Section, Field, Message } from "../components/Form";
import { ClubSelector } from "../components/ClubSelector";
import { AddButton } from "../components/AddButton";

/** Stories A-1, A-4, A-6 and A-11: create clubs, create series, schedule events.
 *
 * **One tab per area**, in the order the work happens: clubs, then a series with those
 * clubs, then events for that series, then the people. A series without clubs has no
 * standings and an event without a series counts toward no scoring, which is why the order
 * is this and not alphabetical — the tabs read as the sequence a new season is set up in.
 *
 * They were five stacked sections until Story A-11. Each is short on its own; together
 * they were a page nobody read top to bottom, with the events area — the one used on a
 * jetty — several screens down. Tabs also mean one area's queries load instead of five.
 */
/** Who may be here: signed in, and `admin` or `editor` — or `admin` alone with `adminOnly`.
 *  The same rule for `/admin` and for every `/admin/<area>/new` page (`AdminNewPage`).
 *  An `event_manager` or `jury` (Story Z-2) is let in as well: the events tab is theirs,
 *  the others do not exist for them (see `AdminTabs`). */
export function AdminAccess({
  adminOnly = false,
  children,
}: {
  adminOnly?: boolean;
  children: ReactNode;
}) {
  const { t } = useTranslation("admin");
  const { account, loading, hasRole } = useAccount();

  if (loading) return <Loading testId="admin-loading" />;
  if (!account) {
    return (
      <ErrorMessage text={t("auth.notSignedInError")} testId="admin-auth-error" />
    );
  }
  if (!(adminOnly ? hasRole("admin") : hasRole("admin", "editor", "event_manager", "jury"))) {
    return (
      <ErrorMessage text={t("auth.noAccessError")} testId="admin-access-error" />
    );
  }
  return <>{children}</>;
}

export function Admin() {
  return (
    <AdminAccess>
      <AdminTabs />
    </AdminAccess>
  );
}

function AdminTabs() {
  const { t } = useTranslation("admin");
  const { hasRole } = useAccount();

  // `render` rather than a node: `TabbedView` mounts only the selected panel, so an area
  // nobody opened never issues its queries. Building the elements eagerly here would undo
  // that — they would be created on every render of this component regardless.
  // The labels are each area's own section title, not a second set of strings: a tab whose
  // wording drifts from the heading it opens is a translation bug waiting to happen.
  // The league office sees every area; the organizer or jury of one event sees the
  // events tab alone — a tab a role may not use does not exist for it (Story A-11).
  const office = hasRole("admin", "editor");
  const tabs: TabDef<AdminTab>[] = office
    ? [
        { key: "clubs", label: t("clubs.title"), render: () => <Clubs /> },
        {
          key: "series",
          label: t("series.title"),
          render: () => <Series editorOnly={!hasRole("admin")} />,
        },
        { key: "events", label: t("events.title"), render: () => <EventsAdmin /> },
        { key: "sailors", label: t("sailors.title"), render: () => <SailorsAdmin /> },
      ]
    : [{ key: "events", label: t("events.title"), render: () => <EventsAdmin /> }];
  // Accounts is admin-only, so for an editor the tab does not exist rather than existing
  // and refusing — the same rule the section already followed.
  if (hasRole("admin")) {
    tabs.push({ key: "accounts", label: t("accounts.title"), render: () => <AccountsAdmin /> });
  }

  return (
    <>
      <PageHeader
        title={t("page.title")}
        testId="admin-header"
      />
      {/* `grid-cols-[minmax(0,1fr)]`, not a bare `grid`: an `auto` column is sized by its
          items' *min-content* width, so a single wide control anywhere in the panel
          stretches the column past the viewport. The browser then zooms the whole page out
          to fit (412px of viewport rendered as 754), which is why the admin screens were
          unusable on a phone (Story A-10). `minmax(0, 1fr)` lets the column be narrower
          than its content, so overflow stays inside whichever box actually overflows. */}
      <TabbedView
        tabs={tabs}
        param="tab"
        testIdPrefix="admin"
        label={t("page.tabsLabel")}
        className="grid grid-cols-[minmax(0,1fr)]"
      />
    </>
  );
}

/** The areas of the admin screen. Also the values `?tab=` accepts — an unknown one falls
 *  back to the first tab rather than erroring (Story A-11). */
export type AdminTab = "clubs" | "series" | "events" | "sailors" | "accounts";

// ---------------------------------------------------------------------- Clubs

function Clubs() {
  const { t } = useTranslation("admin");
  // Every club, not a page: this list is the master data screen and the source for the
  // selects below it (Story A-13).
  const { data, error, loading } = useAsyncRows(useListAllClubs({ limit: WHOLE_LIST }));
  const invalidate = useInvalidate();

  return (
    <Section
      title={t("clubs.title")}
      testId="admin-clubs-section"
      action={<AddButton label={t("clubs.newButton")} to="/admin/clubs/new" testId="admin-clubs-new-button" />}
    >
      {loading && <Loading text={t("clubs.loadingText")} testId="admin-clubs-loading" />}
      {error && <ErrorMessage text={error} testId="admin-clubs-error" />}
      {data && (
        <p data-testid="admin-clubs-stats" className="text-sm text-slate-600">
          {t("clubs.statsText", { count: data.length, visible: data.filter((v) => v.visible).length })}
        </p>
      )}
      {data &&
        (data.length ? (
          <ul
            data-testid="admin-clubs-list"
            className="divide-y divide-slate-100 rounded-lg border border-slate-200"
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

/** One club, with its crest — Story V-3.
 *
 * The crest ("Stander") is uploaded as a file rather than pasted as a URL: most clubs have
 * the image, not a place to host it. The thumbnail sits on a checkerboard so a transparent
 * burgee reads as transparent instead of as a white rectangle — the upload deliberately
 * keeps the alpha channel (see `app/services/crests.py`).
 *
 * **The crest is edited from the crest**, not from a button beside it: hovering it reveals
 * a pen, and clicking it opens the file chooser. A separate "Replace crest" button said the
 * same thing twice and put the action a row's width away from the thing it acts on.
 */
function ClubRow({ club, onChanged }: { club: ClubAdmin; onChanged: () => void }) {
  const { t } = useTranslation("admin");
  const fileInput = useRef<HTMLInputElement>(null);

  const upload = useUploadClubLogo({ mutation: { onSuccess: onChanged } });
  const remove = useDeleteClubLogo({ mutation: { onSuccess: onChanged } });

  const label = club.logo_url ? t("clubs.crestReplaceLabel") : t("clubs.crestUploadLabel");

  return (
    <li data-testid={`admin-club-row-${club.id}`} className="flex flex-wrap items-center gap-3 px-4 py-3">
      <input
        ref={fileInput}
        type="file"
        accept="image/png,image/jpeg,image/webp,image/gif"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          // Reset first: picking the same file twice in a row fires no change event
          // otherwise, so a retry after a failed upload would do nothing.
          e.target.value = "";
          if (file) upload.mutate({ clubId: club.id, data: { file } });
        }}
        data-testid={`admin-club-crest-input-${club.id}`}
      />

      {/* A real button, not a clickable div: it has to be reachable and operable from the
          keyboard, and the pen has to appear on focus as well as on hover — a pen that only
          shows under the mouse pointer tells a keyboard user nothing.

          No cache-busting suffix on the image: `logo_url` already carries the file's mtime
          as a `?v=` stamp (`app/crests.py`), so a replaced crest arrives under a new URL on
          its own once the list is invalidated. */}
      <Tip text={label}>
      <button
        type="button"
        onClick={() => fileInput.current?.click()}
        disabled={upload.isPending}
        aria-label={`${label}: ${club.name}`}
        data-testid={`admin-club-crest-edit-${club.id}`}
        className="crest-backdrop group relative grid size-10 shrink-0 cursor-pointer place-items-center overflow-hidden rounded border border-slate-200 outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
      >
        {club.logo_url ? (
          <img
            src={club.logo_url}
            alt=""
            className="size-10 object-contain"
            data-testid={`admin-club-crest-${club.id}`}
          />
        ) : (
          <span aria-hidden className="text-xs text-slate-400">
            —
          </span>
        )}
        <span
          aria-hidden
          data-testid={`admin-club-crest-pen-${club.id}`}
          className={`absolute inset-0 grid place-items-center bg-slate-900/55 text-white transition-opacity ${
            upload.isPending
              ? "opacity-100"
              : "opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100"
          }`}
        >
          {upload.isPending ? (
            <Spinner size="sm" />
          ) : (
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
              className="size-4"
            >
              <path d="M12 20h9" />
              <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
            </svg>
          )}
        </span>
      </button>
      </Tip>

      <div className="min-w-0 flex-1">
        <Link
          to={`/clubs/${club.id}`}
          data-testid={`admin-club-link-${club.id}`}
          className="font-medium underline-offset-2 hover:underline"
        >
          {club.name}
        </Link>
        <p className="text-sm text-slate-500">
          {[club.short_name, club.city].filter(Boolean).join(" · ")}
        </p>
      </div>

      {/* Removing is a different action from replacing, so it keeps its own control —
          but only when there is something to remove. */}
      {club.logo_url && (
        <Button
          size="sm"
          variant="ghost"
          isDisabled={remove.isPending}
          onPress={() => remove.mutate({ clubId: club.id })}
          data-testid={`admin-club-crest-remove-${club.id}`}
        >
          {t("clubs.crestRemoveButton")}
        </Button>
      )}
      {upload.isError && (
        <ErrorMessage text={errorText(upload.error)} testId={`admin-club-crest-error-${club.id}`} />
      )}
    </li>
  );
}

// ----------------------------------------------------------------------- Series

function Series({ editorOnly }: { editorOnly: boolean }) {
  const { t } = useTranslation("admin");
  const seriesList = useAsyncRows(useListAllSeries({ limit: WHOLE_LIST }));
  // The rows' club selectors have to offer every club, so this asks for the whole list.
  const clubs = useAsyncRows(useListAllClubs({ limit: WHOLE_LIST }));
  const invalidate = useInvalidate();

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
      testId="admin-series-section"
      action={<AddButton label={t("series.newButton")} to="/admin/series/new" testId="admin-series-new-button" />}
    >
      {seriesList.loading && <Loading text={t("series.loadingText")} testId="admin-series-loading" />}
      {seriesList.error && <ErrorMessage text={seriesList.error} testId="admin-series-error" />}
      {seriesList.data &&
        (seriesList.data.length ? (
          <ul data-testid="admin-series-list" className="divide-y divide-slate-100 rounded-lg border border-slate-200">
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
                  ? "bg-brand-50 text-brand-800 ring-brand-200"
                  : "bg-amber-50 text-amber-800 ring-amber-200"
              }`}
            >
              {series.published ? t("series.publishedBadge") : t("series.draftBadge")}
            </span>
          </div>
          <p className="text-sm text-slate-600">
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
              <span className="text-sm text-slate-500">
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
                className="text-sm text-emerald-700"
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
