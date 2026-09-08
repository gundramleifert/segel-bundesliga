import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { api, type Account, type ClubAdmin } from "../api/client";
import { useApi, useInvalidieren } from "../api/useApi";
import { Fehler, Laden, Leer } from "../components/Bausteine";
import { EINGABE, fehlertext } from "../lib/verwaltung";
import { Abschnitt, Feld } from "./verwaltungBausteine";

const ROLES = ["admin", "editor", "race_officer", "club_manager"] as const;

/** Stories Z-2 and Z-3: search accounts, assign the club they act for, grant/revoke
 *  roles. Admin only — set_roles is admin-exclusive on the backend, and showing this to
 *  an editor would just mean every click ends in a 403. */
export function AccountsAdmin() {
  const { t } = useTranslation("admin");
  const invalidieren = useInvalidieren();
  const [suche, setzeSuche] = useState("");

  const konten = useApi(["admin", "accounts", suche], (signal) =>
    api.auth.list({ q: suche || undefined }, signal),
  );
  const vereine = useApi(["admin", "clubs"], (signal) => api.admin.clubs(signal));

  return (
    <Abschnitt titel={t("accounts.title")} hinweis={t("accounts.description")}>
      <Feld label={t("accounts.searchLabel")} hinweis={t("accounts.searchHint")}>
        <input
          className={EINGABE}
          value={suche}
          onChange={(e) => setzeSuche(e.target.value)}
          placeholder={t("accounts.searchPlaceholder")}
        />
      </Feld>

      {konten.loading && <Laden text={t("accounts.loadingText")} />}
      {konten.error && <Fehler text={konten.error} />}
      {konten.data && !konten.data.length && <Leer>{t("accounts.emptyText")}</Leer>}
      {konten.data && konten.data.length > 0 && (
        <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 text-sm">
          {konten.data.map((konto) => (
            <AccountRow
              key={konto.id}
              konto={konto}
              vereine={vereine.data ?? []}
              onChanged={() => invalidieren(["admin", "accounts"])}
            />
          ))}
        </ul>
      )}
    </Abschnitt>
  );
}

function AccountRow({
  konto,
  vereine,
  onChanged,
}: {
  konto: Account;
  vereine: ClubAdmin[];
  onChanged: () => void;
}) {
  const { t } = useTranslation("admin");

  const rollenSetzen = useMutation({
    mutationFn: (roles: string[]) => api.auth.setRoles(konto.id, roles),
    onSuccess: onChanged,
  });
  const vereinSetzen = useMutation({
    mutationFn: (clubId: number | null) => api.auth.setClub(konto.id, clubId),
    onSuccess: onChanged,
  });

  function toggleRolle(rolle: string, gesetzt: boolean) {
    const naechste = gesetzt
      ? [...konto.roles, rolle]
      : konto.roles.filter((r) => r !== rolle);
    rollenSetzen.mutate(naechste);
  }

  const fehler = rollenSetzen.error ?? vereinSetzen.error;

  return (
    <li className="grid gap-2 px-4 py-3 sm:grid-cols-[1.4fr_1fr_1.6fr] sm:items-center">
      <div className="min-w-0">
        <p className="truncate font-medium text-slate-900">{konto.display_name}</p>
        <p className="truncate text-slate-500">{konto.email}</p>
      </div>

      <select
        className={EINGABE}
        value={konto.club_id ?? ""}
        disabled={vereinSetzen.isPending}
        onChange={(e) => vereinSetzen.mutate(e.target.value ? Number(e.target.value) : null)}
      >
        <option value="">{t("accounts.clubNone")}</option>
        {vereine.map((v) => (
          <option key={v.id} value={v.id}>
            {v.name}
          </option>
        ))}
      </select>

      <div className="flex flex-wrap gap-x-3 gap-y-1">
        {ROLES.map((rolle) => (
          <label key={rolle} className="flex items-center gap-1.5">
            <input
              type="checkbox"
              checked={konto.roles.includes(rolle)}
              disabled={rollenSetzen.isPending}
              onChange={(e) => toggleRolle(rolle, e.target.checked)}
            />
            {t(`accounts.roleLabels.${rolle}`)}
          </label>
        ))}
      </div>

      {fehler && <p className="col-span-full text-red-700">{fehlertext(fehler)}</p>}
    </li>
  );
}
