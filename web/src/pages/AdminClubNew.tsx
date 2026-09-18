import { Button } from "@heroui/react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { getListAllClubsQueryKey, useCreateClub } from "../api/generated/sbl";
import { useInvalidate } from "../api/useApi";
import { Field, Message } from "../components/Form";
import { INPUT_CLASS, errorText } from "../lib/admin";
import { AfterCreate, CancelButton, NewEntryPage } from "./AdminNewPage";

/** `/admin/clubs/new` — Story A-1: a club is master data and exists before it competes
 *  (A-7), so this asks for the name, the abbreviation the URL is built from, and the city. */
export function AdminClubNew() {
  const { t } = useTranslation("admin");
  const invalidate = useInvalidate();
  const [name, setName] = useState("");
  const [shortName, setShortName] = useState("");
  const [city, setCity] = useState("");

  const create = useCreateClub({
    mutation: { onSuccess: () => invalidate(getListAllClubsQueryKey(), "/api/clubs") },
  });
  const reset = () => {
    setName("");
    setShortName("");
    setCity("");
    create.reset();
  };

  return (
    <NewEntryPage title={t("clubs.newButton")} testId="admin-clubs-new">
      {!create.isSuccess && (
        <form
          data-testid="admin-clubs-create-form"
          className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-[2fr_1fr_1fr] sm:items-end"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            create.mutate({
              data: {
                name: name.trim(),
                short_name: shortName.trim() || null,
                city: city.trim() || null,
              },
            });
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
          <div className="flex flex-wrap items-center gap-3 sm:col-span-3">
            <Button
              type="submit"
              isDisabled={create.isPending || name.trim().length < 3}
              data-testid="admin-clubs-create-button"
            >
              {create.isPending ? t("clubs.creatingButton") : t("clubs.createButton")}
            </Button>
            <CancelButton tab="clubs" testId="admin-clubs-cancel-button" />
          </div>
        </form>
      )}
      <Message
        testId="admin-clubs-create-message"
        error={create.isError ? errorText(create.error) : null}
        success={create.isSuccess ? t("clubs.createdMessage", { name: create.data?.name }) : null}
      />
      {create.isSuccess && <AfterCreate tab="clubs" onAnother={reset} testIdPrefix="admin-clubs" />}
    </NewEntryPage>
  );
}
