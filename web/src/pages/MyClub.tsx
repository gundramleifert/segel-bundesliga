import { Link, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { Stack } from "../components/Layouts";
import { useMyClubs } from "../api/generated/sbl";
import type { MyClubOut } from "../api/generated/model/myClubOut";
import { useAsync, useAccount } from "../api/useApi";
import { ErrorMessage, Loading, Empty, PageHeader } from "../components/Blocks";
import { SquadPanel } from "../components/SquadPanel";
import { TabbedView, type TabDef } from "../components/Tabs";
import { Field } from "../components/Form";
import { INPUT_CLASS } from "../lib/admin";

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
      <ClubChooser entries={entries} />
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
 * below states it. `?club=` keeps whichever was picked, so the page can be linked and
 * survives a reload.
 */
function ClubChooser({ entries }: { entries: MyClubOut[] }) {
  const { t } = useTranslation("club");
  const [params, setParams] = useSearchParams();

  const requested = params.get("club");
  const entry = entries.find((e) => String(e.club.id) === requested) ?? entries[0];

  const roleOf = (item: MyClubOut) =>
    item.may_manage ? t("mine.roleOrganizer") : t("mine.roleMember");

  return (
    <Stack gap={6}>
      <div className="flex flex-wrap items-center gap-3">
        {entries.length > 1 ? (
          <Field label={t("mine.clubLabel")}>
            <select
              className={INPUT_CLASS}
              value={entry.club.id}
              onChange={(e) =>
                setParams((previous) => {
                  const next = new URLSearchParams(previous);
                  next.set("club", e.target.value);
                  // The chosen series belongs to the club that was open; keeping it would
                  // point at a team of the club just left.
                  next.delete("team");
                  return next;
                })
              }
              data-testid="my-club-select"
            >
              {entries.map((item) => (
                <option key={item.club.id} value={item.club.id}>
                  {item.club.name} — {roleOf(item)}
                </option>
              ))}
            </select>
          </Field>
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
    </Stack>
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
