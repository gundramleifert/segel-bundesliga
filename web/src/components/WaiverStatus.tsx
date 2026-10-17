import { useTranslation } from "react-i18next";

/** A sailor's waiver status in an organizer's list — the event's check-in list (VA-5) and
 * the club's overview (V-14): green when cleared, amber when something is still to do,
 * with the "under 18" mark beside the name. The sailor's own page words it for them
 * instead (`pages/me/Waivers.tsx`). */
export function WaiverName({ first, last, minor }: { first: string; last: string; minor?: boolean | null }) {
  const { t } = useTranslation("admin");
  return (
    <>
      {first} {last}
      {minor && <span className="ml-2 text-xs text-slate-500">{t("manage.waiverMinor")}</span>}
    </>
  );
}

export function WaiverStatus({ status }: { status: string }) {
  const { t } = useTranslation("admin");
  return (
    <span className={status === "cleared" ? "text-emerald-700" : "font-medium text-amber-700"}>
      {t(`manage.waiverStatus.${status}`)}
    </span>
  );
}
