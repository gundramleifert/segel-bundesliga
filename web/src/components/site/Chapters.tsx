import { useEffect, useRef, useState, type PointerEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import type { League } from "../../api/types";
import type { Photo } from "../../content";
import { Footer, TopBar } from "./Frame";
import { Picture } from "./Media";
import { useActiveChapter, useChapterMode } from "./settings";

export type ChapterSpec = {
  id: string;
  label: string;
  title: string;
  photo: Photo;
  more?: { to: string; label: string };
  body: ReactNode;
};

/** The face of a league (or of the association): full-screen chapters over pictures,
 *  dots on the right, each chapter a preview that ends in its own page (Story B-14). */
export function ChapterScroller({ chapters, league }: { chapters: ChapterSpec[]; league?: League | null }) {
  const mode = useChapterMode();
  const current = useActiveChapter(chapters[0].id, `${chapters.map((c) => c.id).join()}|${mode}`);
  // The document behind has nothing to scroll, so Space, Page Down and the arrows have to
  // reach this box: it takes the focus when the page opens (without moving), and a click
  // anywhere in it keeps it there. Tab still starts at the top row, which is inside it.
  const scroller = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (document.activeElement === document.body) scroller.current?.focus({ preventScroll: true });
  }, []);
  return (
    // Its own scroller, fixed over the screen, so the document behind has nothing to
    // scroll and the snapping (when on) is this box's alone.
    <div
      ref={scroller}
      tabIndex={-1}
      className={`scrollbar-none fixed inset-0 overflow-y-auto bg-slate-950 outline-none ${mode === "snap" ? "snap-y snap-mandatory" : ""}`}
      data-testid="site-chapters"
      data-league={league?.slug}
    >
      <TopBar overlay />
      <ChapterDots chapters={chapters.map((c) => [c.id, c.label] as const)} active={current} />
      <main id="content">
        {chapters.map((c, i) => (
          <Chapter key={c.id} spec={c} n={i + 1} of={chapters.length} playing={current === c.id} />
        ))}
      </main>
      <div className="snap-start">
        <Footer />
      </div>
    </div>
  );
}

/** One full-screen chapter: a picture, a number, a title, a short preview — and the link
 *  to the chapter's own page, which is what option E adds. */
function Chapter({ spec, n, of, playing }: { spec: ChapterSpec; n: number; of: number; playing: boolean }) {
  const mode = useChapterMode();
  return (
    <section
      id={spec.id}
      data-chapter={spec.id}
      data-testid={`site-chapter-${spec.id}`}
      className={`relative flex items-end overflow-hidden ${mode === "snap" ? "min-h-dvh snap-start" : "min-h-[85dvh]"}`}
    >
      <Picture photo={spec.photo} play={playing} video={n - 1} />
      <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/65 to-slate-950/25" />
      <div className="relative mx-auto w-full max-w-6xl px-4 pb-16 pr-14 pt-24 text-white lg:pr-24">
        <p className="font-mono text-xs tracking-widest text-white/60">
          {String(n).padStart(2, "0")} / {String(of).padStart(2, "0")}
        </p>
        {/* The first chapter's title is the page's heading; the others are its sections. */}
        {n === 1 ? (
          <h1 className="mb-6 mt-2 text-4xl font-semibold leading-[1.02] tracking-tight sm:text-6xl">{spec.title}</h1>
        ) : (
          <h2 className="mb-6 mt-2 text-4xl font-semibold leading-[1.02] tracking-tight sm:text-6xl">{spec.title}</h2>
        )}
        {spec.body}
        {spec.more && (
          <Link
            to={spec.more.to}
            data-testid={`site-chapter-${spec.id}-more`}
            className="mt-8 inline-flex items-center gap-2 rounded-full bg-white px-5 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-white/90"
          >
            {spec.more.label} <span aria-hidden>→</span>
          </Link>
        )}
      </div>
    </section>
  );
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
function ChapterDots({ chapters, active }: { chapters: readonly (readonly [id: string, label: string])[]; active: string }) {
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
      // `touch-none`: sliding along the dots is this control's gesture, not a page scroll —
      // and the box is the dots and nothing more, so it claims no other swipe.
      className="fixed right-0 top-1/2 z-40 -translate-y-1/2 touch-none select-none py-2 pr-1 lg:pr-4"
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
