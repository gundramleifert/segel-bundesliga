import { Button } from "@heroui/react";
import { useTranslation } from "react-i18next";

import { getListMyMembershipsQueryKey, useAskToJoin, useListMyMemberships } from "../api/generated/sbl";
import { useAccount, useInvalidate } from "../api/useApi";
import { errorText } from "../lib/admin";
import { ErrorMessage } from "./Blocks";

/** Story V-15: *Ask to join* one club — for a signed-in person with no membership,
 *  invitation or request there. Where I am invited, asking accepts. Says where my
 *  request stands once it is sent; renders nothing for a guest or a member. */
export function AskToJoin({ clubId, testId }: { clubId: number; testId: string }) {
  const { t } = useTranslation("club");
  const { account } = useAccount();
  const invalidate = useInvalidate();
  const mine = useListMyMemberships({ query: { enabled: Boolean(account) } });
  const ask = useAskToJoin({
    mutation: { onSuccess: () => invalidate(getListMyMembershipsQueryKey(), "/api/me/contexts", "/api/clubs") },
  });
  if (!account || !mine.data) return null;
  const row = mine.data.find((m) => m.club_id === clubId);
  if (row?.status === "active") return null;
  if (row?.status === "requested") {
    return (
      <p className="text-sm text-muted" data-testid={`${testId}-requested`}>
        {t("join.requested")}
      </p>
    );
  }
  return (
    <div className="flex flex-col items-start gap-1">
      <Button
        size="sm"
        variant={row?.status === "invited" ? "primary" : "secondary"}
        isDisabled={ask.isPending}
        onPress={() => ask.mutate({ data: { club_id: clubId } })}
        data-testid={testId}
      >
        {row?.status === "invited" ? t("join.acceptInvitation") : t("join.ask")}
      </Button>
      {ask.isError && <ErrorMessage text={errorText(ask.error)} testId={`${testId}-error`} />}
    </div>
  );
}
