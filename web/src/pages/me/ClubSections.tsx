import { Button } from "@heroui/react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import {
  getListOwnApplicationsQueryKey,
  useClubWaivers,
  useListAllEvents,
  useListOwnApplications,
  useListSeries,
  useSubmitApplication,
  useWithdrawApplication,
} from "../../api/generated/sbl";
import type { MyClub as MyClubOut, MyEvent } from "../../api/types";
import { WHOLE_LIST, errorText, useAsync, useInvalidate } from "../../api/useApi";
import { AddButton } from "../../components/AddButton";
import { Async } from "../../components/Async";
import { Section } from "../../components/Form";
import { Select } from "../../components/Select";
import { EventLinks } from "./EventLinks";
import { WaiverName, WaiverStatus } from "../../components/WaiverStatus";
import { Badge, Empty, ErrorMessage, StatusBadge } from "../../components/Blocks";
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

  // One row per team: a club with a second team in an event (Story VA-13) lines each up
  // on its own, so the row is the event and, from the second team on, its number.
  const rowOf = (event: MyEvent) =>
    (event.number ?? 1) > 1 ? `${event.event_id}-${event.number}` : String(event.event_id);
  const toggle = (event: MyEvent) =>
    setParams((previous) => {
      const next = new URLSearchParams(previous);
      if (open === rowOf(event)) next.delete("event");
      else next.set("event", rowOf(event));
      return next;
    });

  return (
    <section data-testid={`my-club-events-${entry.club.id}`} className="grid grid-cols-[minmax(0,1fr)] gap-3">
      <p className="text-sm text-muted">{t("mine.eventsHint")}</p>
      {events.length ? (
        <ul className="grid grid-cols-[minmax(0,1fr)] gap-3" data-testid="my-club-events-list">
          {events.map((event) => {
            const row = rowOf(event);
            const isOpen = open === row;
            return (
              <li
                key={event.team_id}
                data-testid={`my-club-event-${row}`}
                className="rounded-lg border border-separator bg-surface p-4"
              >
                <div className="flex flex-wrap items-center gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">
                      {event.title}
                      {(event.number ?? 1) > 1 && (
                        <span className="ml-2 text-sm font-semibold">{event.team_name}</span>
                      )}
                      {event.series && (
                        <span className="ml-2 text-sm font-normal text-muted">{event.series.name}</span>
                      )}
                    </p>
                    <p className="text-sm text-muted">{eventDates(event)}</p>
                  </div>
                  <StatusBadge status={event.status} testId={`my-club-event-status-${row}`} />
                  {!event.published && (
                    <span
                      data-testid={`my-club-event-draft-${row}`}
                      className="rounded-full bg-surface-tertiary px-2.5 py-0.5 text-xs text-muted ring-1 ring-inset ring-border"
                    >
                      {t("mine.draftBadge")}
                    </span>
                  )}
                  <Button
                    size="sm"
                    variant={isOpen ? "outline" : "primary"}
                    onPress={() => toggle(event)}
                    data-testid={`my-club-event-toggle-${row}`}
                  >
                    {isOpen ? t("mine.closeLineup") : t("mine.openLineup")}
                  </Button>
                </div>
                {isOpen && (
                  <div className="mt-4 grid grid-cols-[minmax(0,1fr)] gap-4">
                    {/* An event in no series has its squad on the club's first team there (V-1, VA-13). */}
                    {!event.series && (
                      <SquadPanel
                        teamId={event.squad_team_id}
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
                      testIdPrefix={`my-club-lineup-${row}`}
                    />
                    {event.published && (
                      <Link
                        to={`/events/${event.event_id}`}
                        className="text-sm underline underline-offset-2"
                        data-testid={`my-club-event-link-${row}`}
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
  const { t: ts } = useTranslation("space");
  const [params, setParams] = useSearchParams();
  const teams = entry.teams ?? [];
  const open = params.get("team");
  // Story Z-10: *Squads* is the one place for every squad of the club — a stand-alone
  // event's too, which sits on the club's first team there (V-1, VA-13). Once per event.
  const standalone = (entry.events ?? []).filter(
    (event, i, all) => !event.series && all.findIndex((e) => e.squad_team_id === event.squad_team_id) === i,
  );

  const toggle = (teamId: number) =>
    setParams((previous) => {
      const next = new URLSearchParams(previous);
      if (open === String(teamId)) next.delete("team");
      else next.set("team", String(teamId));
      return next;
    });

  if (!teams.length && !standalone.length) {
    return <Empty testId={`my-club-no-teams-${entry.club.id}`}>{t("mine.noTeamsText")}</Empty>;
  }

  return (
    <section data-testid={`my-club-teams-${entry.club.id}`} className="grid grid-cols-[minmax(0,1fr)] gap-3">
      <p className="text-sm text-muted">{t("mine.seriesHint")}</p>
      <ul className="grid grid-cols-[minmax(0,1fr)] gap-3" data-testid="my-club-teams-list">
        {teams.map((team) => {
          const isOpen = open === String(team.team_id);
          return (
            <li
              key={team.team_id}
              data-testid={`my-club-team-${team.team_id}`}
              className="rounded-lg border border-separator bg-surface p-4"
            >
              <div className="flex flex-wrap items-center gap-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">
                    <Link to={`/series/${team.series.id}`} className="underline-offset-2 hover:underline">
                      {team.series.name}
                    </Link>
                  </p>
                  <p className="text-sm text-muted" data-testid={`my-club-team-size-${team.team_id}`}>
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
        {standalone.map((event) => {
          const isOpen = open === String(event.squad_team_id);
          return (
            <li
              key={`event-${event.squad_team_id}`}
              data-testid={`my-club-team-${event.squad_team_id}`}
              className="rounded-lg border border-separator bg-surface p-4"
            >
              <div className="flex flex-wrap items-center gap-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{event.title}</p>
                  <p className="text-sm text-muted">
                    {ts("clubSections.standaloneEvent")} · {eventDates(event)}
                  </p>
                </div>
                <Button
                  size="sm"
                  variant={isOpen ? "outline" : "primary"}
                  onPress={() => toggle(event.squad_team_id)}
                  data-testid={`my-club-team-toggle-${event.squad_team_id}`}
                >
                  {isOpen ? t("mine.closeSquad") : t("mine.openSquad")}
                </Button>
              </div>
              {isOpen && (
                <div className="mt-4">
                  <SquadPanel teamId={event.squad_team_id} title={event.title} readOnly={!entry.may_manage} />
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/** Stories V-5, A-9: the club applies for a series, and sees what became of it (#39) —
 * for the club's organizers, under its squads, where an accepted application then
 * appears as a registration.
 *
 * Offered are the published series of this year and the next the club is in no way part
 * of yet. Waiting and rejected applications stand with their status (and the reason a
 * rejection gave); both can be withdrawn — a rejected one to apply again.
 */
export function ClubApplications({ entry }: { entry: MyClubOut }) {
  const { t } = useTranslation("space");
  const invalidate = useInvalidate();
  const club = entry.club.id;
  const year = new Date().getFullYear();
  const thisYear = useListSeries({ year });
  const nextYear = useListSeries({ year: year + 1 });
  const applications = useListOwnApplications();
  const [seriesId, setSeriesId] = useState("");
  const done = () => {
    setSeriesId("");
    invalidate(getListOwnApplicationsQueryKey(), "/api/clubs/mine", "/api/me/contexts");
  };
  const apply = useSubmitApplication({ mutation: { onSuccess: done } });
  const withdraw = useWithdrawApplication({ mutation: { onSuccess: done } });

  const ours = (applications.data ?? []).filter((a) => a.club.id === club && a.series);
  const taken = new Set([...ours.map((a) => a.series!.id), ...(entry.teams ?? []).map((team) => team.series.id)]);
  const open = [...(thisYear.data ?? []), ...(nextYear.data ?? [])].filter((s) => !taken.has(s.id));
  const pending = ours.filter((a) => a.status !== "accepted");
  const error = apply.error ?? withdraw.error;

  return (
    <Section title={t("clubSections.applicationsTitle")} testId={`my-club-applications-${club}`}>
      <p className="text-sm text-muted">{t("clubSections.applicationsHint")}</p>
      {pending.length > 0 && (
        <ul className="grid grid-cols-[minmax(0,1fr)] gap-2">
          {pending.map((a) => (
            <li key={a.team_id} className="flex flex-wrap items-center gap-2" data-testid={`my-club-application-${a.team_id}`}>
              <span className="min-w-0 flex-1 truncate">{a.series!.name}</span>
              <Badge tone={a.status === "rejected" ? "danger" : "warning"} testId={`my-club-application-${a.team_id}-status`}>
                {t(`clubSections.applicationStatus.${a.status}`)}
              </Badge>
              {a.decision_note && <span className="w-full text-sm text-muted">{a.decision_note}</span>}
              <Button
                size="sm"
                variant="ghost"
                onPress={() => withdraw.mutate({ teamId: a.team_id })}
                data-testid={`my-club-application-${a.team_id}-withdraw`}
              >
                {t("clubSections.withdraw")}
              </Button>
            </li>
          ))}
        </ul>
      )}
      {open.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          <Select
            size="inline"
            value={seriesId}
            onChange={(e) => setSeriesId(e.target.value)}
            aria-label={t("clubSections.applyFor")}
            testId={`my-club-apply-series-${club}`}
          >
            <option value="">{t("clubSections.applyFor")}</option>
            {open.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </Select>
          <Button
            size="sm"
            isDisabled={!seriesId || apply.isPending}
            onPress={() => apply.mutate({ data: { club_id: club, series_id: Number(seriesId) } })}
            data-testid={`my-club-apply-${club}`}
          >
            {t("clubSections.apply")}
          </Button>
        </div>
      ) : (
        <p className="text-sm text-muted" data-testid={`my-club-apply-none-${club}`}>
          {t("clubSections.applyNone")}
        </p>
      )}
      {error && <ErrorMessage text={errorText(error)} testId={`my-club-applications-${club}-error`} />}
    </Section>
  );
}

/** Story Z-10: the events the club hosts, each opening its own context — where it is
 * organized (a hosted event is not edited here) — and *+ New event*, the event wizard,
 * where a club's organizer creates one outside a series (VA-6).
 *
 * The server narrows the organizers' event list to this host (`host_club_id`, Story A-13).
 */
export function ClubHosting({ club }: { club: { id: number; name: string; short_name?: string | null } }) {
  const { t } = useTranslation("space");
  const events = useAsync(useListAllEvents({ host_club_id: club.id, limit: WHOLE_LIST }));
  return (
    <Section
      testId={`my-club-hosting-${club.id}`}
      action={<AddButton label={t("clubSections.newEvent")} to="/me/event/new" testId="my-club-hosting-new-event" />}
    >
      <p className="text-sm text-muted">{t("clubSections.hostingHint")}</p>
      <Async
        state={events}
        testId="my-club-hosting"
        empty={t("clubSections.noHosted")}
        isEmpty={(page) => !page.items.length}
      >
        {(page) => <EventLinks events={page.items} testId="my-club-hosted" />}
      </Async>
    </Section>
  );
}

/** Story V-14: whose waivers are in — one block per competition the club is in, the
 * missing first, with the status the sailor's own page and the check-in list show. */
export function ClubWaivers({ clubId }: { clubId: number }) {
  const { t } = useTranslation("space");
  const list = useAsync(useClubWaivers(clubId));
  return (
    <Async
      state={list}
      testId="my-club-waivers"
      empty={t("clubWaivers.none")}
      isEmpty={(data) => !data.competitions.length}
    >
      {(data) => (
        <ul className="grid grid-cols-[minmax(0,1fr)] gap-3" data-testid="my-club-waivers-list">
          {data.competitions.map((block) => (
            <li
              key={`${block.scope}-${block.scope_id}`}
              data-testid={`my-club-waivers-${block.scope}-${block.scope_id}`}
              className="rounded-lg border border-separator bg-surface p-4"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                <Link
                  to={block.scope === "series" ? `/series/${block.scope_id}` : `/events/${block.scope_id}`}
                  className="font-medium underline-offset-2 hover:underline"
                >
                  {block.name}
                </Link>
                <span
                  className={`text-sm ${block.outstanding ? "font-medium text-warning-soft-foreground" : "text-success-soft-foreground"}`}
                  data-testid={`my-club-waivers-${block.scope}-${block.scope_id}-summary`}
                >
                  {t("clubWaivers.summary", { cleared: block.cleared, total: block.people.length })}
                </span>
              </div>
              {block.people.length ? (
                <ul className="mt-3 flex flex-col divide-y divide-separator text-sm">
                  {block.people.map((row) => (
                    <li
                      key={row.person_id}
                      className="flex flex-wrap items-baseline justify-between gap-x-3 py-1.5"
                      data-testid={`my-club-waiver-row-${block.scope}-${block.scope_id}-${row.person_id}`}
                      data-status={row.status}
                    >
                      <span>
                        <WaiverName person={row} />
                      </span>
                      <WaiverStatus status={row.status} />
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-sm text-muted">{t("clubWaivers.nobody")}</p>
              )}
            </li>
          ))}
        </ul>
      )}
    </Async>
  );
}
