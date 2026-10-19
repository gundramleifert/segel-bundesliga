import { Button } from "@heroui/react";
import { keepPreviousData } from "@tanstack/react-query";
import { useState, type DragEvent } from "react";
import { useTranslation } from "react-i18next";

import { useFetchMedia, useListMedia } from "../api/generated/sbl";
import type { Media } from "../api/types";
import { errorText, useAsync, useInvalidate } from "../api/useApi";
import { INPUT_CLASS } from "../lib/admin";
import { filesIn, usePhotoUpload } from "../lib/usePhotoUpload";
import { Async } from "./Async";
import { Empty, ErrorMessage } from "./Blocks";
import { NO_CONTEXT, type MediaContext } from "../lib/mediaContext";
import { MediaContextSelect } from "./MediaContextSelect";
import { Pager } from "./Pager";

const PAGE = 18;

/** The library, opened where a picture is wanted — the editor's toolbar, a post's own
 *  picture (Story R-2). Every way a picture gets in is here: pick one from the library,
 *  from the computer (on a phone: the camera or the gallery), from a web address, or
 *  dropped onto the panel. Whatever arrives lands in the library first, and is then
 *  handed to `onPick` like a picked one — so the caller has one path, not four. */
export function MediaPicker({ onPick, onClose, testId }: { onPick: (item: Media) => void; onClose: () => void; testId: string }) {
  const { t } = useTranslation("admin");
  const invalidate = useInvalidate();
  const [q, setQ] = useState("");
  const [context, setContext] = useState<MediaContext>(NO_CONTEXT);
  const [page, setPage] = useState(1);
  const [address, setAddress] = useState<string | null>(null);
  const [over, setOver] = useState(false);

  const arrived = (item: Media) => {
    invalidate("/api/admin/media");
    onPick(item);
  };
  const photo = usePhotoUpload(arrived);
  const fetchUrl = useFetchMedia({ mutation: { onSuccess: arrived } });
  const media = useAsync(
    useListMedia(
      { limit: PAGE, offset: (page - 1) * PAGE, q: q || undefined, event_id: context.event_id ?? undefined, series_id: context.series_id ?? undefined },
      { query: { placeholderData: keepPreviousData } },
    ),
  );

  const fetchAddress = () => {
    if (address?.trim()) fetchUrl.mutate({ data: { url: address.trim() } });
  };

  const drop = (event: DragEvent) => {
    event.preventDefault();
    setOver(false);
    const [file] = filesIn(event.dataTransfer.files);
    if (file) void photo.upload(file).then((item) => item && arrived(item));
  };

  return (
    <div
      className={`grid grid-cols-[minmax(0,1fr)] gap-3 border-t border-slate-200 bg-white p-3 ${over ? "ring-2 ring-inset ring-brand-500" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={drop}
      data-testid={testId}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" variant="outline" isDisabled={photo.busy} onPress={photo.pick} data-testid={`${testId}-upload-button`}>
          {photo.busy ? t("posts.photoUploading") : t("picker.fromComputer")}
        </Button>
        <Button size="sm" variant="outline" onPress={() => setAddress((open) => (open === null ? "" : null))} data-testid={`${testId}-address-button`}>
          {t("picker.fromAddress")}
        </Button>
        <span className="flex-1" />
        <Button size="sm" variant="ghost" onPress={onClose} data-testid={`${testId}-close-button`}>
          {t("picker.close")}
        </Button>
      </div>
      <input {...photo.input} data-testid={`${testId}-input`} />

      {address !== null && (
        // Not a <form>: the picker sits inside the post's form, and Enter must fetch the
        // picture here, not save the post.
        <div className="flex flex-wrap items-center gap-2">
          <input
            className={`${INPUT_CLASS} min-w-0 flex-1`}
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            placeholder="https://…"
            aria-label={t("picker.addressLabel")}
            onKeyDown={(e) => {
              if (e.key !== "Enter") return;
              e.preventDefault();
              fetchAddress();
            }}
            autoFocus
            data-testid={`${testId}-address-input`}
          />
          <Button size="sm" isDisabled={fetchUrl.isPending} onPress={fetchAddress} data-testid={`${testId}-address-fetch`}>
            {fetchUrl.isPending ? t("picker.fetching") : t("picker.fetch")}
          </Button>
        </div>
      )}
      {(photo.error || fetchUrl.error) && <ErrorMessage text={photo.error ?? errorText(fetchUrl.error)} testId={`${testId}-error`} />}

      <div className="grid grid-cols-[minmax(0,1fr)] gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <input
          className={INPUT_CLASS}
          value={q}
          onChange={(e) => (setQ(e.target.value), setPage(1))}
          onKeyDown={(e) => e.key === "Enter" && e.preventDefault()}
          placeholder={t("media.searchPlaceholder")}
          aria-label={t("media.searchLabel")}
          data-testid={`${testId}-search`}
        />
        <MediaContextSelect value={context} onChange={(c) => (setContext(c), setPage(1))} noneLabel={t("media.contextAll")} testId={`${testId}-context`} />
      </div>

      <Async state={media} testId={`${testId}-list`} empty={<Empty testId={`${testId}-empty`}>{t("picker.empty")}</Empty>} isEmpty={(p) => p.items.length === 0}>
        {(result) => (
          <>
            <ul className="grid grid-cols-[repeat(auto-fill,minmax(6rem,1fr))] gap-2" data-testid={`${testId}-grid`}>
              {result.items.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => onPick(item)}
                    className="grid w-full gap-1 rounded p-1 text-left text-xs hover:bg-slate-100 focus-visible:ring-2 focus-visible:ring-brand-500"
                    title={item.alt}
                    data-testid={`${testId}-tile-${item.id}`}
                  >
                    <img src={item.thumb_url} alt={item.alt} loading="lazy" className="aspect-square w-full rounded object-cover" />
                    <span className="truncate text-slate-600">{item.alt || item.original_name}</span>
                  </button>
                </li>
              ))}
            </ul>
            <Pager page={result} current={page} onPage={setPage} testId={`${testId}-pager`} />
          </>
        )}
      </Async>
      <p className="text-xs text-slate-500">{t("picker.hint")}</p>
    </div>
  );
}
