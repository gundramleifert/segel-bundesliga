import { Card } from "@heroui/react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { api, type ClubDetail, type ClubMemberSummary, type Member } from "../api/client";
import { useApi, useKonto } from "../api/useApi";
import { Fehler, Laden, Leer, StatusMarke } from "../components/Bausteine";
import { ortText, rolle, zeitraum } from "../lib/format";

type ClubEvent = NonNullable<NonNullable<ClubDetail["teams"]>[number]["events"]>[number];

/** B-7: The club page — crest, description, and the club's teams for the season. */
export function Club() {
  const { t } = useTranslation("club");
  const { id = "" } = useParams();
  const { konto } = useKonto();
  const { data, error, loading } = useApi(["club", id], (signal) =>
    api.club(Number(id), signal),
  );

  if (loading) return <Laden text={t("loading")} />;
  if (error) return <Fehler text={error} />;
  if (!data) return null;

  return (
    <>
      <header className="mb-8 flex flex-wrap items-start gap-5">
        {data.logo_url ? (
          <img
            src={data.logo_url}
            alt=""
            className="size-20 shrink-0 rounded-xl bg-white object-contain p-2 ring-1 ring-slate-200"
          />
        ) : (
          <span
            aria-hidden
            className="grid size-20 shrink-0 place-items-center rounded-xl bg-marke-600 text-lg font-bold text-white"
          >
            {data.short_name.slice(0, 4)}
          </span>
        )}

        <div className="min-w-0 flex-1">
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{data.name}</h1>
          <p className="mt-1 text-slate-600">
            {[data.short_name, data.city].filter(Boolean).join(" · ")}
          </p>
          {data.website && (
            <a
              href={data.website}
              target="_blank"
              rel="noreferrer noopener"
              className="mt-1 inline-block text-sm text-marke-700 underline-offset-2 hover:underline"
            >
              {t("website")}
            </a>
          )}
        </div>
      </header>

      {data.description && (
        <p className="mb-8 max-w-2xl text-slate-700">{data.description}</p>
      )}

      <h2 className="mb-4 text-lg font-semibold">{t("teams")}</h2>

      {data.teams?.length ? (
        <div className="space-y-6">
          {data.teams.map((mannschaft) => (
            <Card key={mannschaft.id}>
              <Card.Header>
                <Card.Title className="text-base">{mannschaft.series.name}</Card.Title>
                <Card.Description>
                  {t("stats", { count: mannschaft.members?.length ?? 0, events: mannschaft.events?.length ?? 0 })}
                </Card.Description>
              </Card.Header>
              <Card.Content>
                <div className="grid gap-6 lg:grid-cols-2">
                  <section>
                    <h3 className="mb-2 text-sm font-medium text-slate-500">
                      {t("squad")}
                    </h3>
                    <Kader mitglieder={mannschaft.members ?? []} />
                  </section>
                  <section>
                    <h3 className="mb-2 text-sm font-medium text-slate-500">{t("events")}</h3>
                    <Spieltage eintraege={mannschaft.events ?? []} />
                  </section>
                </div>
              </Card.Content>
            </Card>
          ))}
        </div>
      ) : (
        <Leer>{t("unassigned")}</Leer>
      )}

      {data.events?.length ? (
        <section className="mt-8">
          <h2 className="mb-2 text-lg font-semibold">{t("ownEvents")}</h2>
          <p className="mb-3 text-sm text-slate-600">
            {t("ownEvents_desc")}
          </p>
          <Card>
            <Card.Content>
              <Spieltage eintraege={data.events} />
            </Card.Content>
          </Card>
        </section>
      ) : null}

      {konto && <Mitglieder clubId={Number(id)} />}
    </>
  );
}

/** The club's own membership roster (Story V-10) — rendered only for a signed-in active
 * member of *this* club, or staff. Anyone else gets 403 from the endpoint; since a guest
 * or another club's member landing on this page is the normal case, not a failure, that
 * simply hides the section instead of showing an error banner. */
function Mitglieder({ clubId }: { clubId: number }) {
  const { t } = useTranslation("club");
  const { data, error, loading } = useApi(["clubMembers", clubId], (signal) =>
    api.clubMembers(clubId, signal),
  );

  if (loading || error || !data?.length) return null;

  return (
    <section className="mt-8">
      <h2 className="mb-2 text-lg font-semibold">{t("members")}</h2>
      <Card>
        <Card.Content>
          <ul className="divide-y divide-slate-100 text-sm">
            {data.map((mitglied: ClubMemberSummary) => (
              <li
                key={mitglied.user_id}
                className="flex items-center justify-between gap-3 py-2"
              >
                <span>{mitglied.display_name}</span>
                {mitglied.organizer && (
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
function Spieltage({ eintraege }: { eintraege: ClubEvent[] }) {
  const { t } = useTranslation("club");

  if (!eintraege.length) {
    return <p className="text-sm text-slate-500">{t("events_empty")}</p>;
  }

  return (
    <ul className="divide-y divide-slate-100 text-sm">
      {eintraege.map(({ event, crew }) => (
        <li key={event.id} className="py-2">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <Link
              to={`/events/${event.id}`}
              className="font-medium underline-offset-2 hover:underline"
            >
              {event.title}
            </Link>
            <StatusMarke status={event.status} />
          </div>
          <p className="text-slate-500">
            {ortText(event)} · {zeitraum(event.starts_on, event.ends_on)}
          </p>
          <p className="mt-0.5 text-slate-600">
            {crew?.length ? (
              crew.map((mitglied, index) => (
                <span key={mitglied.id}>
                  {index > 0 && ", "}
                  <Link
                    to={`/sailors/${mitglied.id}`}
                    className="underline-offset-2 hover:underline"
                  >
                    {mitglied.first_name} {mitglied.last_name}
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

function Kader({ mitglieder }: { mitglieder: Member[] }) {
  const { t } = useTranslation("club");

  if (!mitglieder.length) return <p className="text-sm text-slate-500">{t("squad_empty")}</p>;

  return (
    <ul className="divide-y divide-slate-100 text-sm">
      {mitglieder.map((mitglied) => (
        <li key={mitglied.id} className="flex items-center justify-between gap-3 py-2">
          <Link
            to={`/sailors/${mitglied.id}`}
            className="font-medium underline-offset-2 hover:underline"
          >
            {mitglied.first_name} {mitglied.last_name}
          </Link>
          <span className="shrink-0 text-slate-500">{rolle(mitglied.role)}</span>
        </li>
      ))}
    </ul>
  );
}
