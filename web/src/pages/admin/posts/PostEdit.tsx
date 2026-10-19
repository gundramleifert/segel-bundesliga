import { Button } from "@heroui/react";
import { Suspense, lazy, useState, type FormEvent } from "react";
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
  useUpdatePost,
} from "../../../api/generated/sbl";
import { PostKind, type PostAdmin, type PostCreate } from "../../../api/types";
import { useAsync, useInvalidate } from "../../../api/useApi";
import { ErrorMessage, Loading } from "../../../components/Blocks";
import { ConfirmButton } from "../../../components/ConfirmButton";
import { Field, Message } from "../../../components/Form";
import { Select } from "../../../components/Select";
import { DSBL_PHOTOS, MEMBER_LEAGUES, OWN_PHOTOS, leaguePhoto } from "../../../content";
import { INPUT_CLASS, errorText } from "../../../lib/admin";
import { todayIso } from "../../../lib/format";
import { href } from "../../../lib/site";
import { usePhotoUpload } from "../../../lib/usePhotoUpload";
import { NewEntryPage } from "../../AdminNewPage";

// TipTap and ProseMirror are only needed here — not by a single reader of the site.
const RichTextEditor = lazy(() => import("../../../components/RichTextEditor"));

/** The site's own pictures, offered beside an upload (Story R-1). */
const LIBRARY = [...Object.values(DSBL_PHOTOS), ...Object.values(OWN_PHOTOS)];

/** The form's state: the request's fields, with every text a string — an empty one is
 *  sent as it is and the server reads it as "none". */
type TextFields = "teaser" | "author" | "quote" | "quote_by" | "photo_credit" | "published_on";
type Draft = Required<Omit<PostCreate, TextFields>> & Record<TextFields, string>;

/** Where a change to a post shows: editorial's list and page, and the public site. */
const POST_PATHS = ["/api/admin/posts", "/api/posts"];

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
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => {
    setSaved(false);
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
        navigate(`/admin/news/${created.id}`, { replace: true });
      },
    },
  });
  const update = useUpdatePost({
    mutation: {
      onSuccess: (updated) => {
        stored(updated);
        setSaved(true);
      },
    },
  });
  const pending = create.isPending || update.isPending;
  const failure = create.error ?? update.error;

  const save = (published = draft.published) => {
    const data = { ...draft, published, published_on: draft.published_on || todayIso() };
    if (post) update.mutate({ postId: post.id, data });
    else create.mutate({ data });
    set("published", published);
  };

  const news = draft.kind === PostKind.news;
  // An association's post is shown under the first member league (`content`, `Home.tsx`).
  const publicLeague = post?.league ?? MEMBER_LEAGUES[0];
  const leagueSlug = leagues.data?.find((l) => l.id === draft.league_id)?.slug ?? MEMBER_LEAGUES[0];

  return (
    <form
      className="grid grid-cols-[minmax(0,1fr)] gap-4"
      data-testid="admin-post-form"
      onSubmit={(e: FormEvent) => {
        e.preventDefault();
        save();
      }}
    >
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

      <Field label={t("posts.titleLabel")}>
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
        <p className="mb-1 font-medium text-slate-700">{t("posts.bodyLabel")}</p>
        <Suspense fallback={<Loading testId="admin-post-editor-loading" />}>
          <RichTextEditor value={draft.body} onChange={(html) => set("body", html)} testId="admin-post-editor" />
        </Suspense>
      </div>

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
        <Button type="submit" isDisabled={pending} data-testid="admin-post-save-button">
          {draft.published ? t("posts.saveButton") : t("posts.saveDraftButton")}
        </Button>
        <Button
          variant={draft.published ? "outline" : "primary"}
          isDisabled={pending || draft.title.trim().length < 3}
          onPress={() => save(!draft.published)}
          data-testid={draft.published ? "admin-post-unpublish-button" : "admin-post-publish-button"}
        >
          {draft.published ? t("posts.unpublishButton") : t("posts.publishButton")}
        </Button>
        {post?.published && (
          <Link
            to={post.kind === PostKind.news ? href.article(publicLeague, post.slug) : href.press(publicLeague)}
            className="text-sm font-medium text-brand-700 hover:underline"
            data-testid="admin-post-view-link"
          >
            {t("posts.viewLink")}
          </Link>
        )}
        <span className="flex-1" />
        <Link to="/admin?tab=news" className="text-sm text-slate-600 hover:underline" data-testid="admin-post-back-link">
          {t("page.backButton")}
        </Link>
        {post && <DeleteButton postId={post.id} />}
      </div>
    </form>
  );
}

/** The post's picture: uploaded, or one of the site's own — and its credit. */
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
  const photo = usePhotoUpload((uploaded) => onChange(uploaded, ""));
  const fromLibrary = LIBRARY.find((p) => p.src === url);

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-3 text-sm sm:grid-cols-[12rem_minmax(0,1fr)]">
      <img
        src={url ?? fallback}
        alt=""
        className={`aspect-[3/2] w-full rounded-md object-cover ${url ? "" : "opacity-50"}`}
        data-testid="admin-post-photo-preview"
      />
      <div className="grid content-start gap-3">
        <p className="font-medium text-slate-700">
          {t("posts.photoLabel")}
          {!url && <span className="ml-2 font-normal text-slate-500">{t("posts.photoNone")}</span>}
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" variant="outline" isDisabled={photo.busy} onPress={photo.pick} data-testid="admin-post-photo-upload-button">
            {photo.busy ? t("posts.photoUploading") : t("posts.photoUpload")}
          </Button>
          <Select
            size="inline"
            value={fromLibrary?.src ?? ""}
            onChange={(e) => {
              const photo = LIBRARY.find((p) => p.src === e.target.value);
              if (photo) onChange(photo.src, photo.credit);
            }}
            testId="admin-post-photo-library-select"
            aria-label={t("posts.photoLibrary")}
          >
            <option value="">{t("posts.photoLibrary")}</option>
            {LIBRARY.map((photo) => (
              <option key={photo.src} value={photo.src}>
                {photo.alt}
              </option>
            ))}
          </Select>
          {url && (
            <Button size="sm" variant="ghost" onPress={() => onChange(null, "")} data-testid="admin-post-photo-remove-button">
              {t("posts.photoRemove")}
            </Button>
          )}
        </div>
        <input {...photo.input} data-testid="admin-post-photo-input" />
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
