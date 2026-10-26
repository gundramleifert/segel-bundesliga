import type { ReactNode } from "react";
import { Navigate, useParams, useSearchParams } from "react-router-dom";

import { useAccount, useInvalidate } from "../../api/useApi";
import { Loading } from "../../components/Blocks";
import { Stack } from "../../components/Layouts";
import { LEGACY_TAB_SECTION } from "../../lib/workspace";
import { AccountInfo, DeleteAccount, SailorProfile, SignInMethods } from "./Profile";
import { MyClubs } from "./MyClubs";
import { BankTab, ClaimsTab, DocumentsTab } from "./Papers";
import { Wards, Waivers } from "./Waivers";
import { useMySpace } from "./shared";
import { WorkspaceFrame, type WorkspaceSection } from "./Workspace";
import { ContextRelation } from "../../api/types";
import { MediaAdmin } from "../admin/media/MediaAdmin";
import { PostsAdmin } from "../admin/posts/PostList";
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
  const { account, loading } = useAccount();
  const invalidate = useInvalidate();
  const { space } = useMySpace();
  if (loading) return <Loading testId="me-context-loading" />;
  if (!account) return <Navigate to="/account" replace />;
  // Which of my sections exist depends on the answer (an editor's *News*): until it is
  // here, a section in the address would look like one I do not have, and the frame would
  // send me away from it.
  if (!space.data && !space.error) return <Loading testId="me-context-loading" />;

  const sections: WorkspaceSection[] = [
    { key: "overview", render: () => overview },
    {
      key: "account",
      render: () => (
        <Stack gap={4} testId="me-profile">
          <AccountInfo account={account} />
          <SignInMethods account={account} onChanged={() => invalidate("/api/auth/me")} />
          <SailorProfile />
          <DeleteAccount />
        </Stack>
      ),
    },
    // Story V-15: my memberships, invitations and requests, and asking a club.
    {
      key: "clubs",
      needs: ["membership_invited"],
      render: () => <MyClubs />,
    },
    { key: "documents", needs: ["documents_expired"], render: () => <DocumentsTab /> },
    { key: "bank", render: () => <BankTab /> },
    {
      key: "waivers",
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
    { key: "claims", needs: ["claim_rejected"], render: () => <ClaimsTab /> },
    {
      key: "news",
      render: () => <PostsAdmin base="/me" testId="me-news" />,
    },
    {
      key: "media",
      render: () => <MediaAdmin withKeys={false} />,
    },
  ];
  return (
    <WorkspaceFrame
      current={{ kind: "me" }}
      name={space.data?.me.name ?? account.display_name}
      // An editor of any regatta has *Me › News* and *Me › Pictures*: every post and picture
      // they may change, across all of them (Story R-1).
      relations={space.data?.contexts.some((c) => c.relations.includes(ContextRelation.editor)) ? [ContextRelation.editor] : []}
      needs={space.data?.me.needs ?? []}
      sections={sections}
      active={active}
    />
  );
}
