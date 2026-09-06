import { Card } from "@heroui/react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { api, type Account as AccountData } from "../api/client";
import { getToken, onTokenChange } from "../api/session";
import { Laden, Seitenkopf } from "../components/Bausteine";

/** Roles and what permissions they grant. Without this page, role switching would be invisible
 *  as long as there are no protected areas yet. */
const RECHTE: { rolle: string; key: string }[] = [
  { rolle: "admin", key: "roles.admin" },
  { rolle: "admin", key: "roles.admin_pairing" },
  { rolle: "editor", key: "roles.editor" },
  { rolle: "race_officer", key: "roles.race_officer" },
  { rolle: "club_manager", key: "roles.club_manager" },
  { rolle: "club_manager", key: "roles.club_manager_squad" },
];

export function Account() {
  const { t } = useTranslation("account");
  const [konto, setKonto] = useState<AccountData | null>(null);
  const [fehler, setFehler] = useState<string | null>(null);
  const [laedt, setLaedt] = useState(true);

  useEffect(() => {
    const laden = () => {
      if (!getToken()) {
        setKonto(null);
        setFehler(null);
        setLaedt(false);
        return;
      }
      setLaedt(true);
      api
        .me()
        .then((daten) => {
          setKonto(daten);
          setFehler(null);
        })
        .catch(() => setFehler(t("sessionExpired")))
        .finally(() => setLaedt(false));
    };
    laden();
    return onTokenChange(laden);
  }, [t]);

  if (laedt) return <Laden />;

  if (!konto) {
    return (
      <>
        <Seitenkopf titel={t("title")} />
        <Card>
          <Card.Header>
            <Card.Title>{t("notSignedIn")}</Card.Title>
            <Card.Description>{t("description")}</Card.Description>
          </Card.Header>
          <Card.Content>
            {fehler && <p className="mb-3 text-red-700">{fehler}</p>}
            <p className="text-sm text-slate-600">{t("devNote")}</p>
          </Card.Content>
        </Card>
      </>
    );
  }

  const meine = new Set(konto.roles);
  const erlaubt = RECHTE.filter((eintrag) => meine.has(eintrag.rolle));

  return (
    <>
      <Seitenkopf titel={t("title")} unterzeile={konto.email} />

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <Card.Header>
            <Card.Title>{konto.display_name}</Card.Title>
            <Card.Description>
              {konto.roles.length ? konto.roles.join(", ") : t("signedInNoRole")}
            </Card.Description>
          </Card.Header>
          <Card.Content>
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
              <dt className="text-slate-500">{t("labels.club")}</dt>
              <dd>{konto.club_id ? `#${konto.club_id}` : t("labels.notAssigned")}</dd>
              <dt className="text-slate-500">{t("labels.signInMethods")}</dt>
              <dd>{konto.identities.map((i) => i.provider).join(", ") || "—"}</dd>
              <dt className="text-slate-500">{t("labels.status")}</dt>
              <dd>{konto.is_active ? t("labels.active") : t("labels.disabled")}</dd>
            </dl>
          </Card.Content>
        </Card>

        <Card>
          <Card.Header>
            <Card.Title>{t("permissions")}</Card.Title>
          </Card.Header>
          <Card.Content>
            {erlaubt.length ? (
              <ul className="space-y-1.5 text-sm">
                {erlaubt.map((eintrag) => (
                  <li key={eintrag.key} className="flex gap-2">
                    <span aria-hidden className="text-marke-600">
                      ✓
                    </span>
                    {t(eintrag.key)}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-600">{t("noPermissions")}</p>
            )}
          </Card.Content>
        </Card>
      </div>
    </>
  );
}
