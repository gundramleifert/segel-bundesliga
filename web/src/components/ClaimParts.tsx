import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { getGetClaimDocumentUrl } from "../api/generated/sbl";
import { ClaimStatus, PaymentState, type Claim, type ClaimItem } from "../api/types";
import { errorText } from "../lib/admin";
import { openFile } from "../lib/files";
import { formatDate, formatMoney } from "../lib/format";
import { Badge, type BadgeTone } from "./Blocks";

/** The parts of an expense claim both sides of it show — the claimant on "My space"
 * (Stories F-2, F-5) and the manager or treasurer on "Reimbursements" (F-3, F-6).
 *
 * Two screens read the same claim, and they must not drift on what an item line says, how
 * a car journey is spelled out, or how a receipt is opened: one is the claim as filed, the
 * other the claim as decided. What differs is the control at the end of a line — the
 * claimant removes an item, the decider lowers it — so that is the one slot each list
 * takes.
 */

const STATUS_TONE: Record<ClaimStatus | typeof PaymentState.paid, BadgeTone> = {
  draft: "neutral",
  submitted: "warning",
  returned: "caution",
  approved: "success",
  rejected: "danger",
  withdrawn: "muted",
  paid: "brand",
};

/** Where the claim stands — and once approved, whether it is paid, which is the part the
 *  claimant actually wants to know. */
export function ClaimStatusBadge({ claim, testId }: { claim: Claim; testId?: string }) {
  const { t } = useTranslation("space");
  const paid = claim.payment_state === PaymentState.paid;
  const label =
    claim.status === ClaimStatus.approved && claim.payment_state
      ? `${t(`statuses.${claim.status}`)} · ${t(`paymentStates.${claim.payment_state}`)}`
      : t(`statuses.${claim.status}`);
  return (
    <Badge
      tone={STATUS_TONE[paid ? PaymentState.paid : claim.status]}
      testId={testId ?? `claim-status-${claim.id}`}
      data-status={claim.status}
      data-payment-state={claim.payment_state ?? undefined}
    >
      {label}
    </Badge>
  );
}

/** "Act 3 Kiel · claimed 12,50 € · approved 10,00 €" — the line under a claim's title. */
export function ClaimSummary({ claim }: { claim: Claim }) {
  const { t } = useTranslation("space");
  const parts = [
    claim.event_title ?? claim.club_name,
    t("claims.claimed", { amount: formatMoney(claim.claimed_cents) }),
    claim.status === ClaimStatus.approved ? t("claims.approved", { amount: formatMoney(claim.approved_cents) }) : null,
    claim.paid_cents > 0 ? t("claims.paid", { amount: formatMoney(claim.paid_cents) }) : null,
  ];
  return <p className="text-xs text-muted">{parts.filter(Boolean).join(" · ")}</p>;
}

/** The claim's items. `end` renders the control at the end of a line, if any. */
export function ClaimItems({
  claim,
  testId,
  end,
}: {
  claim: Claim;
  testId: string;
  end?: (item: ClaimItem) => ReactNode;
}) {
  const { t } = useTranslation("space");
  return (
    <ul
      data-testid={`${testId}-items`}
      className="divide-y divide-separator rounded-lg border border-separator bg-surface px-3 text-sm"
    >
      {claim.items.map((item) => (
        <li
          key={item.id}
          data-testid={`${testId}-item-${item.id}`}
          className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2"
        >
          <span className="min-w-0 flex-1">
            <span className="font-medium">{t(`itemKinds.${item.kind}`)}</span>
            {" · "}
            {item.description}
            <span className="block text-xs text-muted">
              {formatDate(item.incurred_on)}
              {item.distance_km != null && item.rate_cents != null &&
                ` · ${t("itemCar", { km: item.distance_km, rate: formatMoney(item.rate_cents) })}`}
            </span>
          </span>
          <span className="tabular-nums" data-testid={`${testId}-item-amount-${item.id}`}>
            {item.approved_cents != null ? (
              <>
                <s className="mr-1 text-faint">{formatMoney(item.amount_cents)}</s>
                {formatMoney(item.approved_cents)}
              </>
            ) : (
              formatMoney(item.amount_cents)
            )}
          </span>
          {end?.(item)}
        </li>
      ))}
    </ul>
  );
}

/** The receipts, each opened with the bearer token (`lib/files.ts`) — the serving
 *  endpoint admits the claimant and whoever decides, and logs the decider's look. */
export function ClaimReceipts({
  claim,
  testId,
  onRemove,
}: {
  claim: Claim;
  testId: string;
  onRemove?: (documentId: number) => void;
}) {
  const { t } = useTranslation("space");
  const [error, setError] = useState<string | null>(null);
  const items = new Map(claim.items.map((item) => [item.id, item]));

  if (!claim.documents.length) {
    return (
      <p className="text-sm text-muted" data-testid={`${testId}-receipts-empty`}>
        {t("claims.receiptsEmpty")}
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-1">
      <ul data-testid={`${testId}-receipts`} className="flex flex-col gap-1 text-sm">
        {claim.documents.map((doc) => {
          const item = doc.item_id != null ? items.get(doc.item_id) : undefined;
          return (
            <li key={doc.id} className="flex flex-wrap items-center gap-2" data-testid={`${testId}-receipt-${doc.id}`}>
              <button
                type="button"
                className="min-w-0 truncate text-link underline"
                onClick={() =>
                  openFile(getGetClaimDocumentUrl(claim.id, doc.id)).catch((err) => setError(errorText(err)))
                }
                data-testid={`${testId}-receipt-open-${doc.id}`}
              >
                {doc.original_name}
              </button>
              <span className="text-xs text-muted">
                {item ? item.description : t("claims.receiptWholeClaim")}
              </span>
              {onRemove && (
                <button
                  type="button"
                  className="text-xs text-muted hover:text-danger"
                  onClick={() => onRemove(doc.id)}
                  data-testid={`${testId}-receipt-remove-${doc.id}`}
                >
                  {t("claims.removeReceipt")}
                </button>
              )}
            </li>
          );
        })}
      </ul>
      {error && <p className="text-sm text-danger">{error}</p>}
    </div>
  );
}
