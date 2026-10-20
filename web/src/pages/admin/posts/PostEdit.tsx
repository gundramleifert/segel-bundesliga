import { Button } from "@heroui/react";
import { Suspense, lazy, useEffect, useState, type DragEvent, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { useQueryClient } from "@tanstack/react-query";
import {
  getGetAdminPostQueryKey,
  getListAllPostsQueryKey,
  useCreatePost,
  useDeletePost,
  useGetAdminPost,
  useListLeagues,
  usePreviewPost,
  useUpdatePost,
} from "../../../api/generated/sbl";
import { PostKind, type PostAdmin, type PostCreate } from "../../../api/types";
import { useAsync, useInvalidate } from "../../../api/useApi";
import { ErrorMessage, Loading } from "../../../components/Blocks";
import { ConfirmButton } from "../../../components/ConfirmButton";
import { Field, Message } from "../../../components/Form";
import { MediaContextSelect } from "../../../components/MediaContextSelect";
import { MediaPicker } from "../../../components/MediaPicker";
import { Select } from "../../../components/Select";
import { MEMBER_LEAGUES, leaguePhoto } from "../../../content";
import { INPUT_CLASS, errorText } from "../../../lib/admin";
import { todayIso } from "../../../lib/format";
import { repeatsTitle } from "../../../lib/postTitle";
import { href } from "../../../lib/site";
import { useLeaveGuard } from "../../../lib/useLeaveGuard";
import { filesIn, usePhotoUpload } from "../../../lib/usePhotoUpload";
import { ArticleView } from "../../league/ArticleView";
import { NewEntryPage } from "../../AdminNewPage";

// TipTap and ProseMirror are only needed here — not by a single reader of the site.
const RichTextEditor = lazy(() => import("../../../components/RichTextEditor"));

/** The form's state: the request's fields, with every text a string — an empty one is
 *  sent as it is and the server reads it as "none". */
type TextFields = "teaser" | "author" | "quote" | "quote_by" | "photo_credit" | "published_on";
type Draft = Required<Omit<PostCreate, TextFields>> & Record<TextFields, string>;

/** Where a change to a post shows: editorial's list and page, and the public site. */
const POST_PATHS = ["/api/admin/posts", "/api/posts"];

/** Unsaved changes, kept on this device as they are typed (Story R-1) — offered back when
 *  the post is opened again, never sent by themselves: an automatic save would put half
 *  an edit of a published post live. Per post; a new one has its own. */
type Kept = { draft: Draft; at: string; basedOn: string | null };
const keptKey = (postId: number | undefined) => `sbl.post-draft.${postId ?? "new"}`;

function readKept(postId: number | undefined): Kept | null {
  try {
    const raw = localStorage.getItem(keptKey(postId));
    return raw ? (JSON.parse(raw) as Kept) : null;
  } catch {
    return null;
  }
}

function writeKept(postId: number | undefined, kept: Kept | null) {
  try {
    if (kept) localStorage.setItem(keptKey(postId), JSON.stringify(kept));
    else localStorage.removeItem(keptKey(postId));
  } catch {
    // Without storage nothing is kept; leaving still asks first.
  }
}

const same = (a: Draft, b: Draft) => JSON.stringify(a) === JSON.stringify(b);

/** The form's state for this post — or for a new one, a news draft dated today. */
function draftOf(post?: PostAdmin): Draft {
  return {
    kind: post?.kind ?? PostKind.news,
    title: post?.title ?? "",
    published_on: post?.published_on ?? todayIso(),
    league_id: post?.league_id ?? null,
    teaser: post?.teaser ?? "",
    body: post?.body ?? "",
    author: post?.author ?? "",
    quote: post?.quote ?? "",
    quote_by: post?.quote_by ?? "",
    photo_url: post?.photo_url ?? null,
    photo_credit: post?.photo_credit ?? "",
    event_id: post?.event_id ?? null,
    series_id: post?.series_id ?? null,
    published: post?.published ?? false,
  };
}

/** `/admin/news/new` and `/admin/news/:id` — Story R-1: one page to write a post and to
 *  correct it. A new post is saved as a draft unless editorial publishes it right away;
 *  after the first save the page is the post's own. */
export function AdminPostPage() {
  const { t } = useTranslation("admin");
  const { id } = useParams();
  const postId = id ? Number(id) : null;
  const post = useAsync(useGetAdminPost(postId ?? 0, { query: { enabled: postId !== null } }));
  const title = postId === null ? t("posts.newButton") : (post.data?.title ?? t("posts.title"));

  return (
    <NewEntryPage title={title} testId="admin-post">
      {postId === null ? (
        <PostForm />
      ) : (
        <>
          {post.loading && <Loading testId="admin-post-loading" />}
          {post.error && <ErrorMessage text={post.error} testId="admin-post-error" />}
          {post.data && <PostForm post={post.data} key={post.data.id} />}
        </>
      )}
    </NewEntryPage>
  );
}

function PostForm({ post }: { post?: PostAdmin }) {
  const { t } = useTranslation("admin");
  const navigate = useNavigate();
  const invalidate = useInvalidate();
  const leagues = useAsync(useListLeagues());
  const [draft, setDraft] = useState<Draft>(() => draftOf(post));
  const [saved, setSaved] = useState(false);
  // Changed since it was loaded or last saved: leaving then asks first.
  const [dirty, setDirty] = useState(false);
  useLeaveGuard(dirty, t("posts.leaveUnsaved"));
  // What this device kept of an earlier visit, if it differs from what is stored.
  const [offered, setOffered] = useState<Kept | null>(() => {
    const kept = readKept(post?.id);
    return kept && !same(kept.draft, draftOf(post)) ? kept : null;
  });
  useEffect(() => {
    if (!dirty) return;
    const timer = window.setTimeout(
      () => writeKept(post?.id, { draft, at: new Date().toISOString(), basedOn: post?.updated_at ?? null }),
      400,
    );
    return () => window.clearTimeout(timer);
  }, [draft, dirty, post?.id, post?.updated_at]);
  const forget = () => {
    writeKept(post?.id, null);
    setOffered(null);
  };
  const [previewing, setPreviewing] = useState(false);
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => {
    setSaved(false);
    setDirty(true);
    setDraft((d) => ({ ...d, [key]: value }));
  };

  // The answer to a save *is* the post as it now stands: it goes straight into this
  // post's query instead of being asked for again. Only the lists and the public site,
  // which show it among others, are refetched.
  const queryClient = useQueryClient();
  const stored = (saved: PostAdmin) => {
    queryClient.setQueryData(getGetAdminPostQueryKey(saved.id), saved);
    invalidate(getListAllPostsQueryKey(), "/api/posts");
  };
  const create = useCreatePost({
    mutation: {
      onSuccess: (created) => {
        stored(created);
        setDirty(false);
        writeKept(undefined, null);
        navigate(`/admin/news/${created.id}`, { replace: true });
      },
    },
  });
  const update = useUpdatePost({
    mutation: {
      onSuccess: (updated) => {
        stored(updated);
        // Published or not is what the server now holds — never what was asked for.
        setDraft((d) => ({ ...d, published: updated.published }));
        setDirty(false);
        forget();
        setSaved(true);
      },
    },
  });
  const pending = create.isPending || update.isPending;
  // The title is a field of its own: a text that starts with it again cannot be saved.
  const titleInText = repeatsTitle(draft.body, draft.title);
  const failure = create.error ?? update.error;

  const save = (published = draft.published) => {
    const data = { ...draft, published, published_on: draft.published_on || todayIso() };
    if (post) update.mutate({ postId: post.id, data });
    else create.mutate({ data });
  };

  const news = draft.kind === PostKind.news;
  // An association's post is shown under the first member league (`content`, `Home.tsx`).
  const publicLeague = post?.league ?? MEMBER_LEAGUES[0];
  const leagueSlug = leagues.data?.find((l) => l.id === draft.league_id)?.slug ?? MEMBER_LEAGUES[0];

  if (previewing) return <Preview draft={draft} onBack={() => setPreviewing(false)} />;

  return (
    <form
      className="grid grid-cols-[minmax(0,1fr)] gap-4"
      data-testid="admin-post-form"
      onSubmit={(e: FormEvent) => {
        e.preventDefault();
        save();
      }}
    >
      {offered && (
        <div
          className="flex flex-wrap items-center gap-3 rounded-md border border-warning/50 bg-warning-soft px-3 py-2 text-sm text-warning-soft-foreground"
          data-testid="admin-post-kept"
        >
          <span className="min-w-0 flex-1">
            {t("posts.keptOffer", { at: new Date(offered.at) })}
            {post && offered.basedOn !== post.updated_at && <> {t("posts.keptStale")}</>}
          </span>
          <Button
            size="sm"
            onPress={() => {
              setDraft(offered.draft);
              setDirty(true);
              setSaved(false);
              setOffered(null);
            }}
            data-testid="admin-post-kept-restore"
          >
            {t("posts.keptRestore")}
          </Button>
          <Button size="sm" variant="ghost" onPress={forget} data-testid="admin-post-kept-discard">
            {t("posts.keptDiscard")}
          </Button>
        </div>
      )}

      <div className="grid grid-cols-[minmax(0,1fr)] gap-4 sm:grid-cols-3">
        <Field label={t("posts.kindLabel")}>
          <Select value={draft.kind} onChange={(e) => set("kind", e.target.value as PostKind)} testId="admin-post-kind-select">
            <option value={PostKind.news}>{t("posts.kind.news")}</option>
            <option value={PostKind.press}>{t("posts.kind.press")}</option>
          </Select>
        </Field>
        <Field label={t("posts.leagueLabel")} hint={t("posts.leagueHint")}>
          <Select
            value={draft.league_id ?? ""}
            onChange={(e) => set("league_id", e.target.value ? Number(e.target.value) : null)}
            testId="admin-post-league-select"
          >
            <option value="">{t("posts.association")}</option>
            {(leagues.data ?? []).map((league) => (
              <option key={league.id} value={league.id}>
                {league.short_name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t("posts.dateLabel")}>
          <input
            type="date"
            className={INPUT_CLASS}
            value={draft.published_on}
            onChange={(e) => set("published_on", e.target.value)}
            data-testid="admin-post-date-input"
          />
        </Field>
      </div>

      <Field label={t("posts.titleLabel")} hint={t("posts.titleHint")}>
        <input
          className={`${INPUT_CLASS} text-lg font-semibold`}
          value={draft.title}
          onChange={(e) => set("title", e.target.value)}
          required
          minLength={3}
          maxLength={200}
          placeholder={t("posts.titlePlaceholder")}
          data-testid="admin-post-title-input"
        />
      </Field>

      {news && (
        <Field label={t("posts.teaserLabel")} hint={t("posts.teaserHint")}>
          <textarea
            className={INPUT_CLASS}
            rows={2}
            maxLength={500}
            value={draft.teaser}
            onChange={(e) => set("teaser", e.target.value)}
            data-testid="admin-post-teaser-input"
          />
        </Field>
      )}

      <div className="text-sm">
        <p className="mb-1 font-medium text-foreground">{t("posts.bodyLabel")}</p>
        <Suspense fallback={<Loading testId="admin-post-editor-loading" />}>
          <RichTextEditor
            // The editor reads its value once: a restored draft is a new editor.
            key={offered === null ? "editing" : "offered"}
            value={draft.body}
            onChange={(html) => set("body", html)}
            testId="admin-post-editor"
          />
        </Suspense>
        {titleInText && <ErrorMessage text={t("posts.titleInText")} testId="admin-post-title-in-text" />}
      </div>

      <Field label={t("posts.regattaLabel")} hint={t("posts.regattaHint")}>
        <MediaContextSelect
          value={{ event_id: draft.event_id, series_id: draft.series_id }}
          onChange={(context) => {
            set("event_id", context.event_id ?? null);
            set("series_id", context.series_id ?? null);
          }}
          noneLabel={t("posts.regattaNone")}
          testId="admin-post-regatta-select"
        />
      </Field>

      {news && (
        <>
          <PhotoPicker
            url={draft.photo_url}
            credit={draft.photo_credit}
            fallback={leaguePhoto(leagueSlug).src}
            onChange={(url, credit) => {
              set("photo_url", url);
              set("photo_credit", credit);
            }}
          />
          <div className="grid grid-cols-[minmax(0,1fr)] gap-4 sm:grid-cols-[2fr_1fr]">
            <Field label={t("posts.quoteLabel")} hint={t("posts.optional")}>
              <input className={INPUT_CLASS} value={draft.quote} onChange={(e) => set("quote", e.target.value)} data-testid="admin-post-quote-input" />
            </Field>
            <Field label={t("posts.quoteByLabel")}>
              <input className={INPUT_CLASS} value={draft.quote_by} onChange={(e) => set("quote_by", e.target.value)} data-testid="admin-post-quote-by-input" />
            </Field>
          </div>
          <Field label={t("posts.authorLabel")} hint={t("posts.optional")}>
            <input className={INPUT_CLASS} value={draft.author} onChange={(e) => set("author", e.target.value)} data-testid="admin-post-author-input" />
          </Field>
        </>
      )}

      <Message success={saved ? t("posts.saved") : null} error={failure ? errorText(failure, t("posts.saveError")) : null} testId="admin-post-save" />

      <div className="flex flex-wrap items-center gap-3">
        {/* Publishing must never look like an ordinary save: on a draft, Publish is the one
            primary button; on a published post, Save is, and withdrawing is the quiet one. */}
        <Button
          type="submit"
          variant={draft.published ? "primary" : "outline"}
          isDisabled={pending || titleInText}
          data-testid="admin-post-save-button"
        >
          {draft.published ? t("posts.saveButton") : t("posts.saveDraftButton")}
        </Button>
        <Button
          variant={draft.published ? "ghost" : "primary"}
          isDisabled={pending || titleInText || draft.title.trim().length < 3}
          onPress={() => save(!draft.published)}
          data-testid={draft.published ? "admin-post-unpublish-button" : "admin-post-publish-button"}
        >
          {draft.published ? t("posts.unpublishButton") : t("posts.publishButton")}
        </Button>
        <Button
          variant="ghost"
          isDisabled={titleInText || draft.title.trim().length < 3}
          onPress={() => setPreviewing(true)}
          data-testid="admin-post-preview-button"
        >
          {t("posts.previewButton")}
        </Button>
        {post?.published && (
          <Link
            to={post.kind === PostKind.news ? href.article(publicLeague, post.slug) : href.press(publicLeague)}
            className="text-sm font-medium text-link hover:underline"
            data-testid="admin-post-view-link"
          >
            {t("posts.viewLink")}
          </Link>
        )}
        <span className="flex-1" />
        <Link to="/admin?tab=news" className="text-sm text-muted hover:underline" data-testid="admin-post-back-link">
          {t("page.backButton")}
        </Link>
        {post && <DeleteButton postId={post.id} />}
      </div>
    </form>
  );
}

/** The post's picture, from the library or uploaded into it — and its credit. */
function PhotoPicker({
  url,
  credit,
  fallback,
  onChange,
}: {
  url: string | null;
  credit: string;
  fallback: string;
  onChange: (url: string | null, credit: string) => void;
}) {
  const { t } = useTranslation("admin");
  const photo = usePhotoUpload((item) => onChange(item.url, item.credit ?? ""));
  const [over, setOver] = useState(false);
  const [picking, setPicking] = useState(false);

  // The preview is the drop target: a picture dragged out of a folder onto it replaces it.
  const drop = (event: DragEvent) => {
    event.preventDefault();
    setOver(false);
    const [file] = filesIn(event.dataTransfer.files);
    if (file) void photo.upload(file).then((item) => item && onChange(item.url, item.credit ?? ""));
  };

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-3 text-sm sm:grid-cols-[12rem_minmax(0,1fr)]">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={drop}
        className={`rounded-md ${over ? "ring-2 ring-focus ring-offset-2" : ""}`}
        data-testid="admin-post-photo-dropzone"
      >
        <img
          src={url ?? fallback}
          alt=""
          className={`aspect-[3/2] w-full rounded-md object-cover ${url ? "" : "opacity-50"} ${photo.busy ? "animate-pulse" : ""}`}
          data-testid="admin-post-photo-preview"
        />
      </div>
      <div className="grid content-start gap-3">
        <p className="font-medium text-foreground">
          {t("posts.photoLabel")}
          {!url && <span className="ml-2 font-normal text-muted">{t("posts.photoNone")}</span>}
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" variant="outline" onPress={() => setPicking((open) => !open)} data-testid="admin-post-photo-library-button">
            {t("posts.photoFromLibrary")}
          </Button>
          <Button size="sm" variant="outline" isDisabled={photo.busy} onPress={photo.pick} data-testid="admin-post-photo-upload-button">
            {photo.busy ? t("posts.photoUploading") : t("posts.photoUpload")}
          </Button>
          <span className="text-xs text-muted pointer-coarse:hidden">{t("posts.photoDrop")}</span>
          {url && (
            <Button size="sm" variant="ghost" onPress={() => onChange(null, "")} data-testid="admin-post-photo-remove-button">
              {t("posts.photoRemove")}
            </Button>
          )}
        </div>
        <input {...photo.input} data-testid="admin-post-photo-input" />
        {picking && (
          <MediaPicker
            onPick={(item) => {
              onChange(item.url, item.credit ?? "");
              setPicking(false);
            }}
            onClose={() => setPicking(false)}
            testId="admin-post-photo-picker"
          />
        )}
        {url && (
          <Field label={t("posts.photoCreditLabel")}>
            <input className={INPUT_CLASS} value={credit} onChange={(e) => onChange(url, e.target.value)} data-testid="admin-post-photo-credit-input" />
          </Field>
        )}
        {photo.error && <ErrorMessage text={photo.error} testId="admin-post-photo-error" />}
      </div>
    </div>
  );
}

/** The post as readers will see it, saved or not (Story R-1): the server answers what its
 *  public page would — pictures with the library's sizes and credits — and the public
 *  page's own view shows it. Nothing is stored. */
function Preview({ draft, onBack }: { draft: Draft; onBack: () => void }) {
  const { t } = useTranslation("admin");
  const preview = usePreviewPost();
  const { mutate } = preview;
  useEffect(() => {
    mutate({ data: { ...draft, published_on: draft.published_on || todayIso() } });
  }, [draft, mutate]);
  const back = (
    <Button variant="outline" onPress={onBack} data-testid="admin-post-preview-back">
      {t("posts.previewBack")}
    </Button>
  );

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-4" data-testid="admin-post-preview">
      <div className="flex flex-wrap items-center gap-3 rounded-md bg-warning-soft px-3 py-2 text-sm text-warning-soft-foreground">
        <span className="min-w-0 flex-1">{t("posts.previewNote")}</span>
        {back}
      </div>
      {preview.isPending && <Loading testId="admin-post-preview-loading" />}
      {preview.error && <ErrorMessage text={errorText(preview.error, t("posts.previewError"))} testId="admin-post-preview-error" />}
      {preview.data && (
        // The public page sets the article on its league's dark backdrop, in the dark
        // theme whatever the editor's own; so does this.
        <div data-theme="dark" className="dark overflow-hidden rounded-lg bg-background p-3 text-foreground sm:p-6" data-testid="admin-post-preview-article">
          <ArticleView post={preview.data} header />
        </div>
      )}
      <div>{back}</div>
    </div>
  );
}

function DeleteButton({ postId }: { postId: number }) {
  const { t } = useTranslation("admin");
  const navigate = useNavigate();
  const invalidate = useInvalidate();
  const remove = useDeletePost({
    mutation: {
      onSuccess: () => {
        invalidate(...POST_PATHS);
        navigate("/admin?tab=news");
      },
    },
  });
  return (
    <ConfirmButton
      label={t("posts.deleteButton")}
      confirmLabel={t("posts.deleteConfirm")}
      cancelLabel={t("posts.deleteCancel")}
      busy={remove.isPending}
      onConfirm={() => remove.mutate({ postId })}
      testId="admin-post-delete"
    />
  );
}
