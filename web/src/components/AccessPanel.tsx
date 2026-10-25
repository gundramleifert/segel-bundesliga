import { useTranslation } from "react-i18next";

import { getReadTuplesQueryKey, useDeleteTuple, useReadTuples } from "../api/generated/sbl";
import { useAsync, useInvalidate } from "../api/useApi";
import { errorText } from "../lib/admin";
import { AddDialog } from "./AddDialog";
import { Section } from "./Form";
import { Async } from "./Async";
import { ErrorMessage } from "./Blocks";
import { GrantForm } from "./GrantForm";
import { PersonDocuments } from "./PersonDocuments";

/** Story Z-2: who holds what on one object — FGA's "read" for `object`, e.g. `event:3`.
 *
 *  One line per tuple (relation · person) with a remove, and *＋ Person* top-right, a dialog
 *  that names someone by the email of their account (`GrantForm`). Shown to whoever may see the
 *  object's admin panel; the backend lets only the site's admin and the object's managers
 *  write, and the error text says so to everyone else. */
export function AccessPanel({
  object,
  testId,
  onChange,
}: {
  object: string;
  testId: string;
  /** Called after a tuple was written or removed — for a screen that shows a projection of
   *  them (a club's roster) and has to refetch it. */
  onChange?: () => void;
}) {
  const { t } = useTranslation("admin");
  const invalidate = useInvalidate();
  const tuples = useAsync(useReadTuples({ object }));
  const refresh = () => {
    invalidate(getReadTuplesQueryKey({ object }), "/api/auth/users");
    onChange?.();
  };
  const remove = useDeleteTuple({ mutation: { onSuccess: refresh } });

  return (
    <Section
      title={t("access.title")}
      testId={testId}
      action={
        <AddDialog label={t("access.newButton")} title={t("access.newTitle")} testId={testId}>
          {(close) => (
            <GrantForm
              object={object}
              testId={testId}
              onWritten={refresh}
              onDone={close}
            />
          )}
        </AddDialog>
      }
    >
      <p className="mb-2 text-sm text-muted">{t("access.hint")}</p>
      <Async state={tuples} testId={testId} empty={t("access.empty")}>
        {(rows) => (
          <ul className="flex flex-col gap-1.5" data-testid={`${testId}-list`}>
            {rows.map((row) => (
              <li key={row.id} className="flex flex-wrap items-center gap-2" data-testid={`${testId}-tuple-${row.id}`}>
                <span className="font-medium">{t(`accounts.relationLabels.${row.relation}`, { defaultValue: row.relation })}</span>
                <span>
                  {row.user_name} <span className="text-muted">({row.user})</span>
                </span>
                <PersonDocuments userId={row.user_id} name={row.user_name} testId={`${testId}-documents-${row.id}`} />
                <button
                  type="button"
                  className="text-faint hover:text-danger"
                  aria-label={t("access.revoke")}
                  title={t("access.revoke")}
                  disabled={remove.isPending}
                  onClick={() => remove.mutate({ tupleId: row.id })}
                  data-testid={`${testId}-revoke-${row.id}`}
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        )}
      </Async>
      {remove.error && <ErrorMessage text={errorText(remove.error)} testId={`${testId}-revoke-error`} />}
    </Section>
  );
}
