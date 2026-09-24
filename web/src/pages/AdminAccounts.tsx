import { keepPreviousData } from "@tanstack/react-query";
import { createColumnHelper } from "@tanstack/react-table";
import { Button } from "@heroui/react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  useDeleteTuple,
  useGetModel,
  useListAllClubs,
  useListAllEvents,
  useListAllSeries,
  useListUsers,
  useSetClub,
  useWriteTuple,
} from "../api/generated/sbl";
import { ObjectType } from "../api/generated/model/objectType";
import type { Relation } from "../api/generated/model/relation";
import type { Account, ClubAdmin } from "../api/types";
import { WHOLE_LIST, useAsync, useAsyncRows, useInvalidate } from "../api/useApi";
import { DataTable } from "../components/DataTable";
import { TABLE_FEATURES } from "../lib/table";
import { useListParams, type ListParams } from "../lib/listParams";
import { ErrorMessage, Loading } from "../components/Blocks";
import { INPUT_CLASS, errorText } from "../lib/admin";
import { Section, Field } from "../components/Form";

/** Stories Z-2 and Z-3: search accounts, assign the club they act for, write and delete
 *  the relation tuples that give them access. Admin only — the accounts list is
 *  admin-exclusive on the backend, and showing this to an editor would just mean every
 *  click ends in a 403. */
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
          cell: ({ row }) => <TuplesCell account={row.original} onChanged={onChanged} />,
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

/** Story Z-2: one line per tuple — relation, then the object it is held on — with a
 *  revoke on each, and a "＋" that asks object type, relation and object in that order.
 *  Deleting is per tuple, never a rewrite of the list: the checkbox grid this replaced
 *  rebuilt every row on each click and silently dropped the per-club grants. */
function TuplesCell({ account, onChanged }: { account: Account; onChanged: () => void }) {
  const { t } = useTranslation("admin");
  const [adding, setAdding] = useState(false);
  const remove = useDeleteTuple({ mutation: { onSuccess: onChanged } });

  return (
    <div className="flex flex-col gap-1.5" data-testid={`admin-accounts-tuples-${account.id}`}>
      {account.tuples.length === 0 && !adding && (
        <span className="text-slate-400">{t("accounts.tupleNone")}</span>
      )}
      {account.tuples.map((row) => (
        <div key={row.id} className="flex items-center gap-2">
          <span data-testid={`admin-accounts-tuple-${row.id}`}>
            <span className="font-medium">
              {t(`accounts.relationLabels.${row.relation}`, { defaultValue: row.relation })}
            </span>
            <span className="text-slate-500"> · {row.object_name ?? t("accounts.tupleSite")}</span>
          </span>
          <button
            type="button"
            className="text-slate-400 hover:text-red-700"
            aria-label={t("accounts.revoke")}
            title={t("accounts.revoke")}
            disabled={remove.isPending}
            onClick={() => remove.mutate({ tupleId: row.id })}
            data-testid={`admin-accounts-revoke-${row.id}`}
          >
            ✕
          </button>
        </div>
      ))}
      {remove.error && (
        <p data-testid={`admin-accounts-error-${account.id}`} className="text-red-700">
          {errorText(remove.error)}
        </p>
      )}
      {adding ? (
        <TupleForm account={account} onDone={() => { setAdding(false); onChanged(); }} />
      ) : (
        <button
          type="button"
          className="self-start text-sky-700 hover:underline"
          onClick={() => setAdding(true)}
          data-testid={`admin-accounts-tuple-add-${account.id}`}
        >
          ＋ {t("accounts.tupleAdd")}
        </button>
      )}
    </div>
  );
}

/** Object type → relation → object. The model comes from the server (`GET /api/auth/model`),
 *  not from a copy here, so the form can only offer what the server would accept. */
function TupleForm({ account, onDone }: { account: Account; onDone: () => void }) {
  const { t } = useTranslation("admin");
  const model = useAsync(useGetModel());
  const clubs = useAsyncRows(useListAllClubs({ limit: WHOLE_LIST }));
  const series = useAsync(useListAllSeries({ limit: WHOLE_LIST }));
  const events = useAsync(useListAllEvents({ limit: WHOLE_LIST }));
  const write = useWriteTuple({ mutation: { onSuccess: onDone } });

  const [objectType, setObjectType] = useState<ObjectType>(ObjectType.event);
  const [relation, setRelation] = useState<Relation | "">("");
  const [objectId, setObjectId] = useState<number | "">("");

  const types = model.data?.types ?? [];
  const relations = types.find((entry) => entry.type === objectType)?.relations ?? [];
  const chosen = relation && relations.includes(relation) ? relation : relations[0];

  const objects: { id: number; label: string }[] =
    objectType === ObjectType.club
      ? (clubs.data ?? []).map((c) => ({ id: c.id, label: c.name }))
      : objectType === ObjectType.series
        ? (series.data?.items ?? []).map((s) => ({ id: s.id, label: s.name }))
        : objectType === ObjectType.event
          ? (events.data?.items ?? []).map((e) => ({ id: e.id, label: e.title }))
          : [];
  const needsObject = objectType !== ObjectType.site;
  const ready = Boolean(chosen) && (!needsObject || objectId !== "");

  function submit() {
    if (!chosen) return;
    const object = needsObject ? `${objectType}:${objectId}` : "site";
    write.mutate({ data: { user: account.email, relation: chosen, object } });
  }

  return (
    <div
      className="flex flex-wrap items-end gap-2 rounded border border-slate-200 p-2"
      data-testid={`admin-accounts-tuple-form-${account.id}`}
    >
      <label className="flex flex-col text-xs text-slate-500">
        {t("accounts.tupleTypeLabel")}
        <select
          className={INPUT_CLASS}
          value={objectType}
          onChange={(e) => { setObjectType(e.target.value as ObjectType); setObjectId(""); }}
          data-testid={`admin-accounts-tuple-type-${account.id}`}
        >
          {types.map((entry) => (
            <option key={entry.type} value={entry.type}>
              {t(`accounts.objectTypeLabels.${entry.type}`)}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col text-xs text-slate-500">
        {t("accounts.tupleRelationLabel")}
        <select
          className={INPUT_CLASS}
          value={chosen ?? ""}
          onChange={(e) => setRelation(e.target.value as Relation)}
          data-testid={`admin-accounts-tuple-relation-${account.id}`}
        >
          {relations.map((r) => (
            <option key={r} value={r}>{t(`accounts.relationLabels.${r}`)}</option>
          ))}
        </select>
      </label>
      {needsObject && (
        <label className="flex flex-col text-xs text-slate-500">
          {t("accounts.tupleObjectLabel")}
          <select
            className={INPUT_CLASS}
            value={objectId}
            onChange={(e) => setObjectId(e.target.value ? Number(e.target.value) : "")}
            data-testid={`admin-accounts-tuple-object-${account.id}`}
          >
            <option value="">—</option>
            {objects.map((o) => (
              <option key={o.id} value={o.id}>{o.label}</option>
            ))}
          </select>
        </label>
      )}
      <Button
        size="sm"
        isDisabled={!ready || write.isPending}
        onPress={submit}
        data-testid={`admin-accounts-tuple-submit-${account.id}`}
      >
        {t("accounts.tupleButton")}
      </Button>
      <Button size="sm" variant="ghost" onPress={onDone} data-testid={`admin-accounts-tuple-cancel-${account.id}`}>
        {t("accounts.tupleCancel")}
      </Button>
      {write.error && (
        <p className="w-full text-red-700" data-testid={`admin-accounts-tuple-error-${account.id}`}>
          {errorText(write.error)}
        </p>
      )}
    </div>
  );
}
