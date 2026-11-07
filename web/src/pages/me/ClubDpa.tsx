import { Button } from "@heroui/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { getGetClubDpaQueryKey, useAcceptClubDpa, useGetClubDpa } from "../../api/generated/sbl";
import { errorText, useInvalidate } from "../../api/useApi";
import { ErrorMessage } from "../../components/Blocks";
import { formatDate } from "../../lib/format";
import { LegalSections, type LegalSection } from "../../components/LegalText";

/** Story V-17: the club's admin reads and accepts the data processing agreement in force —
 * the club's side of *People*, squads, crews, claims and payments waits on it
 * (`dpa-required`). Once accepted, one line says who accepted when, and the text stays
 * readable. */
export function ClubDpa({ clubId }: { clubId: number }) {
  const { t } = useTranslation("space");
  const { t: legal } = useTranslation("legal");
  const status = useGetClubDpa(clubId);
  const invalidate = useInvalidate();
  const accept = useAcceptClubDpa({
    mutation: { onSuccess: () => invalidate(getGetClubDpaQueryKey(clubId), "/api/me/contexts") },
  });
  const [authorized, setAuthorized] = useState(false);
  const [reading, setReading] = useState(false);

  if (!status.data) return null;
  const sections = legal("dpa.sections", { returnObjects: true }) as LegalSection[];
  const text = (
    <div className="mt-4 max-h-96 overflow-y-auto rounded-md bg-surface p-4" data-testid="club-dpa-text">
      <LegalSections sections={sections} testIdPrefix="club-dpa" />
    </div>
  );

  if (status.data.accepted) {
    return (
      <section data-testid="club-dpa-accepted" className="rounded-lg border border-border p-4">
        <p className="text-sm text-foreground">
          {t("dpa.accepted", {
            version: status.data.version,
            date: status.data.accepted_at ? formatDate(status.data.accepted_at) : "",
            name: status.data.accepted_by_name ?? "",
          })}
        </p>
        <Button
          size="sm"
          variant="outline"
          className="mt-2"
          onPress={() => setReading((v) => !v)}
          data-testid="club-dpa-read"
        >
          {reading ? t("dpa.hide") : t("dpa.read")}
        </Button>
        {reading && text}
      </section>
    );
  }

  return (
    <section
      data-testid="club-dpa"
      className="rounded-lg border-2 border-warning/50 bg-warning-soft/40 p-4 sm:p-6"
    >
      <h2 className="text-lg font-semibold text-foreground">{t("dpa.title")}</h2>
      <p className="mt-1 text-sm text-foreground">{t("dpa.why")}</p>
      <p className="mt-1 text-sm text-muted">
        {t("dpa.version", { version: status.data.version })}
      </p>
      {text}
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
