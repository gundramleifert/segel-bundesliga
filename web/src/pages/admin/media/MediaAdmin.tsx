import { Button } from "@heroui/react";
import { keepPreviousData } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import {
  getGetMediaQueryKey,
  getListImportKeysQueryKey,
  useCreateImportKey,
  useDeleteMedia,
  useGetMedia,
  useListImportKeys,
  useListMedia,
  useRevokeImportKey,
  useUpdateMedia,
  uploadMedia,
} from "../../../api/generated/sbl";
import { ApiError } from "../../../api/http";
import type { ImportKey, ImportKeyCreated, Media, MediaDetail } from "../../../api/types";
import { errorText, useAsync, useInvalidate } from "../../../api/useApi";
import { Async } from "../../../components/Async";
import { BatchUpload } from "../../../components/BatchUpload";
import { Badge, Empty, ErrorMessage } from "../../../components/Blocks";
import { ConfirmButton } from "../../../components/ConfirmButton";
import { Field, Message, Section } from "../../../components/Form";
import { MediaContextSelect } from "../../../components/MediaContextSelect";
import { NO_CONTEXT, type MediaContext } from "../../../lib/mediaContext";
import { Pager } from "../../../components/Pager";
import { INPUT_CLASS } from "../../../lib/admin";
import { formatDate } from "../../../lib/format";
import { useListParams } from "../../../lib/listParams";

const PAGE = 24;

/** Story R-2: the picture library — every picture from editorial and from the sources
 *  with an import key — and the import keys themselves, as upload links. */
export function MediaAdmin() {
  return (
    <>
      <Upload />
      <Library />
      <ImportKeys />
    </>
  );
}

/** Editorial's own upload — a batch, with a credit and an event or series for all of it;
 *  no link needed (Story R-2). Folded until asked for, so the library stays on top. */
function Upload() {
  const { t } = useTranslation("admin");
  const invalidate = useInvalidate();
  const [open, setOpen] = useState(false);
  const [context, setContext] = useState<MediaContext>(NO_CONTEXT);
  return (
    <Section
      title={t("media.uploadTitle")}
      testId="admin-media-upload-section"
      action={
        <Button size="sm" variant={open ? "ghost" : "primary"} onPress={() => setOpen((o) => !o)} data-testid="admin-media-upload-toggle">
          {open ? t("media.uploadClose") : t("media.uploadButton")}
        </Button>
      }
    >
      {open && (
        <BatchUpload
          send={(file, credit) =>
            uploadMedia({ file, credit, event_id: context.event_id ?? undefined, series_id: context.series_id ?? undefined })
          }
          onArrived={() => invalidate("/api/admin/media")}
          testId="admin-media-upload"
        >
          <Field label={t("media.contextLabel")} hint={t("importKeys.optional")}>
            <MediaContextSelect value={context} onChange={setContext} noneLabel={t("media.contextNone")} testId="admin-media-upload-context" />
          </Field>
        </BatchUpload>
      )}
    </Section>
  );
}

function Library() {
  const { t } = useTranslation("admin");
  const list = useListParams(PAGE);
  const [selected, setSelected] = useState<number | null>(null);
  const [context, setContext] = useState<MediaContext>(NO_CONTEXT);
  const media = useAsync(
    useListMedia(
      { ...list.request, q: list.q || undefined, event_id: context.event_id ?? undefined, series_id: context.series_id ?? undefined },
      { query: { placeholderData: keepPreviousData } },
    ),
  );

  return (
    <Section title={t("media.title")} testId="admin-media-section">
      <p className="text-sm text-slate-600">{t("media.intro")}</p>
      <Field label={t("media.searchLabel")}>
        <input
          className={INPUT_CLASS}
          value={list.q}
          onChange={(e) => list.setQuery(e.target.value)}
          placeholder={t("media.searchPlaceholder")}
          data-testid="admin-media-search-input"
        />
      </Field>
      <Field label={t("media.contextLabel")}>
        <MediaContextSelect
          value={context}
          onChange={(c) => (setContext(c), list.setPage(1))}
          noneLabel={t("media.contextAll")}
          testId="admin-media-context-filter"
        />
      </Field>
      {selected !== null && <Entry id={selected} onClose={() => setSelected(null)} key={selected} />}
      <Async state={media} testId="admin-media" empty={<Empty testId="admin-media-empty">{t("media.empty")}</Empty>} isEmpty={(page) => page.items.length === 0}>
        {(page) => (
          <>
            {/* A fixed minimum per tile, so a phone gets two or three columns rather than
                a grid sized by its widest tile (Story A-10). */}
            <ul className="grid grid-cols-[repeat(auto-fill,minmax(7rem,1fr))] gap-3" data-testid="admin-media-grid">
              {page.items.map((item) => (
                <li key={item.id}>
                  <Tile item={item} active={item.id === selected} onPress={() => setSelected(item.id)} />
                </li>
              ))}
            </ul>
            <Pager page={page} current={list.page} onPage={list.setPage} testId="admin-media" />
          </>
        )}
      </Async>
    </Section>
  );
}

function Tile({ item, active, onPress }: { item: Media; active: boolean; onPress: () => void }) {
  return (
    <button
      type="button"
      onClick={onPress}
      className={`grid w-full gap-1 rounded-md p-1 text-left text-xs hover:bg-slate-100 ${active ? "ring-2 ring-brand-500" : ""}`}
      data-testid={`admin-media-tile-${item.id}`}
    >
      <img src={item.thumb_url} alt={item.alt} loading="lazy" className="aspect-square w-full rounded object-cover" />
      <span className="truncate text-slate-700">{item.alt || item.original_name}</span>
      {item.credit && <span className="truncate text-slate-500">© {item.credit}</span>}
      {item.context && <span className="truncate text-brand-700">{item.context}</span>}
    </button>
  );
}

/** One picture: its alt text and credit to correct, where it is used, and deleting it. */
function Entry({ id, onClose }: { id: number; onClose: () => void }) {
  const entry = useAsync(useGetMedia(id));
  return (
    <Async state={entry} testId="admin-media-entry">
      {(item) => <EntryForm item={item} onClose={onClose} />}
    </Async>
  );
}

function EntryForm({ item, onClose }: { item: MediaDetail; onClose: () => void }) {
  const { t } = useTranslation("admin");
  const invalidate = useInvalidate();
  const [alt, setAlt] = useState(item.alt);
  const [credit, setCredit] = useState(item.credit ?? "");
  const [context, setContext] = useState<MediaContext>({ event_id: item.event_id ?? null, series_id: item.series_id ?? null });
  const [saved, setSaved] = useState(false);
  const refresh = () => invalidate("/api/admin/media", getGetMediaQueryKey(item.id));
  const update = useUpdateMedia({ mutation: { onSuccess: () => (refresh(), setSaved(true)) } });
  const remove = useDeleteMedia({ mutation: { onSuccess: () => (invalidate("/api/admin/media"), onClose()) } });
  const inUse = remove.error instanceof ApiError && remove.error.code === "media-in-use";

  return (
    <form
      className="grid grid-cols-[minmax(0,1fr)] gap-4 rounded-md border border-slate-200 bg-slate-50 p-4 sm:grid-cols-[14rem_minmax(0,1fr)]"
      data-testid="admin-media-entry-form"
      onSubmit={(e: FormEvent) => {
        e.preventDefault();
        update.mutate({ mediaId: item.id, data: { alt, credit, ...context } });
      }}
    >
      <a href={item.url} target="_blank" rel="noopener noreferrer">
        <img src={item.thumb_url} alt={item.alt} className="w-full rounded object-contain" />
      </a>
      <div className="grid content-start gap-3">
        <p className="text-xs text-slate-500">
          {item.original_name} · {item.width} × {item.height}
          {item.taken_on && ` · ${t("media.takenOn", { date: formatDate(item.taken_on) })}`}
        </p>
        <Field label={t("media.altLabel")} hint={t("media.altHint")}>
          <input className={INPUT_CLASS} value={alt} onChange={(e) => (setAlt(e.target.value), setSaved(false))} data-testid="admin-media-alt-input" />
        </Field>
        <Field label={t("media.creditLabel")}>
          <input className={INPUT_CLASS} value={credit} onChange={(e) => (setCredit(e.target.value), setSaved(false))} data-testid="admin-media-credit-input" />
        </Field>
        <Field label={t("media.contextLabel")} hint={t("importKeys.optional")}>
          <MediaContextSelect
            value={context}
            onChange={(c) => (setContext(c), setSaved(false))}
            noneLabel={t("media.contextNone")}
            testId="admin-media-context-select"
          />
        </Field>
        <div className="text-sm" data-testid="admin-media-used-in">
          {item.used_in.length === 0 ? (
            <span className="text-slate-500">{t("media.unused")}</span>
          ) : (
            <>
              {t("media.usedIn")}{" "}
              {item.used_in.map((post, i) => (
                <span key={post.id}>
                  {i > 0 && ", "}
                  <Link to={`/admin/news/${post.id}`} className="text-brand-700 underline">
                    {post.title}
                  </Link>
                </span>
              ))}
            </>
          )}
        </div>
        <Message success={saved ? t("media.saved") : null} error={update.error ? errorText(update.error) : null} testId="admin-media-save" />
        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" size="sm" isDisabled={update.isPending} data-testid="admin-media-save-button">
            {t("media.saveButton")}
          </Button>
          <Button size="sm" variant="ghost" onPress={onClose} data-testid="admin-media-close-button">
            {t("media.closeButton")}
          </Button>
          <span className="flex-1" />
          <ConfirmButton
            size="sm"
            label={t("media.deleteButton")}
            confirmLabel={t("media.deleteConfirm")}
            cancelLabel={t("media.deleteCancel")}
            busy={remove.isPending}
            onConfirm={() => remove.mutate({ mediaId: item.id })}
            testId="admin-media-delete"
          />
        </div>
        {remove.error && !inUse && <ErrorMessage text={errorText(remove.error)} testId="admin-media-delete-error" />}
        {inUse && <ErrorMessage text={t("media.inUse")} testId="admin-media-delete-error" />}
      </div>
    </form>
  );
}

// ---------------------------------------------------------------- import keys

/** The link a photographer opens: the key in the `#fragment`, so it never reaches a
 *  server's log or a referrer (Story R-2). */
const uploadLink = (key: string) => `${window.location.origin}/upload#key=${encodeURIComponent(key)}`;

function ImportKeys() {
  const { t } = useTranslation("admin");
  const keys = useAsync(useListImportKeys());
  const [made, setMade] = useState<ImportKeyCreated | null>(null);

  return (
    <Section title={t("importKeys.title")} testId="admin-import-keys-section">
      <p className="text-sm text-slate-600">{t("importKeys.intro")}</p>
      <NewKey onMade={setMade} />
      {made && <ShownOnce made={made} onDone={() => setMade(null)} />}
      <Async state={keys} testId="admin-import-keys" empty={<Empty testId="admin-import-keys-empty">{t("importKeys.empty")}</Empty>}>
        {(rows) => (
          <ul className="divide-y divide-slate-200" data-testid="admin-import-keys-list">
            {rows.map((row) => (
              <KeyRow key={row.id} row={row} />
            ))}
          </ul>
        )}
      </Async>
    </Section>
  );
}

function NewKey({ onMade }: { onMade: (made: ImportKeyCreated) => void }) {
  const { t } = useTranslation("admin");
  const invalidate = useInvalidate();
  const [label, setLabel] = useState("");
  const [credit, setCredit] = useState("");
  const [days, setDays] = useState("30");
  const [context, setContext] = useState<MediaContext>(NO_CONTEXT);
  const create = useCreateImportKey({
    mutation: {
      onSuccess: (made) => {
        invalidate(getListImportKeysQueryKey());
        setLabel("");
        setCredit("");
        setContext(NO_CONTEXT);
        onMade(made);
      },
    },
  });

  return (
    <form
      className="grid grid-cols-[minmax(0,1fr)] items-end gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:grid-cols-[minmax(0,2fr)_minmax(0,2fr)_minmax(0,2fr)_6rem_auto]"
      data-testid="admin-import-key-form"
      onSubmit={(e: FormEvent) => {
        e.preventDefault();
        create.mutate({ data: { label, credit: credit || null, valid_days: days ? Number(days) : null, ...context } });
      }}
    >
      <Field label={t("importKeys.labelLabel")}>
        <input className={INPUT_CLASS} value={label} onChange={(e) => setLabel(e.target.value)} placeholder={t("importKeys.labelPlaceholder")} data-testid="admin-import-key-label-input" />
      </Field>
      <Field label={t("importKeys.creditLabel")} hint={t("importKeys.optional")}>
        <input className={INPUT_CLASS} value={credit} onChange={(e) => setCredit(e.target.value)} data-testid="admin-import-key-credit-input" />
      </Field>
      <Field label={t("importKeys.contextLabel")} hint={t("importKeys.optional")}>
        <MediaContextSelect value={context} onChange={setContext} noneLabel={t("media.contextNone")} testId="admin-import-key-context-select" />
      </Field>
      <Field label={t("importKeys.daysLabel")}>
        <input className={INPUT_CLASS} type="number" min={1} max={366} value={days} onChange={(e) => setDays(e.target.value)} data-testid="admin-import-key-days-input" />
      </Field>
      <Button type="submit" isDisabled={create.isPending || label.trim().length < 3} data-testid="admin-import-key-create-button">
        {t("importKeys.createButton")}
      </Button>
      {create.error && <ErrorMessage text={errorText(create.error)} testId="admin-import-key-create-error" />}
    </form>
  );
}

/** The new key as a link, with a way to copy it — the only time it can be seen. */
function ShownOnce({ made, onDone }: { made: ImportKeyCreated; onDone: () => void }) {
  const { t } = useTranslation("admin");
  const [copied, setCopied] = useState(false);
  const link = uploadLink(made.key);
  return (
    <div className="grid gap-2 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm" data-testid="admin-import-key-made">
      <p className="font-medium text-amber-900">{t("importKeys.shownOnce", { label: made.label })}</p>
      <div className="flex flex-wrap items-center gap-2">
        <input readOnly value={link} onFocus={(e) => e.target.select()} className={`${INPUT_CLASS} min-w-0 flex-1 font-mono text-xs`} data-testid="admin-import-key-link" />
        <Button
          size="sm"
          onPress={() => void navigator.clipboard?.writeText(link).then(() => setCopied(true))}
          data-testid="admin-import-key-copy-button"
        >
          {copied ? t("importKeys.copied") : t("importKeys.copy")}
        </Button>
        <Button size="sm" variant="ghost" onPress={onDone} data-testid="admin-import-key-done-button">
          {t("importKeys.done")}
        </Button>
      </div>
    </div>
  );
}

function KeyRow({ row }: { row: ImportKey }) {
  const { t } = useTranslation("admin");
  const invalidate = useInvalidate();
  const revoke = useRevokeImportKey({ mutation: { onSuccess: () => invalidate(getListImportKeysQueryKey()) } });
  const state = row.revoked_at ? t("importKeys.revoked") : row.active ? t("importKeys.active") : t("importKeys.expired");
  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2 text-sm" data-testid={`admin-import-key-${row.id}`}>
      <span className="min-w-0 flex-1">
        <span className="font-medium">{row.label}</span> <span className="font-mono text-xs text-slate-500">{row.prefix}…</span>
        <span className="block text-xs text-slate-500">
          {t("importKeys.pictures", { count: row.pictures })}
          {row.last_used_at && ` · ${t("importKeys.lastUsed", { date: formatDate(row.last_used_at) })}`}
          {row.expires_at && row.active && ` · ${t("importKeys.validUntil", { date: formatDate(row.expires_at) })}`}
          {row.credit && ` · © ${row.credit}`}
          {row.context && ` · ${row.context}`}
        </span>
      </span>
      <Badge tone={row.active ? "success" : "muted"} testId={`admin-import-key-${row.id}-state`}>
        {state}
      </Badge>
      {row.active && (
        <ConfirmButton
          size="sm"
          label={t("importKeys.revokeButton")}
          confirmLabel={t("importKeys.revokeConfirm")}
          cancelLabel={t("importKeys.revokeCancel")}
          busy={revoke.isPending}
          onConfirm={() => revoke.mutate({ keyId: row.id })}
          testId={`admin-import-key-${row.id}-revoke`}
        />
      )}
    </li>
  );
}
