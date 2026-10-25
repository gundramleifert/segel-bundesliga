import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { useMyClubs } from "../../api/generated/sbl";
import { useAccount } from "../../api/useApi";
import { Loading } from "../../components/Blocks";
import { ClubMembersPanel } from "../../components/ClubMembersPanel";
import { ClubEvents, ClubTeams, ClubWaivers } from "./ClubSections";
import { ClubMoneyTab } from "./Money";
import { ClaimsTab } from "./Papers";
import { type WorkspaceSection } from "./Workspace";
import { ContextFrame, Door } from "./ContextFrame";


/** `/me/club/:id` — members, matchdays and squads, my claims, the club's money. */
export function ClubPage() {
  const { t } = useTranslation("space");
  const { account } = useAccount();
  const navigate = useNavigate();
  // The club screen's own data (Story V-12): members, entries, registrations. A club's
  // treasurer who is neither member nor organizer is not in it, and gets the money only.
  const clubs = useMyClubs({ query: { enabled: Boolean(account) } });
  // The club's own sections come from that answer: until it is here, a section in the
  // address would look like one I do not have, and the frame would send me away from it.
  if (account && clubs.isPending) return <Loading testId="me-context-loading" />;

  return (
    <ContextFrame
      kind="club"
      publicPath={(c) => `/clubs/${c.id}`}
      sections={(c) => {
        const entry = clubs.data?.find((e) => e.club.id === c.id);
        const club: WorkspaceSection[] = entry
          ? [
              { key: "members", label: t("context.tabs.members"), render: () => <ClubMembersPanel entry={entry} onLeft={() => navigate("/me")} /> },
              {
                key: "crews",
                label: t("context.tabs.crews"),
                needs: ["crew_missing"],
                render: () => <ClubEvents entry={entry} />,
              },
              {
                key: "squads",
                label: t("context.tabs.squadsOnly"),
                needs: ["squad_below_min"],
                render: () => <ClubTeams entry={entry} />,
              },
            ]
          : [];
        return [
          ...club,
          {
            key: "waivers",
            label: t("context.tabs.waivers"),
            needs: ["crew_waiver_missing"],
            render: () => <ClubWaivers clubId={c.id} />,
          },
          {
            key: "my-claims",
            label: t("context.tabs.myClaims"),
            needs: ["claim_rejected"],
            render: () => <ClaimsTab target={{ kind: "club", id: c.id }} />,
          },
          {
            key: "decide-claims",
            label: t("context.tabs.money"),
            needs: ["claims"],
            render: () => <ClubMoneyTab clubId={c.id} clubName={c.name} />,
          },
          {
            key: "hosting",
            label: t("context.tabs.hosting"),
            render: () => (
              <Door
                text={t("context.organizeHosted")}
                to="/admin?tab=events"
                label={t("context.organizeLink")}
                testId="me-club-hosting"
              />
            ),
          },
        ];
      }}
    />
  );
}
