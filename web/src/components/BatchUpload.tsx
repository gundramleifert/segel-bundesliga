import { useEffect, useRef, useState, type DragEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { errorText } from "../api/useApi";
import { INPUT_CLASS } from "../lib/admin";
import { PHOTO_ACCEPT, filesIn } from "../lib/usePhotoUpload";
import { Field } from "./Form";

const CREDIT_KEY = "sbl.upload.credit";

type Status = "waiting" | "sending" | "received" | "known" | "failed";
/** One picture in the batch. `file` is let go once it is sent, and `preview` is a local
 *  object URL only while it is being sent — then the library's small copy. A phone that
 *  sends 150 photos must not hold 150 decoded photos in memory (Story R-2). `entry` is
 *  the library entry it became. */
export type UploadItem = {
  id: number;
  name: string;
  file: File | null;
  preview: string | null;
  status: Status;
  error?: string;
  entry?: number;
};

/** What sending one picture answers — the library's entry, with its small copy. */
export type Sent = { created: boolean; thumb_url?: string; id?: number };

/** The credit this device remembers from the last batch, if any. */
export function rememberedCredit(): string | null {
  try {
    return localStorage.getItem(CREDIT_KEY);
  } catch {
    return null;
  }
}

function rememberCredit(name: string) {
  try {
    localStorage.setItem(CREDIT_KEY, name);
  } catch {
    // Remembering the name is a convenience; without storage it is asked again.
  }
}

/** The queue behind every batch upload: pictures sent one after another, each with its
 *  state. `send` and `credit` are read when each picture goes, not when the batch began.
 *  The Media tab uses it bare (its "+" opens the file chooser straight away);
 *  `BatchUpload` wraps it in a form for the upload page. */
export function useBatchUpload({
  send,
  credit,
  onArrived,
}: {
  send: (file: File, credit: string | undefined) => Promise<Sent>;
  credit: string;
  onArrived?: (entry: number | undefined) => void;
}) {
  const [items, setItems] = useState<UploadItem[]>([]);
  const next = useRef(0);
  const set = (id: number, change: Partial<UploadItem>) =>
    setItems((all) => all.map((item) => (item.id === id ? { ...item, ...change } : item)));

  // The one local preview there is at a time, released when its picture is done — and
  // on leaving the page mid-batch.
  const local = useRef<string | null>(null);
  const release = () => {
    if (local.current) URL.revokeObjectURL(local.current);
    local.current = null;
  };
  useEffect(() => release, []);

  // One at a time, in the order chosen: a phone on a pontoon has one slow connection, and
  // six parallel uploads would all crawl instead of one finishing. `queue` holds what is
  // still to send; one loop works it off while it runs, and a new pick joins the line.
  const queue = useRef<UploadItem[]>([]);
  const running = useRef(false);
  // The loop outlives the render that started it: what it reads must be today's — the
  // credit, and `send`, which carries the event or series chosen now, not at the start.
  const creditNow = useRef(credit);
  const sendNow = useRef(send);
  const arrivedNow = useRef(onArrived);
  useEffect(() => {
    creditNow.current = credit;
    sendNow.current = send;
    arrivedNow.current = onArrived;
  });

  const pump = async () => {
    if (running.current) return;
    running.current = true;
    for (let item = queue.current.shift(); item; item = queue.current.shift()) {
      const file = item.file!;
      local.current = URL.createObjectURL(file);
      set(item.id, { status: "sending", preview: local.current });
      const name = creditNow.current.trim();
      rememberCredit(name);
      try {
        const done = await sendNow.current(file, name || undefined);
        release();
        set(item.id, { status: done.created ? "received" : "known", file: null, preview: done.thumb_url ?? null, entry: done.id });
        arrivedNow.current?.(done.id);
      } catch (error) {
        release();
        set(item.id, { status: "failed", file: null, preview: null, error: errorText(error) });
      }
    }
    running.current = false;
  };

  const add = (files: File[]) => {
    if (files.length === 0) return;
    const added = files.map((file) => ({ id: next.current++, name: file.name, file, preview: null, status: "waiting" as const }));
    setItems((all) => [...all, ...added]);
    queue.current.push(...added);
    void pump();
  };

  const received = items.filter((item) => item.status === "received" || item.status === "known").length;
  const busy = items.some((item) => item.status === "waiting" || item.status === "sending");
  return { items, add, received, busy, clear: () => setItems((all) => all.filter((i) => i.status === "waiting" || i.status === "sending")) };
}

/** The batch's pictures and how far each one got. */
export function UploadList({ items, received, testId }: { items: UploadItem[]; received: number; testId: string }) {
  const { t } = useTranslation("upload");
  if (items.length === 0) return null;
  return (
    <>
      <p className="text-sm text-slate-700" data-testid={`${testId}-summary`}>
        {t("summary", { received, count: items.length })}
      </p>
      <ul className="grid grid-cols-[minmax(0,1fr)] gap-2" data-testid={`${testId}-list`}>
        {items.map((item) => (
          <li key={item.id} className="flex items-center gap-3 rounded-md border border-slate-200 bg-white p-2" data-testid={`${testId}-item-${item.id}`}>
            {item.preview ? (
              <img src={item.preview} alt="" className="size-12 shrink-0 rounded object-cover" data-testid={`${testId}-item-${item.id}-preview`} />
            ) : (
              <span className="size-12 shrink-0 rounded bg-slate-200" aria-hidden />
            )}
            <span className="min-w-0 flex-1 truncate text-sm">{item.name}</span>
            <span
              className={`shrink-0 text-sm ${item.status === "failed" ? "text-red-700" : item.status === "sending" || item.status === "waiting" ? "text-slate-500" : "text-emerald-700"}`}
              data-testid={`${testId}-item-${item.id}-status`}
              data-status={item.status}
            >
              {item.status === "failed" ? item.error : t(`status.${item.status}`)}
            </span>
          </li>
        ))}
      </ul>
    </>
  );
}

/** Several pictures at once, sent one after another, each with its state — Story R-2.
 *  The upload page's form: the credit asked once and remembered on the device, then the
 *  drop zone. Whether a file is a picture is the server's to say, by its content;
 *  nothing is filtered here. */
export function BatchUpload({
  send,
  defaultCredit = "",
  onArrived,
  testId,
  children,
}: {
  /** One picture, with the credit given — the import API with a key, or editorial's upload. */
  send: (file: File, credit: string | undefined) => Promise<Sent>;
  /** The credit when this device remembers none — a key's credit, or editorial's own name. */
  defaultCredit?: string;
  /** After each picture that arrived — to refresh a list that shows them. */
  onArrived?: () => void;
  testId: string;
  /** Fields shown between the credit and the drop zone — an event or series, say. */
  children?: ReactNode;
}) {
  const { t } = useTranslation("upload");
  const input = useRef<HTMLInputElement>(null);
  const remembered = useRef(rememberedCredit());
  const [credit, setCredit] = useState(() => remembered.current || defaultCredit);
  // The signed-in name arrives after the first render: fill it in then, unless the
  // device remembered one or the field was typed into meanwhile.
  useEffect(() => {
    if (!remembered.current && defaultCredit) setCredit((typed) => typed || defaultCredit);
  }, [defaultCredit]);
  const [over, setOver] = useState(false);
  const batch = useBatchUpload({ send, credit, onArrived: () => onArrived?.() });
  const { add, items, received } = batch;

  const drop = (event: DragEvent) => {
    event.preventDefault();
    setOver(false);
    add(filesIn(event.dataTransfer.files));
  };

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-5">
      <Field label={t("creditLabel")} hint={t("creditHint")}>
        <input className={INPUT_CLASS} value={credit} onChange={(e) => setCredit(e.target.value)} autoComplete="name" data-testid={`${testId}-credit-input`} />
      </Field>
      {children}

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
        data-testid={`${testId}-dropzone`}
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
        data-testid={`${testId}-input`}
      />

      <UploadList items={items} received={received} testId={testId} />
    </div>
  );
}
