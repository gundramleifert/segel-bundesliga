import { Button } from "@heroui/react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { PageHeader } from "../components/Blocks";
import { Section } from "../components/Form";
import { AdminAccess, type AdminTab } from "./Admin";

/** The page a new entry is created on — `/admin/<area>/new` (Stories A-1, A-6, V-4, VA-6).
 *
 * One shell for all four areas: the same access rule as `/admin`, the page's name in the
 * breadcrumb (`Admin › New event`), and one card holding the form. What the form does on
 * success is its own business; what every one of them offers afterwards is `AfterCreate`.
 */
export function NewEntryPage({
  title,
  adminOnly = false,
  testId,
  children,
}: {
  title: string;
  adminOnly?: boolean;
  testId: string;
  children: ReactNode;
}) {
  return (
    <AdminAccess adminOnly={adminOnly}>
      <PageHeader title={title} testId={`${testId}-header`} />
      <Section title={title} testId={testId}>
        {children}
      </Section>
    </AdminAccess>
  );
}

/** Back to the tab the entry now appears in — the create pages are reached from that tab's
 *  "＋", so this is the way back — with the option to stay and add the next one. */
export function AfterCreate({
  tab,
  onAnother,
  testIdPrefix,
}: {
  tab: AdminTab;
  onAnother: () => void;
  testIdPrefix: string;
}) {
  const { t } = useTranslation("admin");
  const navigate = useNavigate();
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button size="sm" onPress={() => navigate(`/admin?tab=${tab}`)} data-testid={`${testIdPrefix}-back-button`}>
        {t("page.backButton")}
      </Button>
      <Button size="sm" variant="ghost" onPress={onAnother} data-testid={`${testIdPrefix}-another-button`}>
        {t("page.anotherButton")}
      </Button>
    </div>
  );
}

/** Leaves without creating anything — back to the tab. */
export function CancelButton({ tab, testId }: { tab: AdminTab; testId: string }) {
  const { t } = useTranslation("admin");
  const navigate = useNavigate();
  return (
    <Button size="sm" variant="ghost" onPress={() => navigate(`/admin?tab=${tab}`)} data-testid={testId}>
      {t("page.cancelButton")}
    </Button>
  );
}
