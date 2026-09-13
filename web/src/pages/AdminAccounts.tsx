import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useListAllClubs, useListUsers, useSetClub, useSetRoles } from "../api/generated/sbl";
import { Role } from "../api/generated/model/role";
import type { Account, ClubAdmin } from "../api/types";
import { useAsync, useInvalidate } from "../api/useApi";
import { ErrorMessage, Loading, Empty } from "../components/Blocks";
import { INPUT_CLASS, errorText } from "../lib/admin";
import { Section, Field } from "../components/Form";

// The generated enum, not a list written out here: a role added on the backend appears in
// this screen by itself, and one removed there stops compiling here instead of rendering a
// checkbox that every click answers with a 422.
const ROLES = Object.values(Role);

/** Stories Z-2 and Z-3: search accounts, assign the club they act for, grant/revoke
 *  roles. Admin only — set_roles is admin-exclusive on the backend, and showing this to
 *  an editor would just mean every click ends in a 403. */
export function AccountsAdmin() {
  const { t } = useTranslation("admin");
  const invalidate = useInvalidate();
  const [search, setSearch] = useState("");

  const accounts = useAsync(useListUsers({ q: search || undefined }));
  const clubs = useAsync(useListAllClubs());

  return (
    <Section
      title={t("accounts.title")}
      testId="admin-accounts-section"
    >
      <Field label={t("accounts.searchLabel")} hint={t("accounts.searchHint")}>
        <input
          className={INPUT_CLASS}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t("accounts.searchPlaceholder")}
          data-testid="admin-accounts-search-input"
        />
      </Field>

      {accounts.loading && <Loading text={t("accounts.loadingText")} testId="admin-accounts-loading" />}
      {accounts.error && <ErrorMessage text={accounts.error} testId="admin-accounts-error" />}
      {accounts.data && !accounts.data.length && (
        <Empty testId="admin-accounts-empty">{t("accounts.emptyText")}</Empty>
      )}
      {accounts.data && accounts.data.length > 0 && (
        <ul
          data-testid="admin-accounts-list"
          className="divide-y divide-slate-100 rounded-lg border border-slate-200 text-sm"
        >
          {accounts.data.map((account) => (
            <AccountRow
              key={account.id}
              account={account}
              clubs={clubs.data ?? []}
              onChanged={() => invalidate("/api/auth/users")}
            />
          ))}
        </ul>
      )}
    </Section>
  );
}

function AccountRow({
  account,
  clubs,
  onChanged,
}: {
  account: Account;
  clubs: ClubAdmin[];
  onChanged: () => void;
}) {
  const { t } = useTranslation("admin");

  const setRolesMutation = useSetRoles({ mutation: { onSuccess: onChanged } });
  const setClubMutation = useSetClub({ mutation: { onSuccess: onChanged } });

  function toggleRole(role: Role, checked: boolean) {
    // `account.roles` is `string[]` — the server may well know roles this build does not,
    // and dropping them silently on any unrelated edit would quietly demote someone. So
    // the unknown ones are kept and only the known ones are matched against.
    const known = new Set<string>(ROLES);
    const kept = account.roles.filter((r) => !known.has(r)) as Role[];
    const current = ROLES.filter((r) => account.roles.includes(r));
    const nextRoles = [
      ...kept,
      ...(checked ? [...current, role] : current.filter((r) => r !== role)),
    ];
    setRolesMutation.mutate({ userId: account.id, data: { roles: nextRoles } });
  }

  const error = setRolesMutation.error ?? setClubMutation.error;

  return (
    <li
      data-testid={`admin-accounts-row-${account.id}`}
      className="grid grid-cols-[minmax(0,1fr)] gap-2 px-4 py-3 sm:grid-cols-[1.4fr_1fr_1.6fr] sm:items-center"
    >
      <div className="min-w-0">
        <p className="truncate font-medium text-slate-900">{account.display_name}</p>
        <p className="truncate text-slate-500">{account.email}</p>
      </div>

      <select
        className={INPUT_CLASS}
        value={account.club_id ?? ""}
        disabled={setClubMutation.isPending}
        onChange={(e) =>
          setClubMutation.mutate({
            userId: account.id,
            data: { club_id: e.target.value ? Number(e.target.value) : null },
          })
        }
        data-testid={`admin-accounts-club-select-${account.id}`}
      >
        <option value="">{t("accounts.clubNone")}</option>
        {clubs.map((v) => (
          <option key={v.id} value={v.id}>
            {v.name}
          </option>
        ))}
      </select>

      <div className="flex flex-wrap gap-x-3 gap-y-1">
        {ROLES.map((role) => (
          <label key={role} className="flex items-center gap-1.5">
            <input
              type="checkbox"
              checked={account.roles.includes(role)}
              disabled={setRolesMutation.isPending}
              onChange={(e) => toggleRole(role, e.target.checked)}
              data-testid={`admin-accounts-role-checkbox-${account.id}-${role}`}
            />
            {t(`accounts.roleLabels.${role}`)}
          </label>
        ))}
      </div>

      {error && (
        <p data-testid={`admin-accounts-error-${account.id}`} className="col-span-full text-red-700">
          {errorText(error)}
        </p>
      )}
    </li>
  );
}
