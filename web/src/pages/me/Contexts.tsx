import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { useListEvents, useMyClubs } from "../../api/generated/sbl";
import type { MyContext } from "../../api/types";
import { useAccount, useAsync, useInvalidate } from "../../api/useApi";
import { Async } from "../../components/Async";
import { ErrorMessage, Loading, PageHeader, StatusBadge } from "../../components/Blocks";
import { ClubMembersPanel } from "../../components/ClubMembersPanel";
import { Section } from "../../components/Form";
import { Stack } from "../../components/Layouts";
import { eventDates } from "../../lib/format";
import { LEGACY_TAB_SECTION } from "../../lib/workspace";
import { AccountInfo, DeleteAccount, SailorProfile, SignInMethods } from "./Profile";
import { ClubEvents, ClubTeams, ClubWaivers } from "./ClubSections";
import { ClubMoneyTab, EventClaimsTab } from "./Money";
import { BankTab, ClaimsTab, DocumentsTab } from "./Papers";
import { Wards, Waivers } from "./Waivers";
import { RelationChips } from "./Chips";
import { TodoList } from "./Todos";
import { contextPath, useMySpace } from "./shared";
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
function legacyTarget(base: string, map: Record<string, string>, params: URLSearchParams): string | null {
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
function ContextSummary({ context, link }: { context: MyContext; link: string | null }) {
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
    </div>
  );
}

/** The frame every context page shares: find it in my space, else *not found*. */
function ContextFrame({
  kind,
  publicPath,
  sections,
}: {
  kind: ContextKind;
  publicPath: (context: MyContext) => string | null;
  sections: (context: MyContext) => WorkspaceSection[];
}) {
  const { t } = useTranslation("space");
  const { id, section } = useParams();
  const [params] = useSearchParams();
  const { account, accountLoading, space } = useMySpace();

  const legacy = legacyTarget(`/me/${kind}/${id}`, LEGACY_TAB_SECTION[kind], params);
  if (legacy) return <Navigate to={legacy} replace />;
  if (accountLoading) return <Loading testId="me-context-loading" />;
  if (!account) return <Navigate to="/account" replace />;

  return (
    <Async state={space} testId="me-context">
      {(data) => {
        const context = data.contexts.find((c) => c.kind === kind && String(c.id) === id);
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
          render: () => <ContextSummary context={context} link={publicPath(context)} />,
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
      }}
    </Async>
  );
}

/** Story S-1: my unsigned waiver, as a notice with its button. An event of a series asks
 * for the series' waiver — one signature on any of its events clears them all — and the
 * notice goes once it is signed: signing refreshes my space, and with it the need. */
function waiverNotice(t: (key: string) => string, scope: "series" | "event", id: number): WorkspaceSection {
  return {
    key: "waiver",
    label: t("context.tabs.waivers"),
    needs: ["waiver"],
    notice: true,
    render: () => <Waivers only={{ scope, id }} />,
  };
}

/** A section that is a way to another screen, said in a sentence. */
function Door({ text, to, label, testId }: { text: string; to: string; label: string; testId: string }) {
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
function MyTeams({ context, testId }: { context: MyContext; testId: string }) {
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

// ---------------------------------------------------------------------------- me

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

// -------------------------------------------------------------------------- club

/** `/me/club/:id` — members, matchdays and squads, my claims, the club's money. */
export function ClubPage() {
  const { t } = useTranslation("space");
  const { account } = useAccount();
  const navigate = useNavigate();
  // The club screen's own data (Story V-12): members, entries, registrations. A club's
  // treasurer who is neither member nor organizer is not in it, and gets the money only.
  const clubs = useMyClubs({ query: { enabled: Boolean(account) } });
  // The club's own sections come from that answer: until it is here, a section in the
  // address would look like one I do not have, and the frame would send me away from it.
  if (account && clubs.isPending) return <Loading testId="me-context-loading" />;

  return (
    <ContextFrame
      kind="club"
      publicPath={(c) => `/clubs/${c.id}`}
      sections={(c) => {
        const entry = clubs.data?.find((e) => e.club.id === c.id);
        const club: WorkspaceSection[] = entry
          ? [
              { key: "members", label: t("context.tabs.members"), render: () => <ClubMembersPanel entry={entry} onLeft={() => navigate("/me")} /> },
              {
                key: "crews",
                label: t("context.tabs.crews"),
                needs: ["crew_missing"],
                render: () => <ClubEvents entry={entry} />,
              },
              {
                key: "squads",
                label: t("context.tabs.squadsOnly"),
                needs: ["squad_below_min"],
                render: () => <ClubTeams entry={entry} />,
              },
            ]
          : [];
        return [
          ...club,
          {
            key: "waivers",
            label: t("context.tabs.waivers"),
            needs: ["crew_waiver_missing"],
            render: () => <ClubWaivers clubId={c.id} />,
          },
          {
            key: "my-claims",
            label: t("context.tabs.myClaims"),
            needs: ["claim_rejected"],
            render: () => <ClaimsTab target={{ kind: "club", id: c.id }} />,
          },
          {
            key: "decide-claims",
            label: t("context.tabs.money"),
            needs: ["claims"],
            render: () => <ClubMoneyTab clubId={c.id} clubName={c.name} />,
          },
          {
            key: "hosting",
            label: t("context.tabs.hosting"),
            render: () => (
              <Door
                text={t("context.organizeHosted")}
                to="/admin?tab=events"
                label={t("context.organizeLink")}
                testId="me-club-hosting"
              />
            ),
          },
        ];
      }}
    />
  );
}

// ------------------------------------------------------------------------ series

/** `/me/series/:id` — my waiver and my team, the series' events, the organizer's door. */
export function SeriesPage() {
  const { t } = useTranslation("space");
  return (
    <ContextFrame
      kind="series"
      publicPath={(c) => (c.published ? `/series/${c.id}` : null)}
      sections={(c) => [
        waiverNotice(t, "series", c.id),
        {
          key: "team",
          label: t("context.tabs.team"),
          render: () => <MyTeams context={c} testId="me-series-teams" />,
        },
        { key: "events", label: t("context.tabs.events"), render: () => <SeriesEvents seriesId={c.id} /> },
        {
          key: "registrations",
          label: t("context.tabs.organize"),
          render: () => (
            <Door
              text={t("context.organizeSeries")}
              to="/admin?tab=series"
              label={t("context.organizeLink")}
              testId="me-series-organize"
            />
          ),
        },
      ]}
    />
  );
}

/** The series' events, each leading to my page for it when I am part of it. */
function SeriesEvents({ seriesId }: { seriesId: number }) {
  const { t } = useTranslation("space");
  const events = useAsync(useListEvents({ series: seriesId, limit: 100 }));
  const { space } = useMySpace();
  const mine = new Set((space.data?.contexts ?? []).filter((c) => c.kind === "event").map((c) => c.id));
  return (
    <Section title={t("context.tabs.events")} testId="me-series-events">
      <Async state={events} testId="me-series-events" empty={t("context.noEvents")} isEmpty={(page) => !page.items.length}>
        {(page) => (
          <ul className="flex flex-col gap-2" data-testid="me-series-events-list">
            {page.items.map((event) => (
              <li key={event.id} className="flex flex-wrap items-baseline gap-x-3 text-sm">
                <Link
                  to={mine.has(event.id) ? contextPath({ kind: "event", id: event.id }) : `/events/${event.id}`}
                  className="font-medium underline-offset-2 hover:underline"
                  data-testid={`me-series-event-${event.id}`}
                >
                  {event.title}
                </Link>
                <span className="text-muted">{eventDates(event)}</span>
              </li>
            ))}
          </ul>
        )}
      </Async>
    </Section>
  );
}

// ------------------------------------------------------------------------- event

/** `/me/event/:id` — my crew and waiver, my claims, claims to decide, race control. */
export function EventPage() {
  const { t } = useTranslation("space");
  return (
    <ContextFrame
      kind="event"
      publicPath={(c) => (c.published ? `/events/${c.id}` : null)}
      sections={(c) => [
        c.series_id != null ? waiverNotice(t, "series", c.series_id) : waiverNotice(t, "event", c.id),
        {
          key: "crew",
          label: t("context.tabs.crew"),
          render: () => (
            <Stack gap={3}>
              <MyTeams context={c} testId="me-event-teams" />
              {c.published && (
                <Link to={`/events/${c.id}`} className="w-fit text-sm underline underline-offset-2" data-testid="me-event-crews-link">
                  {t("context.crewsAndPairings")}
                </Link>
              )}
            </Stack>
          ),
        },
        {
          // Those who work the event file claims on it (Story F-2); sailing is not work.
          key: "my-claims",
          label: t("context.tabs.myClaims"),
          needs: ["claim_rejected"],
          render: () => <ClaimsTab target={{ kind: "event", id: c.id }} />,
        },
        {
          key: "decide-claims",
          label: t("context.tabs.toDecide"),
          needs: ["claims"],
          render: () => <EventClaimsTab eventId={c.id} />,
        },
        {
          key: "race-control",
          label: t("context.tabs.raceControl"),
          render: () => (
            <Door
              text={t("context.raceControl")}
              to={`/events/${c.id}/race-control`}
              label={t("context.raceControlLink")}
              testId="me-event-race-control"
            />
          ),
        },
        {
          key: "general",
          label: t("context.tabs.organize"),
          render: () => (
            <Door
              text={t("context.organizeEvent")}
              to="/admin?tab=events"
              label={t("context.organizeLink")}
              testId="me-event-organize"
            />
          ),
        },
      ]}
    />
  );
}
