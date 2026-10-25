import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { getGetClaimDocumentUrl } from "../api/generated/sbl";
import { ClaimStatus, PaymentState, type Claim, type ClaimDocument, type ClaimItem } from "../api/types";
import { errorText } from "../lib/admin";
import { openFile } from "../lib/files";
import { dateRange, formatDate, formatMoney } from "../lib/format";
import { Badge, type BadgeTone } from "./Blocks";

/** The parts of an expense claim both sides of it show — the claimant on "My space"
 * (Stories F-2, F-5) and the manager or treasurer on "Reimbursements" (F-3, F-6).
 *
 * Two screens read the same claim, and they must not drift on what an item line says, how
 * a car journey is spelled out, or how a receipt is opened: one is the claim as filed, the
 * other the claim as decided. What differs is the controls of a line — the claimant
 * changes, removes and adds a receipt to an item; the decider only reads it — so those
 * are the slots each list takes.
 */

const STATUS_TONE: Record<ClaimStatus | typeof PaymentState.paid, BadgeTone> = {
  draft: "neutral",
  submitted: "warning",
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

/** "12.06.2026" for one day, "12.–14. Juni 2026" for a range — an item's dates. */
function itemDates(item: Pick<ClaimItem, "incurred_on" | "incurred_until">): string {
  return item.incurred_until ? dateRange(item.incurred_on, item.incurred_until) : formatDate(item.incurred_on);
}

/** The claim's items, each with its own receipts (Story F-5). `end` renders the controls
 *  at the end of a line, `below` what opens under it — the claimant's edit form and
 *  upload; the decider has neither: they approve or reject, and change no amount. */
export function ClaimItems({
  claim,
  testId,
  end,
  below,
  onRemoveReceipt,
}: {
  claim: Claim;
  testId: string;
  end?: (item: ClaimItem) => ReactNode;
  below?: (item: ClaimItem) => ReactNode;
  onRemoveReceipt?: (documentId: number) => void;
}) {
  const { t } = useTranslation("space");
  return (
    <ul
      data-testid={`${testId}-items`}
      className="divide-y divide-separator rounded-lg border border-separator bg-surface px-3 text-sm"
    >
      {claim.items.map((item) => {
        const receipts = claim.documents.filter((doc) => doc.item_id === item.id);
        return (
          <li key={item.id} data-testid={`${testId}-item-${item.id}`} className="flex flex-col gap-1 py-2">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className="min-w-0 flex-1">
                <span className="font-medium">{t(`itemKinds.${item.kind}`)}</span>
                {" · "}
                {item.description}
                <span className="block text-xs text-muted" data-testid={`${testId}-item-dates-${item.id}`}>
                  {itemDates(item)}
                  {item.distance_km != null &&
                    item.rate_cents != null &&
                    ` · ${t("itemCar", { km: item.distance_km, rate: formatMoney(item.rate_cents) })}`}
                </span>
              </span>
              <span className="tabular-nums" data-testid={`${testId}-item-amount-${item.id}`}>
                {formatMoney(item.amount_cents)}
              </span>
              {end?.(item)}
            </div>
            {receipts.length > 0 && (
              <ul className="flex flex-col gap-1 pl-3" data-testid={`${testId}-item-receipts-${item.id}`}>
                {receipts.map((doc) => (
                  <ReceiptLink key={doc.id} claim={claim} doc={doc} testId={testId} onRemove={onRemoveReceipt} />
                ))}
              </ul>
            )}
            {below?.(item)}
          </li>
        );
      })}
    </ul>
  );
}

/** One receipt, opened with the bearer token (`lib/files.ts`) — the serving endpoint
 *  admits the claimant and whoever decides, and logs the decider's look. */
function ReceiptLink({
  claim,
  doc,
  testId,
  onRemove,
}: {
  claim: Claim;
  doc: ClaimDocument;
  testId: string;
  onRemove?: (documentId: number) => void;
}) {
  const { t } = useTranslation("space");
  const [error, setError] = useState<string | null>(null);
  return (
    <li className="flex flex-wrap items-center gap-2" data-testid={`${testId}-receipt-${doc.id}`}>
      <button
        type="button"
        className="min-w-0 truncate text-link underline"
        onClick={() => openFile(getGetClaimDocumentUrl(claim.id, doc.id)).catch((err) => setError(errorText(err)))}
        data-testid={`${testId}-receipt-open-${doc.id}`}
      >
        {doc.original_name}
      </button>
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
      {error && <span className="text-sm text-danger">{error}</span>}
    </li>
  );
}

/** The receipts that cover the whole claim — a hotel invoice over several items. An
 *  item's own receipts are under the item ({@link ClaimItems}). */
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
  const items = new Set(claim.items.map((item) => item.id));
  const whole = claim.documents.filter((doc) => doc.item_id == null || !items.has(doc.item_id));
  if (!whole.length) {
    return (
      <p className="text-sm text-muted" data-testid={`${testId}-receipts-empty`}>
        {t("claims.receiptsEmpty")}
      </p>
    );
  }
  return (
    <ul data-testid={`${testId}-receipts`} className="flex flex-col gap-1 text-sm">
      {whole.map((doc) => (
        <ReceiptLink key={doc.id} claim={claim} doc={doc} testId={testId} onRemove={onRemove} />
      ))}
    </ul>
  );
}
