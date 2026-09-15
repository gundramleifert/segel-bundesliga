import { Button } from "@heroui/react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import {
  useAcceptMembership,
  useListOwnMemberships,
  useRejectMembership,
  useRequestMembership,
  useWithdrawMembership,
} from "../api/generated/sbl";
import { useAccount, useAsync, useInvalidate } from "../api/useApi";
import { errorText } from "../lib/admin";
import { ErrorMessage } from "./Blocks";

/** Joining a club starts on its public page — Story Z-5, the person's half of V-8.
 *
 * One line that says where the signed-in visitor stands with this club, and the one
 * action that follows from it: not a member → ask to join; asked → waiting for the club,
 * with withdraw; invited by the club → accept or decline; member → the way to "Our club".
 * Guests see nothing: joining needs an account, and the sign-in is behind the account
 * button like everything else about the reader.
 */
export function JoinClub({ clubId }: { clubId: number }) {
  const { t } = useTranslation("club");
  const { account } = useAccount();
  const invalidate = useInvalidate();
  const own = useAsync(useListOwnMemberships({ query: { enabled: Boolean(account) } }));
  const mutation = {
    mutation: {
      onSuccess: () => invalidate("/api/club-memberships", "/api/clubs/mine", `/api/clubs/${clubId}/`),
    },
  };
  const request = useRequestMembership(mutation);
  const accept = useAcceptMembership(mutation);
  const reject = useRejectMembership(mutation);
  const withdraw = useWithdrawMembership(mutation);

  if (!account || own.loading || own.error) return null;
  const mine = own.data?.find((m) => m.club.id === clubId);
  const busy = request.isPending || accept.isPending || reject.isPending || withdraw.isPending;
  const failure = [request, accept, reject, withdraw].find((m) => m.isError);

  let body;
  if (!mine || mine.status === "rejected") {
    body = (
      <>
        <span data-testid="club-join-status">
          {mine ? t("join.declined") : t("join.notMember")}
        </span>
        <Button
          size="sm"
          isDisabled={busy}
          onPress={() => request.mutate({ data: { club_id: clubId } })}
          data-testid="club-join-ask"
        >
          {mine ? t("join.askAgain") : t("join.ask")}
        </Button>
      </>
    );
  } else if (mine.status === "pending_club") {
    body = (
      <>
        <span data-testid="club-join-status">{t("join.requested")}</span>
        <Button
          size="sm"
          variant="ghost"
          isDisabled={busy}
          onPress={() => withdraw.mutate({ membershipId: mine.id })}
          data-testid="club-join-withdraw"
        >
          {t("join.withdraw")}
        </Button>
      </>
    );
  } else if (mine.status === "pending_user") {
    body = (
      <>
        <span data-testid="club-join-status">{t("join.invited")}</span>
        <Button
          size="sm"
          isDisabled={busy}
          onPress={() => accept.mutate({ membershipId: mine.id })}
          data-testid="club-join-accept"
        >
          {t("join.accept")}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          isDisabled={busy}
          onPress={() => reject.mutate({ membershipId: mine.id })}
          data-testid="club-join-decline"
        >
          {t("join.decline")}
        </Button>
      </>
    );
  } else {
    body = (
      <>
        <span data-testid="club-join-status">{t("join.member")}</span>
        <Link
          to={`/club?club=${clubId}`}
          className="text-sm underline underline-offset-2"
          data-testid="club-join-open"
        >
          {t("join.openClub")}
        </Link>
      </>
    );
  }

  return (
    <div
      data-testid="club-join"
      className="mb-6 flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm"
    >
      {body}
      {failure && <ErrorMessage text={errorText(failure.error)} />}
    </div>
  );
}
