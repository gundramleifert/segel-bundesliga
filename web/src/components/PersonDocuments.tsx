import { Button } from "@heroui/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { getGetDocumentFileUrl, useListPersonDocuments } from "../api/generated/sbl";
import { errorText } from "../lib/admin";
import { openFile } from "../lib/files";
import { formatDate } from "../lib/format";

/** A person's documents, for their organizers (Story S-5) — the RIB driver's boat
 * licence, checked before the day.
 *
 * A button on a person's row (the event's access list, the club's member list) that
 * opens the list on demand: the request is made only when someone asks, because every
 * look at a file is written to the audit log and a list that loaded itself for every row
 * would also be a request per row. Whether the asker may see them is the server's call
 * (`documents-forbidden`); a refusal hides the panel rather than showing an error, since
 * the button is offered wherever a person is listed and most viewers are not their
 * organizer.
 */
export function PersonDocuments({
  userId,
  name,
  testId,
}: {
  userId: number;
  name: string;
  testId: string;
}) {
  const { t } = useTranslation("space");
  const [open, setOpen] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);
  const documents = useListPersonDocuments(userId, { query: { enabled: open, retry: false } });
  const forbidden = documents.error?.status === 403;

  if (forbidden) return null;
  return (
    <div className="contents">
      <Button
        size="sm"
        variant="ghost"
        onPress={() => setOpen((v) => !v)}
        aria-expanded={open}
        data-testid={`${testId}-button`}
      >
        {t("personDocuments.button")}
      </Button>
      {open && (
        <div
          className="w-full rounded-md bg-slate-50 px-3 py-2 text-sm"
          data-testid={`${testId}-panel`}
          aria-label={t("personDocuments.title", { name })}
        >
          {documents.isPending && <p className="text-slate-500">…</p>}
          {documents.isError && <p className="text-red-700">{errorText(documents.error)}</p>}
          {documents.data && documents.data.length === 0 && (
            <p className="text-slate-500" data-testid={`${testId}-empty`}>
              {t("personDocuments.empty")}
            </p>
          )}
          {documents.data && documents.data.length > 0 && (
            <ul className="flex flex-col gap-1" data-testid={`${testId}-list`}>
              {documents.data.map((doc) => (
                <li key={doc.id} className="flex flex-wrap items-center gap-2" data-testid={`${testId}-${doc.id}`}>
                  <button
                    type="button"
                    className="text-brand-700 underline"
                    onClick={() =>
                      openFile(getGetDocumentFileUrl(doc.id)).catch((err) => setFileError(errorText(err)))
                    }
                    data-testid={`${testId}-open-${doc.id}`}
                  >
                    {t(`kinds.${doc.kind}`)}
                    {doc.title ? ` · ${doc.title}` : ""}
                  </button>
                  {doc.valid_until && (
                    <span className="text-xs text-slate-500">
                      {t("documents.validUntil", { date: formatDate(doc.valid_until) })}
                    </span>
                  )}
                  {doc.expired && <ExpiredBadge testId={`${testId}-expired-${doc.id}`} />}
                </li>
              ))}
            </ul>
          )}
          {fileError && <p className="text-red-700">{fileError}</p>}
        </div>
      )}
    </div>
  );
}

/** "expired" — shown, never hidden: an organizer must see that a licence ran out, not
 *  that there is none (Story S-5). */
export function ExpiredBadge({ testId }: { testId?: string }) {
  const { t } = useTranslation("space");
  return (
    <span
      data-testid={testId}
      className="rounded-full bg-red-50 px-2 py-0.5 text-xs font-medium text-red-800 ring-1 ring-inset ring-red-200"
    >
      {t("documents.expired")}
    </span>
  );
}
