import { useTranslation } from "react-i18next";

import { getReadTuplesQueryKey, useDeleteTuple, useListClubMembers, useReadTuples } from "../api/generated/sbl";
import type { TupleOut } from "../api/generated/model/tupleOut";
import { ObjectType, Relation } from "../api/types";
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
 * Membership is a relation tuple, `user:member:club` (Z-5): nothing is pending, nobody
 * waits for an answer. So the section is three things, each shown only to whom it applies:
 *
 * - **Everyone** who may see it: the roster (`/api/clubs/{id}/members`) — names, and what
 *   else each person is to the club, so the organizers are recognizable (V-10).
 * - A **member**: "Leave the club", which deletes their own `member` tuple — the one
 *   write a person may make on themselves.
 * - The club's **admin**: *＋ Member* top-right, a dialog naming someone by the email of
 *   their account to any of the club's relations (V-8, V-9), and a ✕ on each of a
 *   person's relations. **One list, not two**: the admin's rows are the club's tuples
 *   grouped by person — so an organizer who is no member is listed too — where the roster
 *   and a People panel below it once showed the same people twice.
 *
 * The crest, the guardians and the sailors were here too until #32; each is a section of
 * its own now (*Club page*, *Minors & guardians*, *Sailors*).
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

  const own = account?.tuples.find(
    (row) => row.object_type === ObjectType.club && row.object_id === clubId && row.relation === Relation.member,
  );
  const refresh = () => invalidate("/api/clubs/mine", `/api/clubs/${clubId}/members`, "/api/auth/me", "/api/me/contexts");
  const leave = useDeleteTuple({
    mutation: {
      onSuccess: () => {
        refresh();
        onLeft?.();
      },
    },
  });

  const tuples = useAsync(useReadTuples({ object: `club:${clubId}` }, { query: { enabled: mayAdmin } }));
  const revoke = useDeleteTuple({ mutation: { onSuccess: () => refreshAll() } });
  const refreshAll = () => {
    invalidate(getReadTuplesQueryKey({ object: `club:${clubId}` }));
    refresh();
  };

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
                    initialRelation={Relation.member}
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
            {(rows) => <People people={byPerson(rows)} me={account?.id} onRevoke={(id) => revoke.mutate({ tupleId: id })} />}
          </Async>
        ) : (
          <Async state={roster} testId="my-club-members">
            {(members) => (
              <People
                people={members.map((m) => ({
                  userId: m.user_id,
                  name: m.display_name,
                  relations: (m.relations ?? []).filter((r) => r !== Relation.member).map((r) => ({ relation: r })),
                }))}
                me={account?.id}
              />
            )}
          </Async>
        )}
        {revoke.isError && <ErrorMessage text={errorText(revoke.error)} testId="my-club-member-revoke-error" />}
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
            onConfirm={() => leave.mutate({ tupleId: own.id })}
            testId="my-club-leave"
          />
          {leave.isError && <ErrorMessage text={errorText(leave.error)} />}
        </div>
      )}

    </div>
  );
}

/** One person on the list: their name and what they are to the club — with the tuple's id
 *  where the reader may remove it. */
type Person = { userId: number; name: string; relations: { relation: Relation; tupleId?: number }[] };

/** The club's tuples, one row per person, alphabetical; a person's relations in the
 *  model's order. */
function byPerson(rows: TupleOut[]): Person[] {
  const people = new Map<number, Person>();
  for (const row of rows) {
    const person = people.get(row.user_id) ?? { userId: row.user_id, name: row.user_name, relations: [] };
    person.relations.push({ relation: row.relation, tupleId: row.id });
    people.set(row.user_id, person);
  }
  const order = Object.values(Relation) as string[];
  return [...people.values()]
    .map((p) => ({ ...p, relations: p.relations.sort((a, b) => order.indexOf(a.relation) - order.indexOf(b.relation)) }))
    .sort((a, b) => a.name.localeCompare(b.name));
}

function People({ people, me, onRevoke }: { people: Person[]; me?: number; onRevoke?: (tupleId: number) => void }) {
  const { t } = useTranslation("club");
  if (!people.length) return <Empty testId="my-club-members-empty">{t("members.empty")}</Empty>;
  return (
    <ul
      data-testid="my-club-members-list"
      className="divide-y divide-separator rounded-lg border border-separator bg-surface px-3 text-sm"
    >
      {people.map((person) => (
        <li key={person.userId} data-testid={`my-club-member-${person.userId}`} className="flex flex-wrap items-center gap-2 py-2">
          <span className="min-w-0 flex-1 truncate">{person.name}</span>
          {person.relations.map(({ relation, tupleId }) => (
            <Badge key={relation} tone="brand" testId={`my-club-member-relation-${person.userId}-${relation}`}>
              {t(`members.relations.${relation}`, { defaultValue: relation })}
              {onRevoke && tupleId !== undefined && (
                <button
                  type="button"
                  className="ml-1 text-faint hover:text-danger"
                  aria-label={`${t("members.revoke")}: ${t(`members.relations.${relation}`, { defaultValue: relation })}`}
                  title={t("members.revoke")}
                  onClick={() => onRevoke(tupleId)}
                  data-testid={`my-club-member-revoke-${tupleId}`}
                >
                  ✕
                </button>
              )}
            </Badge>
          ))}
          {person.userId === me ? (
            <span className="text-xs text-muted">{t("members.you")}</span>
          ) : (
            <PersonDocuments userId={person.userId} name={person.name} testId={`my-club-member-documents-${person.userId}`} />
          )}
        </li>
      ))}
    </ul>
  );
}
