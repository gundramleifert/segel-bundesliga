import { useEffect, useRef, useState, type PointerEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import type { League } from "../../api/types";
import type { Photo } from "../../content";
import { BAR_SHADE, PAGE_TITLE, SHADE_ACROSS } from "./Cards";
import { GlassFooter } from "./Footer";
import { TOP_ROW, TopBar } from "./Frame";
import { Picture } from "./Media";
import { useActiveChapter } from "./settings";

export type ChapterSpec = {
  id: string;
  label: string;
  title: string;
  more?: { to: string; label: string };
  body: ReactNode;
};

/** The face of a league (or of the association): its chapters, dots on the right, each a
 *  preview that ends in its own page (Story B-14). **One** picture behind everything —
 *  photo, slideshow or video, as the DEV switch says — reaching up behind the top row,
 *  which lies on it in white; only the text scrolls, in a box that starts under the row.
 *  A chapter is as tall as its content: chapters that each filled the screen and clicked
 *  into place left half a screen of picture between two (removed 2026-10-18). The
 *  overview has no sub-menu: the chapters are its contents, and each leads to its page,
 *  where the sub-menu is. */
export function ChapterScroller({ chapters, photo, league }: { chapters: ChapterSpec[]; photo: Photo; league?: League | null }) {
  const current = useActiveChapter(chapters[0].id, chapters.map((c) => c.id).join());
  // The document behind has nothing to scroll, so Space, Page Down and the arrows have to
  // reach this box: it takes the focus when the page opens (without moving).
  const scroller = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (document.activeElement === document.body) scroller.current?.focus({ preventScroll: true });
  }, []);
  // The dots step aside over the footer: on a phone they lay on its cards.
  const footer = useRef<HTMLDivElement>(null);
  const footerInView = useInView(footer);
  return (
    <div className="fixed inset-0 bg-slate-950">
      <div aria-hidden className="absolute inset-0" data-testid="site-chapters-picture">
        <Picture photo={photo} />
      </div>
      <div aria-hidden className="pointer-events-none absolute inset-0" style={{ background: SHADE_ACROSS }} />
      <div className={`absolute inset-x-0 top-0 z-40 ${BAR_SHADE}`}>
        <TopBar league={league} overlay />
      </div>
      <div className={`absolute inset-x-0 bottom-0 ${TOP_ROW.top}`}>
        <div
          ref={scroller}
          tabIndex={-1}
          // No mask to fade the text out under the row: a mask makes this box a backdrop
          // root, and every card's blur inside it then sees nothing of the picture behind
          // (docs/gotchas).
          className="scrollbar-none absolute inset-0 overflow-y-auto outline-none"
          data-testid="site-chapters"
          data-league={league?.slug}
        >
          <ChapterDots chapters={chapters.map((c) => [c.id, c.label] as const)} active={current} hidden={footerInView} />
          <main id="content">
            {chapters.map((c, i) => (
              <section
                key={c.id}
                id={c.id}
                data-chapter={c.id}
                data-testid={`site-chapter-${c.id}`}
                className="relative border-t border-white/10 first:border-0"
              >
                {/* One column; every block in it spans it (`Cards.tsx`, "the grid"). */}
                <div data-column className="mx-auto w-full max-w-6xl px-4 py-10 pr-14 text-white lg:pr-24">
                  <ChapterHead n={i + 1} of={chapters.length} title={c.title} />
                  <div data-flow className="space-y-6">
                    {c.body}
                  </div>
                  {c.more && <MoreLink id={c.id} more={c.more} />}
                </div>
              </section>
            ))}
          </main>
          <div ref={footer}>
            <GlassFooter />
          </div>
        </div>
      </div>
    </div>
  );
}

function ChapterHead({ n, of, title }: { n: number; of: number; title: string }) {
  // The first chapter's title is the page's heading; the others are its sections.
  const Heading = n === 1 ? "h1" : "h2";
  return (
    <>
      <p className="font-mono text-xs tracking-widest text-white/60">
        {String(n).padStart(2, "0")} / {String(of).padStart(2, "0")}
      </p>
      <Heading className={`mb-6 mt-2 ${PAGE_TITLE}`}>{title}</Heading>
    </>
  );
}

function MoreLink({ id, more }: { id: string; more: { to: string; label: string } }) {
  return (
    <Link
      to={more.to}
      data-testid={`site-chapter-${id}-more`}
      className="mt-8 inline-flex items-center gap-2 rounded-full bg-white px-5 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-white/90"
    >
      {more.label} <span aria-hidden>→</span>
    </Link>
  );
}

/** Whether any of the element is on screen. */
function useInView(ref: React.RefObject<HTMLElement | null>) {
  const [inView, setInView] = useState(false);
  useEffect(() => {
    if (!ref.current) return;
    const observer = new IntersectionObserver(([entry]) => setInView(entry.isIntersecting));
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, [ref]);
  return inView;
}

/** The column of dots on the right. A tap jumps; a thumb sliding along the column shows
 *  every chapter's name and the page follows.
 *
 *  Three rules, each learned on a phone:
 *  - **Only the dots take touch.** The names are laid over the chapter, not beside the
 *    dots in the column: reserving their room made the column an invisible strip a third
 *    of the screen wide, and every swipe that started in it — where a right thumb scrolls —
 *    jumped chapters instead of scrolling the page.
 *  - **The chapter follows the thumb's height**, never what is under it: a thumb drifts
 *    sideways, and once it left the column the slide froze on the last chapter.
 *  - **A tap scrolls, it does not navigate**: following `#season` scrolled a second time
 *    and put every tap into the history, so Back walked the chapters. */
function ChapterDots({
  chapters,
  active,
  hidden = false,
}: {
  chapters: readonly (readonly [id: string, label: string])[];
  active: string;
  hidden?: boolean;
}) {
  const { t } = useTranslation("site");
  const [scrub, setScrub] = useState<string | null>(null);
  const list = useRef<HTMLOListElement>(null);

  /** The chapter whose dot is nearest the pointer's height. */
  const chapterAt = (y: number) => {
    let best: string | null = null;
    let distance = Infinity;
    list.current?.querySelectorAll<HTMLElement>("[data-dot]").forEach((dot) => {
      const box = dot.getBoundingClientRect();
      const d = Math.abs(box.top + box.height / 2 - y);
      if (d < distance) [best, distance] = [dot.dataset.dot ?? null, d];
    });
    return best;
  };

  const jump = (id: string) => document.getElementById(id)?.scrollIntoView({ block: "start" });

  const follow = (event: PointerEvent) => {
    const id = chapterAt(event.clientY);
    if (!id || id === scrub) return;
    setScrub(id);
    jump(id);
  };

  return (
    <nav
      aria-label={t("nav.chapters")}
      data-testid="site-chapter-dots"
      data-scrubbing={scrub ? "" : undefined}
      aria-hidden={hidden || undefined}
      // `touch-none`: sliding along the dots is this control's gesture, not a page scroll —
      // and the box is the dots and nothing more, so it claims no other swipe.
      className={`fixed right-0 top-1/2 z-40 -translate-y-1/2 touch-none select-none py-2 pr-1 transition-opacity lg:pr-4 ${hidden ? "pointer-events-none opacity-0" : ""}`}
      onPointerDown={(event) => {
        if (event.pointerType === "mouse") return;
        try {
          event.currentTarget.setPointerCapture(event.pointerId);
        } catch {
          // A pointer the browser no longer tracks — the slide still works, uncaptured.
        }
        follow(event);
      }}
      onPointerMove={(event) => scrub && follow(event)}
      onPointerUp={() => setScrub(null)}
      onPointerCancel={() => setScrub(null)}
      onLostPointerCapture={() => setScrub(null)}
    >
      {/* While sliding, a dark band behind the names keeps them readable over the chapter.
          Decoration only: it takes no pointer. */}
      <span
        aria-hidden
        className={`pointer-events-none absolute inset-y-0 right-0 w-72 bg-gradient-to-l from-slate-950/95 via-slate-950/80 to-slate-950/0 transition-opacity ${
          scrub ? "opacity-100" : "opacity-0"
        }`}
      />
      <ol ref={list} className="relative flex flex-col">
        {chapters.map(([id, label]) => {
          const current = (scrub ?? active) === id;
          return (
            <li key={id}>
              <a
                href={`#${id}`}
                data-dot={id}
                aria-current={current || undefined}
                aria-label={label}
                onClick={(event) => {
                  event.preventDefault();
                  jump(id);
                }}
                className="group relative flex h-9 w-10 items-center justify-center"
              >
                {/* Laid over the chapter to the left of the dot, so it takes no room. */}
                <span
                  aria-hidden
                  className={`pointer-events-none absolute right-full mr-1 whitespace-nowrap rounded-full text-xs font-semibold uppercase tracking-widest transition ${
                    scrub
                      ? current
                        ? "bg-white px-3 py-1 text-sm text-slate-950"
                        : "text-white/70"
                      : "text-white/0 group-hover:text-white/80"
                  }`}
                >
                  {label}
                </span>
                <span className={`block shrink-0 rounded-full transition-all ${current ? "h-6 w-2 bg-white" : "size-2 bg-white/40 group-hover:bg-white/80"}`} />
              </a>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
