import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState, type DragEvent } from "react";
import { useTranslation } from "react-i18next";

import { getGetImportKeyQueryKey, getImportKey, importMedia } from "../api/generated/sbl";
import { errorText, useAsync } from "../api/useApi";
import { Async } from "../components/Async";
import { PageHeader } from "../components/Blocks";
import { Field } from "../components/Form";
import { INPUT_CLASS } from "../lib/admin";
import { formatDate } from "../lib/format";
import { PHOTO_ACCEPT, filesIn } from "../lib/usePhotoUpload";

/** The key from `#key=…` — a fragment, so it never reaches a server's log or a referrer. */
function keyFromHash(): string | null {
  return new URLSearchParams(window.location.hash.slice(1)).get("key");
}

const CREDIT_KEY = "sbl.upload.credit";

function rememberedCredit(): string | null {
  try {
    return localStorage.getItem(CREDIT_KEY);
  } catch {
    return null;
  }
}

type Status = "waiting" | "sending" | "received" | "known" | "failed";
type Item = { id: number; file: File; preview: string; status: Status; error?: string };

/** `/upload#key=…` — Story R-2: a photographer delivers pictures into the library from a
 *  link, on a phone, without an account. Our own source, and it uses the import API like
 *  any other would — `GET /api/import/key`, `POST /api/import/media` — and nothing else. */
export function UploadPage() {
  const { t } = useTranslation("upload");
  const [key] = useState(keyFromHash);
  const info = useAsync(
    useQuery({
      queryKey: [...getGetImportKeyQueryKey(), key],
      queryFn: () => getImportKey({ headers: { "X-Import-Key": key ?? "" } }),
      enabled: !!key,
      retry: false,
    }),
  );

  return (
    <>
      <PageHeader title={t("title")} testId="upload-header" />
      {!key ? (
        <p className="text-slate-700" data-testid="upload-no-key">{t("noKey")}</p>
      ) : (
        <Async state={info} testId="upload-key">
          {(about) => (
            <>
              <p className="mb-6 text-slate-700" data-testid="upload-for">
                {t("for", { label: about.label })}
                {about.expires_at && <span className="text-slate-500"> · {t("validUntil", { date: formatDate(about.expires_at) })}</span>}
              </p>
              <Uploader importKey={key} defaultCredit={about.credit ?? ""} />
            </>
          )}
        </Async>
      )}
    </>
  );
}

function Uploader({ importKey, defaultCredit }: { importKey: string; defaultCredit: string }) {
  const { t } = useTranslation("upload");
  const input = useRef<HTMLInputElement>(null);
  const [credit, setCredit] = useState(() => rememberedCredit() ?? defaultCredit);
  const [items, setItems] = useState<Item[]>([]);
  const [over, setOver] = useState(false);
  const next = useRef(0);

  const set = (id: number, change: Partial<Item>) =>
    setItems((all) => all.map((item) => (item.id === id ? { ...item, ...change } : item)));

  // One at a time, in the order chosen: a phone on a pontoon has one slow connection, and
  // six parallel uploads would all crawl instead of one finishing. `queue` holds what is
  // still to send; one loop works it off while it runs, and a new pick joins the line.
  const queue = useRef<Item[]>([]);
  const running = useRef(false);
  const creditNow = useRef(credit);
  useEffect(() => {
    creditNow.current = credit;
  }, [credit]);

  const pump = async () => {
    if (running.current) return;
    running.current = true;
    for (let item = queue.current.shift(); item; item = queue.current.shift()) {
      set(item.id, { status: "sending" });
      const name = creditNow.current.trim();
      try {
        localStorage.setItem(CREDIT_KEY, name);
      } catch {
        // Remembering the name is a convenience; without storage it is asked again.
      }
      try {
        const done = await importMedia({ file: item.file, credit: name || undefined }, { headers: { "X-Import-Key": importKey } });
        set(item.id, { status: done.created ? "received" : "known" });
      } catch (error) {
        set(item.id, { status: "failed", error: errorText(error) });
      }
    }
    running.current = false;
  };

  const add = (files: File[]) => {
    if (files.length === 0) return;
    const added = files.map((file) => ({ id: next.current++, file, preview: URL.createObjectURL(file), status: "waiting" as const }));
    setItems((all) => [...all, ...added]);
    queue.current.push(...added);
    void pump();
  };

  const drop = (event: DragEvent) => {
    event.preventDefault();
    setOver(false);
    add(filesIn(event.dataTransfer.files));
  };
  const received = items.filter((item) => item.status === "received" || item.status === "known").length;

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-5">
      <Field label={t("creditLabel")} hint={t("creditHint")}>
        <input className={INPUT_CLASS} value={credit} onChange={(e) => setCredit(e.target.value)} autoComplete="name" data-testid="upload-credit-input" />
      </Field>

      <button
        type="button"
        onClick={() => input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={drop}
        className={`grid min-h-40 place-items-center rounded-lg border-2 border-dashed p-6 text-center ${over ? "border-brand-500 bg-brand-50" : "border-slate-300 bg-white"}`}
        data-testid="upload-dropzone"
      >
        <span>
          <span className="block text-lg font-medium text-slate-800">{t("choose")}</span>
          <span className="block text-sm text-slate-500">{t("chooseHint")}</span>
        </span>
      </button>
      <input
        ref={input}
        type="file"
        multiple
        accept={PHOTO_ACCEPT}
        className="hidden"
        onChange={(e) => {
          add(filesIn(e.target.files));
          e.target.value = "";
        }}
        data-testid="upload-input"
      />

      {items.length > 0 && (
        <>
          <p className="text-sm text-slate-700" data-testid="upload-summary">
            {t("summary", { received, count: items.length })}
          </p>
          <ul className="grid grid-cols-[minmax(0,1fr)] gap-2" data-testid="upload-list">
            {items.map((item) => (
              <li key={item.id} className="flex items-center gap-3 rounded-md border border-slate-200 bg-white p-2" data-testid={`upload-item-${item.id}`}>
                <img src={item.preview} alt="" className="size-12 shrink-0 rounded object-cover" />
                <span className="min-w-0 flex-1 truncate text-sm">{item.file.name}</span>
                <span
                  className={`shrink-0 text-sm ${item.status === "failed" ? "text-red-700" : item.status === "sending" || item.status === "waiting" ? "text-slate-500" : "text-emerald-700"}`}
                  data-testid={`upload-item-${item.id}-status`}
                  data-status={item.status}
                >
                  {item.status === "failed" ? item.error : t(`status.${item.status}`)}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
