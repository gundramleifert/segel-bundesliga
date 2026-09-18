import { Button } from "@heroui/react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { getListSailorsQueryKey, useCreateSailor } from "../api/generated/sbl";
import { useInvalidate } from "../api/useApi";
import { Field, Message } from "../components/Form";
import { INPUT_CLASS, errorText } from "../lib/admin";
import { AfterCreate, CancelButton, NewEntryPage } from "./AdminNewPage";

/** `/admin/sailors/new` — Story V-4: the person, independent of any club or competition.
 *  Club membership and squads are separate steps on the club screen. */
export function AdminSailorNew() {
  const { t } = useTranslation("admin");
  const invalidate = useInvalidate();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");

  const create = useCreateSailor({
    // No params: the generated key is `["/api/admin/sailors"]`, which is a prefix of every
    // search variant, so one call clears them all.
    mutation: { onSuccess: () => invalidate(getListSailorsQueryKey()) },
  });
  const reset = () => {
    setFirstName("");
    setLastName("");
    setEmail("");
    create.reset();
  };

  return (
    <NewEntryPage title={t("sailors.newButton")} testId="admin-sailors-new">
      {!create.isSuccess && (
        <form
          data-testid="admin-sailors-create-form"
          className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-[1fr_1fr_1.4fr] sm:items-end"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            create.mutate({
              data: { first_name: firstName.trim(), last_name: lastName.trim(), email: email.trim() },
            });
          }}
        >
          <Field label={t("sailors.firstNameLabel")}>
            <input
              className={INPUT_CLASS}
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              required
              data-testid="admin-sailors-first-name-input"
            />
          </Field>
          <Field label={t("sailors.lastNameLabel")}>
            <input
              className={INPUT_CLASS}
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              required
              data-testid="admin-sailors-last-name-input"
            />
          </Field>
          <Field label={t("sailors.emailLabel")}>
            <input
              className={INPUT_CLASS}
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder={t("sailors.emailPlaceholder")}
              data-testid="admin-sailors-email-input"
            />
          </Field>
          <div className="flex flex-wrap items-center gap-3 sm:col-span-3">
            <Button
              type="submit"
              isDisabled={create.isPending || !firstName.trim() || !lastName.trim() || !email.trim()}
              data-testid="admin-sailors-create-button"
            >
              {create.isPending ? t("sailors.creatingButton") : t("sailors.createButton")}
            </Button>
            <CancelButton tab="sailors" testId="admin-sailors-cancel-button" />
          </div>
        </form>
      )}
      <Message
        testId="admin-sailors-create-message"
        error={create.isError ? errorText(create.error) : null}
        success={
          create.isSuccess
            ? t("sailors.createdMessage", { firstName: create.data?.first_name, lastName: create.data?.last_name })
            : null
        }
      />
      {create.isSuccess && <AfterCreate tab="sailors" onAnother={reset} testIdPrefix="admin-sailors" />}
    </NewEntryPage>
  );
}
