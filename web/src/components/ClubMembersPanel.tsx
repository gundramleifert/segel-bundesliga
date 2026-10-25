import { useTranslation } from "react-i18next";

import { useDeleteTuple, useListClubMembers } from "../api/generated/sbl";
import { ObjectType, Relation } from "../api/types";
import { useAccount, useAsync, useInvalidate } from "../api/useApi";
import { errorText } from "../lib/admin";
import { AccessPanel } from "./AccessPanel";
import { Async } from "./Async";
import { Badge, Empty, ErrorMessage } from "./Blocks";
import { ConfirmButton } from "./ConfirmButton";
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
 * - The club's **admin**: the `AccessPanel` on `club:<id>`, which is where people are
 *   added by email and removed (V-8, V-9). No separate invite form: it would be a second
 *   copy of that panel with fewer relations.
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

  return (
    <div data-testid="my-club-members" className="grid grid-cols-[minmax(0,1fr)] gap-6">
      <section>
        {/* No `empty`: the heading, with its count, stays over an empty roster too. */}
        <Async state={roster} testId="my-club-members">
          {(members) => (
            <>
              <h3 className="font-medium">{t("members.listTitle", { count: members.length })}</h3>
              {members.length ? (
                <ul
                  data-testid="my-club-members-list"
                  className="mt-2 divide-y divide-separator rounded-lg border border-separator bg-surface px-3 text-sm"
                >
                  {members.map((member) => (
                    <li
                      key={member.user_id}
                      data-testid={`my-club-member-${member.user_id}`}
                      className="flex flex-wrap items-center gap-2 py-2"
                    >
                      <span className="min-w-0 flex-1 truncate">{member.display_name}</span>
                      {(member.relations ?? [])
                        .filter((relation) => relation !== Relation.member)
                        .map((relation) => (
                          <Badge
                            key={relation}
                            tone="brand"
                            testId={`my-club-member-relation-${member.user_id}-${relation}`}
                          >
                            {t(`members.relations.${relation}`, { defaultValue: relation })}
                          </Badge>
                        ))}
                      {member.user_id === account?.id ? (
                        <span className="text-xs text-muted">{t("members.you")}</span>
                      ) : (
                        <PersonDocuments
                          userId={member.user_id}
                          name={member.display_name}
                          testId={`my-club-member-documents-${member.user_id}`}
                        />
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <Empty testId="my-club-members-empty">{t("members.empty")}</Empty>
              )}
            </>
          )}
        </Async>
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

      {mayAdmin && (
        <div className="grid grid-cols-[minmax(0,1fr)] gap-2">
          <p className="text-sm text-muted">{t("members.addHint")}</p>
          <AccessPanel object={`club:${clubId}`} testId={`my-club-access-${clubId}`} onChange={refresh} />
        </div>
      )}
    </div>
  );
}
