import { Button } from "@heroui/react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  useAcceptMembership,
  useGrantOrganizer,
  useInviteMember,
  useListClubMembers,
  useListMembersForMember,
  useListOwnMemberships,
  useRejectMembership,
  useRevokeOrganizer,
  useWithdrawMembership,
} from "../api/generated/sbl";
import type { Membership, MyClub } from "../api/types";
import { useAccount, useAsync, useInvalidate } from "../api/useApi";
import { INPUT_CLASS, errorText } from "../lib/admin";
import { Empty, ErrorMessage, Loading } from "./Blocks";
import { Field, Message } from "./Form";

/** The Members tab of "Our club" — Stories V-8, V-10, Z-5, A-8 on one screen (V-12).
 *
 * Every endpoint here existed for a long time without a page; the help text said so. Two
 * views, decided by what the account is to the club:
 *
 * - The **organizer** sees the leadership list (`/api/admin/clubs/{id}/members`), which
 *   includes what is pending: requests waiting for the club's decision, invitations the
 *   club sent and is waiting on, and the active members with the organizer's tools —
 *   make or revoke organizer, remove — plus the invite-by-email form. Never on
 *   themselves: an organizer who removes their own last organizer role locks the club.
 * - A **member** sees the roster (`/api/clubs/{id}/members`, names only) and can leave.
 *
 * Membership is mutual consent (CLAUDE.md), so "accept" here is always the club's side of
 * it; the invited person accepts on the public club page (`JoinClub`).
 */
export function ClubMembersPanel({ entry }: { entry: MyClub }) {
  const { t } = useTranslation("club");
  const { account } = useAccount();
  const invalidate = useInvalidate();
  const clubId = entry.club.id;
  // Who is *in* the club is the club admin's decision (Story Z-2); a manager decides who
  // sails and sees the roster like any member.
  const manage = entry.may_admin;

  const refresh = () =>
    invalidate(
      `/api/admin/clubs/${clubId}/members`,
      `/api/clubs/${clubId}/members`,
      "/api/club-memberships",
      "/api/clubs/mine",
    );
  const mutation = { mutation: { onSuccess: refresh } };

  const full = useAsync(useListClubMembers(clubId, { query: { enabled: manage } }));
  const roster = useAsync(
    useListMembersForMember(clubId, { query: { enabled: !manage && entry.is_member } }),
  );
  const own = useAsync(useListOwnMemberships({ query: { enabled: entry.is_member && !manage } }));

  const accept = useAcceptMembership(mutation);
  const reject = useRejectMembership(mutation);
  const withdraw = useWithdrawMembership(mutation);
  const grant = useGrantOrganizer(mutation);
  const revoke = useRevokeOrganizer(mutation);
  const invite = useInviteMember({
    mutation: {
      onSuccess: () => {
        refresh();
        setEmail("");
      },
    },
  });
  const [email, setEmail] = useState("");
  const [leaving, setLeaving] = useState(false);

  const busy =
    accept.isPending || reject.isPending || withdraw.isPending || grant.isPending || revoke.isPending;
  const failure = [accept, reject, withdraw, grant, revoke].find((m) => m.isError);

  // ------------------------------------------------------------------ the organizer
  if (manage) {
    if (full.loading) return <Loading testId="my-club-members-loading" />;
    if (full.error) return <ErrorMessage text={full.error} testId="my-club-members-error" />;
    const rows = full.data ?? [];
    const requests = rows.filter((m) => m.status === "pending_club");
    const invited = rows.filter((m) => m.status === "pending_user");
    const members = rows.filter((m) => m.status === "active");

    const sendInvitation = (e: FormEvent) => {
      e.preventDefault();
      if (email.trim()) invite.mutate({ clubId, data: { email: email.trim() } });
    };

    return (
      <div data-testid="my-club-members" className="grid grid-cols-[minmax(0,1fr)] gap-6">
        {requests.length > 0 && (
          <section className="rounded-lg border border-amber-200 bg-amber-50 p-4">
            <h3 className="font-medium">{t("members.requestsTitle", { count: requests.length })}</h3>
            <p className="text-sm text-slate-600">{t("members.requestsHint")}</p>
            <ul className="mt-2 divide-y divide-amber-100 rounded-lg bg-white px-3 text-sm">
              {requests.map((row) => (
                <li
                  key={row.id}
                  data-testid={`my-club-request-${row.id}`}
                  className="flex flex-wrap items-center gap-3 py-2"
                >
                  <Person row={row} />
                  <Button
                    size="sm"
                    isDisabled={busy}
                    onPress={() => accept.mutate({ membershipId: row.id })}
                    data-testid={`my-club-request-accept-${row.id}`}
                  >
                    {t("members.accept")}
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    isDisabled={busy}
                    onPress={() => reject.mutate({ membershipId: row.id })}
                    data-testid={`my-club-request-reject-${row.id}`}
                  >
                    {t("members.decline")}
                  </Button>
                </li>
              ))}
            </ul>
          </section>
        )}

        <section>
          <h3 className="font-medium">{t("members.listTitle", { count: members.length })}</h3>
          {members.length ? (
            <ul data-testid="my-club-members-list" className="mt-2 divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white px-3 text-sm">
              {members.map((row) => {
                const self = row.user_id === account?.id;
                return (
                  <li
                    key={row.id}
                    data-testid={`my-club-member-${row.user_id}`}
                    className="flex flex-wrap items-center gap-3 py-2"
                  >
                    <Person row={row} />
                    {row.organizer && (
                      <span
                        data-testid={`my-club-member-organizer-badge-${row.user_id}`}
                        className="rounded-full bg-brand-50 px-2 py-0.5 text-xs text-brand-800 ring-1 ring-inset ring-brand-200"
                      >
                        {t("organizer")}
                      </span>
                    )}
                    {self ? (
                      <span className="text-xs text-slate-500">{t("members.you")}</span>
                    ) : (
                      <>
                        <Button
                          size="sm"
                          variant="ghost"
                          isDisabled={busy}
                          onPress={() =>
                            row.organizer
                              ? revoke.mutate({ clubId, userId: row.user_id })
                              : grant.mutate({ clubId, userId: row.user_id })
                          }
                          data-testid={`my-club-member-organizer-${row.user_id}`}
                        >
                          {row.organizer ? t("members.revokeOrganizer") : t("members.makeOrganizer")}
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          isDisabled={busy}
                          onPress={() => withdraw.mutate({ membershipId: row.id })}
                          data-testid={`my-club-member-remove-${row.user_id}`}
                        >
                          {t("members.remove")}
                        </Button>
                      </>
                    )}
                  </li>
                );
              })}
            </ul>
          ) : (
            <Empty testId="my-club-members-empty">{t("members.empty")}</Empty>
          )}
        </section>

        {invited.length > 0 && (
          <section>
            <h3 className="font-medium">{t("members.invitedTitle", { count: invited.length })}</h3>
            <ul className="mt-2 divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white px-3 text-sm">
              {invited.map((row) => (
                <li
                  key={row.id}
                  data-testid={`my-club-invited-${row.id}`}
                  className="flex flex-wrap items-center gap-3 py-2"
                >
                  <Person row={row} />
                  <Button
                    size="sm"
                    variant="ghost"
                    isDisabled={busy}
                    onPress={() => withdraw.mutate({ membershipId: row.id })}
                    data-testid={`my-club-invited-withdraw-${row.id}`}
                  >
                    {t("members.withdrawInvitation")}
                  </Button>
                </li>
              ))}
            </ul>
          </section>
        )}

        <form onSubmit={sendInvitation} className="rounded-lg border border-slate-200 bg-white p-4">
          <h3 className="font-medium">{t("members.inviteTitle")}</h3>
          <p className="text-sm text-slate-600">{t("members.inviteHint")}</p>
          <div className="mt-2 grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
            <Field label={t("members.inviteEmailLabel")}>
              <input
                type="email"
                required
                className={INPUT_CLASS}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                data-testid="my-club-invite-email"
              />
            </Field>
            <Button type="submit" size="sm" isDisabled={invite.isPending} data-testid="my-club-invite-button">
              {t("members.inviteButton")}
            </Button>
          </div>
          <div className="mt-2">
            <Message
              testId="my-club-invite-message"
              error={invite.isError ? errorText(invite.error) : null}
              success={invite.isSuccess ? t("members.inviteSent") : null}
            />
          </div>
        </form>

        {failure && <ErrorMessage text={errorText(failure.error)} testId="my-club-members-action-error" />}
      </div>
    );
  }

  // ------------------------------------------------------------------ a member
  if (roster.loading || own.loading) return <Loading testId="my-club-members-loading" />;
  if (roster.error) return <ErrorMessage text={roster.error} testId="my-club-members-error" />;
  const mine = own.data?.find((m) => m.club.id === clubId && m.status === "active");

  return (
    <div data-testid="my-club-members" className="grid grid-cols-[minmax(0,1fr)] gap-6">
      <section>
        <h3 className="font-medium">{t("members.listTitle", { count: roster.data?.length ?? 0 })}</h3>
        {roster.data?.length ? (
          <ul data-testid="my-club-members-list" className="mt-2 divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white px-3 text-sm">
            {roster.data.map((member) => (
              <li
                key={member.user_id}
                data-testid={`my-club-member-${member.user_id}`}
                className="flex flex-wrap items-center gap-3 py-2"
              >
                <span className="min-w-0 flex-1">{member.display_name}</span>
                {member.organizer && <span className="text-xs text-slate-500">{t("organizer")}</span>}
                {member.user_id === account?.id && (
                  <span className="text-xs text-slate-500">{t("members.you")}</span>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <Empty testId="my-club-members-empty">{t("members.empty")}</Empty>
        )}
      </section>

      {mine && (
        <div className="flex flex-wrap items-center gap-3">
          {leaving ? (
            <>
              <span className="text-sm text-slate-700">{t("members.leaveConfirm")}</span>
              <Button
                size="sm"
                variant="danger"
                isDisabled={withdraw.isPending}
                onPress={() => withdraw.mutate({ membershipId: mine.id })}
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
          {withdraw.isError && <ErrorMessage text={errorText(withdraw.error)} />}
        </div>
      )}
    </div>
  );
}

function Person({ row }: { row: Membership }) {
  return (
    <span className="min-w-0 flex-1">
      <span className="block truncate">{row.display_name}</span>
      <span className="block truncate text-xs text-slate-500">{row.email}</span>
    </span>
  );
}
