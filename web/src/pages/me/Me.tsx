import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, useParams, useSearchParams } from "react-router-dom";

import { useAccount, useInvalidate } from "../../api/useApi";
import { Loading } from "../../components/Blocks";
import { Stack } from "../../components/Layouts";
import { LEGACY_TAB_SECTION } from "../../lib/workspace";
import { AccountInfo, DeleteAccount, SailorProfile, SignInMethods } from "./Profile";
import { BankTab, ClaimsTab, DocumentsTab } from "./Papers";
import { Wards, Waivers } from "./Waivers";
import { useMySpace } from "./shared";
import { WorkspaceFrame, type WorkspaceSection } from "./Workspace";
import { legacyTarget } from "./ContextFrame";

/** Stories S-7, Z-10: the *Me* context — my overview (`/me`) and my own sections. */


/** `/me/profile/<section>` — my own things: the account, papers, bank, waivers, all my
 *  claims. `/me/profile` alone opens my account. */
export function ProfilePage() {
  const { section } = useParams();
  const [params] = useSearchParams();
  const legacy = legacyTarget("/me/profile", LEGACY_TAB_SECTION.profile, params);
  if (legacy) return <Navigate to={legacy} replace />;
  if (!section) return <Navigate to="/me/profile/account" replace />;
  return <MeFrame active={section} />;
}

/** The *Me* context (Story Z-10): `/me` its overview — whatever `overview` is — and my
 *  own sections under `/me/profile/`. One list, so the overview and every section share
 *  one sidebar. */
export function MeFrame({ active, overview }: { active?: string; overview?: ReactNode }) {
  const { t } = useTranslation("space");
  const { account, loading } = useAccount();
  const invalidate = useInvalidate();
  const { space } = useMySpace();
  if (loading) return <Loading testId="me-context-loading" />;
  if (!account) return <Navigate to="/account" replace />;

  const sections: WorkspaceSection[] = [
    { key: "overview", label: t("workspace.overview"), render: () => overview },
    {
      key: "account",
      label: t("context.tabs.account"),
      render: () => (
        <Stack gap={4} testId="me-profile">
          <AccountInfo account={account} />
          <SignInMethods account={account} onChanged={() => invalidate("/api/auth/me")} />
          <SailorProfile />
          <DeleteAccount />
        </Stack>
      ),
    },
    { key: "documents", label: t("tabs.documents"), needs: ["documents_expired"], render: () => <DocumentsTab /> },
    { key: "bank", label: t("tabs.bank"), render: () => <BankTab /> },
    {
      key: "waivers",
      label: t("context.tabs.waivers"),
      needs: ["waiver", "ward_waiver"],
      // Mine (S-1), then my children's (S-8) — a parent with no sailor record of their
      // own sees only the second, until *My children* is a section of its own (#32).
      render: () => (
        <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
          <Waivers />
          <Wards />
        </div>
      ),
    },
    { key: "claims", label: t("tabs.claims"), needs: ["claim_rejected"], render: () => <ClaimsTab /> },
  ];
  return (
    <WorkspaceFrame
      current={{ kind: "me" }}
      name={space.data?.me.name ?? account.display_name}
      relations={[]}
      needs={space.data?.me.needs ?? []}
      sections={sections}
      active={active}
    />
  );
}
