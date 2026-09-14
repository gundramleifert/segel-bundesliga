import { keepPreviousData } from "@tanstack/react-query";
import { createColumnHelper } from "@tanstack/react-table";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";

import { useListAllClubs, useListUsers, useSetClub, useSetRoles } from "../api/generated/sbl";
import { Role } from "../api/generated/model/role";
import type { Account, ClubAdmin } from "../api/types";
import { WHOLE_LIST, useAsync, useAsyncRows, useInvalidate } from "../api/useApi";
import { DataTable } from "../components/DataTable";
import { TABLE_FEATURES } from "../lib/table";
import { useListParams, type ListParams } from "../lib/listParams";
import { ErrorMessage, Loading } from "../components/Blocks";
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

  // One account per registered sailor plus the officials — a few hundred rows, so paged,
  // sorted and searched on the server with all three in the URL (Story A-13).
  const list = useListParams();
  const accounts = useAsync(
    useListUsers(
      { ...list.request, q: list.q || undefined, sort: list.sort ?? undefined },
      { query: { placeholderData: keepPreviousData } },
    ),
  );
  // A club selector has to offer every club, so it asks for the whole list.
  const clubs = useAsyncRows(useListAllClubs({ limit: WHOLE_LIST }));

  return (
    <Section
      title={t("accounts.title")}
      testId="admin-accounts-section"
    >
      <Field label={t("accounts.searchLabel")} hint={t("accounts.searchHint")}>
        <input
          className={INPUT_CLASS}
          value={list.q}
          onChange={(e) => list.setQuery(e.target.value)}
          placeholder={t("accounts.searchPlaceholder")}
          data-testid="admin-accounts-search-input"
        />
      </Field>

      {accounts.loading && <Loading text={t("accounts.loadingText")} testId="admin-accounts-loading" />}
      {accounts.error && <ErrorMessage text={accounts.error} testId="admin-accounts-error" />}
      {accounts.data && (
        <AccountTable
          page={accounts.data}
          params={list}
          clubs={clubs.data ?? []}
          onChanged={() => invalidate("/api/auth/users")}
        />
      )}
    </Section>
  );
}

const accountColumn = createColumnHelper<typeof TABLE_FEATURES, Account>();

function AccountTable({
  page,
  params,
  clubs,
  onChanged,
}: {
  page: { items: Account[]; total: number; limit: number; offset: number };
  params: ListParams;
  clubs: ClubAdmin[];
  onChanged: () => void;
}) {
  const { t } = useTranslation("admin");
  // Memoised, as the library asks — a fresh column array every render rebuilds the table.
  const columns = useMemo(
    () =>
      accountColumn.columns([
        accountColumn.accessor("display_name", {
          header: t("accounts.nameHeader"),
          // Sortable exactly where the server can sort (`USER_SORT` in `app/routers/auth.py`).
          enableSorting: true,
          cell: ({ row }) => (
            <span className="font-medium text-slate-900">{row.original.display_name}</span>
          ),
        }),
        accountColumn.accessor("email", {
          header: t("accounts.emailHeader"),
          enableSorting: true,
          cell: ({ row }) => <span className="text-slate-500">{row.original.email}</span>,
        }),
        accountColumn.display({
          id: "club",
          header: t("accounts.clubHeader"),
          cell: ({ row }) => (
            <ClubCell account={row.original} clubs={clubs} onChanged={onChanged} />
          ),
        }),
        accountColumn.display({
          id: "roles",
          header: t("accounts.rolesHeader"),
          cell: ({ row }) => <RolesCell account={row.original} onChanged={onChanged} />,
        }),
      ]),
    [t, clubs, onChanged],
  );

  return (
    <DataTable
      columns={columns}
      page={page}
      params={params}
      testId="admin-accounts"
      empty={t("accounts.emptyText")}
      rowTestId={(account) => account.id}
    />
  );
}

/** The club an account acts for. Its own component, because a cell that changes something
 *  needs the mutation's pending and error state next to the control that caused it. */
function ClubCell({
  account,
  clubs,
  onChanged,
}: {
  account: Account;
  clubs: ClubAdmin[];
  onChanged: () => void;
}) {
  const { t } = useTranslation("admin");
  const setClubMutation = useSetClub({ mutation: { onSuccess: onChanged } });

  return (
    <>
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
      {setClubMutation.error && (
        <p data-testid={`admin-accounts-club-error-${account.id}`} className="text-red-700">
          {errorText(setClubMutation.error)}
        </p>
      )}
    </>
  );
}

function RolesCell({ account, onChanged }: { account: Account; onChanged: () => void }) {
  const { t } = useTranslation("admin");
  const setRolesMutation = useSetRoles({ mutation: { onSuccess: onChanged } });

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

  return (
    <>
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
      {setRolesMutation.error && (
        <p data-testid={`admin-accounts-error-${account.id}`} className="text-red-700">
          {errorText(setRolesMutation.error)}
        </p>
      )}
    </>
  );
}
