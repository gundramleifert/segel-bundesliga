import { useTranslation } from "react-i18next";

/** Public or draft (Stories VA-8, R-1) — on each row of the events and the posts list,
 *  and on the wizard's last screen. */
export function PublicationBadge({ published, testId }: { published: boolean; testId: string }) {
  const { t } = useTranslation("admin");
  return (
    <span
      data-testid={testId}
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${
        published
          ? "bg-accent-soft text-accent-soft-foreground ring-accent/30"
          : "bg-warning-soft text-warning-soft-foreground ring-warning/50"
      }`}
    >
      {published ? t("manage.publishedBadge") : t("manage.draftBadge")}
    </span>
  );
}
