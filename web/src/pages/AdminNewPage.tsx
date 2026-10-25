import { Button } from "@heroui/react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate } from "react-router-dom";

import { ErrorMessage, Loading, PageHeader } from "../components/Blocks";
import { Section } from "../components/Form";
import { useAccount } from "../api/useApi";
import { mayCreateIn, mayCreateOutside, sectionPath, type OfficeArea, type OfficeSection } from "../lib/workspace";
import { useMySpace } from "./me/shared";

/** Who may use a creation page, asked of the model: the league office's `office`
 *  relations from `GET /api/me/contexts` (Story A-11, issue #32) — the section the page
 *  belongs to must be theirs. With `outside`, also those who create in this area without
 *  an office (`CREATE_OUTSIDE_OFFICE`: an organizer's event, a series editor's post). */
export function useCreateAccess(area: OfficeArea, { outside = false } = {}) {
  const { account, accountLoading, space } = useMySpace();
  const { hasRole } = useAccount();
  const loading = accountLoading || (Boolean(account) && !space.data && !space.error);
  const inOffice = mayCreateIn(area, space.data?.office?.relations ?? []);
  return {
    account,
    loading,
    /** The page is theirs from the league office. */
    inOffice,
    allowed: inOffice || (outside && mayCreateOutside(area, hasRole)),
  };
}

/** Which door a page with two addresses was opened by — the office's (`/office/events/new`,
 *  `/office/news/:id`) or My space's (`/me/event/new`, `/me/news/:id`) — and, for someone
 *  who creates there without an office, the address in My space to pass them on to: a
 *  link written for the office, or an old `/admin/…` one, still reaches their page. */
export function useCreateDoor(area: OfficeArea): { atOffice: boolean; passOn: string | null } {
  const { pathname, search } = useLocation();
  const atOffice = pathname.startsWith("/office/");
  const access = useCreateAccess(area, { outside: true });
  const passOn =
    atOffice && !access.loading && access.allowed && !access.inOffice
      ? pathname.replace(/^\/office\/events\//, "/me/event/").replace(/^\/office\/news\//, "/me/news/") + search
      : null;
  return { atOffice, passOn };
}

/** The page a new entry is created on — `/office/<area>/new` (Stories A-1, A-6, V-4, VA-6,
 *  R-1), and the doors outside the office, `/me/event/new` and `/me/news/new`.
 *
 * One shell for every area: the access rule (`useCreateAccess`), the page's name in the
 * breadcrumb (`League office › New club`), and one card holding the form. What the form
 * does on success is its own business; what every one of them offers afterwards is
 * `AfterCreate`.
 */
export function NewEntryPage({
  title,
  area,
  outside = false,
  testId,
  children,
}: {
  title: string;
  /** The office's area — its section must be the reader's. */
  area: OfficeArea;
  /** Also open to those who create in this area without an office (the `/me/…` door). */
  outside?: boolean;
  testId: string;
  children: ReactNode;
}) {
  const { t } = useTranslation("admin");
  const access = useCreateAccess(area, { outside });

  if (access.loading) return <Loading testId="admin-loading" />;
  if (!access.account) return <ErrorMessage text={t("auth.notSignedInError")} testId="admin-auth-error" />;
  if (!access.allowed) return <ErrorMessage text={t("auth.noAccessError")} testId="admin-access-error" />;
  return (
    <>
      {/* The page's name is in the breadcrumb (`PageHeader`); a heading above the form
          would only say it a second time. */}
      <PageHeader title={title} testId={`${testId}-header`} />
      <Section testId={testId}>{children}</Section>
    </>
  );
}

/** Back to the office's section the entry now appears in — the create pages are reached
 *  from that section's "＋", so this is the way back — with the option to stay and add
 *  the next one. */
export function AfterCreate({
  section,
  onAnother,
  testIdPrefix,
}: {
  section: OfficeSection;
  onAnother: () => void;
  testIdPrefix: string;
}) {
  const { t } = useTranslation("admin");
  const navigate = useNavigate();
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button
        size="sm"
        onPress={() => navigate(sectionPath({ kind: "office" }, section))}
        data-testid={`${testIdPrefix}-back-button`}
      >
        {t("page.backButton")}
      </Button>
      <Button size="sm" variant="ghost" onPress={onAnother} data-testid={`${testIdPrefix}-another-button`}>
        {t("page.anotherButton")}
      </Button>
    </div>
  );
}

/** Leaves without creating anything — back to the office's section. */
export function CancelButton({ section, testId }: { section: OfficeSection; testId: string }) {
  const { t } = useTranslation("admin");
  const navigate = useNavigate();
  return (
    <Button size="sm" variant="ghost" onPress={() => navigate(sectionPath({ kind: "office" }, section))} data-testid={testId}>
      {t("page.cancelButton")}
    </Button>
  );
}
