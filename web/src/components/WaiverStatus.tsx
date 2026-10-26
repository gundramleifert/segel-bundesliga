import { useTranslation } from "react-i18next";

import { WaiverStatus as Status } from "../api/types";
import { fullName } from "../lib/format";

/** A sailor's waiver status in an organizer's list — the event's check-in list (VA-5) and
 * the club's overview (V-14): green when cleared, amber when something is still to do,
 * with the "under 18" mark beside the name. The sailor's own page words it for them
 * instead (`pages/me/Waivers.tsx`). */
export function WaiverName({ first, last, minor }: { first: string; last: string; minor?: boolean | null }) {
  const { t } = useTranslation("admin");
  return (
    <>
      {fullName({ first_name: first, last_name: last })}
      {minor && <span className="ml-2 text-xs text-muted">{t("manage.waiverMinor")}</span>}
    </>
  );
}

export function WaiverStatus({ status }: { status: Status }) {
  const { t } = useTranslation("admin");
  return (
    <span className={status === Status.cleared ? "text-success-soft-foreground" : "font-medium text-warning-soft-foreground"}>
      {t(`manage.waiverStatus.${status}`)}
    </span>
  );
}
