import { Stack } from "../../components/Layouts";
import { MediaAdmin } from "../admin/media/MediaAdmin";
import { PostsAdmin } from "../admin/posts/PostList";

/** Stories R-1, R-2 (decided 2026-10-25): a series' or an event's *News & pictures* — every
 *  post and picture about it (a series' with its events'), drafts too, whoever wrote them:
 *  the regatta decides who may change a post, never its author. *New post* starts about
 *  this regatta. The server narrows both lists (`apply_filters`, Story A-13). */
export function RegattaNews({ kind, id }: { kind: "series" | "event"; id: number }) {
  const about = kind === "event" ? { event_id: id } : { series_id: id };
  return (
    <Stack gap={6} testId={`me-${kind}-news`}>
      <PostsAdmin about={about} base="/me" newQuery={`?${kind}=${id}`} testId={`me-${kind}-news-posts`} />
      <MediaAdmin about={{ event_id: about.event_id ?? null, series_id: about.series_id ?? null }} />
    </Stack>
  );
}
