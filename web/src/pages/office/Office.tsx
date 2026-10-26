import { useTranslation } from "react-i18next";
import { Navigate, useLocation, useParams } from "react-router-dom";

import { useAccount } from "../../api/useApi";
import { ErrorMessage, Loading, PageHeader } from "../../components/Blocks";
import { mayCreateIn, officeAddress } from "../../lib/workspace";
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
 *
 *  Someone without a site relation reads that it is not found — a series', an event's or
 *  a club's organizer has no office; their work is in their own context (Story A-11).
 *  A section this screen has not built (`imports`, which runs from the command line) is
 *  left out of the sidebar by `WorkspaceFrame`.
 */
export function OfficePage({ section: fixed }: { section?: string } = {}) {
  const { t } = useTranslation("space");
  const params = useParams();
  const section = fixed ?? params.section;
  const { account, loading } = useAccount();
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
      render: () =>
        office.needs.length ? (
          <TodoList context={{ kind: "office" }} needs={office.needs} testId="office-todo" />
        ) : (
          <p className="text-sm text-muted" data-testid="office-nothing">
            {t("workspace.nothingWaits")}
          </p>
        ),
    },
    { key: "clubs", render: () => <Clubs /> },
    { key: "series", render: () => <SeriesList mayCreate={mayCreateIn("series", office.relations)} /> },
    { key: "events", render: () => <EventsAdmin /> },
    { key: "people", render: () => <SailorsAdmin /> },
    { key: "accounts", render: () => <AccountsAdmin /> },
    { key: "news", render: () => <PostsAdmin /> },
    { key: "media", render: () => <MediaAdmin /> },
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

/** The addresses of the administration before #32 — `/admin`, `/admin?tab=<section>`,
 *  `/admin/<area>/new`, `/admin/news/:id` — were in bookmarks, mails and the handbook;
 *  each goes to its `/office` address, the other query parameters kept
 *  (`officeAddress`, Story A-11). */
export function AdminRedirect() {
  const { pathname, search, hash } = useLocation();
  const rest = pathname.replace(/^\/admin\/?/, "");
  return <Navigate to={`${officeAddress(rest, search)}${hash}`} replace />;
}
