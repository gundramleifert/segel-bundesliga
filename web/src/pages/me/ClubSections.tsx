import { Button } from "@heroui/react";
import { Link, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import type { MyClub as MyClubOut, MyEvent } from "../../api/types";
import { Empty, StatusBadge } from "../../components/Blocks";
import { LineupPanel } from "../../components/LineupPanel";
import { SquadPanel } from "../../components/SquadPanel";
import { eventDates } from "../../lib/format";

/** Story V-12's two lists, now sections of a club's page in my space (Story S-7):
 * the club's matchdays with their crews, and its series registrations with their squads.
 * Both are editable for the club's organizer and read-only for a member.
 */

/** The club's matchdays, each with its lineup — Story V-2's door (Story V-12).
 *
 * One row per event entry, next matchday first. Opening a row shows `LineupPanel`, which
 * draws from the squad the entry belongs to — the series registration, or for an event in
 * no series the entry itself, whose squad is then shown right there too, or a club running
 * its own cup here could enter it and never register anyone. `?event=` keeps the open row
 * across a reload.
 */
export function ClubEvents({ entry }: { entry: MyClubOut }) {
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
export function ClubTeams({ entry }: { entry: MyClubOut }) {
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
