import { useRef, useState, type DragEvent } from "react";
import { useTranslation } from "react-i18next";

/** A file field you can drop a file onto — or tap, which opens the chooser as before.
 *
 * Replaced three bare `<input type="file">`s (personal documents, claim receipts, the
 * signed waiver scan) that each showed the browser's own "Choose file" button — small,
 * unstyled, and no target for a scan dragged out of a folder. The real input stays inside,
 * hidden, and carries `testId`, so a spec's `setInputFiles` reaches it unchanged.
 *
 * A dropped file skips the chooser's `accept` filter, so the same types are checked here;
 * the server checks the content anyway. The input is cleared after every pick: choosing
 * the same file twice in a row fires no change event otherwise, so a retry after a failed
 * upload would do nothing.
 */
export function FileDropzone({
  accept,
  onFile,
  selected,
  disabled = false,
  hint,
  testId,
  id,
}: {
  /** As for `<input accept>`: MIME types, e.g. "application/pdf,image/png". */
  accept: string;
  onFile: (file: File) => void;
  /** The file chosen and not yet sent, shown in the zone — for forms that upload on submit. */
  selected?: File | null;
  disabled?: boolean;
  /** The accepted types and size, in words. */
  hint?: string;
  testId: string;
  /** From `Field`, so its label points at the zone. */
  id?: string;
}) {
  const { t } = useTranslation();
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  const types = accept.split(",").map((type) => type.trim());

  const take = (file: File | undefined) => {
    if (!file || disabled) return;
    const allowed = types.some((type) =>
      type.endsWith("/*") ? file.type.startsWith(type.slice(0, -1)) : file.type === type,
    );
    if (!allowed) {
      setRefused(file.name);
      return;
    }
    setRefused(null);
    onFile(file);
  };

  const drop = (event: DragEvent) => {
    event.preventDefault();
    setOver(false);
    take(event.dataTransfer.files[0]);
  };

  return (
    <div>
      <button
        id={id}
        type="button"
        disabled={disabled}
        onClick={() => input.current?.click()}
        onDragOver={(event) => {
          event.preventDefault();
          if (!disabled) setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={drop}
        data-testid={`${testId}-zone`}
        data-over={String(over)}
        className={
          "flex w-full flex-col items-center justify-center gap-1 rounded-lg border-2 border-dashed " +
          "px-4 py-5 text-center text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-50 " +
          (over
            ? "border-brand-500 bg-brand-50 text-brand-800"
            : "border-slate-300 text-slate-600 hover:border-slate-400 hover:bg-slate-50")
        }
      >
        <svg
          aria-hidden
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          className="size-6"
        >
          <path d="M12 16V4M7 9l5-5 5 5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
        </svg>
        {selected ? (
          <span className="font-medium text-slate-900" data-testid={`${testId}-selected`}>
            {selected.name}
          </span>
        ) : (
          <span className="font-medium">{t("dropzone.prompt")}</span>
        )}
        {hint && <span className="text-xs text-slate-500">{hint}</span>}
      </button>
      <input
        ref={input}
        type="file"
        accept={accept}
        className="hidden"
        disabled={disabled}
        onChange={(event) => {
          const file = event.target.files?.[0];
          event.target.value = "";
          take(file);
        }}
        data-testid={testId}
      />
      {refused && (
        <p className="mt-1 text-sm text-red-700" data-testid={`${testId}-refused`}>
          {t("dropzone.refused", { name: refused })}
        </p>
      )}
    </div>
  );
}
