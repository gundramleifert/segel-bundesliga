import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { useMyClubs } from "../api/generated/sbl";
import type { MyClubOut } from "../api/generated/model/myClubOut";
import { useAsync, useAccount } from "../api/useApi";
import { ErrorMessage, Loading, Empty, PageHeader } from "../components/Blocks";
import { SquadPanel } from "../components/SquadPanel";
import { TabbedView, type TabDef } from "../components/Tabs";

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
        subtitle={t("mine.subtitle", { count: entries.length })}
        testId="my-club-header"
      />
      {/* One club is the normal case and needs no chooser; several happen, because
          `club_manager` is granted per club and a person can hold it for more than one. */}
      {entries.length === 1 ? (
        <ClubTeams entry={entries[0]} />
      ) : (
        <TabbedView
          tabs={entries.map(
            (entry): TabDef<string> => ({
              key: String(entry.club.id),
              label: entry.club.short_name || entry.club.name,
              render: () => <ClubTeams entry={entry} />,
            }),
          )}
          param="club"
          testIdPrefix="my-club"
          label={t("mine.clubTabsLabel")}
          className="grid grid-cols-[minmax(0,1fr)]"
        />
      )}
    </>
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
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
      <p data-testid={`my-club-role-${entry.club.id}`} className="text-sm text-slate-600">
        <Link to={`/clubs/${entry.club.id}`} className="underline underline-offset-2">
          {entry.club.name}
        </Link>
        {" · "}
        {entry.may_manage ? t("mine.roleOrganizer") : t("mine.roleMember")}
      </p>

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
    </div>
  );
}
