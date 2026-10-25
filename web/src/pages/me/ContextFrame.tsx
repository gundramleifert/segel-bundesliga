import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, Navigate, useParams, useSearchParams } from "react-router-dom";

import type { MyContext } from "../../api/types";
import { useReachedContext } from "../../api/generated/sbl";
import { ErrorMessage, Loading, PageHeader, StatusBadge } from "../../components/Blocks";
import { eventDates } from "../../lib/format";
import { LEGACY_TAB_SECTION } from "../../lib/workspace";
import { Waivers } from "./Waivers";
import { RelationChips } from "./Chips";
import { TodoList } from "./Todos";
import { useMySpace } from "./shared";
import { WorkspaceFrame, type WorkspaceSection } from "./Workspace";

/** Stories S-7, Z-10: my page in a club, a series or an event — and my own, `/me/profile`.
 *
 * **Assembled, not written per role.** Each page lists the sections it has built, keyed as
 * `lib/workspace.ts` declares them; the frame (`WorkspaceFrame`) shows those my relations
 * there allow, in the sidebar, and the one in the URL (`/me/club/7/members`). A club's
 * treasurer who also sails there sees the money and their squad, a helper their claims and
 * nothing else. The panels are the ones the tabs had (#31 moved them, unchanged); the
 * sections the plan adds come with #32.
 *
 * A section that needs me says so with its count, so the "needs you" line leads on to the
 * right section instead of a page to search. A section that is only there while it needs
 * me — an unsigned waiver (S-1) — is a **notice** above every section instead.
 */


type ContextKind = "club" | "series" | "event";

/** `?tab=` was the address of a section before #31: the same section, at its own path —
 *  the rest of the query kept (a club's `&event=`). An unknown tab goes to the overview. */
export function legacyTarget(base: string, map: Record<string, string>, params: URLSearchParams): string | null {
  const tab = params.get("tab");
  if (!tab) return null;
  const rest = new URLSearchParams(params);
  rest.delete("tab");
  const query = rest.toString();
  const section = map[tab];
  return `${base}${section ? `/${section}` : ""}${query ? `?${query}` : ""}`;
}

/** What a context opens on (§4): what waits for me there, each a link to the section that
 *  clears it — *Nothing waits for you* when nothing does — then its state: dates, status,
 *  the public page, my relations. */
function ContextSummary({ context, link, extra }: { context: MyContext; link: string | null; extra?: ReactNode }) {
  const { t } = useTranslation("space");
  const testId = `me-context-${context.kind}-${context.id}`;
  return (
    <div className="flex flex-col gap-4" data-testid={testId}>
      {context.needs.length ? (
        <TodoList context={{ kind: context.kind, id: context.id }} needs={context.needs} testId={`${testId}-todo`} />
      ) : (
        <p className="text-sm text-muted" data-testid={`${testId}-nothing`}>
          {t("workspace.nothingWaits")}
        </p>
      )}
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted">
          {(context.kind === "event" || context.starts_on) && <span>{eventDates(context)}</span>}
          {context.status && <StatusBadge status={context.status} testId={`${testId}-status`} />}
          {link && (
            <Link to={link} className="underline underline-offset-2" data-testid={`${testId}-public`}>
              {t("context.publicPage")}
            </Link>
          )}
        </div>
        <RelationChips relations={context.relations} testId={`${testId}-relations`} />
      </div>
      {extra}
    </div>
  );
}

/** The frame every context page shares: find it in my space, else *not found*. */
export function ContextFrame({
  kind,
  publicPath,
  sections,
  overview: overviewExtra,
}: {
  kind: ContextKind;
  publicPath: (context: MyContext) => string | null;
  sections: (context: MyContext) => WorkspaceSection[];
  /** What this kind of context adds to its overview, under its state — an event's
   *  readiness reasons (VA-8). */
  overview?: (context: MyContext) => ReactNode;
}) {
  const { t } = useTranslation("space");
  const { id, section } = useParams();
  const [params] = useSearchParams();
  const { account, accountLoading, space } = useMySpace();
  // Mine, from the list — else reached through another (a series manager's event, the
  // league office opening anything), with the relations the model gives there.
  const listed = space.data?.contexts.find((c) => c.kind === kind && String(c.id) === id);
  const reached = useReachedContext(kind, Number(id), {
    query: { enabled: Boolean(account) && Boolean(space.data) && !listed && /^\d+$/.test(id ?? ""), retry: false },
  });

  const legacy = legacyTarget(`/me/${kind}/${id}`, LEGACY_TAB_SECTION[kind], params);
  if (legacy) return <Navigate to={legacy} replace />;
  if (accountLoading) return <Loading testId="me-context-loading" />;
  if (!account) return <Navigate to="/account" replace />;
  if (space.error) return <ErrorMessage text={space.error} testId="me-context-error" />;
  if (!space.data || (!listed && reached.isPending && reached.fetchStatus !== "idle")) {
    return <Loading testId="me-context-loading" />;
  }
  const context = listed ?? reached.data;
  // Not an empty shell: a page I am not part of is not mine to see.
  if (!context) {
    return (
      <>
        <PageHeader title={t("title")} />
        <ErrorMessage text={t("context.notFound")} testId="me-context-not-found" />
      </>
    );
  }
  const overview: WorkspaceSection = {
    key: "overview",
    label: t("workspace.overview"),
    render: () => <ContextSummary context={context} link={publicPath(context)} extra={overviewExtra?.(context)} />,
  };
  return (
    <WorkspaceFrame
      current={{ kind, id: context.id }}
      name={context.name}
      shortName={context.short_name}
      relations={context.relations}
      needs={context.needs}
      sections={[overview, ...sections(context)]}
      active={section}
      started={context.status === "live" || context.status === "final"}
    />
  );
}

/** Story S-1: my unsigned waiver, as a notice with its button. An event of a series asks
 * for the series' waiver — one signature on any of its events clears them all — and the
 * notice goes once it is signed: signing refreshes my space, and with it the need. */
export function waiverNotice(t: (key: string) => string, scope: "series" | "event", id: number): WorkspaceSection {
  return {
    key: "waiver",
    label: t("context.tabs.waivers"),
    needs: ["waiver"],
    notice: true,
    render: () => <Waivers only={{ scope, id }} />,
  };
}

/** A section that is a way to another screen, said in a sentence. */
export function Door({ text, to, label, testId }: { text: string; to: string; label: string; testId: string }) {
  return (
    <div className="flex flex-col gap-2" data-testid={testId}>
      <p className="text-sm text-muted">{text}</p>
      <Link to={to} className="w-fit font-medium text-link underline-offset-2 hover:underline" data-testid={`${testId}-link`}>
        {label} →
      </Link>
    </div>
  );
}

/** The teams I sail in there — the squad of a series, the crew of an event. */
export function MyTeams({ context, testId }: { context: MyContext; testId: string }) {
  const { t } = useTranslation("space");
  return (
    <ul className="flex flex-col gap-2" data-testid={testId}>
      {context.teams.map((team) => (
        <li key={team.team_id} data-testid={`${testId}-${team.team_id}`} className="text-sm">
          {t("context.sailsFor")}{" "}
          <Link to={`/clubs/${team.club_id}`} className="font-medium underline underline-offset-2">
            {team.club_name}
          </Link>
        </li>
      ))}
    </ul>
  );
}
