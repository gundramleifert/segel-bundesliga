import { Card } from "@heroui/react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { api, type ClubDetail, type ClubMemberSummary, type Member } from "../api/client";
import { useApi, useAccount } from "../api/useApi";
import { ErrorMessage, Loading, Empty, StatusBadge } from "../components/Blocks";
import { locationText, roleText, eventDates } from "../lib/format";

type ClubEvent = NonNullable<NonNullable<ClubDetail["teams"]>[number]["events"]>[number];

/** B-7: The club page — crest, description, and the club's teams for the season. */
export function Club() {
  const { t } = useTranslation("club");
  const { id = "" } = useParams();
  const { account } = useAccount();
  const { data, error, loading } = useApi(["club", id], (signal) =>
    api.club(Number(id), signal),
  );

  if (loading) return <Loading text={t("loading")} testId="club-loading" />;
  if (error) return <ErrorMessage text={error} testId="club-error" />;
  if (!data) return null;

  return (
    <>
      <header data-testid="club-header" className="mb-8 flex flex-wrap items-start gap-5">
        {data.logo_url ? (
          <img
            src={data.logo_url}
            alt=""
            className="size-20 shrink-0 rounded-xl bg-white object-contain p-2 ring-1 ring-slate-200"
          />
        ) : (
          <span
            aria-hidden
            className="grid size-20 shrink-0 place-items-center rounded-xl bg-brand-600 text-lg font-bold text-white"
          >
            {data.short_name.slice(0, 4)}
          </span>
        )}

        <div className="min-w-0 flex-1">
          <h1 data-testid="club-title" className="text-2xl font-semibold tracking-tight sm:text-3xl">
            {data.name}
          </h1>
          <p className="mt-1 text-slate-600">
            {[data.short_name, data.city].filter(Boolean).join(" · ")}
          </p>
          {data.website && (
            <a
              href={data.website}
              target="_blank"
              rel="noreferrer noopener"
              data-testid="club-website-link"
              className="mt-1 inline-block text-sm text-brand-700 underline-offset-2 hover:underline"
            >
              {t("website")}
            </a>
          )}
        </div>
      </header>

      {data.description && (
        <p data-testid="club-description" className="mb-8 max-w-2xl text-slate-700">
          {data.description}
        </p>
      )}

      <h2 className="mb-4 text-lg font-semibold">{t("teams")}</h2>

      {data.teams?.length ? (
        <div data-testid="club-teams-section" className="space-y-6">
          {data.teams.map((team) => (
            <Card key={team.id} data-testid={`club-team-card-${team.id}`}>
              <Card.Header>
                <Card.Title className="text-base">{team.series.name}</Card.Title>
                <Card.Description>
                  {t("stats", { count: team.members?.length ?? 0, events: team.events?.length ?? 0 })}
                </Card.Description>
              </Card.Header>
              <Card.Content>
                <div className="grid gap-6 lg:grid-cols-2">
                  <section>
                    <h3 className="mb-2 text-sm font-medium text-slate-500">
                      {t("squad")}
                    </h3>
                    <Squad members={team.members ?? []} />
                  </section>
                  <section>
                    <h3 className="mb-2 text-sm font-medium text-slate-500">{t("events")}</h3>
                    <Matchdays entries={team.events ?? []} />
                  </section>
                </div>
              </Card.Content>
            </Card>
          ))}
        </div>
      ) : (
        <Empty testId="club-teams-empty">{t("unassigned")}</Empty>
      )}

      {data.events?.length ? (
        <section data-testid="club-own-events-section" className="mt-8">
          <h2 className="mb-2 text-lg font-semibold">{t("ownEvents")}</h2>
          <p className="mb-3 text-sm text-slate-600">
            {t("ownEvents_desc")}
          </p>
          <Card>
            <Card.Content>
              <Matchdays entries={data.events} />
            </Card.Content>
          </Card>
        </section>
      ) : null}

      {account && <Members clubId={Number(id)} />}
    </>
  );
}

/** The club's own membership roster (Story V-10) — rendered only for a signed-in active
 * member of *this* club, or staff. Anyone else gets 403 from the endpoint; since a guest
 * or another club's member landing on this page is the normal case, not a failure, that
 * simply hides the section instead of showing an error banner. */
function Members({ clubId }: { clubId: number }) {
  const { t } = useTranslation("club");
  const { data, error, loading } = useApi(["clubMembers", clubId], (signal) =>
    api.clubMembers(clubId, signal),
  );

  if (loading || error || !data?.length) return null;

  return (
    <section data-testid="club-members-section" className="mt-8">
      <h2 className="mb-2 text-lg font-semibold">{t("members")}</h2>
      <Card>
        <Card.Content>
          <ul className="divide-y divide-slate-100 text-sm">
            {data.map((member: ClubMemberSummary) => (
              <li
                key={member.user_id}
                data-testid={`club-member-row-${member.user_id}`}
                className="flex items-center justify-between gap-3 py-2"
              >
                <span>{member.display_name}</span>
                {member.organizer && (
                  <span className="shrink-0 text-slate-500">{t("organizer")}</span>
                )}
              </li>
            ))}
          </ul>
        </Card.Content>
      </Card>
    </section>
  );
}

/** Matchdays of a team, with crew members sailing for the club. */
function Matchdays({ entries }: { entries: ClubEvent[] }) {
  const { t } = useTranslation("club");

  if (!entries.length) {
    return (
      <p data-testid="club-events-empty" className="text-sm text-slate-500">
        {t("events_empty")}
      </p>
    );
  }

  return (
    <ul className="divide-y divide-slate-100 text-sm">
      {entries.map(({ event, crew }) => (
        <li key={event.id} data-testid={`club-event-row-${event.id}`} className="py-2">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <Link
              to={`/events/${event.id}`}
              data-testid={`club-event-link-${event.id}`}
              className="font-medium underline-offset-2 hover:underline"
            >
              {event.title}
            </Link>
            <StatusBadge status={event.status} />
          </div>
          <p className="text-slate-500">
            {locationText(event)} · {eventDates(event)}
          </p>
          <p className="mt-0.5 text-slate-600">
            {crew?.length ? (
              crew.map((member, index) => (
                <span key={member.id}>
                  {index > 0 && ", "}
                  <Link
                    to={`/sailors/${member.id}`}
                    data-testid={`club-crew-link-${event.id}-${member.id}`}
                    className="underline-offset-2 hover:underline"
                  >
                    {member.first_name} {member.last_name}
                  </Link>
                </span>
              ))
            ) : (
              <span className="text-slate-400">{t("crew_empty")}</span>
            )}
          </p>
        </li>
      ))}
    </ul>
  );
}

function Squad({ members }: { members: Member[] }) {
  const { t } = useTranslation("club");

  if (!members.length)
    return (
      <p data-testid="club-squad-empty" className="text-sm text-slate-500">
        {t("squad_empty")}
      </p>
    );

  return (
    <ul className="divide-y divide-slate-100 text-sm">
      {members.map((member) => (
        <li
          key={member.id}
          data-testid={`club-squad-row-${member.id}`}
          className="flex items-center justify-between gap-3 py-2"
        >
          <Link
            to={`/sailors/${member.id}`}
            data-testid={`club-squad-link-${member.id}`}
            className="font-medium underline-offset-2 hover:underline"
          >
            {member.first_name} {member.last_name}
          </Link>
          <span className="shrink-0 text-slate-500">{roleText(member.role)}</span>
        </li>
      ))}
    </ul>
  );
}
