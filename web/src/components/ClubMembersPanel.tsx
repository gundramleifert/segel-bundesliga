import { useTranslation } from "react-i18next";

import {
  addClubMember,
  getReadTuplesQueryKey,
  useDeleteTuple,
  useListClubMembers,
  useReadTuples,
  useRemoveClubMember,
} from "../api/generated/sbl";
import type { ClubMemberOut } from "../api/generated/model/clubMemberOut";
import type { TupleOut } from "../api/generated/model/tupleOut";
import { Relation } from "../api/types";
import { useAccount, useAsync, useInvalidate } from "../api/useApi";
import { errorText } from "../lib/admin";
import { AddDialog } from "./AddDialog";
import { Async } from "./Async";
import { Badge, Empty, ErrorMessage } from "./Blocks";
import { ConfirmButton } from "./ConfirmButton";
import { GrantForm } from "./GrantForm";
import { PersonDocuments } from "./PersonDocuments";

/** A club's *Members* section — Stories V-10, Z-5, V-8, V-9 on one screen (V-12, Z-10).
 *
 * Membership is a person's active membership of the club (#40, `docs/PLAN_PEOPLE.md`) —
 * a person with or without an account; what each is besides (admin, manager, treasurer)
 * is a tuple on their account. So the section is three things, each shown only to whom
 * it applies:
 *
 * - **Everyone** who may see it: the roster (`/api/clubs/{id}/members`) — names, and what
 *   else each person is to the club, so the organizers are recognizable (V-10).
 * - A **member**: "Leave the club", which ends their own membership — the one change a
 *   person may make on themselves.
 * - The club's **admin**: *＋ Member* top-right, a dialog adding someone by email and
 *   naming them to any of the club's relations at once (V-8, V-9), and a ✕ on each of a
 *   person's relations — on *member*, ending the membership. **One list, not two**: the
 *   roster joined with the club's tuples, so an organizer who is no member is listed too.
 *
 * Until #45 replaces it with the club's *People* table.
 */
export function ClubMembersPanel({
  clubId,
  mayAdmin,
  onLeft,
}: {
  clubId: number;
  /** The club's `admin` — as the model answers it there, the site's admin included. */
  mayAdmin: boolean;
  /** After the person left the club — the page they were on is no longer theirs. */
  onLeft?: () => void;
}) {
  const { t } = useTranslation("club");
  const { account } = useAccount();
  const invalidate = useInvalidate();
  const roster = useAsync(useListClubMembers(clubId));

  const own = roster.data?.find((m) => m.user_id != null && m.user_id === account?.id);
  const refresh = () => invalidate("/api/clubs/mine", `/api/clubs/${clubId}/members`, "/api/auth/me", "/api/me/contexts");
  const leave = useRemoveClubMember({
    mutation: {
      onSuccess: () => {
        refresh();
        onLeft?.();
      },
    },
  });

  const tuples = useAsync(useReadTuples({ object: `club:${clubId}` }, { query: { enabled: mayAdmin } }));
  const refreshAll = () => {
    invalidate(getReadTuplesQueryKey({ object: `club:${clubId}` }));
    refresh();
  };
  const revoke = useDeleteTuple({ mutation: { onSuccess: refreshAll } });
  const remove = useRemoveClubMember({ mutation: { onSuccess: refreshAll } });
  const failed = revoke.error ?? remove.error;

  return (
    <div data-testid="my-club-members" className="grid grid-cols-[minmax(0,1fr)] gap-6">
      <section className="flex flex-col gap-2">
        {/* No `empty`: the heading, with its count, stays over an empty roster too. */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="font-medium" data-testid="my-club-members-count">
            {t("members.listTitle", { count: roster.data?.length ?? 0 })}
          </h3>
          {mayAdmin && (
            <AddDialog label={t("members.newButton")} title={t("members.newTitle")} testId={`my-club-access-${clubId}`}>
              {(close) => (
                <div className="flex flex-col gap-3">
                  <p className="text-sm text-muted">{t("members.addHint")}</p>
                  <GrantForm
                    object={`club:${clubId}`}
                    testId={`my-club-access-${clubId}`}
                    addMember={(email) => addClubMember(clubId, { email })}
                    onWritten={refreshAll}
                    onDone={close}
                  />
                </div>
              )}
            </AddDialog>
          )}
        </div>
        {mayAdmin ? (
          <Async state={tuples} testId="my-club-members">
            {(rows) => (
              <People
                people={joined(roster.data ?? [], rows)}
                me={account?.id}
                onRevoke={(id) => revoke.mutate({ tupleId: id })}
                onRemove={(personId) => remove.mutate({ clubId, personId })}
              />
            )}
          </Async>
        ) : (
          <Async state={roster} testId="my-club-members">
            {(members) => <People people={joined(members, [])} me={account?.id} />}
          </Async>
        )}
        {failed && <ErrorMessage text={errorText(failed)} testId="my-club-member-revoke-error" />}
      </section>

      {own && (
        <div className="flex flex-wrap items-center gap-3">
          <ConfirmButton
            size="sm"
            label={t("members.leave")}
            prompt={t("members.leaveConfirm")}
            confirmLabel={t("members.leave")}
            cancelLabel={t("members.leaveCancel")}
            busy={leave.isPending}
            onConfirm={() => leave.mutate({ clubId, personId: own.person_id })}
            testId="my-club-leave"
          />
          {leave.isError && <ErrorMessage text={errorText(leave.error)} />}
        </div>
      )}
    </div>
  );
}

/** One person on the list: their name and what they are to the club — with the tuple's id
 *  where the reader may remove it; `personId` where they are a member. */
type Person = {
  key: string;
  userId?: number | null;
  personId?: number;
  name: string;
  relations: { relation: Relation; tupleId?: number }[];
};

/** The roster joined with the club's tuples, one row per person, alphabetical; a
 *  person's relations in the model's order. Without tuples (a plain member's view) the
 *  roster's own relations are shown, none removable. */
function joined(members: ClubMemberOut[], rows: TupleOut[]): Person[] {
  const people = new Map<string, Person>();
  const keyOf = (userId: number | null | undefined, personId?: number) =>
    userId != null ? String(userId) : `person-${personId}`;
  for (const m of members) {
    const relations = rows.length
      ? [{ relation: Relation.member }]
      : (m.relations ?? []).map((relation) => ({ relation }));
    people.set(keyOf(m.user_id, m.person_id), {
      key: keyOf(m.user_id, m.person_id),
      userId: m.user_id,
      personId: m.person_id,
      name: m.display_name,
      relations,
    });
  }
  for (const row of rows) {
    const key = keyOf(row.user_id);
    const person = people.get(key) ?? { key, userId: row.user_id, name: row.user_name, relations: [] };
    person.relations.push({ relation: row.relation, tupleId: row.id });
    people.set(key, person);
  }
  const order = Object.values(Relation) as string[];
  return [...people.values()]
    .map((p) => ({ ...p, relations: p.relations.sort((a, b) => order.indexOf(a.relation) - order.indexOf(b.relation)) }))
    .sort((a, b) => a.name.localeCompare(b.name));
}

function People({
  people,
  me,
  onRevoke,
  onRemove,
}: {
  people: Person[];
  me?: number;
  onRevoke?: (tupleId: number) => void;
  onRemove?: (personId: number) => void;
}) {
  const { t } = useTranslation("club");
  if (!people.length) return <Empty testId="my-club-members-empty">{t("members.empty")}</Empty>;
  return (
    <ul
      data-testid="my-club-members-list"
      className="divide-y divide-separator rounded-lg border border-separator bg-surface px-3 text-sm"
    >
      {people.map((person) => (
        <li key={person.key} data-testid={`my-club-member-${person.key}`} className="flex flex-wrap items-center gap-2 py-2">
          <span className="min-w-0 flex-1 truncate">{person.name}</span>
          {person.relations.map(({ relation, tupleId }) => {
            const label = t(`members.relations.${relation}`, { defaultValue: relation });
            const drop =
              tupleId !== undefined
                ? onRevoke && (() => onRevoke(tupleId))
                : relation === Relation.member && person.personId !== undefined
                  ? onRemove && (() => onRemove(person.personId!))
                  : undefined;
            return (
              <Badge key={relation} tone="brand" testId={`my-club-member-relation-${person.key}-${relation}`}>
                {label}
                {drop && (
                  <button
                    type="button"
                    className="ml-1 text-faint hover:text-danger"
                    aria-label={`${t("members.revoke")}: ${label}`}
                    title={t("members.revoke")}
                    onClick={drop}
                    data-testid={`my-club-member-revoke-${tupleId ?? `member-${person.personId}`}`}
                  >
                    ✕
                  </button>
                )}
              </Badge>
            );
          })}
          {person.userId == null ? null : person.userId === me ? (
            <span className="text-xs text-muted">{t("members.you")}</span>
          ) : (
            <PersonDocuments userId={person.userId} name={person.name} testId={`my-club-member-documents-${person.userId}`} />
          )}
        </li>
      ))}
    </ul>
  );
}
