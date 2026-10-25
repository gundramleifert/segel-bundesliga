import { useTranslation } from "react-i18next";
import { Navigate, useParams } from "react-router-dom";

import { useAccount } from "../../api/useApi";
import { ErrorMessage, Loading, PageHeader } from "../../components/Blocks";
import { mayCreateIn } from "../../lib/workspace";
import { AccountsAdmin } from "../AdminAccounts";
import { Clubs, SeriesList } from "../Admin";
import { SailorsAdmin } from "../AdminSailors";
import { EventsAdmin } from "../admin/events/EventList";
import { MediaAdmin } from "../admin/media/MediaAdmin";
import { PostsAdmin } from "../admin/posts/PostList";
import { TodoList } from "../me/Todos";
import { useMySpace } from "../me/shared";
import { WorkspaceFrame, type WorkspaceSection } from "../me/Workspace";

/** Story Z-10: the league office — the site's own work, a context of the workspace like a
 *  club or an event (`/office/<section>`, issue #32). Only for someone with a site
 *  relation (`office` in `GET /api/me/contexts`); its sections are what those relations
 *  give (`lib/workspace.ts`): the admin all of them, editorial *News* and *Media*, the
 *  site's race committee the events it runs. Every object's own work lives in its
 *  context; an object opened from here becomes the context.
 */
export function OfficePage() {
  const { t } = useTranslation("space");
  const ta = useTranslation("admin").t;
  const { section } = useParams();
  const { account, loading, hasRole } = useAccount();
  const { space } = useMySpace();

  if (loading || (account && !space.data && !space.error)) return <Loading testId="office-loading" />;
  if (!account) return <Navigate to="/account" replace />;
  const office = space.data?.office;
  if (!office) {
    return (
      <>
        <PageHeader title={t("workspace.kinds.office")} />
        <ErrorMessage text={t("context.notFound")} testId="office-not-found" />
      </>
    );
  }

  const sections: WorkspaceSection[] = [
    {
      key: "overview",
      label: t("workspace.overview"),
      render: () =>
        office.needs.length ? (
          <TodoList context={{ kind: "office" }} needs={office.needs} testId="office-todo" />
        ) : (
          <p className="text-sm text-muted" data-testid="office-nothing">
            {t("workspace.nothingWaits")}
          </p>
        ),
    },
    { key: "clubs", label: ta("clubs.title"), render: () => <Clubs /> },
    { key: "series", label: ta("series.title"), render: () => <SeriesList mayCreate={mayCreateIn("series", hasRole)} /> },
    { key: "events", label: ta("events.title"), render: () => <EventsAdmin /> },
    { key: "sailors", label: ta("sailors.title"), render: () => <SailorsAdmin /> },
    { key: "accounts", label: ta("accounts.title"), render: () => <AccountsAdmin /> },
    { key: "news", label: ta("posts.title"), render: () => <PostsAdmin /> },
    { key: "media", label: ta("media.title"), render: () => <MediaAdmin /> },
  ];
  return (
    <WorkspaceFrame
      current={{ kind: "office" }}
      name={t("workspace.kinds.office")}
      relations={office.relations}
      needs={office.needs}
      sections={sections}
      active={section}
    />
  );
}
