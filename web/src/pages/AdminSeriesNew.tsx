import { Button } from "@heroui/react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  getListAllSeriesQueryKey,
  useCreateSeries,
  useListAllClubs,
} from "../api/generated/sbl";
import { WHOLE_LIST, useAsyncRows, useInvalidate } from "../api/useApi";
import { Loading } from "../components/Blocks";
import { ClubSelector } from "../components/ClubSelector";
import { Field, Message } from "../components/Form";
import { INPUT_CLASS, errorText, toggleSet } from "../lib/admin";
import { AfterCreate, CancelButton, NewEntryPage } from "./AdminNewPage";

/** `/admin/series/new` — Stories A-4 and A-6: a series and its clubs in one step. Admin
 *  only, like the rest of series management. */
export function AdminSeriesNew() {
  const { t } = useTranslation("admin");
  // A club selector has to offer every club, so it asks for the whole list (Story A-13).
  const clubs = useAsyncRows(useListAllClubs({ limit: WHOLE_LIST }));
  const invalidate = useInvalidate();

  const [name, setName] = useState("");
  // No default: the year is optional, not implicitly "this year". An admin planning
  // ahead should be able to leave it blank rather than having to clear a prefilled value.
  const [year, setYear] = useState("");
  const [startsOn, setStartsOn] = useState("");
  const [endsOn, setEndsOn] = useState("");
  const [selectedClubs, setSelectedClubs] = useState<Set<number>>(new Set());
  const toggle = toggleSet(setSelectedClubs);

  const create = useCreateSeries({
    mutation: { onSuccess: () => invalidate(getListAllSeriesQueryKey(), "/api/series", "/api/clubs") },
  });
  const reset = () => {
    setName("");
    setYear("");
    setStartsOn("");
    setEndsOn("");
    setSelectedClubs(new Set());
    create.reset();
  };

  return (
    <NewEntryPage title={t("series.newButton")} adminOnly testId="admin-series-new">
      {!create.isSuccess && (
        <form
          data-testid="admin-series-create-form"
          className="grid grid-cols-[minmax(0,1fr)] gap-3"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            create.mutate({
              data: {
                name: name.trim(),
                year: year ? Number(year) : null,
                starts_on: startsOn || null,
                ends_on: endsOn || null,
                clubs: [...selectedClubs],
                // A new series starts as a draft: clubs are still being assigned and the
                // name still argued over. The row's own Publish button makes it visible
                // (Story VA-8).
                published: false,
              },
            });
          }}
        >
          <div className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-[2fr_1fr]">
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

          <div className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-2">
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

          <div className="flex flex-wrap items-center gap-3">
            <Button
              type="submit"
              isDisabled={create.isPending || name.trim().length < 3}
              data-testid="admin-series-create-button"
            >
              {create.isPending ? t("series.creatingButton") : t("series.createButton")}
            </Button>
            <CancelButton tab="series" testId="admin-series-cancel-button" />
          </div>
        </form>
      )}
      <Message
        testId="admin-series-create-message"
        error={create.isError ? errorText(create.error) : null}
        success={
          create.isSuccess
            ? t("series.createdMessage", { name: create.data?.name, count: create.data?.clubs?.length ?? 0 })
            : null
        }
      />
      {create.isSuccess && <AfterCreate tab="series" onAnother={reset} testIdPrefix="admin-series" />}
    </NewEntryPage>
  );
}
