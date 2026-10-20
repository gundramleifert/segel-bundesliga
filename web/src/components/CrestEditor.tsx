import { Button, Spinner } from "@heroui/react";
import { useRef } from "react";
import { useTranslation } from "react-i18next";

import { useDeleteClubLogo, useUploadClubLogo } from "../api/generated/sbl";
import { errorText } from "../lib/admin";
import { ErrorMessage } from "./Blocks";
import { Tip } from "./Tip";

/** A club's crest, and the way to change it — Story V-3.
 *
 * Used by the admin screen's club list and by the club's own page in my space, where the
 * club's admin keeps it (the endpoint always let them; until then no screen did).
 *
 * The crest ("Stander") is uploaded as a file rather than pasted as a URL: most clubs have
 * the image, not a place to host it. The thumbnail sits on a checkerboard so a transparent
 * burgee reads as transparent instead of as a white rectangle — the upload deliberately
 * keeps the alpha channel (see `app/services/crests.py`).
 *
 * **The crest is edited from the crest**, not from a button beside it: hovering it reveals
 * a pen, and clicking it opens the file chooser. A separate "Replace crest" button said the
 * same thing twice and put the action a row's width away from the thing it acts on.
 *
 * Renders the thumbnail button and, after `children`, the remove button and any error —
 * so a caller lays out the club's name in between.
 */
export function CrestEditor({
  club,
  onChanged,
  testIdPrefix,
  children,
}: {
  club: { id: number; name: string; logo_url?: string | null };
  onChanged: () => void;
  /** e.g. `admin-club-crest` → `admin-club-crest-edit-<id>`, `admin-club-crest-<id>`, … */
  testIdPrefix: string;
  children?: React.ReactNode;
}) {
  const { t } = useTranslation("common");
  const fileInput = useRef<HTMLInputElement>(null);

  const upload = useUploadClubLogo({ mutation: { onSuccess: onChanged } });
  const remove = useDeleteClubLogo({ mutation: { onSuccess: onChanged } });

  const label = club.logo_url ? t("crest.replace") : t("crest.upload");

  return (
    <>
      <input
        ref={fileInput}
        type="file"
        accept="image/png,image/jpeg,image/webp,image/gif"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          // Reset first: picking the same file twice in a row fires no change event
          // otherwise, so a retry after a failed upload would do nothing.
          e.target.value = "";
          if (file) upload.mutate({ clubId: club.id, data: { file } });
        }}
        data-testid={`${testIdPrefix}-input-${club.id}`}
      />

      {/* A real button, not a clickable div: it has to be reachable and operable from the
          keyboard, and the pen has to appear on focus as well as on hover — a pen that only
          shows under the mouse pointer tells a keyboard user nothing.

          No cache-busting suffix on the image: `logo_url` already carries the file's mtime
          as a `?v=` stamp (`app/crests.py`), so a replaced crest arrives under a new URL on
          its own once the list is invalidated. */}
      <Tip text={label}>
        <button
          type="button"
          onClick={() => fileInput.current?.click()}
          disabled={upload.isPending}
          aria-label={`${label}: ${club.name}`}
          data-testid={`${testIdPrefix}-edit-${club.id}`}
          className="crest-backdrop group relative grid size-10 shrink-0 cursor-pointer place-items-center overflow-hidden rounded border border-separator outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          {club.logo_url ? (
            <img
              src={club.logo_url}
              alt=""
              className="size-10 object-contain"
              data-testid={`${testIdPrefix}-${club.id}`}
            />
          ) : (
            <span aria-hidden className="text-xs text-faint">
              —
            </span>
          )}
          <span
            aria-hidden
            data-testid={`${testIdPrefix}-pen-${club.id}`}
            className={`absolute inset-0 grid place-items-center bg-slate-900/55 text-white transition-opacity ${
              upload.isPending
                ? "opacity-100"
                : "opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100"
            }`}
          >
            {upload.isPending ? (
              <Spinner size="sm" />
            ) : (
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
                className="size-4"
              >
                <path d="M12 20h9" />
                <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
              </svg>
            )}
          </span>
        </button>
      </Tip>

      {children}

      {/* Removing is a different action from replacing, so it keeps its own control —
          but only when there is something to remove. */}
      {club.logo_url && (
        <Button
          size="sm"
          variant="ghost"
          isDisabled={remove.isPending}
          onPress={() => remove.mutate({ clubId: club.id })}
          data-testid={`${testIdPrefix}-remove-${club.id}`}
        >
          {t("crest.remove")}
        </Button>
      )}
      {(upload.isError || remove.isError) && (
        <ErrorMessage
          text={errorText(upload.error ?? remove.error)}
          testId={`${testIdPrefix}-error-${club.id}`}
        />
      )}
    </>
  );
}
