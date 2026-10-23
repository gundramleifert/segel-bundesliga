import { useTranslation } from "react-i18next";

import type { Post } from "../../api/types";
import { RichText } from "../../components/RichText";
import { PAGE_TITLE, Panel, tone } from "../../components/site/Cards";
import { Link } from "react-router-dom";

import { Gallery } from "../../components/site/Gallery";
import { Img } from "../../components/site/Media";
import { articleOf, fromLibrary } from "../../content";
import { href } from "../../lib/site";
import { formatDate } from "../../lib/format";
import { ExampleNote } from "./shared";

/** One article as a reader sees it — Story R-1. Takes the post instead of reading it, so
 *  the public page and editorial's preview render the same thing: the page passes what
 *  `GET /api/posts/{slug}` answered, the preview what `…/preview` did.
 *
 *  On the public page the title, date and cover are the depth page's own header and
 *  picture (`DepthPage`), so it shows only the article. `header` adds them here, the way
 *  that header shows them, for a preview that has no depth page around it. */
export function ArticleView({ post, header = false }: { post: Post; header?: boolean }) {
  const photos = (post.gallery ?? []).map(fromLibrary);
  const { t } = useTranslation("site");
  const article = articleOf(post);
  return (
    <>
      {header && (
        <header className="relative mb-6 overflow-hidden rounded-2xl bg-background text-foreground" data-testid="site-article-header">
          <div aria-hidden className="absolute inset-0">
            {article.photo && <Img photo={article.photo} />}
            <div className="absolute inset-0 bg-gradient-to-t from-background/90 via-background/40 to-background/10" />
          </div>
          <div className="relative px-4 pb-8 pt-32 sm:px-8">
            <p className="text-xs font-semibold uppercase tracking-widest text-muted" data-testid="site-kicker">
              {`${t("pages.news")} · ${formatDate(article.date)}`}
            </p>
            <h1 className={`mt-2 ${PAGE_TITLE}`}>{article.title}</h1>
          </div>
        </header>
      )}
      {article.example && <ExampleNote text={t("news.example")} />}
      {/* Text to read closely: one column of a reading width, centred on its glass. */}
      <Panel width="reading" className="mb-12 sm:p-10">
        <article data-testid="site-article">
          <p className="text-xl font-medium leading-relaxed text-foreground" data-testid="site-article-lead">{article.teaser}</p>
          {article.author && (
            <p className="mt-3 text-sm text-muted" data-testid="site-article-byline">
              {t("news.byline", { author: article.author, date: formatDate(article.date) })}
            </p>
          )}
          <RichText html={article.body} className="mt-8 text-lg leading-relaxed text-foreground" testId="site-article-body" />
          {article.quote && (
            <blockquote className="my-10 border-l-4 border-accent pl-6">
              <p className="text-2xl font-semibold leading-snug tracking-tight text-foreground">“{article.quote.text}”</p>
              <footer className="mt-2 text-sm text-muted">— {article.quote.by}</footer>
            </blockquote>
          )}
        </article>
      </Panel>
      {/* The regatta's photos, by themselves (Story R-1): the post names an event or a
          series, the library has the pictures. */}
      {photos.length > 0 && (
        <section className="mb-12" data-testid="site-article-gallery">
          <h2 className={`mb-4 text-xl font-semibold ${tone.text}`}>{t("news.galleryTitle", { regatta: post.regatta ?? "" })}</h2>
          <Gallery photos={photos} grouped={false} />
          {(post.gallery_total ?? 0) > photos.length && post.league && (
            <Link to={href.media(post.league)} className={`text-sm font-medium ${tone.link}`} data-testid="site-article-gallery-more">
              {t("news.galleryMore", { count: post.gallery_total ?? 0 })}
            </Link>
          )}
        </section>
      )}
    </>
  );
}
