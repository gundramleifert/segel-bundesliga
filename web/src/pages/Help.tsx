import { Children, useEffect, useMemo, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useParams } from "react-router-dom";
import Markdown, { defaultUrlTransform, type Components, type ExtraProps } from "react-markdown";
import remarkGfm from "remark-gfm";

import { useMyContexts, useWardWaivers } from "../api/generated/sbl";
import type { Account, MyContext } from "../api/types";
import { useAccount } from "../api/useApi";
import { Loading, PageHeader, TableFrame } from "../components/Blocks";
import { CardGrid, Stack } from "../components/Layouts";
import { LinkCard } from "../components/LinkCard";
import {
  AUDIENCES,
  anchorPath,
  getPage,
  helpLocale,
  helpPath,
  pagesOfType,
  relatedPages,
  searchPages,
  startPageId,
  type Audience,
} from "../handbook";
import { useMediaQuery } from "../lib/useMediaQuery";

/** Story B-18: the help for what I do.
 *
 * The pages are markdown files in `web/src/handbook/`, written from the stories and
 * journeys by the `handbook` skill; this file only renders them. It replaced a
 * hand-written roles matrix and seven how-to cards that had gone stale in five places —
 * the matrix is now the `roles` page, the cards are guides.
 *
 * **For signed-in accounts only.** The handbook is internal: the public site must explain
 * itself, so a guest gets a sign-in prompt here and no page content. Signed in, **nothing
 * is hidden** — every page is readable by every account, because someone about to become
 * a team manager should be able to read what that means. Who you are only *orders* the
 * audiences.
 *
 * (The store is still bundled into the public JavaScript by the eager glob, so its text
 * is not secret — it contains nothing that has to be. The gate is about what the public
 * site shows, not about protecting the content.)
 */

// ------------------------------------------------------------------ Who the reader is

/** Which audiences a signed-in person *has*, from the same answer my space uses
 *  (`GET /api/me/contexts`, Story Z-8) plus the summary site roles. Someone with none
 *  sees the audiences in their usual order. */
/** A parent linked to a child as guardian (Story V-13) reads the sailor's pages for that
 * child — the waiver above all (S-8). The link sits on the sailor, which neither the
 * account's roles nor my space's contexts list, so it comes from the wards themselves. */
function audiencesOf(account: Account | null, contexts: MyContext[], hasWards: boolean): Set<Audience> {
  const out = new Set<Audience>();
  if (!account) return out;
  if (hasWards) out.add("sailor");
  const byRole: Record<string, Audience> = {
    admin: "administration",
    editor: "administration",
    race_officer: "race-committee",
    jury: "race-committee",
    series_manager: "event-organizer",
    event_manager: "event-organizer",
    helper: "event-organizer",
    team_manager: "club",
    club_admin: "club",
    treasurer: "treasurer",
  };
  for (const role of account.roles) if (byRole[role]) out.add(byRole[role]);
  for (const context of contexts) {
    for (const relation of context.relations) {
      if (relation === "sailor" || relation === "member") out.add("sailor");
      else if (relation === "treasurer") out.add("treasurer");
      else if (relation === "race_officer" || relation === "jury") out.add("race-committee");
      else if (relation === "manager" || relation === "admin" || relation === "helper") {
        out.add(context.kind === "club" && relation !== "helper" ? "club" : "event-organizer");
      }
    }
  }
  return out;
}

function useReaderAudiences(): { mine: Set<Audience>; signedIn: boolean } {
  const { account } = useAccount();
  const contexts = useMyContexts({
    query: { enabled: Boolean(account), staleTime: 5 * 60_000, refetchOnWindowFocus: false },
  });
  const wards = useWardWaivers({
    query: { enabled: Boolean(account), staleTime: 5 * 60_000, refetchOnWindowFocus: false },
  });
  const hasWards = (wards.data?.length ?? 0) > 0;
  const mine = useMemo(
    () => audiencesOf(account, account ? (contexts.data?.contexts ?? []) : [], hasWards),
    [account, contexts.data, hasWards],
  );
  return { mine, signedIn: Boolean(account) };
}

// ------------------------------------------------------------------ The landing page

/** Only for a signed-in account; a guest gets a short prompt and nothing else. */
function SignedInOnly({ children }: { children: ReactNode }) {
  const { t } = useTranslation("help");
  const { account, loading } = useAccount();
  if (loading) return <Loading testId="help-loading" />;
  if (account) return <>{children}</>;
  return (
    <Stack gap={4} testId="help-sign-in">
      <PageHeader title={t("title")} />
      <p className="max-w-2xl text-slate-600">{t("signIn.text")}</p>
      <p>
        <Link
          to="/account"
          data-testid="help-sign-in-link"
          className="inline-block rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
        >
          {t("signIn.link")}
        </Link>
      </p>
    </Stack>
  );
}

export function HelpLanding() {
  return (
    <SignedInOnly>
      <Landing />
    </SignedInOnly>
  );
}

export function HelpPageView() {
  return (
    <SignedInOnly>
      <PageView />
    </SignedInOnly>
  );
}

function Landing() {
  const { t, i18n } = useTranslation("help");
  const language = i18n.resolvedLanguage;
  const [query, setQuery] = useState("");
  const { mine } = useReaderAudiences();

  // Theirs first, in the usual order; then the rest.
  const audiences = [...AUDIENCES.filter((a) => mine.has(a)), ...AUDIENCES.filter((a) => !mine.has(a))];
  const journeys = pagesOfType("journey", language);
  const lookup = [...pagesOfType("doc", language), ...pagesOfType("faq", language)];
  const empty = !journeys.length && !lookup.length && !pagesOfType("start", language).length;

  return (
    <Stack gap={8} testId="help-landing">
      <PageHeader title={t("title")} />
      <p className="max-w-3xl text-slate-600">{t("intro")}</p>

      <label className="flex max-w-xl flex-col gap-1">
        <span className="text-sm font-medium text-slate-700">{t("search.label")}</span>
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t("search.placeholder")}
          data-testid="help-search"
          className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
        />
      </label>

      {query.trim() ? (
        <SearchResults query={query} />
      ) : (
        <>
          <section className="flex flex-col gap-3" data-testid="help-audiences">
            <div>
              <h2 className="text-lg font-semibold">{t("audiencesTitle")}</h2>
              {mine.size > 0 && <p className="text-sm text-slate-500">{t("audiencesSignedIn")}</p>}
            </div>
            <CardGrid columns={3}>
              {audiences.map((audience) => (
                <li key={audience}>
                  <LinkCard
                    to={helpPath(startPageId(audience))}
                    testId={`help-audience-${audience}`}
                    title={t(`audiences.${audience}.title`)}
                    description={t(`audiences.${audience}.description`)}
                    aside={mine.has(audience) ? <MineChip testId={`help-audience-${audience}-mine`} /> : undefined}
                  />
                </li>
              ))}
            </CardGrid>
          </section>

          {empty && (
            <p className="text-slate-500" data-testid="help-empty">
              {t("empty")}
            </p>
          )}

          {journeys.length > 0 && (
            <section className="flex flex-col gap-3" data-testid="help-journeys">
              <div>
                <h2 className="text-lg font-semibold">{t("journeysTitle")}</h2>
                <p className="text-sm text-slate-500">{t("journeysIntro")}</p>
              </div>
              <CardGrid>
                {journeys.map((page) => (
                  <li key={page.id}>
                    <LinkCard
                      to={helpPath(page.id)}
                      testId={`help-journey-${page.id}`}
                      title={page.title}
                      description={page.audience.map((a) => t(`audiences.${a}.title`)).join(" · ")}
                    />
                  </li>
                ))}
              </CardGrid>
            </section>
          )}

          {lookup.length > 0 && (
            <section className="flex flex-col gap-3" data-testid="help-lookup">
              <h2 className="text-lg font-semibold">{t("lookupTitle")}</h2>
              <CardGrid columns={3}>
                {lookup.map((page) => (
                  <li key={page.id}>
                    <LinkCard
                      to={helpPath(page.id)}
                      testId={`help-page-${page.id}`}
                      title={page.title}
                      description={t(`types.${page.type}`)}
                    />
                  </li>
                ))}
              </CardGrid>
            </section>
          )}
        </>
      )}
    </Stack>
  );
}

function MineChip({ testId }: { testId: string }) {
  const { t } = useTranslation("help");
  return (
    <span
      data-testid={testId}
      className="shrink-0 rounded-full bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-800 ring-1 ring-inset ring-brand-200"
    >
      {t("mine")}
    </span>
  );
}

/** Titles, headings and search words, in either language — client-side, the store is
 *  small. A matching section links straight to its anchor. */
function SearchResults({ query }: { query: string }) {
  const { t, i18n } = useTranslation("help");
  const hits = searchPages(query, i18n.resolvedLanguage);

  return (
    <section className="flex flex-col gap-3" data-testid="help-search-results" aria-live="polite">
      <p className="text-sm text-slate-500">
        {hits.length ? t("search.results", { count: hits.length }) : t("search.none", { query: query.trim() })}
      </p>
      <ul className="flex flex-col gap-3">
        {hits.map(({ page, headings }) => (
          <li
            key={page.id}
            data-testid={`help-result-${page.id}`}
            className="min-w-0 rounded-xl bg-white px-4 py-3 shadow-sm ring-1 ring-slate-200"
          >
            <Link to={helpPath(page.id)} className="font-medium text-brand-700 hover:underline">
              {page.title}
            </Link>
            <span className="ml-2 text-xs text-slate-500">{t(`types.${page.type}`)}</span>
            {headings.length > 0 && (
              <ul className="mt-1 flex flex-col gap-0.5 text-sm">
                {headings.map((heading) => (
                  <li key={heading.anchor}>
                    <Link
                      to={helpPath(page.id, heading.anchor!)}
                      data-testid={`help-result-${page.id}-${heading.anchor}`}
                      className="text-slate-600 hover:underline"
                    >
                      {heading.text}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

// ------------------------------------------------------------------ One page

function PageView() {
  const { page: id = "" } = useParams();
  const { t, i18n } = useTranslation("help");
  const language = i18n.resolvedLanguage;
  const page = getPage(id, language);
  const { hash } = useLocation();

  // `/help/roles#roles-matrix` lands on the section, in a fresh tab too. Deferred one
  // tick: the layout's scroll-to-top runs in the *parent's* effect, which comes after
  // this one, and would otherwise undo it.
  useEffect(() => {
    if (!hash) return;
    const timer = window.setTimeout(() => {
      document.getElementById(decodeURIComponent(hash.slice(1)))?.scrollIntoView();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [hash, page?.id, page?.locale]);

  if (!page) {
    return (
      <Stack gap={4} testId="help-not-found">
        <PageHeader title={t("notFound.title")} />
        <p className="text-slate-600">{t("notFound.text", { id })}</p>
        <p>
          <Link to={helpPath()} className="text-brand-700 underline underline-offset-2">
            {t("notFound.link")}
          </Link>
        </p>
      </Stack>
    );
  }

  const sections = page.headings.filter((h) => h.level === 3 && h.anchor);
  const related = relatedPages(page, language);
  const untranslated = page.locale !== helpLocale(language);

  return (
    <Stack gap={6}>
      <PageHeader title={page.title} />
      <p>
        <Link to={helpPath()} data-testid="help-back" className="text-sm text-brand-700 hover:underline">
          ← {t("back")}
        </Link>
      </p>

      {untranslated && (
        <p className="text-sm text-slate-500" data-testid="help-untranslated">
          {t("untranslated")}
        </p>
      )}

      {sections.length > 1 && (
        <nav
          aria-label={t("toc")}
          data-testid="help-toc"
          className="rounded-xl bg-white px-4 py-3 shadow-sm ring-1 ring-slate-200"
        >
          <p className="mb-1 text-sm font-medium text-slate-700">{t("toc")}</p>
          <ul className="flex flex-col gap-0.5 text-sm">
            {sections.map((section) => (
              <li key={section.anchor}>
                <Link
                  to={helpPath(page.id, section.anchor!)}
                  data-testid={`help-toc-${section.anchor}`}
                  className="text-brand-700 hover:underline"
                >
                  {section.text}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      )}

      <article
        data-testid={`help-article-${page.id}`}
        data-locale={page.locale}
        lang={page.locale}
        className="flex min-w-0 flex-col gap-3 text-slate-800"
      >
        <HelpMarkdown body={page.body} />
      </article>

      {related.length > 0 && (
        <section className="flex flex-col gap-3" data-testid="help-related">
          <h2 className="text-lg font-semibold">{t("related")}</h2>
          <CardGrid>
            {related.map((other) => (
              <li key={other.id}>
                <LinkCard
                  to={helpPath(other.id)}
                  testId={`help-related-${other.id}`}
                  title={other.title}
                  description={other.audience.map((a) => t(`audiences.${a}.title`)).join(" · ")}
                />
              </li>
            ))}
          </CardGrid>
        </section>
      )}
    </Stack>
  );
}

// ------------------------------------------------------------------ Markdown

type HastNode = NonNullable<ExtraProps["node"]>;
type HastChild = HastNode["children"][number];

const ANCHOR = /\s*\{#([a-z0-9-]+)\}\s*$/;
const SHOT = "shot:";

function textOf(node: HastChild | HastNode | undefined): string {
  if (!node) return "";
  if (node.type === "text") return node.value;
  if ("children" in node) return node.children.map((child) => textOf(child as HastChild)).join("");
  return "";
}

/** The heading's text without its `{#anchor}` — the anchor is the element's `id`. */
function stripAnchor(children: ReactNode): ReactNode {
  const list = Children.toArray(children);
  const last = list[list.length - 1];
  if (typeof last === "string") list[list.length - 1] = last.replace(ANCHOR, "");
  return list;
}

function heading(Tag: "h2" | "h3" | "h4", className: string): Components["h2"] {
  return function Heading({ node, children }) {
    const anchor = ANCHOR.exec(textOf(node))?.[1];
    return (
      <Tag id={anchor} className={className}>
        {stripAnchor(children)}
      </Tag>
    );
  };
}

/** `> **Note:** …` and `> **Careful:** …` (Hinweis/Achtung) become the site's info and
 *  warning boxes; any other quote stays a quote. */
function calloutKind(node: HastNode | undefined): "note" | "careful" | null {
  const paragraph = node?.children.find((c) => c.type === "element") as HastNode | undefined;
  const first = paragraph?.children.find((c) => !(c.type === "text" && !c.value.trim()));
  if (!first || first.type !== "element" || first.tagName !== "strong") return null;
  const word = textOf(first).replace(/[:\s]+$/, "").toLowerCase();
  if (word === "note" || word === "hinweis") return "note";
  if (word === "careful" || word === "achtung") return "careful";
  return null;
}

/** Links: `#anchor` opens the page owning it, `/path` is a router link (no reload),
 *  anything else opens outside the site. */
function HelpAnchor({ href = "", children }: { href?: string; children?: ReactNode }) {
  const className = "text-brand-700 underline underline-offset-2 hover:text-brand-800";
  if (href.startsWith("#")) {
    return (
      <Link to={anchorPath(href.slice(1)) ?? href} className={className}>
        {children}
      </Link>
    );
  }
  if (href.startsWith("/")) {
    return (
      <Link to={href} className={className}>
        {children}
      </Link>
    );
  }
  return (
    <a href={href} target="_blank" rel="noreferrer" className={className}>
      {children}
    </a>
  );
}

/** `![Caption](shot:<id>)` → the screenshot for the reader's language, the phone version
 *  under `md` when it exists, and a "screenshot pending" box — never a broken image —
 *  when none does. Keyed by the variant, so a new language or width starts afresh. */
function Shot({ id, caption }: { id: string; caption: string }) {
  const { i18n } = useTranslation();
  const narrow = !useMediaQuery("(min-width: 768px)");
  const locale = helpLocale(i18n.resolvedLanguage);
  return <ShotImage key={`${locale}-${narrow}`} id={id} caption={caption} locale={locale} narrow={narrow} />;
}

function ShotImage({ id, caption, locale, narrow }: { id: string; caption: string; locale: string; narrow: boolean }) {
  const { t } = useTranslation("help");
  const candidates = narrow ? [`${id}_${locale}_phone`, `${id}_${locale}`] : [`${id}_${locale}`];
  const [attempt, setAttempt] = useState(0);
  const pending = attempt >= candidates.length;

  // Spans, not a <figure>: react-markdown puts an image in a <p>, which may not hold one.
  return (
    <span role="figure" aria-label={caption} data-testid={`help-shot-${id}`} data-state={pending ? "pending" : "shown"} className="my-2 block">
      {pending ? (
        <span className="grid min-h-32 place-items-center rounded-lg border-2 border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
          {t("shotPending")}
        </span>
      ) : (
        <img
          src={`${import.meta.env.BASE_URL}handbook/screenshots/${candidates[attempt]}.png`}
          alt={caption}
          onError={() => setAttempt((n) => n + 1)}
          className="block h-auto max-w-full rounded-lg ring-1 ring-slate-200"
        />
      )}
      {caption && <span className="mt-1 block text-sm text-slate-500">{caption}</span>}
    </span>
  );
}

const COMPONENTS: Components = {
  // The page's h1 is the breadcrumb (PageHeader); a stray `#` must not add a second.
  h1: heading("h2", "mt-4 text-xl font-semibold text-slate-900"),
  h2: heading("h2", "mt-2 text-xl font-semibold text-slate-900"),
  h3: heading("h3", "mt-4 text-lg font-semibold text-slate-900"),
  h4: heading("h4", "mt-3 font-semibold text-slate-900"),
  p: ({ children }) => <p className="leading-relaxed">{children}</p>,
  ul: ({ children }) => <ul className="list-disc space-y-1 pl-6">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal space-y-1 pl-6">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  a: ({ href, children }) => <HelpAnchor href={href}>{children}</HelpAnchor>,
  code: ({ children }) => <code className="rounded bg-slate-100 px-1 py-0.5 text-[0.9em]">{children}</code>,
  hr: () => <hr className="my-2 border-slate-200" />,
  img: ({ src, alt }) => {
    const source = typeof src === "string" ? src : "";
    return source.startsWith(SHOT) ? (
      <Shot id={source.slice(SHOT.length)} caption={alt ?? ""} />
    ) : (
      <img src={source} alt={alt ?? ""} className="h-auto max-w-full" />
    );
  },
  blockquote: function Quote({ node, children }) {
    const { t } = useTranslation("help");
    const kind = calloutKind(node);
    if (!kind) {
      return <blockquote className="border-l-4 border-slate-200 pl-4 text-slate-600">{children}</blockquote>;
    }
    const style =
      kind === "careful"
        ? "border-amber-300 bg-amber-50 text-amber-900"
        : "border-sky-200 bg-sky-50 text-sky-900";
    return (
      <aside
        role="note"
        aria-label={t(`callout.${kind}`)}
        data-testid={`help-callout-${kind}`}
        className={`flex flex-col gap-2 rounded-lg border px-4 py-3 text-sm ${style}`}
      >
        {children}
      </aside>
    );
  },
  // A wide table scrolls inside itself, never the page (Story A-10); the surface is on the
  // table, not on a box around it (docs/gotchas: a wrapper cannot carry the surface).
  table: ({ children }) => (
    <TableFrame testId="help-table">
      <div className="overflow-x-auto">
        <table className="data-table w-full border-collapse text-sm">{children}</table>
      </div>
    </TableFrame>
  ),
  thead: ({ children }) => <thead className="border-b border-slate-200 bg-slate-50 text-left">{children}</thead>,
  tbody: ({ children }) => <tbody className="divide-y divide-slate-100">{children}</tbody>,
  th: ({ children, style }) => (
    <th scope="col" style={style} className="align-bottom font-medium text-slate-700">
      {children}
    </th>
  ),
  td: ({ children, style }) => (
    <td style={style} className="align-top text-slate-700">
      {children}
    </td>
  ),
};

/** `shot:` is ours; everything else gets react-markdown's own URL sanitising. */
function urlTransform(url: string): string {
  return url.startsWith(SHOT) ? url : defaultUrlTransform(url);
}

function HelpMarkdown({ body }: { body: string }) {
  return (
    <Markdown remarkPlugins={[remarkGfm]} components={COMPONENTS} urlTransform={urlTransform}>
      {body}
    </Markdown>
  );
}
