import { Button } from "@heroui/react";
import { Link, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { Stack } from "../components/Layouts";
import { useMyClubs } from "../api/generated/sbl";
import type { MyClub as MyClubOut, MyEvent } from "../api/types";
import { useAsync, useAccount } from "../api/useApi";
import { ActiveClubSelect } from "../components/ActiveClubSelect";
import { ErrorMessage, Loading, Empty, PageHeader, StatusBadge } from "../components/Blocks";
import { LineupPanel } from "../components/LineupPanel";
import { SquadPanel } from "../components/SquadPanel";
import { TabbedView, type TabDef } from "../components/Tabs";
import { eventDates } from "../lib/format";

/** Story V-12: a club manager's own screen.
 *
 * V-1 has always said the squad may be registered "by the leadership of their **own**
 * club", and the endpoint has always allowed it. The screen did not: the only squad panel
 * sat under `/admin`, which refuses anyone who is not `admin` or `editor`, and it found a
 * team by first listing every series through an admin-only route. The permission existed
 * and there was no door.
 *
 * So nothing on the way in here may be admin-only. `GET /api/clubs/mine` and
 * `/api/admin/teams/{id}/members` are both open to a club's own organizer, and borrowing
 * the admin page's queries would bring the defect straight back.
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
        title={t("mine.title")}
        testId="my-club-header"
      />
      <ClubChooser entries={entries} activeClubId={account.club_id ?? null} />
    </>
  );
}

/** Which club, and what you are in it.
 *
 * A dropdown rather than tabs: the two things a person needs to see here are the club's
 * name and their standing in it, and a tab strip can show one of those. Someone can be an
 * organizer of one club and merely a member of another — the same screen then offers
 * editing in one and not in the other, and the row has to say which without being asked.
 *
 * One club is still the normal case, so with one there is no chooser at all; the line
 * below states it. The choice is **remembered on the account** (`ActiveClubSelect`,
 * Story V-12), so the next visit and the account page open the same club; `?club=` in the
 * URL still wins for one visit, so a link to a particular club keeps working.
 */
function ClubChooser({
  entries,
  activeClubId,
}: {
  entries: MyClubOut[];
  activeClubId: number | null;
}) {
  const { t } = useTranslation("club");
  const [params, setParams] = useSearchParams();

  const requested = params.get("club") ?? (activeClubId == null ? null : String(activeClubId));
  // Nothing chosen yet: a club the person organizes over one they merely belong to —
  // this is the screen for acting, and the organizer's club is where they can.
  const entry =
    entries.find((e) => String(e.club.id) === requested) ??
    entries.find((e) => e.may_manage) ??
    entries[0];

  const roleOf = (item: MyClubOut) =>
    item.may_manage ? t("mine.roleOrganizer") : t("mine.roleMember");

  return (
    <Stack gap={6}>
      <div className="flex flex-wrap items-center gap-3">
        {entries.length > 1 ? (
          <ActiveClubSelect
            entries={entries}
            value={entry.club.id}
            testId="my-club-select"
            onChange={(clubId) =>
              setParams((previous) => {
                const next = new URLSearchParams(previous);
                next.set("club", String(clubId));
                // The chosen series and matchday belong to the club that was open;
                // keeping them would point at a team of the club just left.
                next.delete("team");
                next.delete("event");
                return next;
              })
            }
          />
        ) : (
          <p data-testid={`my-club-role-${entry.club.id}`} className="text-sm text-slate-600">
            <Link to={`/clubs/${entry.club.id}`} className="underline underline-offset-2">
              {entry.club.name}
            </Link>
            {" · "}
            {roleOf(entry)}
          </p>
        )}
      </div>

      <ClubTeams entry={entry} />
      <ClubEvents entry={entry} />
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
      <div>
        <h2 className="text-lg font-semibold">{t("mine.eventsTitle")}</h2>
        <p className="text-sm text-slate-600">{t("mine.eventsHint")}</p>
      </div>
      {events.length ? (
        <ul className="grid grid-cols-[minmax(0,1fr)] gap-3" data-testid="my-club-events-list">
          {events.map((event) => {
            const isOpen = open === String(event.event_id);
            return (
              <li
                key={event.event_id}
                data-testid={`my-club-event-${event.event_id}`}
                className="rounded-lg border border-slate-200 p-4"
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

/** One club's series registrations, each with its squad.
 *
 * A squad belongs to a series registration, never to a club as such (Story V-1) — a club
 * in the first league and the juniors has two, and they are different people.
 */
function ClubTeams({ entry }: { entry: MyClubOut }) {
  const { t } = useTranslation("club");
  const teams = entry.teams ?? [];

  if (!teams.length) {
    return <Empty testId={`my-club-no-teams-${entry.club.id}`}>{t("mine.noTeamsText")}</Empty>;
  }

  return (
    <Stack gap={6}>
      <TabbedView
        tabs={teams.map(
          (team): TabDef<string> => ({
            key: String(team.team_id),
            label: team.series.name,
            render: () => (
              <SquadPanel
                teamId={team.team_id}
                title={team.series.name}
                // A member who is not this club's organizer sees the squad and cannot
                // change it. The controls are absent rather than disabled: a disabled
                // button is a promise the server would not keep anyway.
                readOnly={!entry.may_manage}
              />
            ),
          }),
        )}
        param="team"
        testIdPrefix="my-club-team"
        label={t("mine.seriesTabsLabel")}
        className="grid grid-cols-[minmax(0,1fr)]"
      />
    </Stack>
  );
}
