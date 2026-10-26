import { Button, Dropdown } from "@heroui/react";
import { keepPreviousData } from "@tanstack/react-query";
import { createColumnHelper } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import {
  addClubMember,
  getListMyMembershipsQueryKey,
  getListPeopleQueryKey,
  getReadTuplesQueryKey,
  useAcceptClubMember,
  useCreatePerson,
  useDeleteTuple,
  useEndMyMembership,
  useGetClub,
  useListClubPeople,
  useListMyMemberships,
  useReadTuples,
  useRemoveClubMember,
  useUpdateClub,
  useUpdatePerson,
} from "../../api/generated/sbl";
import type { ClubPersonOut } from "../../api/generated/model/clubPersonOut";
import type { MembershipStatus } from "../../api/generated/model/membershipStatus";
import type { TupleOut } from "../../api/generated/model/tupleOut";
import { Relation, Role } from "../../api/types";
import { useAccount, useAsync, useInvalidate } from "../../api/useApi";
import { AddDialog } from "../../components/AddDialog";
import { Async } from "../../components/Async";
import { Badge, ErrorMessage } from "../../components/Blocks";
import { ConfirmButton } from "../../components/ConfirmButton";
import { CrestEditor } from "../../components/CrestEditor";
import { Field, Message } from "../../components/Form";
import { DataTable } from "../../components/DataTable";
import { GrantForm } from "../../components/GrantForm";
import { PersonDocuments } from "../../components/PersonDocuments";
import { NewPerson } from "../../components/SquadPanel";
import { INPUT_CLASS, errorText } from "../../lib/admin";
import { useListParams, type ListParams } from "../../lib/listParams";
import { TABLE_FEATURES } from "../../lib/table";

/** Story Z-10: the club's *People* and its *Club page*. */

/** *Club › People* (#45, Stories V-8, V-10, V-15; `docs/PLAN_PEOPLE.md` §4) — one list of
 * the club's people where *Members* and *Sailors* were two: a page at a time, searched,
 * filtered and sorted on the server (`GET /api/clubs/{id}/people`, A-13), with the
 * filters in the address so a to-do can land on its rows.
 *
 * Who reads it decides how much it offers. A plain member reads the roster — names,
 * accounts and roles — and may leave. The club's organizers see everyone with a row,
 * the dates of birth (a missing one is set right on the row, which clears the club's
 * `person_without_birth_date`), and add people with *＋ Person*: a new person, created
 * for the club. The club's admin also adds someone on record by email, with roles at
 * once — someone in another club is invited (V-15) — accepts or declines requests, and
 * removes a role or a membership with its ✕.
 */
export function ClubPeopleSection({
  clubId,
  mayAdmin,
  mayOrganize,
  onLeft,
}: {
  clubId: number;
  /** The club's `admin` — who is in the club, and the roles. */
  mayAdmin: boolean;
  /** `admin` or `manager` — the whole list, dates of birth, new people. */
  mayOrganize: boolean;
  onLeft?: () => void;
}) {
  const { t } = useTranslation("club");
  const invalidate = useInvalidate();
  const list = useListParams();
  const flag = (key: string) => (list.filter(key) === "" ? undefined : list.filter(key) === "true");
  const people = useAsync(
    useListClubPeople(
      clubId,
      {
        ...list.request,
        q: list.q || undefined,
        sort: list.sort ?? undefined,
        role: (list.filter("role") || undefined) as Relation | undefined,
        account: flag("account"),
        in_squad: flag("in_squad"),
        ...(mayOrganize
          ? {
              minor: flag("minor"),
              no_birth_date: flag("no_birth_date"),
              status: (list.filter("status") || undefined) as MembershipStatus | undefined,
            }
          : {}),
      },
      { query: { placeholderData: keepPreviousData } },
    ),
  );
  const tuples = useReadTuples({ object: `club:${clubId}` }, { query: { enabled: mayAdmin } });
  const refresh = () => {
    invalidate(
      `/api/clubs/${clubId}`,
      getReadTuplesQueryKey({ object: `club:${clubId}` }),
      "/api/clubs/mine",
      "/api/me",
      "/api/auth/me",
      getListPeopleQueryKey(),
    );
  };
  const id = `my-club-people`;

  return (
    <section data-testid={id} className="grid grid-cols-[minmax(0,1fr)] gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-medium" data-testid={`${id}-count`}>
          {t("people.count", { count: people.data?.total ?? 0 })}
        </h3>
        {mayOrganize && <AddPerson clubId={clubId} mayAdmin={mayAdmin} onAdded={refresh} />}
      </div>
      <Async state={people} testId={id}>
        {(page) => (
          <PeopleTable
            clubId={clubId}
            page={page}
            list={list}
            mayAdmin={mayAdmin}
            mayOrganize={mayOrganize}
            tuples={tuples.data ?? []}
            onChanged={refresh}
          />
        )}
      </Async>
      <Leave clubId={clubId} onLeft={onLeft} />
    </section>
  );
}

/** *＋ Person*: a new person for the club — or, for the club's admin, someone on record by
 *  email, with roles at once. */
function AddPerson({ clubId, mayAdmin, onAdded }: { clubId: number; mayAdmin: boolean; onAdded: () => void }) {
  const { t } = useTranslation("club");
  const [mode, setMode] = useState<"new" | "email">("new");
  const create = useCreatePerson({ mutation: { onSuccess: onAdded } });
  const testId = `my-club-access-${clubId}`;
  return (
    <AddDialog label={t("people.newButton")} title={t("people.newTitle")} testId={testId}>
      {(close) => (
        <div className="flex flex-col gap-3">
          {mayAdmin && (
            <div className="flex flex-wrap gap-4 text-sm" role="radiogroup" data-testid={`${testId}-mode`}>
              {(["new", "email"] as const).map((m) => (
                <label key={m} className="flex items-center gap-2">
                  <input type="radio" name={`${testId}-mode`} checked={mode === m} onChange={() => setMode(m)} data-testid={`${testId}-mode-${m}`} />
                  {t(`people.mode.${m}`)}
                </label>
              ))}
            </div>
          )}
          {mode === "new" ? (
            <NewPerson
              testIdPrefix="my-club-people-new"
              pending={create.isPending}
              error={create.isError ? errorText(create.error) : null}
              onCancel={close}
              onCreate={(person) => create.mutate({ data: { ...person, club_id: clubId } }, { onSuccess: close })}
            />
          ) : (
            <>
              <p className="text-sm text-muted">{t("members.addHint")}</p>
              <GrantForm
                object={`club:${clubId}`}
                testId={testId}
                addMember={(email) => addClubMember(clubId, { email })}
                onWritten={onAdded}
                onDone={close}
              />
            </>
          )}
        </div>
      )}
    </AddDialog>
  );
}

/** The filters of the list, each in the header of the column it narrows (`DataTable`) —
 *  a member gets those that reveal nothing personal. */
function useFilters(mayOrganize: boolean) {
  const { t } = useTranslation("club");
  const yesNo = (param: string, label: string) => ({
    param,
    label: t(`people.filters.${label}`),
    options: [
      { value: "true", label: t(`people.filters.${label}Yes`) },
      { value: "false", label: t(`people.filters.${label}No`) },
    ],
  });
  // Memoised: the columns depend on it, and a fresh object each render rebuilds the table.
  return useMemo(() => ({
    roles: [
      {
        param: "role",
        label: t("people.filters.role"),
        options: [Relation.admin, Relation.manager, Relation.treasurer].map((r) => ({
          value: r,
          label: t(`members.relations.${r}`),
        })),
      },
    ],
    membership: mayOrganize
      ? [
          {
            param: "status",
            label: t("people.filters.status"),
            options: ["active", "invited", "requested"].map((s) => ({ value: s, label: t(`join.status.${s}`) })),
          },
        ]
      : [],
    account: [yesNo("account", "account")],
    squad: [yesNo("in_squad", "in_squad")],
    birth: mayOrganize ? [yesNo("minor", "minor"), yesNo("no_birth_date", "no_birth_date")] : [],
  // eslint-disable-next-line react-hooks/exhaustive-deps -- `yesNo` is built from `t` alone
  }), [t, mayOrganize]);
}

const column = createColumnHelper<typeof TABLE_FEATURES, ClubPersonOut>();

function PeopleTable({
  clubId,
  page,
  list,
  mayAdmin,
  mayOrganize,
  tuples,
  onChanged,
}: {
  clubId: number;
  page: { items: ClubPersonOut[]; total: number; limit: number; offset: number };
  list: ListParams;
  mayAdmin: boolean;
  mayOrganize: boolean;
  tuples: TupleOut[];
  onChanged: () => void;
}) {
  const { t } = useTranslation("club");
  const { account } = useAccount();
  const revoke = useDeleteTuple({ mutation: { onSuccess: onChanged } });
  const remove = useRemoveClubMember({ mutation: { onSuccess: onChanged } });
  const accept = useAcceptClubMember({ mutation: { onSuccess: onChanged } });
  const failed = revoke.error ?? remove.error ?? accept.error;
  const filters = useFilters(mayOrganize);
  // The tuple behind each role chip, so the club's admin can take that one away.
  const tupleOf = useMemo(() => {
    const ids = new Map<string, number>();
    for (const row of tuples) ids.set(`${row.user_id}:${row.relation}`, row.id);
    return ids;
  }, [tuples]);

  const columns = useMemo(
    () =>
      column.columns([
        column.accessor("last_name", {
          header: t("people.name"),
          enableSorting: true,
          cell: ({ row }) => (
            <span className="flex flex-wrap items-center gap-2">
              <Link to={`/people/${row.original.person_id}`} className="font-medium underline-offset-2 hover:underline">
                {[row.original.first_name, row.original.last_name].filter(Boolean).join(" ")}
              </Link>
              {row.original.user_id != null && row.original.user_id === account?.id && (
                <span className="text-xs text-muted">{t("members.you")}</span>
              )}
              {/* Only the organizers' (Story S-5) — a plain member would only be refused (#11). */}
              {mayOrganize && row.original.user_id != null && row.original.user_id !== account?.id && (
                <PersonDocuments
                  userId={row.original.user_id}
                  name={[row.original.first_name, row.original.last_name].filter(Boolean).join(" ")}
                  testId={`my-club-member-documents-${row.original.user_id}`}
                />
              )}
            </span>
          ),
        }),
        // Membership is no role: it is the person's row in the club — active, invited or
        // asking — and ends by leaving or by the admin, never as a chip's ✕.
        column.accessor("status", {
          header: t("people.membership"),
          enableSorting: false,
          meta: { filters: filters.membership },
          cell: ({ row }) => {
            const p = row.original;
            const key = p.user_id ?? `person-${p.person_id}`;
            if (p.status === "active") {
              return <Badge tone="brand" testId={`my-club-member-relation-${key}-member`}>{t("members.relations.member")}</Badge>;
            }
            if (p.status === "invited" || p.status === "requested") {
              return (
                <Badge tone="warning" testId={`my-club-member-pending-${key}`}>
                  {p.status === "requested" ? t("members.statusRequested") : t("members.statusInvited")}
                </Badge>
              );
            }
            return <span className="text-muted">—</span>;
          },
        }),
        column.accessor("roles", {
          header: t("people.roles"),
          enableSorting: false,
          meta: { filters: filters.roles },
          cell: ({ row }) => {
            const p = row.original;
            const key = p.user_id ?? `person-${p.person_id}`;
            return (
              <span className="flex flex-wrap items-center gap-1">
                {(p.roles ?? []).map((relation) => (
                  <Badge key={relation} tone="brand" testId={`my-club-member-relation-${key}-${relation}`}>
                    {t(`members.relations.${relation}`, { defaultValue: relation })}
                  </Badge>
                ))}
              </span>
            );
          },
        }),
        column.accessor("user_id", {
          header: t("people.account"),
          enableSorting: false,
          meta: { filters: filters.account },
          cell: ({ row }) => <span className="text-muted">{row.original.user_id != null ? "✓" : "—"}</span>,
        }),
        column.accessor("in_squad", {
          header: t("people.squad"),
          enableSorting: false,
          meta: { filters: filters.squad },
          cell: ({ row }) => <span className="text-muted">{row.original.in_squad ? "✓" : "—"}</span>,
        }),
        ...(mayOrganize
          ? [
              column.accessor("birth_date", {
                header: t("people.birthDate"),
                enableSorting: true,
                meta: { filters: filters.birth },
                cell: ({ row }) => <BirthDate person={row.original} onChanged={onChanged} />,
              }),
            ]
          : []),
        ...(mayAdmin
          ? [
              column.display({
                id: "actions",
                header: () => <span className="sr-only">{t("people.actions")}</span>,
                cell: ({ row }) => (
                  <RowActions
                    person={row.original}
                    self={row.original.user_id != null && row.original.user_id === account?.id}
                    tupleOf={tupleOf}
                    onAccept={() => accept.mutate({ clubId, personId: row.original.person_id })}
                    onEnd={() => remove.mutate({ clubId, personId: row.original.person_id })}
                    onRevoke={(tupleId) => revoke.mutate({ tupleId })}
                  />
                ),
              }),
            ]
          : []),
      ]),
    [t, account?.id, mayAdmin, mayOrganize, clubId, tupleOf, remove, accept, revoke, onChanged, filters],
  );

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-2">
      <DataTable
        columns={columns}
        page={page}
        params={list}
        testId="my-club-people"
        empty={t("people.empty")}
        search={t("people.search")}
        rowTestId={(p) => p.person_id}
      />
      {failed && <ErrorMessage text={errorText(failed)} testId="my-club-member-revoke-error" />}
    </div>
  );
}

/** Every change to a row, behind one "⋯" (the club's admin's): accept or decline a
 * request, withdraw an invitation, take a role away, end a membership. Ending one's own
 * membership is not offered here — that is *Leave*, with its own confirmation — and the
 * server keeps the club's last admin (Story A-8). */
function RowActions({
  person,
  self,
  tupleOf,
  onAccept,
  onEnd,
  onRevoke,
}: {
  person: ClubPersonOut;
  self: boolean;
  tupleOf: Map<string, number>;
  onAccept: () => void;
  onEnd: () => void;
  onRevoke: (tupleId: number) => void;
}) {
  const { t } = useTranslation("club");
  const id = person.person_id;
  const items: { key: string; label: string; testId: string; danger?: boolean; run: () => void }[] = [];
  if (person.status === "requested") {
    items.push({ key: "accept", label: t("members.accept"), testId: `my-club-member-accept-${id}`, run: onAccept });
    items.push({ key: "decline", label: t("members.decline"), testId: `my-club-member-decline-${id}`, danger: true, run: onEnd });
  }
  if (person.status === "invited") {
    items.push({ key: "withdraw", label: t("members.withdrawInvitation"), testId: `my-club-member-decline-${id}`, danger: true, run: onEnd });
  }
  for (const relation of person.roles ?? []) {
    const tupleId = person.user_id != null ? tupleOf.get(`${person.user_id}:${relation}`) : undefined;
    if (tupleId === undefined) continue;
    items.push({
      key: `revoke-${relation}`,
      label: t("members.revokeRole", { role: t(`members.relations.${relation}`, { defaultValue: relation }) }),
      testId: `my-club-member-revoke-${relation}-${id}`,
      danger: true,
      run: () => onRevoke(tupleId),
    });
  }
  if (person.status === "active" && !self) {
    items.push({ key: "end", label: t("members.endMembership"), testId: `my-club-member-revoke-member-${id}`, danger: true, run: onEnd });
  }
  if (!items.length) return null;
  return (
    <Dropdown>
      <Dropdown.Trigger
        aria-label={t("people.actionsFor", { name: [person.first_name, person.last_name].filter(Boolean).join(" ") })}
        className="rounded-md p-1 text-muted hover:bg-surface-secondary hover:text-foreground"
        data-testid={`my-club-member-actions-${id}`}
      >
        <svg aria-hidden="true" viewBox="0 0 16 16" className="size-4" fill="currentColor">
          <circle cx="3" cy="8" r="1.5" />
          <circle cx="8" cy="8" r="1.5" />
          <circle cx="13" cy="8" r="1.5" />
        </svg>
      </Dropdown.Trigger>
      <Dropdown.Popover placement="bottom end">
        <Dropdown.Menu
          aria-label={t("people.actions")}
          onAction={(key) => items.find((item) => item.key === key)?.run()}
        >
          {items.map((item) => (
            <Dropdown.Item
              key={item.key}
              id={item.key}
              textValue={item.label}
              variant={item.danger ? "danger" : "default"}
              data-testid={item.testId}
            >
              {item.label}
            </Dropdown.Item>
          ))}
        </Dropdown.Menu>
      </Dropdown.Popover>
    </Dropdown>
  );
}

/** The date of birth — or, without one, the field to set it (S-3: no waiver without it). */
function BirthDate({ person, onChanged }: { person: ClubPersonOut; onChanged: () => void }) {
  const { t } = useTranslation("space");
  const { t: tc } = useTranslation("club");
  const id = person.person_id;
  const [birthDate, setBirthDate] = useState("");
  const save = useUpdatePerson({ mutation: { onSuccess: onChanged } });
  if (person.birth_date) {
    return (
      <span className="flex flex-wrap items-center gap-2">
        {person.birth_date}
        {person.minor && <Badge tone="warning">{tc("guardians.minor")}</Badge>}
      </span>
    );
  }
  return (
    <form
      className="flex flex-wrap items-center gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate({ personId: id, data: { birth_date: birthDate } });
      }}
    >
      <div className="w-40">
        <input
          type="date"
          required
          value={birthDate}
          onChange={(e) => setBirthDate(e.target.value)}
          aria-label={t("clubSections.birthDateLabel")}
          className={INPUT_CLASS}
          data-testid={`my-club-sailor-birth-date-${id}`}
        />
      </div>
      <Button size="sm" type="submit" isDisabled={save.isPending || !birthDate} data-testid={`my-club-sailor-birth-date-save-${id}`}>
        {t("clubSections.saveBirthDate")}
      </Button>
      {save.isError && <ErrorMessage text={errorText(save.error)} testId={`my-club-sailor-birth-date-error-${id}`} />}
    </form>
  );
}

/** *Leave the club* — for whoever is an active member here (Story Z-5). */
function Leave({ clubId, onLeft }: { clubId: number; onLeft?: () => void }) {
  const { t } = useTranslation("club");
  const invalidate = useInvalidate();
  const mine = useListMyMemberships();
  const leave = useEndMyMembership({
    mutation: {
      onSuccess: () => {
        invalidate(getListMyMembershipsQueryKey(), "/api/clubs/mine", "/api/me", `/api/clubs/${clubId}`);
        onLeft?.();
      },
    },
  });
  if (!mine.data?.some((m) => m.club_id === clubId && m.status === "active")) return null;
  return (
    <div className="flex flex-wrap items-center gap-3">
      <ConfirmButton
        size="sm"
        label={t("members.leave")}
        prompt={t("members.leaveConfirm")}
        confirmLabel={t("members.leave")}
        cancelLabel={t("members.leaveCancel")}
        busy={leave.isPending}
        onConfirm={() => leave.mutate({ clubId })}
        testId="my-club-leave"
      />
      {leave.isError && <ErrorMessage text={errorText(leave.error)} />}
    </div>
  );
}

/** The club's own page (Story V-3): its crest, kept by the club's `admin` — and its name,
 * short name, city and website as the public page shows them. Those are the league
 * office's to change (`PATCH /api/admin/clubs/{id}` is the site admin's): the site's
 * admin, who reaches every club from the office, gets the fields (#39); everyone else
 * reads them, rather than meeting fields that would answer 403.
 */
export function ClubPageSection({ clubId }: { clubId: number }) {
  const { t } = useTranslation("space");
  const { t: tc } = useTranslation("club");
  const invalidate = useInvalidate();
  const { hasRole } = useAccount();
  const club = useAsync(useGetClub(clubId));

  return (
    <Async state={club} testId="my-club-page">
      {(data) => (
        <div className="grid grid-cols-[minmax(0,1fr)] gap-5" data-testid={`my-club-page-${clubId}`}>
          <section className="flex flex-wrap items-center gap-3" data-testid={`my-club-crest-${clubId}-section`}>
            <CrestEditor
              club={data}
              onChanged={() => invalidate("/api/clubs", "/api/admin/clubs")}
              testIdPrefix="my-club-crest"
            >
              <p className="min-w-0 flex-1 text-sm text-muted">{tc("members.crestHint")}</p>
            </CrestEditor>
          </section>
          {hasRole(Role.admin) ? (
            <ClubFacts club={data} onSaved={() => invalidate("/api/clubs", "/api/admin/clubs", "/api/me/contexts")} />
          ) : (
            <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 text-sm" data-testid={`my-club-page-${clubId}-facts`}>
              <dt className="text-muted">{t("clubSections.name")}</dt>
              <dd>{data.name}</dd>
              <dt className="text-muted">{t("clubSections.shortName")}</dt>
              <dd>{data.short_name}</dd>
              {data.city && (
                <>
                  <dt className="text-muted">{t("clubSections.city")}</dt>
                  <dd>{data.city}</dd>
                </>
              )}
              {data.website && (
                <>
                  <dt className="text-muted">{t("clubSections.website")}</dt>
                  <dd className="break-all">{data.website}</dd>
                </>
              )}
            </dl>
          )}
          {hasRole(Role.admin) || <p className="text-sm text-muted">{t("clubSections.factsByOffice")}</p>}
        </div>
      )}
    </Async>
  );
}

/** The league office's fields for a club's facts (#39) — name, short name, city, website. */
function ClubFacts({
  club,
  onSaved,
}: {
  club: { id: number; name: string; short_name: string; city?: string | null; website?: string | null };
  onSaved: () => void;
}) {
  const { t } = useTranslation("space");
  const [form, setForm] = useState({
    name: club.name,
    short_name: club.short_name,
    city: club.city ?? "",
    website: club.website ?? "",
  });
  const save = useUpdateClub({ mutation: { onSuccess: onSaved } });
  const field = (key: keyof typeof form, label: string) => (
    <Field label={label} testId={`my-club-page-${club.id}-${key}`}>
      <input
        className={INPUT_CLASS}
        value={form[key]}
        onChange={(e) => setForm({ ...form, [key]: e.target.value })}
        data-testid={`my-club-page-${club.id}-${key}-input`}
      />
    </Field>
  );
  return (
    <form
      className="grid grid-cols-[minmax(0,1fr)] gap-3"
      data-testid={`my-club-page-${club.id}-facts-form`}
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate({
          clubId: club.id,
          data: { name: form.name, short_name: form.short_name, city: form.city || null, website: form.website || null },
        });
      }}
    >
      {field("name", t("clubSections.name"))}
      {field("short_name", t("clubSections.shortName"))}
      {field("city", t("clubSections.city"))}
      {field("website", t("clubSections.website"))}
      <div>
        <Button type="submit" size="sm" isDisabled={save.isPending} data-testid={`my-club-page-${club.id}-facts-save`}>
          {t("clubSections.saveFacts")}
        </Button>
      </div>
      <Message
        success={save.isSuccess ? t("clubSections.factsSaved") : null}
        error={save.isError ? errorText(save.error) : null}
        testId={`my-club-page-${club.id}-facts`}
      />
    </form>
  );
}
