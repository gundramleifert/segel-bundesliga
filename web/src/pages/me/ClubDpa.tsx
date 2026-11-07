import { Button } from "@heroui/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { getGetClubDpaQueryKey, useAcceptClubDpa, useGetClubDpa } from "../../api/generated/sbl";
import { errorText, useInvalidate } from "../../api/useApi";
import { ErrorMessage } from "../../components/Blocks";
import { LegalSections, type LegalSection } from "../../components/LegalText";

/** Story V-17: the club's admin reads and accepts the data processing agreement in force.
 * Shown until it is accepted; the club's side of *People*, squads and crews waits on it
 * (`dpa-required`). */
export function ClubDpa({ clubId }: { clubId: number }) {
  const { t } = useTranslation("space");
  const { t: legal } = useTranslation("legal");
  const status = useGetClubDpa(clubId);
  const invalidate = useInvalidate();
  const accept = useAcceptClubDpa({
    mutation: { onSuccess: () => invalidate(getGetClubDpaQueryKey(clubId), "/api/me/contexts") },
  });
  const [authorized, setAuthorized] = useState(false);

  if (!status.data || status.data.accepted) return null;
  const sections = legal("dpa.sections", { returnObjects: true }) as LegalSection[];

  return (
    <section
      data-testid="club-dpa"
      className="rounded-lg border-2 border-warning/50 bg-warning-soft/40 p-4 sm:p-6"
    >
      <h2 className="text-lg font-semibold text-foreground">{t("dpa.title")}</h2>
      <p className="mt-1 text-sm text-foreground">{t("dpa.why")}</p>
      <p className="mt-1 text-sm text-muted">
        {legal("dpa.draft")} · {t("dpa.version", { version: status.data.version })}
      </p>
      <div className="mt-4 max-h-96 overflow-y-auto rounded-md bg-surface p-4" data-testid="club-dpa-text">
        <LegalSections sections={sections} testIdPrefix="club-dpa" />
      </div>
      <label className="mt-4 flex items-start gap-2 text-sm text-foreground">
        <input
          type="checkbox"
          checked={authorized}
          onChange={(e) => setAuthorized(e.target.checked)}
          className="mt-0.5"
          data-testid="club-dpa-authorized"
        />
        <span>{t("dpa.authorized")}</span>
      </label>
      <Button
        className="mt-3"
        isDisabled={!authorized || accept.isPending}
        onPress={() => accept.mutate({ clubId, data: { version: status.data.version, authorized } })}
        data-testid="club-dpa-accept"
      >
        {t("dpa.accept")}
      </Button>
      {accept.isError && <ErrorMessage text={errorText(accept.error)} testId="club-dpa-error" />}
    </section>
  );
}
