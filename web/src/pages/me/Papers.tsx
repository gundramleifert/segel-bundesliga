import { Button } from "@heroui/react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

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
  useUpdateClaimItem,
  useUploadClaimDocument,
  useUploadMyDocument,
  useWithdrawClaim,
} from "../../api/generated/sbl";
import {
  ClaimStatus,
  type ClaimItem,
  DocumentKind,
  ExpenseKind,
  type BankAccount,
  type Claim,
  type ClaimTarget,
  type PersonalDocument,
  type UnavailableEvent,
  UnclaimableReason,
} from "../../api/types";
import { useAsync, useInvalidate } from "../../api/useApi";
import { Async } from "../../components/Async";
import { ClaimItems, ClaimReceipts, ClaimStatusBadge, ClaimSummary } from "../../components/ClaimParts";
import { ConfirmButton } from "../../components/ConfirmButton";
import { Field, Message, Section } from "../../components/Form";
import { Stack } from "../../components/Layouts";
import { FileDropzone } from "../../components/FileDropzone";
import { ExpiredBadge } from "../../components/PersonDocuments";
import { INPUT_CLASS, errorText } from "../../lib/admin";
import { openFile } from "../../lib/files";
import { centsText, formatDate, parseCents, todayIso } from "../../lib/format";
import { Select } from "../../components/Select";

/** The papers of my space (Stories S-5, S-6, F-2, F-5): documents and licences, the bank
 * account costs go back to, and claims. Sections of `/me/profile` — and the claims, with
 * a fixed target, of an event's or a club's page (Story S-7).
 *
 * All three belong to the account rather than to a sailor record: a helper or a jury
 * member may never have sailed in a result.
 */

/** Where a claim is filed: an event, or a club. */
type ClaimTargetRef = { kind: "event" | "club"; id: number };

// ------------------------------------------------------------------ documents (S-5)

export function DocumentsTab() {
  const { t } = useTranslation("space");
  const documents = useAsync(useListMyDocuments());

  return (
    <Stack gap={6}>
      <Section title={t("documents.title")} testId="my-space-documents">
        <p className="text-sm text-muted">{t("documents.hint")}</p>
        <Async state={documents} testId="my-space-documents" empty={t("documents.empty")}>
          {(rows) => (
            <ul
              data-testid="my-space-documents-list"
              className="divide-y divide-separator rounded-lg border border-separator bg-surface px-3 text-sm"
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
  const [error, setError] = useState<string | null>(null);
  const remove = useDeleteMyDocument({ mutation: { onSuccess: () => invalidate("/api/me/documents", "/api/me/contexts") } });

  return (
    <li data-testid={`my-space-document-${doc.id}`} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2">
      <span className="min-w-0 flex-1">
        <span className="font-medium">{t(`kinds.${doc.kind}`)}</span>
        {doc.title && <> · {doc.title}</>}
        <span className="block text-xs text-muted">
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
      <ConfirmButton
        size="sm"
        label={t("documents.delete")}
        confirmLabel={t("documents.deleteConfirm")}
        cancelLabel={t("documents.cancel")}
        busy={remove.isPending}
        onConfirm={() => remove.mutate({ documentId: doc.id })}
        testId={`my-space-document-delete-${doc.id}`}
      />
      {(error || remove.error) && (
        <p className="w-full text-sm text-danger">{error ?? errorText(remove.error)}</p>
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
        invalidate("/api/me/documents", "/api/me/contexts");
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
          <Select
            value={kind}
            onChange={(e) => setKind(e.target.value as DocumentKind)}
            testId="my-space-document-kind"
          >
            {Object.values(DocumentKind).map((value) => (
              <option key={value} value={value}>
                {t(`kinds.${value}`)}
              </option>
            ))}
          </Select>
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

export function BankTab() {
  const { t } = useTranslation("space");
  const account = useAsync(useGetMyBankAccount());

  return (
    <Section title={t("bank.title")} testId="my-space-bank">
      <p className="text-sm text-muted">{t("bank.hint")}</p>
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

/** My claims — all of them, or (with `target`) those on one event or club, where a new
 *  one is then filed without asking where. */
export function ClaimsTab({ target }: { target?: ClaimTargetRef }) {
  const { t } = useTranslation("space");
  const claims = useAsync(useListMyClaims());
  const [openId, setOpenId] = useState<number | null>(null);
  const mine = (rows: Claim[]) =>
    target
      ? rows.filter((claim) =>
          target.kind === "event" ? claim.event_id === target.id : claim.event_id == null && claim.club_id === target.id,
        )
      : rows;

  return (
    <Stack gap={6}>
      <NewClaim onCreated={setOpenId} target={target} />
      <Section title={t("claims.listTitle")} testId="my-space-claims">
        <Async state={claims} testId="my-space-claims" empty={t("claims.empty")}>
          {(all) => {
            const rows = mine(all);
            return rows.length ? (
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
            ) : (
              <p className="text-sm text-muted" data-testid="my-space-claims-none">
                {t("claims.empty")}
              </p>
            );
          }}
        </Async>
      </Section>
    </Stack>
  );
}

function targetKey(target: Pick<ClaimTarget, "kind" | "id">): string {
  return `${target.kind}:${target.id}`;
}

/** The events I work at but cannot claim on yet — what I am there and why, in words
 *  (Story F-2). One line each: "You are on the jury at Act 3 Friedrichshafen, but it has no
 *  host club yet …". The first relation names the work; most people hold one. */
function UnavailableNotes({ events }: { events: UnavailableEvent[] }) {
  const { t } = useTranslation("space");
  return (
    <ul className="flex flex-col gap-2" data-testid="my-space-claim-unavailable">
      {events.map((event) => (
        <li
          key={event.id}
          className="rounded-md bg-warning-soft px-3 py-2 text-sm text-warning-soft-foreground"
          data-testid={`my-space-claim-unavailable-${event.id}`}
        >
          {t("claims.unavailable.at", { relation: event.relations[0] ?? "other", event: event.name })}{" "}
          {t(event.reason === UnclaimableReason.no_host_club ? "claims.unavailable.noHostClub" : "claims.unavailable.notCovered")}
        </li>
      ))}
    </ul>
  );
}

function NewClaim({ onCreated, target: fixed }: { onCreated: (id: number) => void; target?: ClaimTargetRef }) {
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
      <p className="text-sm text-muted">{t("claims.newHint")}</p>
      <Async state={targets} testId="my-space-claim-targets">
        {({ targets: all, unavailable }) => {
          // On an event's or a club's page the claim goes there — if it may (the server
          // lists only what I may claim on), else there is nothing to file here.
          const rows = fixed ? all.filter((row) => targetKey(row) === targetKey(fixed)) : all;
          // Where I work but cannot claim, and why — said, never "you hold nothing"
          // (Story F-2). On an event's page, only that event.
          const why = fixed ? unavailable.filter((u) => targetKey({ kind: "event", id: u.id }) === targetKey(fixed)) : unavailable;
          const notes = why.length > 0 && <UnavailableNotes events={why} />;
          if (!rows.length) {
            return (
              notes || (
                <p className="text-sm text-muted" data-testid="my-space-claim-targets-empty">
                  {t("claims.noTargets")}
                </p>
              )
            );
          }
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
            <>
            {notes}
            <form onSubmit={submit} className="flex flex-col gap-3">
              {!fixed && (
              <Field label={t("claims.targetLabel")} testId="my-space-claim-target-field">
                <Select
                  value={targetKey(target)}
                  onChange={(e) => setChosen(e.target.value)}
                  testId="my-space-claim-target"
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
                </Select>
              </Field>
              )}
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
            </>
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
      className="rounded-lg border border-separator bg-surface p-4"
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
      {/* The decider's message stays while the claimant corrects the claim — a change
          makes it a draft, and the message goes only when it is submitted again. */}
      {claim.decision_note && (claim.status === ClaimStatus.rejected || claim.status === ClaimStatus.draft) && (
        <p className="mt-2 rounded-md bg-warning-soft px-3 py-2 text-sm text-warning-soft-foreground" data-testid={`my-space-claim-note-${claim.id}`}>
          {t("claims.decisionNote", { note: claim.decision_note })}
        </p>
      )}
      {open && <ClaimDetail claim={claim} />}
    </li>
  );
}

/** One claim, opened: its items and receipts, and — while it is the claimant's to change
 *  (`may_edit`: until it is approved) — the forms that change them and the way to submit.
 *  A change to a submitted or rejected claim makes it a draft again (Story F-2). */
function ClaimDetail({ claim }: { claim: Claim }) {
  const { t } = useTranslation("space");
  const invalidate = useInvalidate();
  const id = `my-space-claim-${claim.id}`;
  const refresh = { mutation: { onSuccess: () => invalidate("/api/me/claims", "/api/claims", "/api/me/contexts") } };
  const removeItem = useDeleteClaimItem(refresh);
  const removeReceipt = useDeleteClaimDocument(refresh);
  const submit = useSubmitClaim(refresh);
  const withdraw = useWithdrawClaim(refresh);
  const remove = useDeleteClaim(refresh);
  // Which item has its edit form or its receipt upload open, if any.
  const [open, setOpen] = useState<{ item: number; what: "edit" | "receipt" } | null>(null);
  const editable = claim.may_edit;
  const submittable = claim.status === ClaimStatus.draft || claim.status === ClaimStatus.rejected;
  // A claim submitted once stays on record: a change makes it a draft again, but it is
  // withdrawn from then on, never deleted (Story F-2).
  const everSubmitted = claim.submitted_at !== null;
  const withdrawable =
    claim.status === ClaimStatus.submitted ||
    claim.status === ClaimStatus.rejected ||
    (claim.status === ClaimStatus.draft && everSubmitted);
  const deletable = claim.status === ClaimStatus.draft && !everSubmitted;
  const error = removeItem.error ?? removeReceipt.error ?? submit.error ?? withdraw.error ?? remove.error;
  const toggle = (item: number, what: "edit" | "receipt") =>
    setOpen(open?.item === item && open.what === what ? null : { item, what });
  const action = (item: ClaimItem, what: "edit" | "receipt" | "remove", label: string, onClick: () => void) => (
    <button
      type="button"
      className={`text-xs text-muted ${what === "remove" ? "hover:text-danger" : "hover:text-foreground"}`}
      disabled={removeItem.isPending}
      onClick={onClick}
      data-testid={`${id}-item-${what}-${item.id}`}
    >
      {label}
    </button>
  );

  return (
    <div className="mt-4 flex flex-col gap-4" data-testid={`${id}-detail`}>
      {claim.payer_club_name && <p className="text-sm text-muted">{t("claims.payer", { club: claim.payer_club_name })}</p>}
      {editable && claim.status !== ClaimStatus.draft && (
        <p className="text-sm text-muted" data-testid={`${id}-reopen-hint`}>
          {t("claims.reopenHint")}
        </p>
      )}

      <div className="flex flex-col gap-2">
        <h4 className="text-sm font-semibold">{t("claims.itemsTitle")}</h4>
        {claim.items.length > 0 && (
          <ClaimItems
            claim={claim}
            testId={id}
            onRemoveReceipt={editable ? (documentId) => removeReceipt.mutate({ claimId: claim.id, documentId }) : undefined}
            end={
              editable
                ? (item) => (
                    <span className="flex gap-3">
                      {action(item, "receipt", t("claims.itemReceipt"), () => toggle(item.id, "receipt"))}
                      {action(item, "edit", t("claims.editItem"), () => toggle(item.id, "edit"))}
                      {action(item, "remove", t("claims.removeItem"), () =>
                        removeItem.mutate({ claimId: claim.id, itemId: item.id }),
                      )}
                    </span>
                  )
                : undefined
            }
            below={(item) =>
              editable && open?.item === item.id ? (
                open.what === "edit" ? (
                  <ItemForm claim={claim} item={item} onDone={() => setOpen(null)} />
                ) : (
                  <UploadReceipt claim={claim} item={item} onDone={() => setOpen(null)} />
                )
              ) : null
            }
          />
        )}
        {editable && <ItemForm claim={claim} />}
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
        {submittable && (
          <Button
            isDisabled={submit.isPending}
            onPress={() => submit.mutate({ claimId: claim.id })}
            data-testid={`${id}-submit`}
          >
            {t("claims.submit")}
          </Button>
        )}
        {withdrawable && (
          <ConfirmButton
            label={t("claims.withdraw")}
            prompt={t("claims.withdrawPrompt")}
            confirmLabel={t("claims.withdrawConfirm")}
            cancelLabel={t("claims.keep")}
            busy={withdraw.isPending}
            onConfirm={() => withdraw.mutate({ claimId: claim.id })}
            testId={`${id}-withdraw`}
          />
        )}
        {deletable && (
          <ConfirmButton
            label={t("claims.deleteDraft")}
            confirmLabel={t("claims.deleteDraftConfirm")}
            cancelLabel={t("claims.keep")}
            busy={remove.isPending}
            onConfirm={() => remove.mutate({ claimId: claim.id })}
            testId={`${id}-delete`}
          />
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

/** Adds an item — or, with `item`, changes that one. A day, or a range of days (a
 *  hotel's nights); an amount in the reader's own notation ("12,50" or "12.50"), a car
 *  journey in kilometres, which the paying club's rate turns into money. */
function ItemForm({ claim, item, onDone }: { claim: Claim; item?: ClaimItem; onDone?: () => void }) {
  const { t } = useTranslation("space");
  const invalidate = useInvalidate();
  const id = item ? `my-space-claim-${claim.id}-edit-${item.id}` : `my-space-claim-${claim.id}-add`;
  const [kind, setKind] = useState<ExpenseKind>(item?.kind ?? ExpenseKind.travel_car);
  const [date, setDate] = useState(item?.incurred_on ?? todayIso());
  const [until, setUntil] = useState(item?.incurred_until ?? "");
  const [description, setDescription] = useState(item?.description ?? "");
  const [distance, setDistance] = useState(item?.distance_km != null ? String(item.distance_km) : "");
  const [amount, setAmount] = useState(item && item.kind !== ExpenseKind.travel_car ? centsText(item.amount_cents) : "");
  const saved = {
    mutation: {
      onSuccess: () => {
        if (!item) {
          setDescription("");
          setDistance("");
          setAmount("");
          setUntil("");
        }
        invalidate("/api/me/claims", "/api/claims", "/api/me/contexts");
        onDone?.();
      },
    },
  };
  const add = useAddClaimItem(saved);
  const update = useUpdateClaimItem(saved);
  const save = item ? update : add;
  const car = kind === ExpenseKind.travel_car;
  const cents = parseCents(amount);
  const backwards = until !== "" && until < date;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const data = {
      kind,
      incurred_on: date,
      incurred_until: until || null,
      description: description.trim(),
      distance_km: car ? Number(distance) : null,
      amount_cents: car ? null : cents,
    };
    if (item) update.mutate({ claimId: claim.id, itemId: item.id, data });
    else add.mutate({ claimId: claim.id, data });
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-3 rounded-lg bg-surface-secondary p-3" data-testid={id}>
      <p className="text-sm font-medium">{item ? t("claims.editItemTitle") : t("claims.addItemTitle")}</p>
      <div className="flex flex-wrap gap-3">
        <div className="min-w-40 flex-1">
          <Field label={t("claims.kindLabel")} testId={`${id}-kind-field`}>
            <Select
              value={kind}
              onChange={(e) => setKind(e.target.value as ExpenseKind)}
              testId={`${id}-kind`}
            >
              {Object.values(ExpenseKind).map((value) => (
                <option key={value} value={value}>
                  {t(`itemKinds.${value}`)}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        <div className="min-w-36 flex-1">
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
        <div className="min-w-36 flex-1">
          <Field label={t("claims.untilLabel")} hint={t("claims.untilHint")} testId={`${id}-until-field`}>
            <input
              type="date"
              className={INPUT_CLASS}
              value={until}
              min={date}
              onChange={(e) => setUntil(e.target.value)}
              aria-invalid={backwards}
              data-testid={`${id}-until`}
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
            placeholder={centsText(0)}
            onChange={(e) => setAmount(e.target.value)}
            aria-invalid={amount !== "" && cents === null}
            data-testid={`${id}-amount`}
          />
        </Field>
      )}
      <div className="flex flex-wrap gap-2">
        <Button
          type="submit"
          size="sm"
          isDisabled={save.isPending || backwards || (!car && cents === null)}
          data-testid={`${id}-submit`}
        >
          {item ? t("claims.saveItem") : t("claims.addItem")}
        </Button>
        {onDone && (
          <Button size="sm" variant="ghost" onPress={onDone} data-testid={`${id}-cancel`}>
            {t("claims.cancel")}
          </Button>
        )}
      </div>
      <Message error={save.error ? errorText(save.error) : null} testId={`${id}-message`} />
    </form>
  );
}

/** A receipt for one item — or, without `item`, one that covers the whole claim, like a
 *  hotel invoice over several nights and the breakfasts (Story F-5). */
function UploadReceipt({ claim, item, onDone }: { claim: Claim; item?: ClaimItem; onDone?: () => void }) {
  const { t } = useTranslation("space");
  const invalidate = useInvalidate();
  const id = item ? `my-space-claim-${claim.id}-item-${item.id}-upload` : `my-space-claim-${claim.id}-receipt`;
  const upload = useUploadClaimDocument({
    mutation: {
      onSuccess: () => {
        invalidate("/api/me/claims", "/api/claims", "/api/me/contexts");
        onDone?.();
      },
    },
  });

  return (
    <div className="flex flex-col gap-2 rounded-lg bg-surface-secondary p-3" data-testid={id}>
      <Field
        label={item ? t("claims.uploadItemReceipt") : t("claims.uploadClaimReceipt")}
        hint={t("documents.fileHint")}
        testId={`${id}-file-field`}
      >
        <FileDropzone
          accept="application/pdf,image/jpeg,image/png"
          disabled={upload.isPending}
          onFile={(file) => upload.mutate({ claimId: claim.id, data: { file, item_id: item?.id ?? null } })}
          testId={`${id}-file`}
        />
      </Field>
      <Message error={upload.error ? errorText(upload.error) : null} testId={`${id}-message`} />
    </div>
  );
}
