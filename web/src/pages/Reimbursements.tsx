import { Button } from "@heroui/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  useApproveClaim,
  useListPendingClaims,
  usePayClaim,
  useRejectClaim,
  useReturnClaim,
} from "../api/generated/sbl";
import type { Claim } from "../api/types";
import { useAccount, useAsync, useInvalidate } from "../api/useApi";
import { Async } from "../components/Async";
import { PageHeader } from "../components/Blocks";
import { ClaimItems, ClaimReceipts, ClaimStatusBadge, ClaimSummary } from "../components/ClaimParts";
import { Field, Message, Section } from "../components/Form";
import { Stack } from "../components/Layouts";
import { INPUT_CLASS, errorText } from "../lib/admin";
import { formatDate, formatMoney, parseCents } from "../lib/format";

/** Reimbursements — what waits for the manager or treasurer (Stories F-3, F-4, F-6).
 *
 * One list over every event and club whose money the person holds, because claims arrive
 * between matchdays and a list per event is a list nobody opens. Each row is either to
 * **decide** (approve, return, reject) or, once approved, to **pay**; which one is the
 * server's `action`, so this page never re-derives who may do what. The claimant's own
 * claims never appear here — four eyes (F-3).
 */
export function Reimbursements() {
  const { t } = useTranslation("space");
  const { account } = useAccount();
  const pending = useAsync(useListPendingClaims({ query: { enabled: Boolean(account) } }));

  return (
    <Stack gap={6} testId="reimbursements">
      <PageHeader title={t("pending.title")} />
      <p className="text-sm text-slate-600">{t("pending.hint")}</p>
      <Async state={pending} testId="reimbursements" empty={t("pending.empty")}>
        {(rows) => (
          <ul data-testid="reimbursements-list" className="flex flex-col gap-4">
            {rows.map((claim) => (
              <PendingClaim key={claim.id} claim={claim} />
            ))}
          </ul>
        )}
      </Async>
    </Stack>
  );
}

function PendingClaim({ claim }: { claim: Claim }) {
  const { t } = useTranslation("space");
  const id = `reimbursements-claim-${claim.id}`;
  return (
    <li data-testid={id} data-action={claim.action ?? undefined}>
      <Section
        title={`${claim.claimant_name} · ${claim.title}`}
        testId={`${id}-section`}
        action={<ClaimStatusBadge claim={claim} testId={`${id}-status`} />}
      >
        <div className="flex flex-col gap-1">
          <ClaimSummary claim={claim} />
          {claim.submitted_at && (
            <p className="text-xs text-slate-500">
              {t("pending.submittedOn", { date: formatDate(claim.submitted_at) })}
            </p>
          )}
          {claim.iban && (
            <p className="break-all text-sm" data-testid={`${id}-payee`}>
              {t("pending.payee", { name: claim.payee_name ?? claim.claimant_name, iban: claim.iban })}
            </p>
          )}
        </div>
        {claim.action === "decide" ? <Decide claim={claim} /> : <ClaimItems claim={claim} testId={id} />}
        <div className="flex flex-col gap-2">
          <h4 className="text-sm font-semibold">{t("claims.receiptsTitle")}</h4>
          <ClaimReceipts claim={claim} testId={id} />
        </div>
        {claim.action === "pay" && <Pay claim={claim} />}
      </Section>
    </li>
  );
}

function useRefresh() {
  const invalidate = useInvalidate();
  return { mutation: { onSuccess: () => invalidate("/api/claims", "/api/me/claims") } };
}

/** Approve, optionally lowering items, or send it back with a note. An item's field
 *  starts at what was claimed and only a lower amount is sent — the server refuses a
 *  higher one anyway (`expense-approval-above-claim`). */
function Decide({ claim }: { claim: Claim }) {
  const { t } = useTranslation("space");
  const id = `reimbursements-claim-${claim.id}`;
  const refresh = useRefresh();
  const approve = useApproveClaim(refresh);
  const giveBack = useReturnClaim(refresh);
  const reject = useRejectClaim(refresh);
  const [note, setNote] = useState("");
  const [cuts, setCuts] = useState<Record<number, string>>({});

  const parsed = claim.items.map((item) => {
    const raw = cuts[item.id];
    return { item, cents: raw === undefined ? item.amount_cents : parseCents(raw) };
  });
  const valid = parsed.every(({ item, cents }) => cents !== null && cents <= item.amount_cents);
  const busy = approve.isPending || giveBack.isPending || reject.isPending;
  const error = approve.error ?? giveBack.error ?? reject.error;

  const doApprove = () =>
    approve.mutate({
      claimId: claim.id,
      data: {
        items: parsed
          .filter(({ item, cents }) => cents !== null && cents < item.amount_cents)
          .map(({ item, cents }) => ({ item_id: item.id, approved_cents: cents! })),
        note: note.trim() || null,
      },
    });

  return (
    <div className="flex flex-col gap-3" data-testid={`${id}-decide`}>
      <ClaimItems
        claim={claim}
        testId={id}
        end={(item) => (
          <label className="flex items-center gap-1 text-xs text-slate-500">
            <span className="sr-only sm:not-sr-only">{t("pending.approveAs")}</span>
            <input
              inputMode="decimal"
              className={`${INPUT_CLASS} w-24 text-right`}
              value={cuts[item.id] ?? (item.amount_cents / 100).toFixed(2)}
              onChange={(e) => setCuts((prev) => ({ ...prev, [item.id]: e.target.value }))}
              aria-invalid={parsed.find((p) => p.item.id === item.id)?.cents == null}
              data-testid={`${id}-cut-${item.id}`}
            />
          </label>
        )}
      />
      <Field label={t("pending.noteLabel")} hint={t("pending.noteHint")} testId={`${id}-note-field`}>
        <textarea
          className={INPUT_CLASS}
          rows={2}
          maxLength={1000}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          data-testid={`${id}-note`}
        />
      </Field>
      <div className="flex flex-wrap gap-2">
        <Button isDisabled={busy || !valid} onPress={doApprove} data-testid={`${id}-approve`}>
          {t("pending.approve")}
        </Button>
        <Button
          variant="outline"
          isDisabled={busy || !note.trim()}
          onPress={() => giveBack.mutate({ claimId: claim.id, data: { note: note.trim() } })}
          data-testid={`${id}-return`}
        >
          {t("pending.return")}
        </Button>
        <Button
          variant="danger"
          isDisabled={busy || !note.trim()}
          onPress={() => reject.mutate({ claimId: claim.id, data: { note: note.trim() } })}
          data-testid={`${id}-reject`}
        >
          {t("pending.reject")}
        </Button>
      </div>
      <Message error={error ? errorText(error) : null} testId={`${id}-decide-message`} />
    </div>
  );
}

/** "Mark as paid" (Story F-4): the transfer was made in the decider's own banking; this
 *  records it — one settled payment over what is still open. */
function Pay({ claim }: { claim: Claim }) {
  const { t } = useTranslation("space");
  const id = `reimbursements-claim-${claim.id}`;
  const pay = usePayClaim(useRefresh());
  const [paidOn, setPaidOn] = useState("");
  const [reference, setReference] = useState(claim.title.slice(0, 140));

  return (
    <div className="flex flex-col gap-3 rounded-lg bg-slate-50 p-3" data-testid={`${id}-pay`}>
      <p className="text-sm font-medium tabular-nums">{formatMoney(claim.approved_cents - claim.paid_cents)}</p>
      <div className="flex flex-wrap gap-3">
        <div className="min-w-40 flex-1">
          <Field label={t("pending.paidOnLabel")} hint={t("pending.paidOnHint")} testId={`${id}-paid-on-field`}>
            <input
              type="date"
              className={INPUT_CLASS}
              value={paidOn}
              onChange={(e) => setPaidOn(e.target.value)}
              data-testid={`${id}-paid-on`}
            />
          </Field>
        </div>
        <div className="min-w-40 flex-1">
          <Field label={t("pending.referenceLabel")} testId={`${id}-reference-field`}>
            <input
              className={INPUT_CLASS}
              value={reference}
              maxLength={140}
              onChange={(e) => setReference(e.target.value)}
              data-testid={`${id}-reference`}
            />
          </Field>
        </div>
      </div>
      <div>
        <Button
          isDisabled={pay.isPending}
          onPress={() =>
            pay.mutate({
              claimId: claim.id,
              data: { paid_on: paidOn || null, reference: reference.trim() || null },
            })
          }
          data-testid={`${id}-pay-button`}
        >
          {t("pending.pay")}
        </Button>
      </div>
      <Message error={pay.error ? errorText(pay.error) : null} testId={`${id}-pay-message`} />
    </div>
  );
}
