import { useNavigate } from "react-router-dom";

import { useMyClubs } from "../../api/generated/sbl";
import { Relation } from "../../api/types";
import { useAccount } from "../../api/useApi";
import { Loading } from "../../components/Blocks";
import { GuardiansPanel } from "../../components/GuardiansPanel";
import { Stack } from "../../components/Layouts";
import { ClubDpa } from "./ClubDpa";
import { ClubApplications, ClubEvents, ClubHosting, ClubTeams, ClubWaivers } from "./ClubSections";
import { ClubPageSection, ClubPeopleSection } from "./ClubPeople";
import { ClubBankAccount, ClubDecideClaims, ClubPaymentRuns } from "./Money";
import { ClaimsTab } from "./Papers";
import { type WorkspaceSection } from "./Workspace";
import { ContextFrame } from "./ContextFrame";

/** `/me/club/:id` — Story Z-10: the club's sections, as `lib/workspace.ts` declares them —
 * People (people, minors & guardians, waivers), Racing (squads, events & crews,
 * hosting), Money (my claims, decide claims, payment runs, bank account) and the club page.
 *
 * Who sees what is the frame's business, from the relations the model gives me on the club
 * — the site's admin opening a club reached through the league office arrives as its
 * `admin`. A section's panel decides only *how much* it offers (read-only for a member).
 */
export function ClubPage() {
  const { account } = useAccount();
  const navigate = useNavigate();
  // Squads and crews come from `GET /api/clubs/mine` (Story V-12): the club's entries and
  // registrations. It answers "mine" — member or organizer — so a club reached through the
  // league office is not in it, and those two sections are left out there rather than
  // drawn empty; the league office has its own squad screen.
  const clubs = useMyClubs({ query: { enabled: Boolean(account) } });
  // Until it is here, a section in the address would look like one I do not have, and the
  // frame would send me away from it.
  if (account && clubs.isPending) return <Loading testId="me-context-loading" />;

  return (
    <ContextFrame
      kind="club"
      publicPath={(c) => `/clubs/${c.id}`}
      sections={(c) => {
        const entry = clubs.data?.find((e) => e.club.id === c.id);
        const mayAdmin = c.relations.includes(Relation.admin);
        const racing: WorkspaceSection[] = entry
          ? [
              {
                key: "squads",
                render: () => (
                  <Stack>
                    <ClubTeams entry={entry} />
                    {entry.may_manage && <ClubApplications entry={entry} />}
                  </Stack>
                ),
              },
              {
                key: "crews",
                render: () => <ClubEvents entry={entry} />,
              },
            ]
          : [];
        return [
          {
            // One list where *Members* and *Sailors* were two (#45).
            key: "people",
            render: () => (
              <Stack>
                {mayAdmin && <ClubDpa clubId={c.id} />}
                <ClubPeopleSection
                  clubId={c.id}
                  mayAdmin={mayAdmin}
                  mayOrganize={mayAdmin || c.relations.includes(Relation.manager)}
                  onLeft={() => navigate("/me")}
                />
              </Stack>
            ),
          },
          {
            // Whose parent may accept a young sailor's waiver (Story V-13).
            key: "minors",
            render: () => <GuardiansPanel clubId={c.id} />,
          },
          {
            key: "waivers",
            render: () => <ClubWaivers clubId={c.id} />,
          },
          ...racing,
          {
            key: "hosting",
            render: () => <ClubHosting club={{ id: c.id, name: c.name, short_name: c.short_name }} />,
          },
          {
            key: "my-claims",
            render: () => <ClaimsTab target={{ kind: "club", id: c.id }} />,
          },
          {
            key: "decide-claims",
            render: () => <ClubDecideClaims clubId={c.id} />,
          },
          {
            key: "payment-runs",
            render: () => <ClubPaymentRuns clubId={c.id} />,
          },
          {
            key: "bank-account",
            render: () => <ClubBankAccount clubId={c.id} />,
          },
          {
            key: "club-page",
            render: () => <ClubPageSection clubId={c.id} />,
          },
        ];
      }}
    />
  );
}
