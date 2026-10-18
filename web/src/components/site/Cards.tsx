import { createContext, useContext, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { useSiteVersion } from "./settings";

// The building blocks of the official pages: one card, one card with a picture, one panel
// for what needs white paper — so a page deeper looks like the chapter it came from, and a
// new look is written here once, not on every page (2026-10-18).
//
// **What they lie on decides how they are drawn.** Over a picture (the chapters, and every
// page in the sub-menu layout) a card is frosted glass with white type; on white (the
// classic layout's depth pages) it is a bordered white card. The frame says which with
// `Surface`, and the content is written once for both. Without one, the layout decides:
// a page component reads its tone *before* its frame is drawn around it, and in the
// sub-menu layout every official page lies on its picture.

export type SurfaceKind = "dark" | "light";

/** The glass itself, from the look's variables (index.css). */
export const GLASS = "bg-[rgb(2_6_23/var(--site-card-alpha))] backdrop-blur-[var(--site-card-blur)]";

const SurfaceContext = createContext<SurfaceKind | null>(null);

/** Says what the content inside lies on. */
export function Surface({ kind, children }: { kind: SurfaceKind; children: ReactNode }) {
  return <SurfaceContext.Provider value={kind}>{children}</SurfaceContext.Provider>;
}

/** The type and lines of the surface a component lies on. */
export function useTone() {
  const declared = useContext(SurfaceContext);
  const layout = useSiteVersion();
  const dark = (declared ?? (layout === "submenu" ? "dark" : "light")) === "dark";
  return {
    dark,
    text: dark ? "text-white" : "text-slate-900",
    // Over a picture, from the look's variables (index.css) — the DEV switch tunes them.
    muted: dark ? "text-[rgb(255_255_255/var(--site-text))]" : "text-slate-600",
    faint: dark ? "text-[rgb(255_255_255/calc(var(--site-text)-0.2))]" : "text-slate-500",
    line: dark ? "border-white/15" : "border-slate-200",
    link: dark ? "font-medium text-white underline-offset-4 hover:underline" : "font-medium text-brand-700 hover:underline",
    /** A small rounded link — a year, a tab of an act. Glass over a picture: no small
     *  text lies on a photo bare. */
    chip: dark
      ? `rounded-full px-3.5 py-1.5 text-white ${GLASS} transition hover:bg-[rgb(2_6_23/calc(var(--site-card-alpha)+0.15))]`
      : "rounded-full border border-slate-200 px-3.5 py-1.5 text-slate-700 hover:border-slate-400",
    chipOn: dark ? "rounded-full bg-white px-3.5 py-1.5 text-slate-950" : "rounded-full bg-slate-900 px-3.5 py-1.5 text-white",
    /** The card itself, without padding. */
    card: dark ? `rounded-2xl ${GLASS}` : "rounded-2xl border border-slate-200 bg-white",
    cardHover: dark
      ? "transition hover:bg-[rgb(2_6_23/calc(var(--site-card-alpha)+0.15))]"
      : "transition hover:border-slate-400 hover:shadow-sm",
  };
}

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
  const tone = useTone();
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
  image: { src: string; alt: string; credit?: string };
  kicker?: string;
  title?: string;
  text?: string;
  /** Marks the picture as a video's still. */
  play?: boolean;
  aspect?: string;
  testId?: string;
}) {
  const tone = useTone();
  return (
    <Card to={to} className="group h-full overflow-hidden" testId={testId}>
      <div className={`relative overflow-hidden bg-slate-900 ${aspect}`}>
        <img
          src={image.src}
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

/** Room for what is read closely — a full table, an article, a matchday's tables. Over a
 *  picture it is a card like the others, and `.on-glass` (index.css) turns the light
 *  colours of what is inside — tables shared with the internal screens — into the glass's;
 *  on white it is white paper. Inside, everything is written as for white. */
export function Panel({ children, className = "", testId }: { children: ReactNode; className?: string; testId?: string }) {
  const tone = useTone();
  return (
    <div
      className={`p-4 sm:p-6 ${tone.dark ? `${tone.card} on-glass` : "rounded-2xl border border-slate-200 bg-white text-slate-900"} ${className}`}
      data-testid={testId}
    >
      <Surface kind="light">{children}</Surface>
    </div>
  );
}

/** Text on its own — an introduction, a note, a line of facts — on a card, because over a
 *  picture no text is left bare. */
export function TextCard({ children, className = "", testId }: { children: ReactNode; className?: string; testId?: string }) {
  const tone = useTone();
  return (
    <Card className={`p-4 sm:p-5 ${tone.muted} ${className}`} testId={testId}>
      {children}
    </Card>
  );
}

/** Cards in a grid: one column on a phone, more as the screen grows. `minmax(0,1fr)`, not
 *  `1fr`: a long word would otherwise widen the page (Story A-10). */
export function CardRow({ children, columns = 3, testId }: { children: ReactNode; columns?: 2 | 3 | 4 | 6; testId?: string }) {
  const wide = {
    2: "sm:grid-cols-2",
    3: "sm:grid-cols-2 lg:grid-cols-3",
    4: "sm:grid-cols-2 lg:grid-cols-4",
    6: "grid-cols-2 sm:grid-cols-3 lg:grid-cols-6",
  }[columns];
  return (
    <ul className={`grid gap-4 ${columns === 6 ? "" : "grid-cols-[minmax(0,1fr)]"} ${wide}`} data-testid={testId}>
      {children}
    </ul>
  );
}
