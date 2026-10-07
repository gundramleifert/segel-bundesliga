import { Button } from "@heroui/react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  getDownloadClubClaimsXlsxUrl,
  getGetClaimGirocodeUrl,
  getDownloadPaymentRunSepaUrl,
  getDownloadPaymentRunXlsxUrl,
  useApproveClaim,
  useCreatePaymentRun,
  useFailPayment,
  useGetClubBankAccount,
  useListOpenPaymentRuns,
  useListPendingClaims,
  usePayClaim,
  useRejectClaim,
  useReturnClaim,
  useSaveClubBankAccount,
  useSettlePaymentRun,
} from "../api/generated/sbl";
import type { RunOut } from "../api/generated/model/runOut";
import type { RunPaymentOut } from "../api/generated/model/runPaymentOut";
import { ApiError } from "../api/http";
import type { Claim } from "../api/types";
import { useAccount, useAsync, useInvalidate } from "../api/useApi";
import { Async } from "../components/Async";
import { PageHeader } from "../components/Blocks";
import { ClaimItems, ClaimReceipts, ClaimStatusBadge, ClaimSummary } from "../components/ClaimParts";
import { Field, Message, Section } from "../components/Form";
import { Stack } from "../components/Layouts";
import { INPUT_CLASS, errorText } from "../lib/admin";
import { downloadFile, fetchFileUrl } from "../lib/files";
import { formatDate, formatMoney, parseCents } from "../lib/format";

/** Reimbursements — what waits for the manager or treasurer (Stories F-3, F-4, F-6).
 *
 * One list over every event and club whose money the person holds, because claims arrive
 * between matchdays and a list per event is a list nobody opens. Each row is either to
 * **decide** (approve, return, reject) or, once approved, to **pay**; which one is the
 * server's `action`, so this page never re-derives who may do what. The claimant's own
 * claims never appear here — four eyes (F-3).
 *
 * Paying is per **club**, because the money leaves one club's account (Story F-7): each
 * club the person pays for gets a section with its account, the SEPA file over its
 * approved claims, the runs still waiting for the bank and the year's books.
 */
export function Reimbursements() {
  const { t } = useTranslation("space");
  const { account } = useAccount();
  const enabled = { query: { enabled: Boolean(account) } };
  const pending = useAsync(useListPendingClaims(enabled));
  const runs = useListOpenPaymentRuns(enabled);

  return (
    <Stack gap={6} testId="reimbursements">
      <PageHeader title={t("pending.title")} />
      <p className="text-sm text-slate-600">{t("pending.hint")}</p>
      <Async state={pending} testId="reimbursements">
        {(rows) => {
          const toDecide = rows.filter((claim) => claim.action === "decide");
          const clubs = payingClubs(rows, runs.data ?? [], account?.tuples ?? []);
          if (!toDecide.length && !clubs.length) {
            return (
              <p className="text-sm text-slate-500" data-testid="reimbursements-empty">
                {t("pending.empty")}
              </p>
            );
          }
          return (
            <Stack gap={8}>
              {toDecide.length > 0 && (
                <div className="flex flex-col gap-3">
                  <h2 className="text-lg font-semibold">{t("pending.toDecide")}</h2>
                  <ul data-testid="reimbursements-list" className="flex flex-col gap-4">
                    {toDecide.map((claim) => (
                      <PendingClaim key={claim.id} claim={claim} />
                    ))}
                  </ul>
                </div>
              )}
              {clubs.map((club) => (
                <ClubMoney
                  key={club.id}
                  club={club}
                  toPay={rows.filter(
                    (claim) => claim.action === "pay" && claim.payer_club_id === club.id,
                  )}
                  runs={(runs.data ?? []).filter((run) => run.payer_club_id === club.id)}
                />
              ))}
            </Stack>
          );
        }}
      </Async>
    </Stack>
  );
}

type PayingClub = { id: number; name: string };

/** The clubs this person pays for: those with a claim to pay or a run at the bank, and
 *  those they hold `manager`, `admin` or `treasurer` on directly — so a treasurer with
 *  nothing pending can still save the account and download the books. The server decides
 *  each card again; one it refuses (`club-money-forbidden`) hides itself. */
function payingClubs(
  claims: Claim[],
  runs: RunOut[],
  tuples: { relation: string; object_type: string; object_id: number | null; object_name?: string | null }[],
): PayingClub[] {
  const found = new Map<number, string>();
  for (const claim of claims) {
    if (claim.action === "pay" && claim.payer_club_id != null) {
      found.set(claim.payer_club_id, claim.payer_club_name ?? "");
    }
  }
  for (const run of runs) found.set(run.payer_club_id, run.payer_club_name);
  for (const tuple of tuples) {
    if (
      tuple.object_type === "club" &&
      tuple.object_id != null &&
      ["manager", "admin", "treasurer"].includes(tuple.relation) &&
      !found.has(tuple.object_id)
    ) {
      found.set(tuple.object_id, tuple.object_name ?? "");
    }
  }
  return [...found].map(([id, name]) => ({ id, name })).sort((a, b) => a.name.localeCompare(b.name));
}

/** One club's money: its account, the SEPA file, the runs at the bank, the books. */
function ClubMoney({ club, toPay, runs }: { club: PayingClub; toPay: Claim[]; runs: RunOut[] }) {
  const { t } = useTranslation("space");
  const id = `reimbursements-club-${club.id}`;
  const account = useGetClubBankAccount(club.id);
  // Not this person's to see: the server said so, and the whole section goes with it.
  if (account.error instanceof ApiError && account.error.code === "club-money-forbidden") return null;

  return (
    <section className="flex flex-col gap-4" data-testid={id}>
      <h2 className="text-lg font-semibold">{t("bankRun.clubTitle", { name: club.name })}</h2>
      <ClubAccount clubId={club.id} saved={account.data ?? null} loading={account.isPending} />
      {toPay.length > 0 && <SepaRun clubId={club.id} claims={toPay} hasAccount={Boolean(account.data)} />}
      {toPay.length > 0 && (
        <div className="flex flex-col gap-3">
          <h3 className="font-semibold">{t("bankRun.claimsTitle")}</h3>
          <ul className="flex flex-col gap-4" data-testid={`${id}-claims`}>
            {toPay.map((claim) => (
              <PendingClaim key={claim.id} claim={claim} />
            ))}
          </ul>
        </div>
      )}
      {runs.map((run) => (
        <OpenRun key={run.id} run={run} />
      ))}
      <Books clubId={club.id} />
    </section>
  );
}

function useMoneyRefresh() {
  const invalidate = useInvalidate();
  return () => invalidate("/api/claims", "/api/me/claims", "/api/payment-runs", "/api/clubs");
}

/** The account the club pays from — the debtor of its SEPA files (Story F-7). */
function ClubAccount({
  clubId,
  saved,
  loading,
}: {
  clubId: number;
  saved: { holder: string; iban: string; bic: string | null } | null;
  loading: boolean;
}) {
  if (loading) return null;
  return <ClubAccountForm key={saved?.iban ?? "none"} clubId={clubId} saved={saved} />;
}

function ClubAccountForm({
  clubId,
  saved,
}: {
  clubId: number;
  saved: { holder: string; iban: string; bic: string | null } | null;
}) {
  const { t } = useTranslation("space");
  const id = `reimbursements-club-${clubId}-account`;
  const refresh = useMoneyRefresh();
  const save = useSaveClubBankAccount({ mutation: { onSuccess: refresh } });
  const [holder, setHolder] = useState(saved?.holder ?? "");
  const [iban, setIban] = useState(saved?.iban ?? "");
  const [bic, setBic] = useState(saved?.bic ?? "");

  return (
    <Section title={t("bankRun.accountTitle")} testId={id}>
      <p className="text-sm text-slate-600">{t("bankRun.accountHint")}</p>
      <div className="flex flex-col gap-3">
        <Field label={t("bank.holderLabel")} testId={`${id}-holder-field`}>
          <input
            id={`${id}-holder`}
            className={INPUT_CLASS}
            value={holder}
            maxLength={160}
            onChange={(e) => setHolder(e.target.value)}
            data-testid={`${id}-holder`}
          />
        </Field>
        <Field label={t("bank.ibanLabel")} testId={`${id}-iban-field`}>
          <input
            className={INPUT_CLASS}
            value={iban}
            maxLength={50}
            autoComplete="off"
            onChange={(e) => setIban(e.target.value)}
            data-testid={`${id}-iban`}
          />
        </Field>
        <Field label={t("bank.bicLabel")} hint={t("bankRun.bicHint")} testId={`${id}-bic-field`}>
          <input
            className={INPUT_CLASS}
            value={bic}
            maxLength={11}
            onChange={(e) => setBic(e.target.value)}
            data-testid={`${id}-bic`}
          />
        </Field>
        <div>
          <Button
            isDisabled={save.isPending || !holder.trim() || !iban.trim()}
            onPress={() =>
              save.mutate({
                clubId,
                data: { holder: holder.trim(), iban: iban.trim(), bic: bic.trim() || null },
              })
            }
            data-testid={`${id}-save`}
          >
            {t("bank.save")}
          </Button>
        </div>
        <Message
          success={save.isSuccess ? t("bankRun.accountSaved") : null}
          error={save.error ? errorText(save.error) : null}
          testId={`${id}-message`}
        />
      </div>
    </Section>
  );
}

function today(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** "Pay by SEPA file": the approved claims to pay, all ticked; one file for the club's
 *  online banking, downloaded the moment the run is made. */
function SepaRun({ clubId, claims, hasAccount }: { clubId: number; claims: Claim[]; hasAccount: boolean }) {
  const { t } = useTranslation("space");
  const id = `reimbursements-club-${clubId}-sepa`;
  const refresh = useMoneyRefresh();
  const [unticked, setUnticked] = useState<Set<number>>(new Set());
  const [executionDate, setExecutionDate] = useState(today());
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const create = useCreatePaymentRun({
    mutation: {
      onSuccess: (run) => {
        refresh();
        setDownloadError(null);
        downloadFile(getDownloadPaymentRunSepaUrl(run.id), `sepa-${run.message_id}.xml`).catch((error) =>
          setDownloadError(errorText(error)),
        );
      },
      onError: (error) => {
        if (error instanceof ApiError && error.code === "club-bank-account-missing") focusAccount(clubId);
      },
    },
  });

  const chosen = claims.filter((claim) => !unticked.has(claim.id));
  const open = (claim: Claim) => claim.approved_cents - claim.paid_cents;
  const sum = chosen.reduce((total, claim) => total + open(claim), 0);
  const toggle = (claimId: number) =>
    setUnticked((prev) => {
      const next = new Set(prev);
      if (next.has(claimId)) next.delete(claimId);
      else next.add(claimId);
      return next;
    });

  return (
    <Section title={t("bankRun.sepaTitle")} testId={id}>
      <p className="text-sm text-slate-600">{t("bankRun.sepaHint")}</p>
      <div className="flex flex-col gap-3">
        {!hasAccount && (
          <p className="text-sm text-amber-700" data-testid={`${id}-no-account`}>
            {t("bankRun.noAccount")}{" "}
            <button type="button" className="underline" onClick={() => focusAccount(clubId)}>
              {t("bankRun.toAccount")}
            </button>
          </p>
        )}
        <ul className="flex flex-col gap-1" data-testid={`${id}-claims`}>
          {claims.map((claim) => (
            <li key={claim.id}>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={!unticked.has(claim.id)}
                  onChange={() => toggle(claim.id)}
                  data-testid={`${id}-claim-${claim.id}`}
                />
                <span className="min-w-0 flex-1 truncate">
                  {claim.claimant_name} · {claim.title}
                </span>
                <span className="tabular-nums">{formatMoney(open(claim))}</span>
              </label>
            </li>
          ))}
        </ul>
        <p className="text-sm font-medium tabular-nums" data-testid={`${id}-sum`}>
          {t("bankRun.sum", { count: chosen.length, amount: formatMoney(sum) })}
        </p>
        <div className="max-w-xs">
          <Field label={t("bankRun.executionDate")} testId={`${id}-date-field`}>
            <input
              type="date"
              className={INPUT_CLASS}
              value={executionDate}
              onChange={(e) => setExecutionDate(e.target.value)}
              data-testid={`${id}-date`}
            />
          </Field>
        </div>
        <div>
          <Button
            isDisabled={create.isPending || chosen.length === 0}
            onPress={() =>
              create.mutate({
                clubId,
                data: { claim_ids: chosen.map((claim) => claim.id), execution_date: executionDate || null },
              })
            }
            data-testid={`${id}-create`}
          >
            {t("bankRun.create")}
          </Button>
        </div>
        <Message
          success={create.isSuccess ? t("bankRun.created") : null}
          error={create.error ? errorText(create.error) : downloadError}
          testId={`${id}-message`}
        />
      </div>
    </Section>
  );
}

function focusAccount(clubId: number) {
  const input = document.getElementById(`reimbursements-club-${clubId}-account-holder`);
  input?.scrollIntoView({ behavior: "smooth", block: "center" });
  input?.focus();
}

/** A run at the bank: download it again, mark it booked, or mark one transfer returned. */
function OpenRun({ run }: { run: RunOut }) {
  const { t } = useTranslation("space");
  const id = `reimbursements-run-${run.id}`;
  const refresh = useMoneyRefresh();
  const settle = useSettlePaymentRun({ mutation: { onSuccess: refresh } });
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const download = (url: string, name: string) =>
    downloadFile(url, name).then(
      () => setDownloadError(null),
      (error) => setDownloadError(errorText(error)),
    );

  return (
    <Section
      title={t("bankRun.runTitle", { date: formatDate(run.execution_date), amount: formatMoney(run.total_cents) })}
      testId={id}
    >
      <p className="text-sm text-slate-600">{t("bankRun.runHint")}</p>
      <div className="flex flex-col gap-3">
        <p className="break-all text-xs text-slate-500" data-testid={`${id}-message-id`}>
          {t("bankRun.messageId", { id: run.message_id })}
        </p>
        <ul className="flex flex-col gap-2" data-testid={`${id}-payments`}>
          {run.payments.map((payment) => (
            <RunPayment key={payment.id} payment={payment} runId={run.id} />
          ))}
        </ul>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            onPress={() => download(getDownloadPaymentRunSepaUrl(run.id), `sepa-${run.message_id}.xml`)}
            data-testid={`${id}-sepa`}
          >
            {t("bankRun.downloadSepa")}
          </Button>
          <Button
            variant="outline"
            onPress={() => download(getDownloadPaymentRunXlsxUrl(run.id), `payment-run-${run.id}.xlsx`)}
            data-testid={`${id}-xlsx`}
          >
            {t("bankRun.downloadXlsx")}
          </Button>
          <Button
            isDisabled={settle.isPending}
            onPress={() => settle.mutate({ runId: run.id, data: null })}
            data-testid={`${id}-settle`}
          >
            {t("bankRun.settle")}
          </Button>
        </div>
        <Message
          error={settle.error ? errorText(settle.error) : downloadError}
          testId={`${id}-message`}
        />
      </div>
    </Section>
  );
}

function RunPayment({ payment, runId }: { payment: RunPaymentOut; runId: number }) {
  const { t } = useTranslation("space");
  const id = `reimbursements-run-${runId}-payment-${payment.id}`;
  const refresh = useMoneyRefresh();
  const fail = useFailPayment({ mutation: { onSuccess: refresh } });
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");

  return (
    <li className="flex flex-col gap-2 rounded-lg bg-slate-50 p-3 text-sm" data-testid={id} data-status={payment.status}>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="font-medium">{payment.payee_name}</span>
        <span className="break-all text-slate-500">{payment.iban}</span>
        <span className="ml-auto tabular-nums">{formatMoney(payment.amount_cents)}</span>
      </div>
      <p className="text-xs text-slate-500">
        {t(`bankRun.paymentStatus.${payment.status}`)}
        {payment.failure_reason ? ` — ${payment.failure_reason}` : ""}
      </p>
      {payment.status === "issued" &&
        (open ? (
          <div className="flex flex-col gap-2">
            <Field label={t("bankRun.returnReason")} hint={t("bankRun.returnReasonHint")} testId={`${id}-reason-field`}>
              <input
                className={INPUT_CLASS}
                value={reason}
                maxLength={200}
                onChange={(e) => setReason(e.target.value)}
                data-testid={`${id}-reason`}
              />
            </Field>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="danger"
                isDisabled={fail.isPending || !reason.trim()}
                onPress={() => fail.mutate({ paymentId: payment.id, data: { reason: reason.trim() } })}
                data-testid={`${id}-fail`}
              >
                {t("bankRun.markReturned")}
              </Button>
              <Button variant="ghost" onPress={() => setOpen(false)} data-testid={`${id}-cancel`}>
                {t("bankRun.cancel")}
              </Button>
            </div>
            <Message error={fail.error ? errorText(fail.error) : null} testId={`${id}-message`} />
          </div>
        ) : (
          <div>
            <Button size="sm" variant="ghost" onPress={() => setOpen(true)} data-testid={`${id}-returned`}>
              {t("bankRun.returned")}
            </Button>
          </div>
        ))}
    </li>
  );
}

/** The year's claims as a spreadsheet, for the club's cash audit. */
function Books({ clubId }: { clubId: number }) {
  const { t } = useTranslation("space");
  const id = `reimbursements-club-${clubId}-books`;
  const thisYear = new Date().getFullYear();
  const [year, setYear] = useState(thisYear);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const download = () => {
    setBusy(true);
    downloadFile(getDownloadClubClaimsXlsxUrl(clubId, { year }), `claims-${clubId}-${year}.xlsx`)
      .then(
        () => setError(null),
        (failure) => setError(errorText(failure)),
      )
      .finally(() => setBusy(false));
  };

  return (
    <Section title={t("bankRun.booksTitle")} testId={id}>
      <p className="text-sm text-slate-600">{t("bankRun.booksHint")}</p>
      <div className="flex flex-wrap items-end gap-3">
        <div className="w-32">
          <Field label={t("bankRun.year")} testId={`${id}-year-field`}>
            <select
              className={INPUT_CLASS}
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              data-testid={`${id}-year`}
            >
              {[0, 1, 2, 3, 4].map((back) => (
                <option key={back} value={thisYear - back}>
                  {thisYear - back}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <Button variant="outline" isDisabled={busy} onPress={download} data-testid={`${id}-download`}>
          {t("bankRun.downloadBooks")}
        </Button>
      </div>
      <Message error={error} testId={`${id}-message`} />
    </Section>
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
  return {
    mutation: { onSuccess: () => invalidate("/api/claims", "/api/me/claims", "/api/payment-runs") },
  };
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
      <p className="text-xs text-slate-500">{t("pending.payByHandHint")}</p>
      <p className="text-sm font-medium tabular-nums">{formatMoney(claim.approved_cents - claim.paid_cents)}</p>
      <GiroCode claimId={claim.id} />
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

/** The claim as a GiroCode (Story F-8): scanned with a banking app's photo transfer, it
 *  fills in payee, IBAN, amount and line — the app's own TAN pays, and "Mark as paid"
 *  records it. Fetched with the token, as a plain `<img src>` would not send it. */
function GiroCode({ claimId }: { claimId: number }) {
  const { t } = useTranslation("space");
  const id = `reimbursements-claim-${claimId}-girocode`;
  const [shown, setShown] = useState(false);
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (!shown) return;
    let objectUrl: string | null = null;
    let live = true;
    fetchFileUrl(getGetClaimGirocodeUrl(claimId))
      .then((made) => {
        objectUrl = made;
        if (live) setUrl(made);
        else URL.revokeObjectURL(made);
      })
      .catch((caught: unknown) => live && setError(caught));
    return () => {
      live = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [shown, claimId]);

  if (!shown) {
    return (
      <div>
        <Button variant="secondary" size="sm" onPress={() => setShown(true)} data-testid={`${id}-show`}>
          {t("pending.girocodeShow")}
        </Button>
      </div>
    );
  }
  return (
    <div className="flex flex-col items-start gap-2" data-testid={id}>
      {url && (
        <img
          src={url}
          alt={t("pending.girocodeAlt")}
          className="size-48 rounded-md bg-white p-1"
          data-testid={`${id}-image`}
        />
      )}
      <p className="text-xs text-slate-500">{t("pending.girocodeHint")}</p>
      <Message error={error ? errorText(error) : null} testId={`${id}-message`} />
    </div>
  );
}
