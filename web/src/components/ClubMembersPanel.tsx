import { Button } from "@heroui/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useDeleteTuple, useListClubMembers } from "../api/generated/sbl";
import type { MyClub } from "../api/types";
import { useAccount, useAsync, useInvalidate } from "../api/useApi";
import { errorText } from "../lib/admin";
import { AccessPanel } from "./AccessPanel";
import { Empty, ErrorMessage, Loading } from "./Blocks";

/** The Members tab of "Our club" — Stories V-10, Z-5, V-8, V-9 on one screen (V-12).
 *
 * Membership is a relation tuple, `user:member:club` (Z-5): nothing is pending, nobody
 * waits for an answer. So the tab is three things, each shown only to whom it applies:
 *
 * - **Everyone** who may see it: the roster (`/api/clubs/{id}/members`) — names, and what
 *   else each person is to the club, so the organizers are recognizable (V-10).
 * - A **member**: "Leave the club", which deletes their own `member` tuple — the one
 *   write a person may make on themselves.
 * - The club's **admin**: the `AccessPanel` on `club:<id>`, which is where people are
 *   added by email and removed (V-8, V-9). No separate invite form: it would be a second
 *   copy of that panel with fewer relations.
 */
export function ClubMembersPanel({ entry }: { entry: MyClub }) {
  const { t } = useTranslation("club");
  const { account } = useAccount();
  const invalidate = useInvalidate();
  const clubId = entry.club.id;
  const roster = useAsync(useListClubMembers(clubId));
  const [leaving, setLeaving] = useState(false);

  const own = account?.tuples.find(
    (row) => row.object_type === "club" && row.object_id === clubId && row.relation === "member",
  );
  const refresh = () => invalidate("/api/clubs/mine", `/api/clubs/${clubId}/members`, "/api/auth/me");
  const leave = useDeleteTuple({
    mutation: {
      onSuccess: () => {
        setLeaving(false);
        refresh();
      },
    },
  });

  return (
    <div data-testid="my-club-members" className="grid grid-cols-[minmax(0,1fr)] gap-6">
      <section>
        {roster.loading && <Loading testId="my-club-members-loading" />}
        {roster.error && <ErrorMessage text={roster.error} testId="my-club-members-error" />}
        {roster.data && (
          <>
            <h3 className="font-medium">{t("members.listTitle", { count: roster.data.length })}</h3>
            {roster.data.length ? (
              <ul
                data-testid="my-club-members-list"
                className="mt-2 divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white px-3 text-sm"
              >
                {roster.data.map((member) => (
                  <li
                    key={member.user_id}
                    data-testid={`my-club-member-${member.user_id}`}
                    className="flex flex-wrap items-center gap-2 py-2"
                  >
                    <span className="min-w-0 flex-1 truncate">{member.display_name}</span>
                    {(member.relations ?? [])
                      .filter((relation) => relation !== "member")
                      .map((relation) => (
                        <span
                          key={relation}
                          data-testid={`my-club-member-relation-${member.user_id}-${relation}`}
                          className="rounded-full bg-brand-50 px-2 py-0.5 text-xs text-brand-800 ring-1 ring-inset ring-brand-200"
                        >
                          {t(`members.relations.${relation}`, { defaultValue: relation })}
                        </span>
                      ))}
                    {member.user_id === account?.id && (
                      <span className="text-xs text-slate-500">{t("members.you")}</span>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <Empty testId="my-club-members-empty">{t("members.empty")}</Empty>
            )}
          </>
        )}
      </section>

      {own && (
        <div className="flex flex-wrap items-center gap-3">
          {leaving ? (
            <>
              <span className="text-sm text-slate-700">{t("members.leaveConfirm")}</span>
              <Button
                size="sm"
                variant="danger"
                isDisabled={leave.isPending}
                onPress={() => leave.mutate({ tupleId: own.id })}
                data-testid="my-club-leave-confirm"
              >
                {t("members.leave")}
              </Button>
              <Button size="sm" variant="ghost" onPress={() => setLeaving(false)}>
                {t("members.leaveCancel")}
              </Button>
            </>
          ) : (
            <Button size="sm" variant="outline" onPress={() => setLeaving(true)} data-testid="my-club-leave">
              {t("members.leave")}
            </Button>
          )}
          {leave.isError && <ErrorMessage text={errorText(leave.error)} />}
        </div>
      )}

      {entry.may_admin && (
        <div className="grid grid-cols-[minmax(0,1fr)] gap-2">
          <p className="text-sm text-slate-600">{t("members.addHint")}</p>
          <AccessPanel object={`club:${clubId}`} testId={`my-club-access-${clubId}`} onChange={refresh} />
        </div>
      )}
    </div>
  );
}
