import { Card } from "@heroui/react";
import { useTranslation } from "react-i18next";

import { Seitenkopf } from "../components/Bausteine";

const ROLE_COLUMNS = ["admin", "editor", "raceOfficer", "clubManager"] as const;
type RoleColumn = (typeof ROLE_COLUMNS)[number];

/** What a role can do in one area: full access, none, only for its own club, or a
 *  narrower "may create, not maintain" case (hosting club creating its own Event). */
type Access = "yes" | "no" | "own" | "hostsCreate";

interface AreaRow {
  key: string;
  access: Record<RoleColumn, Access>;
}

/** Source of truth: the permissions table in CLAUDE.md. Two of its rows ("Create and
 *  maintain Events" and "Create Event: additionally club_manager if own club hosts")
 *  describe the same area from two angles and are merged into one row here. */
const AREAS: AreaRow[] = [
  {
    key: "createClubsEnroll",
    access: { admin: "yes", editor: "yes", raceOfficer: "no", clubManager: "no" },
  },
  {
    key: "createSeries",
    access: { admin: "yes", editor: "no", raceOfficer: "no", clubManager: "no" },
  },
  {
    key: "maintainEvents",
    access: { admin: "yes", editor: "yes", raceOfficer: "yes", clubManager: "hostsCreate" },
  },
  {
    key: "pairingAccountsRoles",
    access: { admin: "yes", editor: "no", raceOfficer: "no", clubManager: "no" },
  },
  {
    key: "enterResults",
    access: { admin: "yes", editor: "no", raceOfficer: "yes", clubManager: "no" },
  },
  {
    key: "assignUserToClub",
    access: { admin: "yes", editor: "no", raceOfficer: "no", clubManager: "own" },
  },
  {
    key: "registerParticipants",
    access: { admin: "yes", editor: "no", raceOfficer: "no", clubManager: "own" },
  },
  {
    key: "maintainSailors",
    access: { admin: "yes", editor: "yes", raceOfficer: "no", clubManager: "own" },
  },
  {
    key: "registerSquad",
    access: { admin: "yes", editor: "no", raceOfficer: "no", clubManager: "own" },
  },
  {
    key: "acceptClubMembers",
    access: { admin: "yes", editor: "no", raceOfficer: "no", clubManager: "own" },
  },
];

const HOWTO_KEYS = [
  "createSeries",
  "createEvent",
  "createClub",
  "createAccount",
  "registerSeries",
  "registerEvent",
  "joinClub",
] as const;

/** New help page: the roles matrix plus step-by-step instructions for the common admin
 *  and registration tasks. Public — everyone, including guests, can read it. */
export function Help() {
  const { t } = useTranslation("help");

  return (
    <>
      <Seitenkopf titel={t("title")} unterzeile={t("intro")} testId="help-header" />

      <section data-testid="help-roles-section" className="mb-10">
        <h2 className="mb-1 text-lg font-semibold">{t("roles.title")}</h2>
        <p className="mb-3 text-sm text-slate-600">{t("roles.intro")}</p>

        {/* Scrolls horizontally inside its own box on narrow screens, matching the
            approach TabellenRahmen uses for results tables — the page itself never
            scrolls sideways. */}
        <div className="tabelle-scroll rounded-xl border border-slate-200 bg-white">
          <table data-testid="help-roles-table" className="w-full min-w-[640px] border-collapse text-sm">
            <thead className="tabelle-kopf">
              <tr className="border-b border-slate-200 bg-slate-50 text-left">
                <th scope="col" className="px-4 py-2.5 font-medium text-slate-700">
                  {t("roles.areaHeader")}
                </th>
                {ROLE_COLUMNS.map((role) => (
                  <th key={role} scope="col" className="px-4 py-2.5 font-medium text-slate-700">
                    {t(`roles.columns.${role}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {AREAS.map((area) => (
                <tr key={area.key} data-testid={`help-roles-row-${area.key}`}>
                  <th scope="row" className="px-4 py-2.5 text-left font-normal text-slate-800">
                    {t(`roles.areas.${area.key}`)}
                  </th>
                  {ROLE_COLUMNS.map((role) => (
                    <td key={role} className="px-4 py-2.5 text-slate-600">
                      <AccessCell value={area.access[role]} testId={`help-access-cell-${area.key}-${role}`} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-sm text-slate-600">{t("roles.guestNote")}</p>
      </section>

      <section data-testid="help-howto-section" className="grid gap-6">
        <h2 className="text-lg font-semibold">{t("howTo.title")}</h2>
        {HOWTO_KEYS.map((key) => (
          <Card key={key} data-testid={`help-howto-card-${key}`}>
            <Card.Header>
              <Card.Title>{t(`howTo.${key}.title`)}</Card.Title>
              <Card.Description>{t(`howTo.${key}.who`)}</Card.Description>
            </Card.Header>
            <Card.Content>
              <HowToSteps howToKey={key} />
              <p className="mt-3 text-sm text-slate-500">{t(`howTo.${key}.note`)}</p>
            </Card.Content>
          </Card>
        ))}
      </section>
    </>
  );
}

function AccessCell({ value, testId }: { value: Access; testId: string }) {
  const { t } = useTranslation("help");

  if (value === "yes") {
    return (
      <span data-testid={testId} className="text-marke-700">
        <span aria-hidden>✓</span>
        <span className="sr-only"> {t("roles.cells.yes")}</span>
      </span>
    );
  }
  if (value === "no") {
    return (
      <span aria-hidden data-testid={testId} className="text-slate-300">
        {t("roles.cells.no")}
      </span>
    );
  }
  return <span data-testid={testId}>{t(`roles.cells.${value}`)}</span>;
}

function HowToSteps({ howToKey }: { howToKey: (typeof HOWTO_KEYS)[number] }) {
  const { t } = useTranslation("help");
  // The steps arrays live in help.json; there's no typed resource declaration in this
  // project, so react-i18next can't infer the array shape from the key alone.
  const steps = t(`howTo.${howToKey}.steps`, { returnObjects: true }) as string[];

  return (
    <ol className="list-decimal space-y-1.5 pl-5 text-sm text-slate-700">
      {steps.map((step) => (
        <li key={step}>{step}</li>
      ))}
    </ol>
  );
}
