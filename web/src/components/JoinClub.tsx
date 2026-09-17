import { Button } from "@heroui/react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import {
  useAcceptMembership,
  useListOwnMemberships,
  useRejectMembership,
  useWithdrawMembership,
} from "../api/generated/sbl";
import { useAccount, useAsync, useInvalidate } from "../api/useApi";
import { errorText } from "../lib/admin";
import { ErrorMessage } from "./Blocks";

/** Where the signed-in visitor stands with this club — the person's half of Story V-8.
 *
 * One line, shown only when there is something between the two: invited by the club →
 * accept or decline; a request on file → waiting, with withdraw; member → the way to
 * "My club". A visitor with no relationship sees nothing — deliberately **no "ask to
 * join"** for anyone who happens by: membership starts with the club's invitation
 * (Members tab, Story Z-5), not with a stranger's click on a public page.
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
  const accept = useAcceptMembership(mutation);
  const reject = useRejectMembership(mutation);
  const withdraw = useWithdrawMembership(mutation);

  if (!account || own.loading || own.error) return null;
  const mine = own.data?.find((m) => m.club.id === clubId);
  if (!mine || mine.status === "rejected") return null;
  const busy = accept.isPending || reject.isPending || withdraw.isPending;
  const failure = [accept, reject, withdraw].find((m) => m.isError);

  let body;
  if (mine.status === "pending_club") {
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
