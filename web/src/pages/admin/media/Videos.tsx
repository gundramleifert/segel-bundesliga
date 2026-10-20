import { Button } from "@heroui/react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { getListAllVideosQueryKey, useCreateVideo, useDeleteVideo, useListAllVideos, useUpdateVideo } from "../../../api/generated/sbl";
import type { VideoOut } from "../../../api/generated/model/videoOut";
import { errorText, useAsync, useInvalidate } from "../../../api/useApi";
import { Async } from "../../../components/Async";
import { Empty, ErrorMessage } from "../../../components/Blocks";
import { ConfirmButton } from "../../../components/ConfirmButton";
import { Field, Section } from "../../../components/Form";
import { MediaContextSelect } from "../../../components/MediaContextSelect";
import { INPUT_CLASS } from "../../../lib/admin";
import { NO_CONTEXT, type MediaContext } from "../../../lib/mediaContext";

/** Where a public league page refetches its videos — and editorial's list. */
const VIDEO_PATHS = ["/api/admin/videos", "/api/videos"];

/** `1:30` for a start 90 seconds in. */
const clock = (seconds: number) => `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;

/** Story R-3: the videos a league's media page shows — YouTube links, never files, each
 *  of an event or a series, shown once that is public. */
export function Videos() {
  const { t } = useTranslation("admin");
  const videos = useAsync(useListAllVideos());
  return (
    <Section title={t("media.videos.title")} testId="admin-videos-section">
      <p className="text-sm text-slate-600">{t("media.videos.intro")}</p>
      <NewVideo />
      <Async state={videos} testId="admin-videos" empty={<Empty testId="admin-videos-empty">{t("media.videos.empty")}</Empty>}>
        {(rows) => (
          <ul className="divide-y divide-slate-200" data-testid="admin-videos-list">
            {rows.map((video) => (
              <VideoRow key={video.id} video={video} />
            ))}
          </ul>
        )}
      </Async>
    </Section>
  );
}

function NewVideo() {
  const { t } = useTranslation("admin");
  const invalidate = useInvalidate();
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [context, setContext] = useState<MediaContext>(NO_CONTEXT);
  const create = useCreateVideo({
    mutation: {
      onSuccess: () => {
        invalidate(...VIDEO_PATHS);
        setUrl("");
        setTitle("");
      },
    },
  });
  return (
    <form
      className="grid grid-cols-[minmax(0,1fr)] items-end gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:grid-cols-[minmax(0,2fr)_minmax(0,2fr)_minmax(0,2fr)_auto]"
      data-testid="admin-videos-form"
      onSubmit={(e: FormEvent) => {
        e.preventDefault();
        create.mutate({ data: { url, title, ...context } });
      }}
    >
      <Field label={t("media.videos.urlLabel")}>
        <input
          className={INPUT_CLASS}
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://www.youtube.com/watch?v=…"
          inputMode="url"
          data-testid="admin-videos-url-input"
        />
      </Field>
      <Field label={t("media.videos.titleLabel")}>
        <input className={INPUT_CLASS} value={title} onChange={(e) => setTitle(e.target.value)} data-testid="admin-videos-title-input" />
      </Field>
      <Field label={t("media.videos.contextLabel")}>
        <MediaContextSelect value={context} onChange={setContext} noneLabel={t("media.contextNone")} testId="admin-videos-context-select" />
      </Field>
      <Button type="submit" isDisabled={create.isPending || url.trim().length < 8 || title.trim().length < 2} data-testid="admin-videos-add-button">
        {t("media.videos.add")}
      </Button>
      {create.error && <ErrorMessage text={errorText(create.error)} testId="admin-videos-add-error" />}
    </form>
  );
}

function VideoRow({ video }: { video: VideoOut }) {
  const { t } = useTranslation("admin");
  const invalidate = useInvalidate();
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(video.title);
  const [context, setContext] = useState<MediaContext>({ event_id: video.event_id ?? null, series_id: video.series_id ?? null });
  const update = useUpdateVideo({ mutation: { onSuccess: () => (invalidate(...VIDEO_PATHS), setEditing(false)) } });
  const remove = useDeleteVideo({ mutation: { onSuccess: () => invalidate(getListAllVideosQueryKey(), "/api/videos") } });

  return (
    <li className="grid grid-cols-[6rem_minmax(0,1fr)] gap-3 py-3 text-sm" data-testid={`admin-videos-${video.id}`}>
      <a href={`https://www.youtube.com/watch?v=${video.youtube_id}`} target="_blank" rel="noopener noreferrer">
        <img src={`https://i.ytimg.com/vi/${video.youtube_id}/mqdefault.jpg`} alt="" loading="lazy" className="aspect-video w-full rounded object-cover" />
      </a>
      {editing ? (
        <form
          className="grid gap-2"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            update.mutate({ videoId: video.id, data: { title, ...context } });
          }}
        >
          <input className={INPUT_CLASS} value={title} onChange={(e) => setTitle(e.target.value)} data-testid={`admin-videos-${video.id}-title-input`} />
          <MediaContextSelect value={context} onChange={setContext} noneLabel={t("media.contextNone")} testId={`admin-videos-${video.id}-context-select`} />
          <div className="flex flex-wrap gap-2">
            <Button type="submit" size="sm" isDisabled={update.isPending || title.trim().length < 2} data-testid={`admin-videos-${video.id}-save`}>
              {t("media.videos.save")}
            </Button>
            <Button size="sm" variant="ghost" onPress={() => setEditing(false)} data-testid={`admin-videos-${video.id}-cancel`}>
              {t("media.videos.cancel")}
            </Button>
          </div>
          {update.error && <ErrorMessage text={errorText(update.error)} testId={`admin-videos-${video.id}-error`} />}
        </form>
      ) : (
        <div className="flex flex-wrap items-start gap-x-3 gap-y-2">
          <span className="min-w-0 flex-1">
            <span className="block font-medium" data-testid={`admin-videos-${video.id}-title`}>
              {video.title}
            </span>
            <span className="block text-xs text-slate-500">
              {video.context ?? t("media.videos.noContext")}
              {video.start > 0 && ` · ${t("media.videos.startsAt", { time: clock(video.start) })}`}
            </span>
          </span>
          <Button size="sm" variant="ghost" onPress={() => setEditing(true)} data-testid={`admin-videos-${video.id}-edit`}>
            {t("media.videos.edit")}
          </Button>
          <ConfirmButton
            size="sm"
            label={t("media.videos.remove")}
            confirmLabel={t("media.videos.removeConfirm")}
            cancelLabel={t("media.videos.removeCancel")}
            busy={remove.isPending}
            onConfirm={() => remove.mutate({ videoId: video.id })}
            testId={`admin-videos-${video.id}-remove`}
          />
        </div>
      )}
    </li>
  );
}
