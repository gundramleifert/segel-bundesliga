import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { getGetImportKeyQueryKey, getImportKey, importMedia, uploadMedia } from "../api/generated/sbl";
import { Role } from "../api/types";
import { useAccount, useAsync } from "../api/useApi";
import { Async } from "../components/Async";
import { BatchUpload } from "../components/BatchUpload";
import { PageHeader } from "../components/Blocks";
import { Field } from "../components/Form";
import { MediaContextSelect } from "../components/MediaContextSelect";
import { formatDate } from "../lib/format";
import { NO_CONTEXT, type MediaContext } from "../lib/mediaContext";

/** The key from `#key=…` — a fragment, so it never reaches a server's log or a referrer. */
function keyFromHash(): string | null {
  return new URLSearchParams(window.location.hash.slice(1)).get("key");
}

/** `/upload#key=…` — Story R-2: a photographer delivers pictures into the library from a
 *  link, on a phone, without an account. Our own source, and it uses the import API like
 *  any other would — `GET /api/import/key`, `POST /api/import/media` — and nothing else.
 *  `/upload` without a key is editorial's own upload, signed in, under their account. */
export function UploadPage() {
  const { t } = useTranslation("upload");
  const [key] = useState(keyFromHash);
  const info = useAsync(
    useQuery({
      queryKey: [...getGetImportKeyQueryKey(), key],
      queryFn: () => getImportKey({ headers: { "X-Import-Key": key ?? "" } }),
      enabled: !!key,
      retry: false,
    }),
  );

  return (
    <>
      <PageHeader title={t("title")} testId="upload-header" />
      {!key ? (
        <SignedInUpload />
      ) : (
        <Async state={info} testId="upload-key">
          {(about) => (
            <>
              <p className="mb-6 text-foreground" data-testid="upload-for">
                {t("for", { label: about.label })}
                {about.context && <span className="font-medium"> · {about.context}</span>}
                {about.expires_at && <span className="text-muted"> · {t("validUntil", { date: formatDate(about.expires_at) })}</span>}
              </p>
              <BatchUpload
                send={(file, credit) => importMedia({ file, credit }, { headers: { "X-Import-Key": key } })}
                defaultCredit={about.credit ?? ""}
                testId="upload"
              />
            </>
          )}
        </Async>
      )}
    </>
  );
}

/** Without a link: editorial, signed in, uploads under their own account and says what
 *  the pictures are of. Anyone else is told what this page needs. */
function SignedInUpload() {
  const { t } = useTranslation("upload");
  const { account, hasRole } = useAccount();
  const [context, setContext] = useState<MediaContext>(NO_CONTEXT);
  if (!hasRole(Role.admin, Role.editor)) {
    return (
      <p className="text-foreground" data-testid="upload-no-key">
        {t("noKey")}
      </p>
    );
  }
  return (
    <>
      <p className="mb-6 text-foreground" data-testid="upload-signed-in">{t("signedIn")}</p>
      <BatchUpload
        send={(file, credit) =>
          uploadMedia({ file, credit, event_id: context.event_id ?? undefined, series_id: context.series_id ?? undefined })
        }
        defaultCredit={account?.display_name ?? ""}
        testId="upload"
      >
        <Field label={t("contextLabel")} hint={t("contextHint")}>
          <MediaContextSelect value={context} onChange={setContext} noneLabel={t("contextNone")} testId="upload-context-select" />
        </Field>
      </BatchUpload>
    </>
  );
}
