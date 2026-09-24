import { Button } from "@heroui/react";
import { useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { Stack } from "../components/Layouts";
import { useMyClubs, useUpdateMe } from "../api/generated/sbl";
import type { MyClub as MyClubOut, MyEvent } from "../api/types";
import { useAsync, useAccount, useInvalidate } from "../api/useApi";
import { ClubMembersPanel } from "../components/ClubMembersPanel";
import { AccessPanel } from "../components/AccessPanel";
import { ErrorMessage, Loading, Empty, PageHeader, StatusBadge } from "../components/Blocks";
import { LineupPanel } from "../components/LineupPanel";
import { SquadPanel } from "../components/SquadPanel";
import { TabbedView, type TabDef } from "../components/Tabs";
import { eventDates } from "../lib/format";

/** Story V-12: "Our club" — one screen for whoever belongs to a club.
 *
 * Three tabs: **Members** (the roster, and for the organizer the requests, invitations
 * and organizer tools — Stories V-8, V-10, Z-5, A-8), **Matchdays** (the club's entries
 * with their lineups — V-2) and **Series** (the registrations with their squads — V-1).
 *
 * Nothing on the way in here may be admin-only. The screen began as the door for V-1's
 * permission: the endpoint had always let a club's leadership register its squad, and
 * the only panel sat under `/admin`, which refuses them. `GET /api/clubs/mine` is what
 * the whole screen navigates by, and borrowing the admin page's queries would bring
 * that defect straight back.
 *
 * Which club, when there are several, is chosen in the **navigation** — "Our club"
 * expands into one entry per club — not on the page; `?club=` names the one shown and
 * the choice is remembered on the account (`ClubScreen`).
 */
export function MyClub() {
  const { t } = useTranslation("club");
  const { account, loading: accountLoading } = useAccount();
  const clubs = useAsync(useMyClubs({ query: { enabled: Boolean(account) } }));

  if (accountLoading) return <Loading testId="my-club-loading" />;
  if (!account) {
    return <ErrorMessage text={t("mine.notSignedIn")} testId="my-club-auth-error" />;
  }
  if (clubs.loading) return <Loading testId="my-club-loading" />;
  if (clubs.error) return <ErrorMessage text={clubs.error} testId="my-club-error" />;

  const entries = clubs.data ?? [];
  if (!entries.length) {
    // Not an empty box: a person with no club needs to know where joining one starts
    // (Story V-7), and this is the only screen that can tell them.
    return (
      <>
        <PageHeader title={t("mine.title")} testId="my-club-header" />
        <Empty testId="my-club-empty">
          {t("mine.noClubText")}{" "}
          <Link to="/clubs" className="underline underline-offset-2">
            {t("mine.noClubLink")}
          </Link>
        </Empty>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title={entries.length > 1 ? t("mine.titlePlural") : t("mine.title")}
        testId="my-club-header"
      />
      <ClubScreen entries={entries} activeClubId={account.club_id ?? null} />
    </>
  );
}

/** The club being shown, and its three tabs.
 *
 * `?club=` says which club; missing, the account's remembered club, else a club the
 * person organizes over one they merely belong to — this is the screen for acting, and
 * the organizer's club is where they can. The URL is then completed (`replace`), so the
 * navigation's sub-entry for the open club can light up, and a club that was reached by
 * URL or sub-entry becomes the remembered one (`PATCH /api/auth/me`), so the next visit
 * and the account page agree with the navigation. One save per change, none on failure.
 */
function ClubScreen({
  entries,
  activeClubId,
}: {
  entries: MyClubOut[];
  activeClubId: number | null;
}) {
  const { t } = useTranslation("club");
  const [params, setParams] = useSearchParams();
  const invalidate = useInvalidate();
  const remember = useUpdateMe({ mutation: { onSuccess: () => invalidate("/api/auth/me") } });

  const requested = params.get("club");
  const entry =
    entries.find((e) => String(e.club.id) === requested) ??
    entries.find((e) => e.club.id === activeClubId) ??
    entries.find((e) => e.may_manage) ??
    entries[0];
  const shown = entry.club.id;

  useEffect(() => {
    if (requested !== String(shown)) {
      setParams(
        (previous) => {
          const next = new URLSearchParams(previous);
          next.set("club", String(shown));
          return next;
        },
        { replace: true },
      );
    }
  }, [requested, shown, setParams]);

  useEffect(() => {
    if (requested === String(shown) && activeClubId !== shown && remember.isIdle) {
      remember.mutate({ data: { club_id: shown } });
    }
    // `remember` is a stable mutation object; listing it would re-run on every state change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requested, shown, activeClubId]);

  const roleOf = (item: MyClubOut) =>
    item.may_manage ? t("mine.roleOrganizer") : t("mine.roleMember");

  const tabs: TabDef<"members" | "events" | "series">[] = [
    {
      key: "members",
      label: t("mine.tabs.members"),
      render: () => (
        <>
          <ClubMembersPanel entry={entry} />
          {entry.may_admin && (
            <AccessPanel object={`club:${entry.club.id}`} testId={`my-club-access-${entry.club.id}`} />
          )}
        </>
      ),
    },
    { key: "events", label: t("mine.tabs.events"), render: () => <ClubEvents entry={entry} /> },
    { key: "series", label: t("mine.tabs.series"), render: () => <ClubTeams entry={entry} /> },
  ];

  return (
    <Stack gap={5}>
      <p data-testid={`my-club-role-${shown}`} className="text-sm text-slate-600">
        <Link to={`/clubs/${shown}`} className="underline underline-offset-2">
          {entry.club.name}
        </Link>
        {" · "}
        {roleOf(entry)}
      </p>
      <TabbedView
        tabs={tabs}
        param="tab"
        testIdPrefix="my-club"
        label={t("mine.tabsLabel")}
        className="grid grid-cols-[minmax(0,1fr)]"
      />
    </Stack>
  );
}

/** The club's matchdays, each with its lineup — Story V-2's door (Story V-12).
 *
 * One row per event entry, next matchday first. Opening a row shows `LineupPanel`, which
 * draws from the squad the entry belongs to — the series registration, or for an event in
 * no series the entry itself, whose squad is then shown right there too, or a club running
 * its own cup here could enter it and never register anyone. `?event=` keeps the open row
 * across a reload.
 */
function ClubEvents({ entry }: { entry: MyClubOut }) {
  const { t } = useTranslation("club");
  const [params, setParams] = useSearchParams();
  const events = entry.events ?? [];
  const open = params.get("event");

  const toggle = (event: MyEvent) =>
    setParams((previous) => {
      const next = new URLSearchParams(previous);
      if (open === String(event.event_id)) next.delete("event");
      else next.set("event", String(event.event_id));
      return next;
    });

  return (
    <section data-testid={`my-club-events-${entry.club.id}`} className="grid grid-cols-[minmax(0,1fr)] gap-3">
      <p className="text-sm text-slate-600">{t("mine.eventsHint")}</p>
      {events.length ? (
        <ul className="grid grid-cols-[minmax(0,1fr)] gap-3" data-testid="my-club-events-list">
          {events.map((event) => {
            const isOpen = open === String(event.event_id);
            return (
              <li
                key={event.event_id}
                data-testid={`my-club-event-${event.event_id}`}
                className="rounded-lg border border-slate-200 bg-white p-4"
              >
                <div className="flex flex-wrap items-center gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">
                      {event.title}
                      {event.series && (
                        <span className="ml-2 text-sm font-normal text-slate-500">{event.series.name}</span>
                      )}
                    </p>
                    <p className="text-sm text-slate-600">{eventDates(event)}</p>
                  </div>
                  <StatusBadge status={event.status} testId={`my-club-event-status-${event.event_id}`} />
                  {!event.published && (
                    <span
                      data-testid={`my-club-event-draft-${event.event_id}`}
                      className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-600 ring-1 ring-inset ring-slate-200"
                    >
                      {t("mine.draftBadge")}
                    </span>
                  )}
                  <Button
                    size="sm"
                    variant={isOpen ? "outline" : "primary"}
                    onPress={() => toggle(event)}
                    data-testid={`my-club-event-toggle-${event.event_id}`}
                  >
                    {isOpen ? t("mine.closeLineup") : t("mine.openLineup")}
                  </Button>
                </div>
                {isOpen && (
                  <div className="mt-4 grid grid-cols-[minmax(0,1fr)] gap-4">
                    {/* An event in no series has its squad on the entry itself (V-1). */}
                    {!event.series && (
                      <SquadPanel
                        teamId={event.team_id}
                        title={t("mine.standaloneSquad")}
                        readOnly={!entry.may_manage}
                      />
                    )}
                    <LineupPanel
                      eventId={event.event_id}
                      teamId={event.team_id}
                      squadTeamId={event.squad_team_id}
                      crewSize={event.crew_size}
                      readOnly={!entry.may_manage}
                      testIdPrefix={`my-club-lineup-${event.event_id}`}
                    />
                    {event.published && (
                      <Link
                        to={`/events/${event.event_id}`}
                        className="text-sm underline underline-offset-2"
                        data-testid={`my-club-event-link-${event.event_id}`}
                      >
                        {t("mine.openEvent")}
                      </Link>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      ) : (
        <Empty testId={`my-club-no-events-${entry.club.id}`}>{t("mine.eventsEmpty")}</Empty>
      )}
    </section>
  );
}

/** One club's series registrations, each with its squad — a list, like the matchdays.
 *
 * A row per registration, the squad opening under it on demand (`?team=` keeps the open
 * one across a reload). Tabs were the first shape and did not scale: a club that sails
 * ten series gets ten tab labels in a strip, and a strip says nothing about any of them,
 * where a row can state the year and how many are registered before anyone opens it.
 * A squad belongs to a series registration, never to a club as such (Story V-1).
 */
function ClubTeams({ entry }: { entry: MyClubOut }) {
  const { t } = useTranslation("club");
  const [params, setParams] = useSearchParams();
  const teams = entry.teams ?? [];
  const open = params.get("team");

  const toggle = (teamId: number) =>
    setParams((previous) => {
      const next = new URLSearchParams(previous);
      if (open === String(teamId)) next.delete("team");
      else next.set("team", String(teamId));
      return next;
    });

  if (!teams.length) {
    return <Empty testId={`my-club-no-teams-${entry.club.id}`}>{t("mine.noTeamsText")}</Empty>;
  }

  return (
    <section data-testid={`my-club-teams-${entry.club.id}`} className="grid grid-cols-[minmax(0,1fr)] gap-3">
      <p className="text-sm text-slate-600">{t("mine.seriesHint")}</p>
      <ul className="grid grid-cols-[minmax(0,1fr)] gap-3" data-testid="my-club-teams-list">
        {teams.map((team) => {
          const isOpen = open === String(team.team_id);
          return (
            <li
              key={team.team_id}
              data-testid={`my-club-team-${team.team_id}`}
              className="rounded-lg border border-slate-200 bg-white p-4"
            >
              <div className="flex flex-wrap items-center gap-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">
                    <Link to={`/series/${team.series.id}`} className="underline-offset-2 hover:underline">
                      {team.series.name}
                    </Link>
                  </p>
                  <p className="text-sm text-slate-600" data-testid={`my-club-team-size-${team.team_id}`}>
                    {t("mine.squadSize", {
                      count: team.squad_size,
                      min: team.squad_min,
                      max: team.squad_max,
                    })}
                  </p>
                </div>
                <Button
                  size="sm"
                  variant={isOpen ? "outline" : "primary"}
                  onPress={() => toggle(team.team_id)}
                  data-testid={`my-club-team-toggle-${team.team_id}`}
                >
                  {isOpen ? t("mine.closeSquad") : t("mine.openSquad")}
                </Button>
              </div>
              {isOpen && (
                <div className="mt-4">
                  <SquadPanel
                    teamId={team.team_id}
                    title={team.series.name}
                    // A member who is not this club's organizer sees the squad and cannot
                    // change it. The controls are absent rather than disabled: a disabled
                    // button is a promise the server would not keep anyway.
                    readOnly={!entry.may_manage}
                  />
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
