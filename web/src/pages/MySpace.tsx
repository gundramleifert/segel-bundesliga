import { Button } from "@heroui/react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { DocumentKind } from "../api/generated/model/documentKind";
import { ExpenseKind } from "../api/generated/model/expenseKind";
import {
  getGetDocumentFileUrl,
  useAddClaimItem,
  useCreateClaim,
  useDeleteClaim,
  useDeleteClaimDocument,
  useDeleteClaimItem,
  useDeleteMyBankAccount,
  useDeleteMyDocument,
  useGetMyBankAccount,
  useListMyClaimTargets,
  useListMyClaims,
  useListMyDocuments,
  useSaveMyBankAccount,
  useSubmitClaim,
  useUploadClaimDocument,
  useUploadMyDocument,
  useWithdrawClaim,
} from "../api/generated/sbl";
import type { BankAccount, Claim, ClaimTarget, PersonalDocument } from "../api/types";
import { useAccount, useAsync, useInvalidate } from "../api/useApi";
import { Async } from "../components/Async";
import { PageHeader } from "../components/Blocks";
import { ClaimItems, ClaimReceipts, ClaimStatusBadge, ClaimSummary } from "../components/ClaimParts";
import { Field, Message, Section } from "../components/Form";
import { Stack } from "../components/Layouts";
import { FileDropzone } from "../components/FileDropzone";
import { ExpiredBadge } from "../components/PersonDocuments";
import { TabbedView } from "../components/Tabs";
import { INPUT_CLASS, errorText } from "../lib/admin";
import { openFile } from "../lib/files";
import { formatDate, formatMoney, parseCents } from "../lib/format";

/** My space — a signed-in person's own corner (Stories S-5, S-6, F-2, F-5).
 *
 * Three things that belong to the account rather than to a sailor record: the papers
 * someone may be asked for, the bank account their costs go back to, and the claims they
 * filed. A helper or a jury member may never have sailed in a result, so none of this
 * hangs off the profile page.
 */
export function MySpace() {
  const { t } = useTranslation("space");
  const { account, loading } = useAccount();

  return (
    <Stack gap={6} testId="my-space">
      <PageHeader title={t("title")} />
      {!loading && !account ? (
        <p data-testid="my-space-not-signed-in" className="text-slate-600">
          {t("notSignedIn")}
        </p>
      ) : account ? (
        <TabbedView
          param="tab"
          testIdPrefix="my-space"
          label={t("tabsLabel")}
          tabs={[
            { key: "documents", label: t("tabs.documents"), render: () => <DocumentsTab /> },
            { key: "bank", label: t("tabs.bank"), render: () => <BankTab /> },
            { key: "claims", label: t("tabs.claims"), render: () => <ClaimsTab /> },
          ]}
        />
      ) : null}
    </Stack>
  );
}

// ------------------------------------------------------------------ documents (S-5)

function DocumentsTab() {
  const { t } = useTranslation("space");
  const documents = useAsync(useListMyDocuments());

  return (
    <Stack gap={6}>
      <Section title={t("documents.title")} testId="my-space-documents">
        <p className="text-sm text-slate-600">{t("documents.hint")}</p>
        <Async state={documents} testId="my-space-documents" empty={t("documents.empty")}>
          {(rows) => (
            <ul
              data-testid="my-space-documents-list"
              className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white px-3 text-sm"
            >
              {rows.map((doc) => (
                <DocumentRow key={doc.id} doc={doc} />
              ))}
            </ul>
          )}
        </Async>
      </Section>
      <UploadDocument />
    </Stack>
  );
}

function DocumentRow({ doc }: { doc: PersonalDocument }) {
  const { t } = useTranslation("space");
  const invalidate = useInvalidate();
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const remove = useDeleteMyDocument({ mutation: { onSuccess: () => invalidate("/api/me/documents") } });

  return (
    <li data-testid={`my-space-document-${doc.id}`} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2">
      <span className="min-w-0 flex-1">
        <span className="font-medium">{t(`kinds.${doc.kind}`)}</span>
        {doc.title && <> · {doc.title}</>}
        <span className="block text-xs text-slate-500">
          {doc.original_name}
          {doc.valid_until && ` · ${t("documents.validUntil", { date: formatDate(doc.valid_until) })}`}
        </span>
      </span>
      {doc.expired && <ExpiredBadge testId={`my-space-document-expired-${doc.id}`} />}
      <Button
        size="sm"
        variant="ghost"
        onPress={() => openFile(getGetDocumentFileUrl(doc.id)).catch((err) => setError(errorText(err)))}
        data-testid={`my-space-document-open-${doc.id}`}
      >
        {t("documents.open")}
      </Button>
      {confirming ? (
        <>
          <Button
            size="sm"
            variant="danger"
            isDisabled={remove.isPending}
            onPress={() => remove.mutate({ documentId: doc.id })}
            data-testid={`my-space-document-delete-confirm-${doc.id}`}
          >
            {t("documents.deleteConfirm")}
          </Button>
          <Button size="sm" variant="ghost" onPress={() => setConfirming(false)}>
            {t("documents.cancel")}
          </Button>
        </>
      ) : (
        <Button
          size="sm"
          variant="outline"
          onPress={() => setConfirming(true)}
          data-testid={`my-space-document-delete-${doc.id}`}
        >
          {t("documents.delete")}
        </Button>
      )}
      {(error || remove.error) && (
        <p className="w-full text-sm text-red-700">{error ?? errorText(remove.error)}</p>
      )}
    </li>
  );
}

function UploadDocument() {
  const { t } = useTranslation("space");
  const invalidate = useInvalidate();
  const [kind, setKind] = useState<DocumentKind>(DocumentKind.boat_licence_sea);
  const [title, setTitle] = useState("");
  const [validUntil, setValidUntil] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const upload = useUploadMyDocument({
    mutation: {
      onSuccess: () => {
        setTitle("");
        setValidUntil("");
        setFile(null);
        invalidate("/api/me/documents");
      },
    },
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!file) return;
    upload.mutate({
      data: { file, kind, title: title.trim() || null, valid_until: validUntil || null },
    });
  };

  return (
    <Section title={t("documents.uploadTitle")} testId="my-space-document-upload">
      <form onSubmit={submit} className="flex flex-col gap-3">
        <Field label={t("documents.kindLabel")} testId="my-space-document-kind-field">
          <select
            className={INPUT_CLASS}
            value={kind}
            onChange={(e) => setKind(e.target.value as DocumentKind)}
            data-testid="my-space-document-kind"
          >
            {Object.values(DocumentKind).map((value) => (
              <option key={value} value={value}>
                {t(`kinds.${value}`)}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("documents.titleLabel")} hint={t("documents.titleHint")} testId="my-space-document-title-field">
          <input
            className={INPUT_CLASS}
            value={title}
            maxLength={200}
            required={kind === DocumentKind.other}
            onChange={(e) => setTitle(e.target.value)}
            data-testid="my-space-document-title"
          />
        </Field>
        <Field
          label={t("documents.validUntilLabel")}
          hint={t("documents.validUntilHint")}
          testId="my-space-document-valid-until-field"
        >
          <input
            type="date"
            className={INPUT_CLASS}
            value={validUntil}
            onChange={(e) => setValidUntil(e.target.value)}
            data-testid="my-space-document-valid-until"
          />
        </Field>
        <Field label={t("documents.fileLabel")} hint={t("documents.fileHint")} testId="my-space-document-file-field">
          <FileDropzone
            accept="application/pdf,image/jpeg,image/png"
            selected={file}
            onFile={setFile}
            testId="my-space-document-file"
          />
        </Field>
        <div>
          <Button type="submit" isDisabled={!file || upload.isPending} data-testid="my-space-document-submit">
            {t("documents.upload")}
          </Button>
        </div>
        <Message
          success={upload.isSuccess ? t("documents.uploaded") : null}
          error={upload.error ? errorText(upload.error) : null}
          testId="my-space-document-upload-message"
        />
      </form>
    </Section>
  );
}

// ------------------------------------------------------------------ bank account (S-6)

function BankTab() {
  const { t } = useTranslation("space");
  const account = useAsync(useGetMyBankAccount());

  return (
    <Section title={t("bank.title")} testId="my-space-bank">
      <p className="text-sm text-slate-600">{t("bank.hint")}</p>
      {/* `null` is a real answer here — no account saved yet — so the form is drawn for it
          too; only loading and error are Async's to handle. */}
      {account.loading || account.error ? (
        <Async state={account} testId="my-space-bank">
          {() => null}
        </Async>
      ) : (
        <BankForm key={account.data?.iban ?? "none"} saved={account.data} />
      )}
    </Section>
  );
}

function BankForm({ saved }: { saved: BankAccount | null }) {
  const { t } = useTranslation("space");
  const invalidate = useInvalidate();
  const [holder, setHolder] = useState(saved?.holder ?? "");
  const [iban, setIban] = useState(saved?.iban ?? "");
  const [bic, setBic] = useState(saved?.bic ?? "");
  const [done, setDone] = useState<string | null>(null);
  const refresh = () => invalidate("/api/me/bank-account");
  const save = useSaveMyBankAccount({
    mutation: {
      onSuccess: () => {
        setDone(t("bank.saved"));
        refresh();
      },
    },
  });
  const remove = useDeleteMyBankAccount({
    mutation: {
      onSuccess: () => {
        setDone(t("bank.deleted"));
        refresh();
      },
    },
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setDone(null);
    save.mutate({ data: { holder: holder.trim(), iban, bic: bic.trim() || null } });
  };

  const error = save.error ?? remove.error;
  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <Field label={t("bank.holderLabel")} testId="my-space-bank-holder-field">
        <input
          className={INPUT_CLASS}
          value={holder}
          required
          maxLength={160}
          autoComplete="name"
          onChange={(e) => setHolder(e.target.value)}
          data-testid="my-space-bank-holder"
        />
      </Field>
      <Field label={t("bank.ibanLabel")} testId="my-space-bank-iban-field">
        <input
          className={`${INPUT_CLASS} font-mono`}
          value={iban}
          required
          minLength={15}
          maxLength={50}
          spellCheck={false}
          onChange={(e) => setIban(e.target.value)}
          data-testid="my-space-bank-iban"
        />
      </Field>
      <Field label={t("bank.bicLabel")} hint={t("bank.bicHint")} testId="my-space-bank-bic-field">
        <input
          className={`${INPUT_CLASS} font-mono`}
          value={bic}
          maxLength={11}
          spellCheck={false}
          onChange={(e) => setBic(e.target.value)}
          data-testid="my-space-bank-bic"
        />
      </Field>
      <div className="flex flex-wrap gap-2">
        <Button type="submit" isDisabled={save.isPending} data-testid="my-space-bank-save">
          {t("bank.save")}
        </Button>
        {saved && (
          <Button
            variant="outline"
            isDisabled={remove.isPending}
            onPress={() => {
              setDone(null);
              remove.mutate();
            }}
            data-testid="my-space-bank-delete"
          >
            {t("bank.delete")}
          </Button>
        )}
      </div>
      <Message success={done} error={error ? errorText(error) : null} testId="my-space-bank-message" />
    </form>
  );
}

// ------------------------------------------------------------------ claims (F-2, F-5)

function ClaimsTab() {
  const { t } = useTranslation("space");
  const claims = useAsync(useListMyClaims());
  const [openId, setOpenId] = useState<number | null>(null);

  return (
    <Stack gap={6}>
      <NewClaim onCreated={setOpenId} />
      <Section title={t("claims.listTitle")} testId="my-space-claims">
        <Async state={claims} testId="my-space-claims" empty={t("claims.empty")}>
          {(rows) => (
            <ul data-testid="my-space-claims-list" className="flex flex-col gap-3">
              {rows.map((claim) => (
                <ClaimCard
                  key={claim.id}
                  claim={claim}
                  open={openId === claim.id}
                  onToggle={() => setOpenId(openId === claim.id ? null : claim.id)}
                />
              ))}
            </ul>
          )}
        </Async>
      </Section>
    </Stack>
  );
}

function targetKey(target: Pick<ClaimTarget, "kind" | "id">): string {
  return `${target.kind}:${target.id}`;
}

function NewClaim({ onCreated }: { onCreated: (id: number) => void }) {
  const { t } = useTranslation("space");
  const invalidate = useInvalidate();
  const targets = useAsync(useListMyClaimTargets());
  const [chosen, setChosen] = useState("");
  const [title, setTitle] = useState("");
  const create = useCreateClaim({
    mutation: {
      onSuccess: (claim) => {
        setTitle("");
        invalidate("/api/me/claims");
        onCreated(claim.id);
      },
    },
  });

  return (
    <Section title={t("claims.newTitle")} testId="my-space-claim-new">
      <p className="text-sm text-slate-600">{t("claims.newHint")}</p>
      <Async state={targets} testId="my-space-claim-targets" empty={t("claims.noTargets")}>
        {(rows) => {
          const target = rows.find((row) => targetKey(row) === chosen) ?? rows[0];
          const events = rows.filter((row) => row.kind === "event");
          const clubs = rows.filter((row) => row.kind === "club");
          const submit = (e: FormEvent) => {
            e.preventDefault();
            create.mutate({
              data: {
                title: title.trim(),
                event_id: target.kind === "event" ? target.id : null,
                club_id: target.kind === "club" ? target.id : null,
              },
            });
          };
          return (
            <form onSubmit={submit} className="flex flex-col gap-3">
              <Field label={t("claims.targetLabel")} testId="my-space-claim-target-field">
                <select
                  className={INPUT_CLASS}
                  value={targetKey(target)}
                  onChange={(e) => setChosen(e.target.value)}
                  data-testid="my-space-claim-target"
                >
                  {events.length > 0 && (
                    <optgroup label={t("claims.targetEvents")}>
                      {events.map((row) => (
                        <option key={targetKey(row)} value={targetKey(row)}>
                          {row.starts_on ? `${row.name} (${formatDate(row.starts_on)})` : row.name}
                        </option>
                      ))}
                    </optgroup>
                  )}
                  {clubs.length > 0 && (
                    <optgroup label={t("claims.targetClubs")}>
                      {clubs.map((row) => (
                        <option key={targetKey(row)} value={targetKey(row)}>
                          {row.name}
                        </option>
                      ))}
                    </optgroup>
                  )}
                </select>
              </Field>
              <Field label={t("claims.titleLabel")} testId="my-space-claim-title-field">
                <input
                  className={INPUT_CLASS}
                  value={title}
                  required
                  maxLength={200}
                  placeholder={t("claims.titlePlaceholder")}
                  onChange={(e) => setTitle(e.target.value)}
                  data-testid="my-space-claim-title"
                />
              </Field>
              <div>
                <Button type="submit" isDisabled={create.isPending} data-testid="my-space-claim-create">
                  {t("claims.create")}
                </Button>
              </div>
              <Message error={create.error ? errorText(create.error) : null} testId="my-space-claim-new-message" />
            </form>
          );
        }}
      </Async>
    </Section>
  );
}

function ClaimCard({ claim, open, onToggle }: { claim: Claim; open: boolean; onToggle: () => void }) {
  const { t } = useTranslation("space");
  return (
    <li
      data-testid={`my-space-claim-${claim.id}`}
      className="rounded-lg border border-slate-200 bg-white p-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium">{claim.title}</p>
          <ClaimSummary claim={claim} />
        </div>
        <ClaimStatusBadge claim={claim} testId={`my-space-claim-status-${claim.id}`} />
        <Button size="sm" variant="ghost" onPress={onToggle} data-testid={`my-space-claim-toggle-${claim.id}`}>
          {open ? t("claims.close") : t("claims.open")}
        </Button>
      </div>
      {claim.decision_note && (claim.status === "returned" || claim.status === "rejected") && (
        <p className="mt-2 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-900" data-testid={`my-space-claim-note-${claim.id}`}>
          {t("claims.decisionNote", { note: claim.decision_note })}
        </p>
      )}
      {open && <ClaimDetail claim={claim} />}
    </li>
  );
}

/** One claim, opened: its items and receipts, and — while it is the claimant's to change
 *  (`may_edit`: a draft, or returned) — the forms that change them and the way to submit. */
function ClaimDetail({ claim }: { claim: Claim }) {
  const { t } = useTranslation("space");
  const invalidate = useInvalidate();
  const id = `my-space-claim-${claim.id}`;
  const refresh = { mutation: { onSuccess: () => invalidate("/api/me/claims", "/api/claims") } };
  const removeItem = useDeleteClaimItem(refresh);
  const removeReceipt = useDeleteClaimDocument(refresh);
  const submit = useSubmitClaim(refresh);
  const withdraw = useWithdrawClaim(refresh);
  const remove = useDeleteClaim(refresh);
  const editable = claim.may_edit;
  const withdrawable = ["draft", "submitted", "returned"].includes(claim.status);
  const error = removeItem.error ?? removeReceipt.error ?? submit.error ?? withdraw.error ?? remove.error;

  return (
    <div className="mt-4 flex flex-col gap-4" data-testid={`${id}-detail`}>
      {claim.payer_club_name && <p className="text-sm text-slate-600">{t("claims.payer", { club: claim.payer_club_name })}</p>}

      <div className="flex flex-col gap-2">
        <h4 className="text-sm font-semibold">{t("claims.itemsTitle")}</h4>
        {claim.items.length > 0 && (
          <ClaimItems
            claim={claim}
            testId={id}
            end={
              editable
                ? (item) => (
                    <button
                      type="button"
                      className="text-xs text-slate-500 hover:text-red-700"
                      disabled={removeItem.isPending}
                      onClick={() => removeItem.mutate({ claimId: claim.id, itemId: item.id })}
                      data-testid={`${id}-item-remove-${item.id}`}
                    >
                      {t("claims.removeItem")}
                    </button>
                  )
                : undefined
            }
          />
        )}
        {editable && <AddItem claim={claim} />}
      </div>

      <div className="flex flex-col gap-2">
        <h4 className="text-sm font-semibold">{t("claims.receiptsTitle")}</h4>
        <ClaimReceipts
          claim={claim}
          testId={id}
          onRemove={editable ? (documentId) => removeReceipt.mutate({ claimId: claim.id, documentId }) : undefined}
        />
        {editable && <UploadReceipt claim={claim} />}
      </div>

      <div className="flex flex-wrap gap-2">
        {editable && (
          <Button
            isDisabled={submit.isPending}
            onPress={() => submit.mutate({ claimId: claim.id })}
            data-testid={`${id}-submit`}
          >
            {t("claims.submit")}
          </Button>
        )}
        {withdrawable && claim.status !== "draft" && (
          <Button
            variant="outline"
            isDisabled={withdraw.isPending}
            onPress={() => withdraw.mutate({ claimId: claim.id })}
            data-testid={`${id}-withdraw`}
          >
            {t("claims.withdraw")}
          </Button>
        )}
        {claim.status === "draft" && (
          <Button
            variant="danger"
            isDisabled={remove.isPending}
            onPress={() => remove.mutate({ claimId: claim.id })}
            data-testid={`${id}-delete`}
          >
            {t("claims.deleteDraft")}
          </Button>
        )}
      </div>
      <Message
        success={submit.isSuccess ? t("claims.submitted") : null}
        error={error ? errorText(error) : null}
        testId={`${id}-message`}
      />
    </div>
  );
}

function AddItem({ claim }: { claim: Claim }) {
  const { t } = useTranslation("space");
  const invalidate = useInvalidate();
  const id = `my-space-claim-${claim.id}-add`;
  const [kind, setKind] = useState<ExpenseKind>(ExpenseKind.travel_car);
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [description, setDescription] = useState("");
  const [distance, setDistance] = useState("");
  const [amount, setAmount] = useState("");
  const add = useAddClaimItem({
    mutation: {
      onSuccess: () => {
        setDescription("");
        setDistance("");
        setAmount("");
        invalidate("/api/me/claims", "/api/claims");
      },
    },
  });
  const car = kind === ExpenseKind.travel_car;
  const cents = parseCents(amount);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    add.mutate({
      claimId: claim.id,
      data: {
        kind,
        incurred_on: date,
        description: description.trim(),
        distance_km: car ? Number(distance) : null,
        amount_cents: car ? null : cents,
      },
    });
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-3 rounded-lg bg-slate-50 p-3" data-testid={id}>
      <p className="text-sm font-medium">{t("claims.addItemTitle")}</p>
      <div className="flex flex-wrap gap-3">
        <div className="min-w-40 flex-1">
          <Field label={t("claims.kindLabel")} testId={`${id}-kind-field`}>
            <select
              className={INPUT_CLASS}
              value={kind}
              onChange={(e) => setKind(e.target.value as ExpenseKind)}
              data-testid={`${id}-kind`}
            >
              {Object.values(ExpenseKind).map((value) => (
                <option key={value} value={value}>
                  {t(`itemKinds.${value}`)}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <div className="min-w-40 flex-1">
          <Field label={t("claims.dateLabel")} testId={`${id}-date-field`}>
            <input
              type="date"
              className={INPUT_CLASS}
              value={date}
              required
              onChange={(e) => setDate(e.target.value)}
              data-testid={`${id}-date`}
            />
          </Field>
        </div>
      </div>
      <Field label={t("claims.descriptionLabel")} testId={`${id}-description-field`}>
        <input
          className={INPUT_CLASS}
          value={description}
          required
          maxLength={300}
          onChange={(e) => setDescription(e.target.value)}
          data-testid={`${id}-description`}
        />
      </Field>
      {car ? (
        <Field label={t("claims.distanceLabel")} testId={`${id}-distance-field`}>
          <input
            type="number"
            inputMode="numeric"
            min={1}
            max={10000}
            className={INPUT_CLASS}
            value={distance}
            required
            onChange={(e) => setDistance(e.target.value)}
            data-testid={`${id}-distance`}
          />
        </Field>
      ) : (
        <Field label={t("claims.amountLabel")} testId={`${id}-amount-field`}>
          <input
            inputMode="decimal"
            className={INPUT_CLASS}
            value={amount}
            required
            placeholder="0,00"
            onChange={(e) => setAmount(e.target.value)}
            aria-invalid={amount !== "" && cents === null}
            data-testid={`${id}-amount`}
          />
        </Field>
      )}
      <div>
        <Button
          type="submit"
          size="sm"
          isDisabled={add.isPending || (!car && cents === null)}
          data-testid={`${id}-submit`}
        >
          {t("claims.addItem")}
        </Button>
      </div>
      <Message error={add.error ? errorText(add.error) : null} testId={`${id}-message`} />
    </form>
  );
}

function UploadReceipt({ claim }: { claim: Claim }) {
  const { t } = useTranslation("space");
  const invalidate = useInvalidate();
  const id = `my-space-claim-${claim.id}-receipt`;
  const [itemId, setItemId] = useState("");
  const upload = useUploadClaimDocument({
    mutation: {
      onSuccess: () => {
        invalidate("/api/me/claims", "/api/claims");
      },
    },
  });

  return (
    <div className="flex flex-col gap-2 rounded-lg bg-slate-50 p-3" data-testid={id}>
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-40 flex-1">
          <Field label={t("claims.receiptFor")} testId={`${id}-item-field`}>
            <select
              className={INPUT_CLASS}
              value={itemId}
              onChange={(e) => setItemId(e.target.value)}
              data-testid={`${id}-item`}
            >
              <option value="">{t("claims.receiptWholeClaim")}</option>
              {claim.items.map((item) => (
                <option key={item.id} value={String(item.id)}>
                  {`${t(`itemKinds.${item.kind}`)} · ${item.description} · ${formatMoney(item.amount_cents)}`}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <div className="min-w-40 flex-1">
          <Field label={t("claims.uploadReceipt")} hint={t("documents.fileHint")} testId={`${id}-file-field`}>
            <FileDropzone
              accept="application/pdf,image/jpeg,image/png"
              disabled={upload.isPending}
              onFile={(file) =>
                upload.mutate({
                  claimId: claim.id,
                  data: { file, item_id: itemId ? Number(itemId) : null },
                })
              }
              testId={`${id}-file`}
            />
          </Field>
        </div>
      </div>
      <Message error={upload.error ? errorText(upload.error) : null} testId={`${id}-message`} />
    </div>
  );
}
