import { Button } from "@heroui/react";
import { useMutation } from "@tanstack/react-query";
import { useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { api, type ClubAdmin, type SeriesAdmin } from "../api/client";
import { useApi, useInvalidate, useAccount } from "../api/useApi";
import { ErrorMessage, Loading, Empty, PageHeader } from "../components/Blocks";
import { AccountsAdmin } from "./AdminAccounts";
import { EventsAdmin } from "./AdminEvents";
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
        <EventsAdmin />
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
      {data &&
        (data.length ? (
          <ul
            data-testid="admin-clubs-list"
            className="divide-y divide-slate-100 rounded-lg border border-slate-200"
          >
            {data.map((club) => (
              <ClubRow key={club.id} club={club} onChanged={() => invalidate(["admin", "clubs"], ["clubs"])} />
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
 */
function ClubRow({ club, onChanged }: { club: ClubAdmin; onChanged: () => void }) {
  const { t } = useTranslation("admin");
  const fileInput = useRef<HTMLInputElement>(null);

  const upload = useMutation({
    mutationFn: (file: File) => api.admin.uploadClubCrest(club.id, file),
    onSuccess: onChanged,
  });
  const remove = useMutation({
    mutationFn: () => api.admin.deleteClubCrest(club.id),
    onSuccess: onChanged,
  });

  return (
    <li data-testid={`admin-club-row-${club.id}`} className="flex flex-wrap items-center gap-3 px-4 py-3">
      {/* No cache-busting suffix needed: `logo_url` already carries the file's mtime as a
          `?v=` stamp (`app/crests.py`), so a replaced crest arrives under a new URL on its
          own once the list is invalidated. */}
      <span className="crest-backdrop grid size-10 shrink-0 place-items-center overflow-hidden rounded border border-slate-200">
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
      </span>

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
          if (file) upload.mutate(file);
        }}
        data-testid={`admin-club-crest-input-${club.id}`}
      />
      <Button
        size="sm"
        variant="ghost"
        isDisabled={upload.isPending}
        onPress={() => fileInput.current?.click()}
        data-testid={`admin-club-crest-upload-${club.id}`}
      >
        {upload.isPending
          ? t("clubs.crestUploadingButton")
          : club.logo_url
            ? t("clubs.crestReplaceButton")
            : t("clubs.crestUploadButton")}
      </Button>
      {club.logo_url && (
        <Button
          size="sm"
          variant="ghost"
          isDisabled={remove.isPending}
          onPress={() => remove.mutate()}
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
        // A new series starts as a draft: clubs are still being assigned and the name
        // still argued over. The row's own Publish button makes it visible (Story VA-8).
        published: false,
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
            {seriesList.data.map((series) => (
              <SeriesRow
                key={series.id}
                series={series}
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

  const save = useMutation({
    mutationFn: () => api.admin.setSeriesClubs(series.id, [...selectedClubs]),
    onSuccess: () => {
      setOpen(false);
      onChanged();
    },
  });

  const saveDescription = useMutation({
    mutationFn: () =>
      api.admin.updateSeries(series.id, { description: description.trim() || null }),
    onSuccess: () => onChanged(),
  });

  // Story VA-8: a series is planned long before anyone should read about it — clubs are
  // still being assigned, the name still argued over. Publishing changes only who can see
  // it and locks nothing, which is why this is a plain toggle and not a final step.
  const publish = useMutation({
    mutationFn: () => api.admin.publishSeries(series.id, !series.published),
    onSuccess: () => onChanged(),
  });

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
                  ? "bg-marke-50 text-marke-800 ring-marke-200"
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
            isDisabled={publish.isPending}
            onPress={() => publish.mutate()}
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
      {publish.isError && (
        <ErrorMessage
          text={errorText(publish.error)}
          testId={`admin-series-publish-error-${series.id}`}
        />
      )}

      {open && (
        <div className="mt-3 grid gap-4">
          <div className="grid gap-3">
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
                onPress={() => save.mutate()}
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
          </div>

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
              onPress={() => saveDescription.mutate()}
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
        </div>
      )}
    </li>
  );
}
