import { Button } from "@heroui/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import {
  getListMyMembershipsQueryKey,
  useAcceptInvitation,
  useEndMyMembership,
  useListClubs,
  useListMyMemberships,
} from "../../api/generated/sbl";
import type { MyMembershipOut } from "../../api/generated/model/myMembershipOut";
import { useAsync, useInvalidate } from "../../api/useApi";
import { AskToJoin } from "../../components/AskToJoin";
import { Async } from "../../components/Async";
import { Badge, ErrorMessage } from "../../components/Blocks";
import { ConfirmButton } from "../../components/ConfirmButton";
import { INPUT_CLASS, errorText } from "../../lib/admin";

/** Story V-15: *Me › My clubs* — the clubs I am in, the invitations to answer and my
 *  open requests, each with what I can do about it; below, a search to ask a club to
 *  take me in. An active club opens its context; *Leave* ends the membership. */
export function MyClubs() {
  const { t } = useTranslation("club");
  const invalidate = useInvalidate();
  const mine = useAsync(useListMyMemberships());
  const refresh = () => invalidate(getListMyMembershipsQueryKey(), "/api/me/contexts", "/api/clubs");
  const accept = useAcceptInvitation({ mutation: { onSuccess: refresh } });
  const end = useEndMyMembership({ mutation: { onSuccess: refresh } });
  const failed = accept.error ?? end.error;

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6" data-testid="me-clubs">
      <Async state={mine} testId="me-clubs" empty={t("join.none")}>
        {(rows) => (
          <ul className="divide-y divide-separator rounded-lg border border-separator bg-surface px-3 text-sm" data-testid="me-clubs-list">
            {rows.map((row) => (
              <Row
                key={row.club_id}
                row={row}
                busy={accept.isPending || end.isPending}
                onAccept={() => accept.mutate({ clubId: row.club_id })}
                onEnd={() => end.mutate({ clubId: row.club_id })}
              />
            ))}
          </ul>
        )}
      </Async>
      {failed && <ErrorMessage text={errorText(failed)} testId="me-clubs-error" />}
      <Ask />
    </div>
  );
}

function Row({ row, busy, onAccept, onEnd }: { row: MyMembershipOut; busy: boolean; onAccept: () => void; onEnd: () => void }) {
  const { t } = useTranslation("club");
  const id = row.club_id;
  return (
    <li className="flex flex-wrap items-center gap-2 py-2" data-testid={`me-club-row-${id}`}>
      <span className="min-w-0 flex-1 truncate">
        {row.status === "active" ? (
          <Link to={`/me/club/${id}`} className="text-link underline-offset-2 hover:underline">
            {row.club_name}
          </Link>
        ) : (
          row.club_name
        )}
      </span>
      <Badge tone={row.status === "active" ? "brand" : "warning"} testId={`me-club-status-${id}`}>
        {t(`join.status.${row.status}`)}
      </Badge>
      {row.status === "invited" && (
        <>
          <Button size="sm" isDisabled={busy} onPress={onAccept} data-testid={`me-club-accept-${id}`}>
            {t("join.accept")}
          </Button>
          <Button size="sm" variant="secondary" isDisabled={busy} onPress={onEnd} data-testid={`me-club-decline-${id}`}>
            {t("join.decline")}
          </Button>
        </>
      )}
      {row.status === "requested" && (
        <Button size="sm" variant="secondary" isDisabled={busy} onPress={onEnd} data-testid={`me-club-withdraw-${id}`}>
          {t("join.withdraw")}
        </Button>
      )}
      {row.status === "active" && (
        <ConfirmButton
          size="sm"
          label={t("members.leave")}
          prompt={t("members.leaveConfirm")}
          confirmLabel={t("members.leave")}
          cancelLabel={t("members.leaveCancel")}
          busy={busy}
          onConfirm={onEnd}
          testId={`me-club-leave-${id}`}
        />
      )}
    </li>
  );
}

/** Finding a club to ask — among the clubs the site shows publicly (`GET /api/clubs`,
 *  narrowed on the server, Story A-13). */
function Ask() {
  const { t } = useTranslation("club");
  const [q, setQ] = useState("");
  const found = useListClubs({ q: q || undefined, limit: 8 }, { query: { enabled: q.length >= 2 } });
  return (
    <section className="flex flex-col gap-2" data-testid="me-clubs-ask">
      <h3 className="font-medium">{t("join.askTitle")}</h3>
      <label className="flex flex-col text-xs text-muted">
        {t("join.searchLabel")}
        <input className={INPUT_CLASS} value={q} onChange={(e) => setQ(e.target.value)} data-testid="me-clubs-search" />
      </label>
      {q.length >= 2 && (
        <ul className="flex flex-col gap-2 text-sm" data-testid="me-clubs-found">
          {(found.data?.items ?? []).map((club) => (
            <li key={club.id} className="flex flex-wrap items-center gap-3" data-testid={`me-clubs-found-${club.id}`}>
              <span className="min-w-0 flex-1 truncate">{club.name}</span>
              <AskToJoin clubId={club.id} testId={`me-clubs-ask-${club.id}`} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
