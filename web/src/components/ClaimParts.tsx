import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { getGetClaimDocumentUrl } from "../api/generated/sbl";
import type { Claim, ClaimItem } from "../api/types";
import { errorText } from "../lib/admin";
import { openFile } from "../lib/files";
import { formatDate, formatMoney } from "../lib/format";

/** The parts of an expense claim both sides of it show — the claimant on "My space"
 * (Stories F-2, F-5) and the manager or treasurer on "Reimbursements" (F-3, F-6).
 *
 * Two screens read the same claim, and they must not drift on what an item line says, how
 * a car journey is spelled out, or how a receipt is opened: one is the claim as filed, the
 * other the claim as decided. What differs is the control at the end of a line — the
 * claimant removes an item, the decider lowers it — so that is the one slot each list
 * takes.
 */

const STATUS_STYLE: Record<string, string> = {
  draft: "bg-slate-100 text-slate-700 ring-slate-200",
  submitted: "bg-amber-100 text-amber-800 ring-amber-300",
  returned: "bg-orange-100 text-orange-800 ring-orange-300",
  approved: "bg-emerald-100 text-emerald-800 ring-emerald-300",
  rejected: "bg-red-100 text-red-800 ring-red-200",
  withdrawn: "bg-slate-100 text-slate-500 ring-slate-200",
  paid: "bg-brand-100 text-brand-800 ring-brand-200",
};

/** Where the claim stands — and once approved, whether it is paid, which is the part the
 *  claimant actually wants to know. */
export function ClaimStatusBadge({ claim, testId }: { claim: Claim; testId?: string }) {
  const { t } = useTranslation("space");
  const paid = claim.payment_state === "paid";
  const label =
    claim.status === "approved" && claim.payment_state
      ? `${t(`statuses.${claim.status}`)} · ${t(`paymentStates.${claim.payment_state}`)}`
      : t(`statuses.${claim.status}`);
  return (
    <span
      data-testid={testId ?? `claim-status-${claim.id}`}
      data-status={claim.status}
      data-payment-state={claim.payment_state ?? undefined}
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${
        STATUS_STYLE[paid ? "paid" : claim.status] ?? STATUS_STYLE.draft
      }`}
    >
      {label}
    </span>
  );
}

/** "Act 3 Kiel · claimed 12,50 € · approved 10,00 €" — the line under a claim's title. */
export function ClaimSummary({ claim }: { claim: Claim }) {
  const { t } = useTranslation("space");
  const parts = [
    claim.event_title ?? claim.club_name,
    t("claims.claimed", { amount: formatMoney(claim.claimed_cents) }),
    claim.status === "approved" ? t("claims.approved", { amount: formatMoney(claim.approved_cents) }) : null,
    claim.paid_cents > 0 ? t("claims.paid", { amount: formatMoney(claim.paid_cents) }) : null,
  ];
  return <p className="text-xs text-slate-500">{parts.filter(Boolean).join(" · ")}</p>;
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
      className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white px-3 text-sm"
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
            <span className="block text-xs text-slate-500">
              {formatDate(item.incurred_on)}
              {item.distance_km != null && item.rate_cents != null &&
                ` · ${t("itemCar", { km: item.distance_km, rate: formatMoney(item.rate_cents) })}`}
            </span>
          </span>
          <span className="tabular-nums" data-testid={`${testId}-item-amount-${item.id}`}>
            {item.approved_cents != null ? (
              <>
                <s className="mr-1 text-slate-400">{formatMoney(item.amount_cents)}</s>
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
      <p className="text-sm text-slate-500" data-testid={`${testId}-receipts-empty`}>
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
                className="min-w-0 truncate text-brand-700 underline"
                onClick={() =>
                  openFile(getGetClaimDocumentUrl(claim.id, doc.id)).catch((err) => setError(errorText(err)))
                }
                data-testid={`${testId}-receipt-open-${doc.id}`}
              >
                {doc.original_name}
              </button>
              <span className="text-xs text-slate-500">
                {item ? item.description : t("claims.receiptWholeClaim")}
              </span>
              {onRemove && (
                <button
                  type="button"
                  className="text-xs text-slate-500 hover:text-red-700"
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
      {error && <p className="text-sm text-red-700">{error}</p>}
    </div>
  );
}
