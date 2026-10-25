/** The handbook store (Story B-18): the `<id>.<locale>.md` files beside this module,
 * parsed once at load.
 *
 * The pages are written by the `handbook` skill (`.claude/skills/handbook/`), and
 * `scripts/check-docs.py` holds them to the stories, the journeys, the routes and each
 * other. This module only reads them — it is the one place outside `App.tsx` that knows
 * where the help lives, so every link into it goes through `helpPath`, `anchorPath` and
 * `helpFor` rather than spelling `/help/…` out.
 *
 * The glob is **literal and eager**: the store is a few dozen kilobytes of text, and a lazy
 * glob fetches each page over HTTP in development — it then works in one mode and is empty
 * in the other. Frontmatter is parsed by hand: it is deliberately restricted (flat
 * `key: value`, `[a, b]` lists, `true`/`false`, `null`, a quoted title), which is the same
 * subset `check-docs.py` reads, so a page one cannot read the other cannot either. No YAML
 * dependency for six kinds of line.
 */
import { matchPath } from "react-router-dom";

/** Who the help is for. Not the public: the handbook is for **signed-in** accounts only —
 *  the public site must explain itself, so there is no `visitor` audience. */
export const AUDIENCES = [
  "sailor",
  "club",
  "event-organizer",
  "race-committee",
  "treasurer",
  "administration",
] as const;
export type Audience = (typeof AUDIENCES)[number];

export const PAGE_TYPES = ["start", "guide", "journey", "doc", "faq"] as const;
export type PageType = (typeof PAGE_TYPES)[number];

export const HELP_LOCALES = ["en", "de"] as const;
export type HelpLocale = (typeof HELP_LOCALES)[number];

export interface Heading {
  level: 2 | 3 | 4;
  /** The heading as written, without its `{#anchor}`. */
  text: string;
  /** The explicit anchor, or `null` (the first `##` is the page title and has none). */
  anchor: string | null;
}

export interface HelpPage {
  id: string;
  locale: HelpLocale;
  type: PageType;
  order: number;
  audience: Audience[];
  stories: string[];
  journey: string | null;
  route: string | null;
  tags: string[];
  title: string;
  /** The markdown below the frontmatter. */
  body: string;
  headings: Heading[];
}

type MetaValue = string | number | boolean | null | string[];

const FRONTMATTER = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/;
const META_LINE = /^([a-z_]+):\s*(.*)$/;
const FILE_NAME = /^\.\/([a-z0-9-]+)\.([a-z]{2})\.md$/;
const HEADING = /^(#{2,4})\s+(.*?)\s*$/;
const ANCHOR = /\s*\{#([a-z0-9-]+)\}\s*$/;
const FENCE = /^\s*(```|~~~)/;

function unquote(raw: string): string {
  return raw.length >= 2 && raw[0] === raw[raw.length - 1] && (raw[0] === '"' || raw[0] === "'")
    ? raw.slice(1, -1)
    : raw;
}

/** One frontmatter value: `[a, b]`, `null`, `true`/`false`, a number, or a (quoted) string. */
export function parseMetaValue(text: string): MetaValue {
  const raw = text.trim();
  if (raw.startsWith("[") && raw.endsWith("]")) {
    return raw
      .slice(1, -1)
      .split(",")
      .map((part) => unquote(part.trim()))
      .filter(Boolean);
  }
  if (raw === "" || raw === "null" || raw === "~") return null;
  if (raw === "true" || raw === "false") return raw === "true";
  if (/^-?\d+$/.test(raw)) return Number(raw);
  return unquote(raw);
}

/** `## Text {#anchor}` → its text and anchor; headings inside code fences are not headings. */
export function parseHeadings(body: string): Heading[] {
  const out: Heading[] = [];
  let fenced = false;
  for (const line of body.split(/\r?\n/)) {
    if (FENCE.test(line)) {
      fenced = !fenced;
      continue;
    }
    if (fenced) continue;
    const match = HEADING.exec(line);
    if (!match) continue;
    const anchor = ANCHOR.exec(match[2]);
    out.push({
      level: match[1].length as Heading["level"],
      text: match[2].replace(ANCHOR, ""),
      anchor: anchor ? anchor[1] : null,
    });
  }
  return out;
}

const asList = (value: MetaValue | undefined): string[] =>
  Array.isArray(value) ? value : typeof value === "string" ? [value] : [];
const asText = (value: MetaValue | undefined): string | null =>
  value === null || value === undefined || typeof value === "boolean" ? null : String(value);

/** One store file → a page, or `null` when it is not one (a bad name, no frontmatter, an
 *  unknown type). A broken page is left out rather than breaking `/help` — the checks in
 *  `check-docs.py` are where it is reported. */
export function parsePage(path: string, source: string): HelpPage | null {
  const name = FILE_NAME.exec(path);
  const parts = FRONTMATTER.exec(source);
  if (!name || !parts) return null;
  const locale = name[2] as HelpLocale;
  if (!HELP_LOCALES.includes(locale)) return null;

  const meta: Record<string, MetaValue> = {};
  for (const line of parts[1].split(/\r?\n/)) {
    const field = META_LINE.exec(line.trim());
    if (field) meta[field[1]] = parseMetaValue(field[2]);
  }
  const type = asText(meta.type) as PageType | null;
  if (!type || !PAGE_TYPES.includes(type)) return null;

  const body = parts[2];
  return {
    id: name[1],
    locale,
    type,
    order: typeof meta.order === "number" ? meta.order : 0,
    audience: asList(meta.audience).filter((a): a is Audience => (AUDIENCES as readonly string[]).includes(a)),
    stories: asList(meta.stories),
    journey: asText(meta.journey),
    route: asText(meta.route),
    tags: asList(meta.tags),
    title: asText(meta.title) ?? name[1],
    body,
    headings: parseHeadings(body),
  };
}

const files = import.meta.glob("./*.md", { query: "?raw", import: "default", eager: true }) as Record<
  string,
  string
>;

const STORE: HelpPage[] = Object.entries(files)
  .map(([path, source]) => parsePage(path, source))
  .filter((page): page is HelpPage => page !== null);

/** Page id → locale → page. */
const BY_ID = new Map<string, Partial<Record<HelpLocale, HelpPage>>>();
for (const page of STORE) {
  BY_ID.set(page.id, { ...BY_ID.get(page.id), [page.locale]: page });
}

/** Anchor → the id of the page that owns it. Anchors are the same in both locales and
 *  unique in the store (`check-docs.py`), so either locale's headings will do; a page's
 *  own id is its anchor too. */
const ANCHORS = new Map<string, string>();
for (const page of STORE) {
  ANCHORS.set(page.id, page.id);
  for (const heading of page.headings) if (heading.anchor) ANCHORS.set(heading.anchor, page.id);
}

/** `de-DE`, `de`, `en`, undefined → a locale the store is written in. */
export function helpLocale(language: string | undefined): HelpLocale {
  const short = (language ?? "en").slice(0, 2);
  return (HELP_LOCALES as readonly string[]).includes(short) ? (short as HelpLocale) : "en";
}

/** The page in this language, else its English source. */
export function getPage(id: string, language?: string): HelpPage | undefined {
  const byLocale = BY_ID.get(id);
  return byLocale?.[helpLocale(language)] ?? byLocale?.en ?? byLocale?.de;
}

/** Every page, one per id, in the reader's language where it exists — by type, then order. */
export function allPages(language?: string): HelpPage[] {
  return [...BY_ID.keys()]
    .map((id) => getPage(id, language)!)
    .sort((a, b) => PAGE_TYPES.indexOf(a.type) - PAGE_TYPES.indexOf(b.type) || a.order - b.order);
}

export function pagesOfType(type: PageType, language?: string): HelpPage[] {
  return allPages(language).filter((page) => page.type === type);
}

/** The id of the page an anchor belongs to. */
export function pageOfAnchor(anchor: string): string | undefined {
  return ANCHORS.get(anchor);
}

export const HELP_ROOT = "/help";

export function helpPath(pageId?: string, anchor?: string): string {
  if (!pageId) return HELP_ROOT;
  return `${HELP_ROOT}/${pageId}${anchor && anchor !== pageId ? `#${anchor}` : ""}`;
}

/** `/help/<page>#anchor` for an anchor anywhere in the store, or `undefined` if no page
 *  has it — a link to it would land nowhere. */
export function anchorPath(anchor: string): string | undefined {
  const pageId = pageOfAnchor(anchor);
  return pageId ? helpPath(pageId, anchor) : undefined;
}

export function startPageId(audience: Audience): string {
  return `start-${audience}`;
}

/** Pages written for a different audience that document one of the same stories —
 *  "the other side of this". Guides and journeys only: a start page has no stories, and
 *  a reference page shares a story with half the store. */
export function relatedPages(page: HelpPage, language?: string): HelpPage[] {
  if (!page.stories.length) return [];
  const mine = new Set(page.audience);
  return allPages(language).filter(
    (other) =>
      other.id !== page.id &&
      (other.type === "guide" || other.type === "journey") &&
      other.audience.some((a) => !mine.has(a)) &&
      other.stories.some((story) => page.stories.includes(story)),
  );
}

/** The screens "help for this page" may answer for: the signed-in part of the site.
 *
 * The handbook is internal (only signed-in accounts read it), and a public page must
 * explain itself — so a public screen never gets a handbook page, even when a page's
 * `route` would match it. `/events/:id` is the case in point: the race committee corrects
 * results there, but it is first the public matchday page every fan reads. */
const INTERNAL_SCREENS = ["/me/*", "/office/*", "/account", "/help/*", "/events/:id/race-control"];

/** The help page that explains the screen at `pathname`, or `undefined`.
 *
 * Only for an internal screen (`INTERNAL_SCREENS`). Matched with react-router's own
 * `matchPath` against each page's `route` — the pattern as written in `App.tsx` — and
 * the most specific match wins: more static segments first, so `/me/club/3` is answered
 * by a page routed `/me/club/:id` before one routed `/me/*`.
 */
export function helpFor(pathname: string, language?: string): HelpPage | undefined {
  if (!INTERNAL_SCREENS.some((path) => matchPath({ path, end: true }, pathname))) return undefined;
  let best: { page: HelpPage; statics: number } | undefined;
  for (const page of allPages(language)) {
    if (!page.route || !matchPath({ path: page.route, end: true }, pathname)) continue;
    const statics = page.route.split("/").filter((s) => s && !s.startsWith(":") && s !== "*").length;
    if (!best || statics > best.statics) best = { page, statics };
  }
  return best?.page;
}

export interface SearchHit {
  page: HelpPage;
  /** Headings whose text matched, with their anchors — to link straight to the section. */
  headings: Heading[];
}

/** Every term must occur in the page's title, headings or tags; case and accents folded.
 *  Searches the reader's language **and** the other one, so a German word finds the
 *  English page (the `tags` carry the German domain word in both locales). */
export function searchPages(query: string, language?: string): SearchHit[] {
  const terms = fold(query).split(/\s+/).filter(Boolean);
  if (!terms.length) return [];
  const hits: SearchHit[] = [];
  for (const page of allPages(language)) {
    const versions = Object.values(BY_ID.get(page.id) ?? {});
    const haystack = versions
      .flatMap((v) => [v.title, ...v.tags, ...v.headings.map((h) => h.text)])
      .map(fold)
      .join("\n");
    if (!terms.every((term) => haystack.includes(term))) continue;
    const headings = page.headings.filter(
      (h) => h.anchor && terms.some((term) => fold(h.text).includes(term)),
    );
    hits.push({ page, headings });
  }
  return hits;
}

function fold(text: string): string {
  return text.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();
}
