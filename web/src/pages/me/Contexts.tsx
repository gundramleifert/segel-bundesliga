import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";

import { useListEvents, useMyClubs } from "../../api/generated/sbl";
import type { MyContext, Need } from "../../api/types";
import { useAccount, useAsync, useInvalidate } from "../../api/useApi";
import { Async } from "../../components/Async";
import { ErrorMessage, Loading, PageHeader, StatusBadge } from "../../components/Blocks";
import { ClubMembersPanel } from "../../components/ClubMembersPanel";
import { Section } from "../../components/Form";
import { Stack } from "../../components/Layouts";
import { TabbedView, type TabDef } from "../../components/Tabs";
import { eventDates } from "../../lib/format";
import { AccountInfo, DeleteAccount, SailorProfile, SignInMethods } from "../Account";
import { ClubEvents, ClubTeams } from "./ClubSections";
import { ClubMoneyTab, EventClaimsTab } from "./Money";
import { BankTab, ClaimsTab, DocumentsTab } from "./Papers";
import { Waivers } from "./Waivers";
import { NeedsLine, RelationChips } from "./Chips";
import { contextPath, useMySpace } from "./shared";

/** Story S-7: my page in a club, a series or an event — and my own, `/me/profile`.
 *
 * **Assembled, not written per role.** Each section says which of my relations show it,
 * and the page shows those my relations allow: a club's treasurer who also sails there sees
 * the money and their squad, a helper sees their claims and nothing else. The sections
 * are the panels the separate screens had (`/club`, `/reimbursements`, `/account`) —
 * moved here, not changed.
 *
 * A tab that needs me says so on its label, so the "needs you" line of the overview card
 * leads on to the right tab instead of a page to search.
 */

type SectionDef = {
  key: string;
  label: string;
  /** Shown when I hold one of these there (`sailor` included); none — always. */
  for?: string[];
  /** Overview "needs" codes this tab is where to act on. */
  needs?: string[];
  render: () => ReactNode;
};

function visible(sections: SectionDef[], relations: string[]): SectionDef[] {
  return sections.filter((s) => !s.for || s.for.some((r) => relations.includes(r)));
}

function labelled(section: SectionDef, needs: Need[]): string {
  const count = needs.filter((n) => section.needs?.includes(n.code)).reduce((sum, n) => sum + n.count, 0);
  return count ? `${section.label} (${count})` : section.label;
}

/** The frame every context page shares: find it in my space, else *not found*. */
function ContextFrame({
  kind,
  publicPath,
  sections,
}: {
  kind: MyContext["kind"];
  publicPath: (context: MyContext) => string | null;
  sections: (context: MyContext) => SectionDef[];
}) {
  const { t } = useTranslation("space");
  const { id } = useParams();
  const { account, accountLoading, space } = useMySpace();

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
              <BackLink />
            </>
          );
        }
        const shown = visible(sections(context), context.relations);
        const testId = `me-context-${context.kind}-${context.id}`;
        const link = publicPath(context);
        return (
          <Stack gap={5} testId={testId}>
            <PageHeader title={context.name} />
            <BackLink />
            <div className="flex flex-col gap-2">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-600">
                {(context.kind === "event" || context.starts_on) && <span>{eventDates(context)}</span>}
                {context.status && <StatusBadge status={context.status} testId={`${testId}-status`} />}
                {link && (
                  <Link to={link} className="underline underline-offset-2" data-testid={`${testId}-public`}>
                    {t("context.publicPage")}
                  </Link>
                )}
              </div>
              <RelationChips relations={context.relations} testId={`${testId}-relations`} />
              <NeedsLine needs={context.needs} testId={`${testId}-needs`} />
            </div>
            {shown.length ? (
              <TabbedView
                param="tab"
                testIdPrefix="me-context"
                label={t("context.tabsLabel")}
                className="grid grid-cols-[minmax(0,1fr)]"
                tabs={shown.map((s): TabDef<string> => ({ key: s.key, label: labelled(s, context.needs), render: s.render }))}
              />
            ) : (
              <p className="text-sm text-slate-500" data-testid={`${testId}-nothing`}>
                {t("context.nothingHere")}
              </p>
            )}
          </Stack>
        );
      }}
    </Async>
  );
}

function BackLink() {
  const { t } = useTranslation("space");
  return (
    <Link to="/me" className="w-fit text-sm text-brand-700 underline-offset-2 hover:underline" data-testid="me-context-back">
      ← {t("context.back")}
    </Link>
  );
}

/** A section that is a way to another screen, said in a sentence. */
function Door({ text, to, label, testId }: { text: string; to: string; label: string; testId: string }) {
  return (
    <div className="flex flex-col gap-2" data-testid={testId}>
      <p className="text-sm text-slate-600">{text}</p>
      <Link to={to} className="w-fit font-medium text-brand-700 underline-offset-2 hover:underline" data-testid={`${testId}-link`}>
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

const ORGANIZERS = ["admin", "manager"];

// ---------------------------------------------------------------------------- me

/** `/me/profile` — my own things: the account, papers, bank, waivers, all my claims. */
export function ProfilePage() {
  const { t } = useTranslation("space");
  const { account, loading } = useAccount();
  const invalidate = useInvalidate();
  if (loading) return <Loading testId="me-context-loading" />;
  if (!account) return <Navigate to="/account" replace />;

  return (
    <Stack gap={5} testId="me-profile">
      <PageHeader title={t("overview.me")} />
      <BackLink />
      <TabbedView
        param="tab"
        testIdPrefix="me-context"
        label={t("context.tabsLabel")}
        className="grid grid-cols-[minmax(0,1fr)]"
        tabs={[
          {
            key: "account",
            label: t("context.tabs.account"),
            render: () => (
              <Stack gap={4}>
                <AccountInfo account={account} />
                <SignInMethods account={account} onChanged={() => invalidate("/api/auth/me")} />
                <SailorProfile />
                <DeleteAccount />
              </Stack>
            ),
          },
          { key: "documents", label: t("tabs.documents"), render: () => <DocumentsTab /> },
          { key: "bank", label: t("tabs.bank"), render: () => <BankTab /> },
          { key: "waivers", label: t("context.tabs.waivers"), render: () => <Waivers /> },
          { key: "claims", label: t("tabs.claims"), render: () => <ClaimsTab /> },
        ]}
      />
    </Stack>
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

  return (
    <ContextFrame
      kind="club"
      publicPath={(c) => `/clubs/${c.id}`}
      sections={(c) => {
        const entry = clubs.data?.find((e) => e.club.id === c.id);
        const club: SectionDef[] = entry
          ? [
              { key: "members", label: t("context.tabs.members"), render: () => <ClubMembersPanel entry={entry} onLeft={() => navigate("/me")} /> },
              {
                key: "events",
                label: t("context.tabs.matchdays"),
                needs: ["crew_missing"],
                render: () => <ClubEvents entry={entry} />,
              },
              {
                key: "series",
                label: t("context.tabs.squads"),
                needs: ["squad_below_min"],
                render: () => <ClubTeams entry={entry} />,
              },
            ]
          : [];
        return [
          ...club,
          {
            key: "claims",
            label: t("context.tabs.myClaims"),
            for: ["member"],
            render: () => <ClaimsTab target={{ kind: "club", id: c.id }} />,
          },
          {
            key: "money",
            label: t("context.tabs.money"),
            for: [...ORGANIZERS, "treasurer"],
            needs: ["claims"],
            render: () => <ClubMoneyTab clubId={c.id} clubName={c.name} />,
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
        {
          key: "waiver",
          label: t("context.tabs.waiver"),
          for: ["sailor"],
          needs: ["waiver"],
          render: () => <Waivers only={{ scope: "series", id: c.id }} />,
        },
        {
          key: "team",
          label: t("context.tabs.team"),
          for: ["sailor"],
          render: () => <MyTeams context={c} testId="me-series-teams" />,
        },
        { key: "events", label: t("context.tabs.events"), render: () => <SeriesEvents seriesId={c.id} /> },
        {
          key: "organize",
          label: t("context.tabs.organize"),
          for: ORGANIZERS,
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
                <span className="text-slate-500">{eventDates(event)}</span>
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
        {
          key: "crew",
          label: t("context.tabs.crew"),
          for: ["sailor"],
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
          key: "waiver",
          label: t("context.tabs.waiver"),
          for: ["sailor"],
          needs: ["waiver"],
          // An event of a series is covered by the series' waiver (Story S-1).
          render: () =>
            c.series_id != null ? (
              <Door
                text={t("context.waiverInSeries")}
                to={`${contextPath({ kind: "series", id: c.series_id })}?tab=waiver`}
                label={t("context.waiverInSeriesLink")}
                testId="me-event-waiver-series"
              />
            ) : (
              <Waivers only={{ scope: "event", id: c.id }} />
            ),
        },
        {
          key: "claims",
          label: t("context.tabs.myClaims"),
          // Those who work the event file claims on it (Story F-2); sailing is not work.
          for: ["admin", "manager", "treasurer", "race_officer", "jury", "helper"],
          render: () => <ClaimsTab target={{ kind: "event", id: c.id }} />,
        },
        {
          key: "decide",
          label: t("context.tabs.toDecide"),
          for: [...ORGANIZERS, "treasurer"],
          needs: ["claims"],
          render: () => <EventClaimsTab eventId={c.id} />,
        },
        {
          key: "race",
          label: t("context.tabs.raceControl"),
          for: [...ORGANIZERS, "race_officer"],
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
          key: "organize",
          label: t("context.tabs.organize"),
          for: ORGANIZERS,
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
