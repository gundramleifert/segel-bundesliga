import { Children, type ReactNode } from "react";
import { Link } from "react-router-dom";

// The building blocks of the official pages: one card, one card with a picture, one panel
// for what is read closely — so a page deeper looks like the chapter it came from, and a
// new look is written here once, not on every page (2026-10-18). Every official page lies
// on its picture, so they are frosted glass with white type. The tables shared with the
// internal screens are written in light colours; inside a `Panel`, `.on-glass` (index.css)
// turns those into the glass's.

/** The look over the pictures: variables in index.css, tuned live by the DEV switch. */
const HOVER_GLASS = "hover:bg-[rgb(2_6_23/calc(var(--site-card-alpha)+0.15))]";

/** The glass itself. */
export const GLASS = "bg-[rgb(2_6_23/var(--site-card-alpha))] backdrop-blur-[var(--site-card-blur)]";

/** The rows' background on every official page: the picture shows through, darkened and
 *  blurred, so white type reads on any photo and on content passing under. */
export const BAR_SHADE = "bg-slate-950/70 backdrop-blur-md";

/** The picture's shade behind a chapter page — darker on the left, where the text is. */
export const SHADE_ACROSS =
  "linear-gradient(to right, rgb(2 6 23 / calc(var(--site-shade) + 0.35)), rgb(2 6 23 / calc(var(--site-shade) + 0.1)) 55%, rgb(2 6 23 / calc(var(--site-shade) - 0.15)))";

/** The picture's shade behind a page deeper — darker at the foot, where the cards pile up. */
export const SHADE_DOWN =
  "linear-gradient(to bottom, rgb(2 6 23 / calc(var(--site-shade) + 0.1)), rgb(2 6 23 / calc(var(--site-shade) - 0.1)) 40%, rgb(2 6 23 / calc(var(--site-shade) + 0.3)))";

/** A page's title — a chapter page's first chapter, a page deeper's heading. */
export const PAGE_TITLE = "text-4xl font-semibold leading-[1.05] tracking-tight sm:text-6xl";

/** The type and lines for anything on the glass that is not one of the cards below. */
export const tone = {
  text: "text-white",
  muted: "text-[rgb(255_255_255/var(--site-text))]",
  faint: "text-[rgb(255_255_255/calc(var(--site-text)-0.2))]",
  line: "border-white/15",
  link: "font-medium text-white underline-offset-4 hover:underline",
  /** A small rounded link — a year, a tab of an act; glass, as no small text lies bare. */
  chip: `rounded-full px-3.5 py-1.5 text-white ${GLASS} transition ${HOVER_GLASS}`,
  chipOn: "rounded-full bg-white px-3.5 py-1.5 text-slate-950",
  /** The card itself, without padding. */
  card: `rounded-2xl ${GLASS}`,
  cardHover: `transition ${HOVER_GLASS}`,
};

/** A card: a box of its own, a link when it has `to`. */
export function Card({
  to,
  children,
  className = "",
  testId,
}: {
  to?: string;
  children: ReactNode;
  className?: string;
  testId?: string;
}) {
  if (to) {
    return (
      <Link to={to} className={`block ${tone.card} ${tone.cardHover} ${className}`} data-testid={testId}>
        {children}
      </Link>
    );
  }
  return (
    <div className={`${tone.card} ${className}`} data-testid={testId}>
      {children}
    </div>
  );
}

/** A card led by a picture: an article, a video, a photo — the chapter page's news card. */
/** How wide a card's picture is shown: a third of the column on a desktop, half on a
 *  tablet, the full width on a phone — so the browser fetches the library size it needs. */
const CARD_SIZES = "(min-width: 64rem) 24rem, (min-width: 40rem) 50vw, 100vw";

export function MediaCard({
  to,
  image,
  kicker,
  title,
  text,
  play = false,
  aspect = "aspect-[16/9]",
  testId,
}: {
  to?: string;
  image: { src: string; alt: string; credit?: string; srcset?: string };
  kicker?: string;
  title?: string;
  text?: string;
  /** Marks the picture as a video's still. */
  play?: boolean;
  aspect?: string;
  testId?: string;
}) {
  return (
    <Card to={to} className="group h-full overflow-hidden" testId={testId}>
      <div className={`relative overflow-hidden bg-slate-900 ${aspect}`}>
        <img
          src={image.src}
          srcSet={image.srcset}
          sizes={image.srcset ? CARD_SIZES : undefined}
          alt={image.alt}
          title={image.credit ? `© ${image.credit}` : undefined}
          loading="lazy"
          className="block h-full w-full object-cover transition duration-500 group-hover:scale-105"
        />
        {play && (
          <span aria-hidden className="absolute inset-0 m-auto flex size-12 items-center justify-center rounded-full bg-white/90 pl-1 text-slate-950">
            ▶
          </span>
        )}
      </div>
      {(kicker || title || text) && (
        <div className="p-4">
          {kicker && <p className={`text-xs uppercase tracking-widest ${tone.faint}`}>{kicker}</p>}
          {title && <p className={`mt-1 font-semibold leading-snug ${tone.text}`}>{title}</p>}
          {text && <p className={`mt-1 line-clamp-2 text-sm ${tone.muted}`}>{text}</p>}
        </div>
      )}
    </Card>
  );
}

/** Room for what is read closely — a full table, an article, a matchday's tables: a card
 *  like the others, whose `.on-glass` scope (index.css) turns the light colours of the
 *  tables shared with the internal screens into the glass's. */
/** How wide a panel is. `column`, the rule: the page's column (Story B-13). The one
 *  exception, for what has a width of its own — where a full-width panel left empty glass
 *  beside it — and marked `data-fit` so the grid's check knows:
 *  - `reading`: an article's reading width (~70 characters a line), centred, whatever the
 *    text's length — a short article must not shrink its panel;
 *  - `content`: as wide as what it holds — a table sized by its numbers — under its
 *    heading. Never wider than the column: a wider table scrolls inside. */
const PANEL_WIDTH = {
  column: "",
  reading: "mx-auto w-full max-w-3xl",
  content: "w-fit max-w-full",
} as const;

export function Panel({
  children,
  className = "",
  testId,
  width = "column",
}: {
  children: ReactNode;
  className?: string;
  testId?: string;
  width?: keyof typeof PANEL_WIDTH;
}) {
  return (
    <div
      className={`p-4 sm:p-6 ${tone.card} on-glass ${PANEL_WIDTH[width]} ${className}`}
      data-testid={testId}
      data-fit={width === "column" ? undefined : width}
    >
      {children}
    </div>
  );
}

/** Text on its own — an introduction, a note, a line of facts — on a card, because over a
 *  picture no text is left bare. */
export function TextCard({ children, className = "", testId }: { children: ReactNode; className?: string; testId?: string }) {
  return (
    <Card className={`p-4 sm:p-5 ${tone.muted} ${className}`} testId={testId}>
      {children}
    </Card>
  );
}

// ---------------------------------------------------------------- the grid
//
// **The width belongs to the frame, never to the content** (2026-10-18). A chapter, and a
// page deeper, has one column; every block in it spans the column — content sets no
// `max-w-*` of its own (text *inside* a card may keep a readable measure). Tiles and
// column splits sit on one 12-column grid with one gap, so their edges line up from one
// chapter to the next: 1, 2, 3, 4 or 6 equal tiles, or 2 : 1. `e2e/visitor.spec.ts` ›
// "one column, one grid" measures every official page and names a block that breaks it.

type Split = 1 | 2 | 3 | 4 | 6;

/** The span of each tile, for 1–6 equal tiles, from a phone up. */
const SPANS: Record<Split, string> = {
  1: "[&>*]:col-span-12",
  2: "[&>*]:col-span-12 sm:[&>*]:col-span-6",
  3: "[&>*]:col-span-12 sm:[&>*]:col-span-6 lg:[&>*]:col-span-4",
  4: "[&>*]:col-span-12 sm:[&>*]:col-span-6 lg:[&>*]:col-span-3",
  6: "[&>*]:col-span-6 sm:[&>*]:col-span-4 lg:[&>*]:col-span-2",
};

/** Equal tiles in a row. `columns` is the most there are; fewer tiles than that take the
 *  whole row between them, so a row never ends in an empty gap. */
export function CardRow({ children, columns = 3, testId }: { children: ReactNode; columns?: Split; testId?: string }) {
  const count = Children.toArray(children).length;
  const split = ([1, 2, 3, 4, 6] as const).filter((n) => n <= Math.max(1, Math.min(count, columns))).pop() ?? 1;
  return (
    <ul className={`grid grid-cols-12 gap-4 ${SPANS[columns === 6 ? 6 : split]}`} data-testid={testId} data-card-row>
      {children}
    </ul>
  );
}

/** Blocks side by side on the same grid: `halves` (1 : 1) or `twoToOne` (2 : 1, which
 *  breaks where a row of three does). One column on a phone. */
export function Columns({ children, split = "halves", testId }: { children: ReactNode; split?: "halves" | "twoToOne"; testId?: string }) {
  const spans =
    split === "halves"
      ? "[&>*]:col-span-12 lg:[&>*]:col-span-6"
      : "[&>*]:col-span-12 lg:[&>*:first-child]:col-span-8 lg:[&>*:last-child]:col-span-4";
  return (
    <div className={`grid grid-cols-12 gap-4 ${spans}`} data-testid={testId} data-card-row={split === "halves" ? "" : undefined}>
      {children}
    </div>
  );
}

/** One of a few, as pills on the glass — a matchday's division, the language. */
export function PillSwitch<T extends string>({
  label,
  value,
  options,
  onChange,
  className = "",
  testId,
}: {
  label: string;
  value: T;
  options: readonly { value: T; label: string; testId?: string }[];
  onChange: (value: T) => void;
  className?: string;
  testId?: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className={`inline-flex rounded-full bg-white/10 p-1 ${className}`} data-testid={testId}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={o.value === value}
          onClick={() => onChange(o.value)}
          data-testid={o.testId}
          className={`rounded-full px-3.5 py-1.5 text-sm font-medium ${o.value === value ? "bg-white text-slate-950" : "text-white/75 hover:text-white"}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
