import { Link } from "react-router-dom";
import { Card } from "@heroui/react";
import { useTranslation } from "react-i18next";
import { Tip } from "../../../components/Tip";
import { useGetEventCrew } from "../../../api/generated/sbl";
import type { TeamCrew } from "../../../api/types";
import { useAsync } from "../../../api/useApi";
import { Async } from "../../../components/Async";
import { CardGrid } from "../../../components/Layouts";
import { SailorName } from "../../../components/SailorName";
import { roleText } from "../../../lib/format";

/** B-12: who sails for each team at this matchday.
 *
 *  Public with no login, and no name is ever hidden: whoever is entered here is already on
 *  the pairing list, the results and the standings. Club *membership* is the private thing
 *  (V-10), and this is not that.
 *
 *  Deliberately **not** a `LinkCard`, which is one anchor around the whole card: each name
 *  is its own link to a sailor page, and an anchor inside an anchor is invalid HTML that
 *  browsers silently unnest. The club link therefore sits in the card header on its own. */
export function Crew({ eventId }: { eventId: number }) {
  const { t } = useTranslation("matchday");
  const crew = useAsync(useGetEventCrew(eventId));

  return (
    <Async
      state={crew}
      testId="matchday-crew"
      loadingText={t("crewLoading")}
      empty={t("noTeamsEntered")}
      isEmpty={(data) => !data.teams?.length}
    >
      {(data) => (
        <CardGrid columns={3} testId="matchday-crew-list">
          {(data.teams ?? []).map((entry) => (
            <li key={entry.team.id} data-testid={`matchday-crew-team-${entry.team.id}`}>
              <TeamCrewCard entry={entry} />
            </li>
          ))}
        </CardGrid>
      )}
    </Async>
  );
}

function TeamCrewCard({ entry }: { entry: TeamCrew }) {
  const { t } = useTranslation("matchday");
  const { team, crew } = entry;

  return (
    <Card className="h-full">
      <Card.Header>
        <div className="flex items-start gap-3">
          {team.club.logo_url && (
            <img src={team.club.logo_url} alt="" className="size-8 shrink-0 object-contain" />
          )}
          {/* `min-w-0` so a long club name truncates instead of widening the grid track
              and zooming the page out on a phone (Story A-10). */}
          <div className="min-w-0 flex-1">
            <Card.Title className="truncate text-base">
              <Tip text={team.club.name}>
                <Link
                  to={`/clubs/${team.club.id}`}
                  data-testid={`matchday-crew-club-link-${team.id}`}
                  className="underline-offset-2 hover:underline"
                >
                  {team.name}
                </Link>
              </Tip>
            </Card.Title>
            {team.club.city && <Card.Description>{team.club.city}</Card.Description>}
          </div>
        </div>
      </Card.Header>
      <Card.Content>
        {crew?.length ? (
          <ul className="divide-y divide-slate-100 text-sm">
            {crew.map((member) => (
              <li
                key={member.id}
                data-testid={`matchday-crew-row-${team.id}-${member.id}`}
                className="flex items-center justify-between gap-3 py-2"
              >
                <SailorName
                  member={member}
                  testId={`matchday-crew-sailor-link-${team.id}-${member.id}`}
                  className="truncate font-medium"
                />
                <span className="shrink-0 text-slate-500">{roleText(member.role)}</span>
              </li>
            ))}
          </ul>
        ) : (
          /* Entered but nobody named yet — said out loud, because an empty card reads as
             a page that failed to load. */
          <p
            data-testid={`matchday-crew-unnamed-${team.id}`}
            className="text-sm text-slate-400"
          >
            {t("crewNotNamed")}
          </p>
        )}
      </Card.Content>
    </Card>
  );
}
