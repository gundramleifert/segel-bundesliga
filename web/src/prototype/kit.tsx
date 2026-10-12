import { useEffect, useState, useSyncExternalStore, type PointerEvent } from "react";

import type { Photo } from "./data";

// Generic pieces of the option-E prototype (issue #14), inherited from the wireframes of
// issue #13 when those were removed.

export function Img({ photo, className = "" }: { photo: Photo; className?: string }) {
  return (
    <img
      src={photo.src}
      alt={photo.alt}
      title={`Photo: ${photo.credit}, ${photo.license}`}
      loading="lazy"
      className={`block h-full w-full object-cover ${className}`}
    />
  );
}

/** Pictures that take turns in one box: cross-fading with a slow zoom (`fade`), or pushed
 *  in from the right (`push`). `slides` is the set to take turns with. */
export function Slideshow({
  photo,
  className,
  kind,
  slides: pool,
  indicator = true,
}: {
  photo: Photo;
  className: string;
  kind: "fade" | "push";
  slides: Photo[];
  /** The row of marks at the bottom saying which slide is showing. */
  indicator?: boolean;
}) {
  const slides = [photo, ...pool.filter((p) => p.src !== photo.src)].slice(0, 4);
  const [index, setIndex] = useState(0);
  useEffect(() => {
    // Staggered by picture, so three slideshows on one page do not all change at once.
    let timer: number | undefined;
    const start = window.setTimeout(() => {
      setIndex((i) => (i + 1) % slides.length);
      timer = window.setInterval(() => setIndex((i) => (i + 1) % slides.length), 5000);
    }, 3000 + pick(photo.src, 5) * 400);
    return () => {
      window.clearTimeout(start);
      window.clearInterval(timer);
    };
  }, [photo.src, slides.length]);
  return (
    <div className={className}>
      {slides.map((slide, i) => {
        let place: string;
        if (kind === "fade") {
          // Cross-fade, and a slow zoom on the one showing (Ken Burns).
          place = i === index ? "scale-110 opacity-100 duration-[6000ms]" : "scale-100 opacity-0 duration-1000";
        } else {
          // A push from right to left: the one showing sits at 0 and the one before it
          // slides out to the left, both animated; every other slide waits off the right
          // edge without animating, so the jump from far left back to the right is never seen.
          const previous = (index - 1 + slides.length) % slides.length;
          place =
            i === index
              ? "translate-x-0 duration-700"
              : i === previous
                ? "-translate-x-full duration-700"
                : "translate-x-full duration-0";
        }
        return (
          <div
            key={slide.src}
            className={`absolute inset-0 ease-in-out ${kind === "fade" ? "transition-[opacity,transform]" : "transition-transform"} ${place}`}
          >
            <Img photo={slide} />
          </div>
        );
      })}
      {indicator && <div className="absolute inset-x-0 bottom-2 z-10 flex justify-center gap-1.5">
        {slides.map((slide, i) => (
          <span key={slide.src} className={`h-1 rounded-full bg-white transition-all ${i === index ? "w-6" : "w-1.5 opacity-50"}`} />
        ))}
      </div>}
    </div>
  );
}

/** Top right on every page: the personal area. A `<details>`, so it opens without any
 *  state — this is a prototype, the real one is `UserMenu`. */
export function MyArea({ tone = "light", compact = false }: { tone?: "light" | "dark"; compact?: boolean }) {
  const dark = tone === "dark";
  return (
    <details className="relative" data-testid="proto-my-area">
      <summary
        className={`flex cursor-pointer list-none items-center gap-2 rounded-full px-2 py-1 text-sm ${
          dark ? "text-white hover:bg-white/10" : "text-slate-700 hover:bg-slate-100"
        }`}
      >
        <span
          className={`grid size-7 place-items-center rounded-full text-xs font-semibold ${dark ? "bg-white text-brand-800" : "bg-brand-600 text-white"
          }`}
        >
          AS
        </span>
        {!compact && <span className="hidden sm:inline">My area</span>}
      </summary>
      <div className="absolute right-0 z-50 mt-2 w-60 rounded-xl border border-slate-200 bg-white p-2 text-sm text-slate-700 shadow-xl">
        <p className="px-3 py-2 text-xs text-slate-500">Signed in as Anna Sailor</p>
        {["My clubs (2)", "My matchdays", "Waiver & documents", "Expense claims", "Administration"].map(
          (item) => (
            <a key={item} href="#" className="block rounded-md px-3 py-2 hover:bg-slate-100">
              {item}
            </a>
          ),
        )}
        <hr className="my-1 border-slate-200" />
        <a href="#" className="block rounded-md px-3 py-2 hover:bg-slate-100">
          Sign out
        </a>
      </div>
    </details>
  );
}

/** The column of dots on the right. With a mouse, hovering shows a dot's name. With a
 *  thumb there is no hover, so it works like the letter index of a phone's contacts:
 *  put the thumb on the dots and slide — every chapter's name appears, the one under the
 *  thumb lights up, and the page follows it. Letting go keeps you there. */
export function ChapterDots({
  chapters,
  active,
}: {
  chapters: readonly (readonly [id: string, label: string])[];
  active: string;
}) {
  const [scrub, setScrub] = useState<string | null>(null);

  const chapterAt = (event: PointerEvent) =>
    (document.elementFromPoint(event.clientX, event.clientY)?.closest("[data-dot]") as HTMLElement | null)?.dataset.dot ?? null;

  const follow = (event: PointerEvent) => {
    const id = chapterAt(event);
    if (!id || id === scrub) return;
    setScrub(id);
    document.getElementById(id)?.scrollIntoView({ block: "start" });
  };

  return (
    <nav
      aria-label="Chapters"
      // `touch-none`: sliding along the dots is this control's gesture, not a page scroll.
      // While sliding, a dark band behind the names keeps them readable over the chapter.
      className={`fixed right-0 top-1/2 z-40 -translate-y-1/2 touch-none select-none rounded-l-3xl py-2 pl-6 pr-3 transition-colors lg:pr-6 ${
        scrub ? "bg-gradient-to-l from-slate-950/95 via-slate-950/80 to-slate-950/0" : ""
      }`}
      onPointerDown={(event) => {
        if (event.pointerType === "mouse") return;
        // Keeps the slide on the dots even when the thumb drifts off the column.
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
    >
      <ol className="flex flex-col">
        {chapters.map(([id, label]) => {
          const current = (scrub ?? active) === id;
          return (
            <li key={id}>
              <a href={`#${id}`} data-dot={id} className="group flex items-center justify-end gap-3 py-1.5">
                <span
                  className={`whitespace-nowrap rounded-full text-xs font-semibold uppercase tracking-widest transition ${
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

export const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });

/** What the big picture areas show: the still photo, a slideshow — cross-fading, or
 *  pushed in from the right — or a silent video loop.
 *  One setting for every page, so it survives navigating, and remembered
 *  in this browser — a convenience, so a failing storage just means "photo". */
export type MediaMode = "photo" | "slideshow" | "slide" | "video";

const MEDIA_KEY = "prototype.media";
const mediaListeners = new Set<() => void>();
let mediaMode: MediaMode = (() => {
  try {
    const saved = localStorage.getItem(MEDIA_KEY);
    return saved === "slideshow" || saved === "slide" || saved === "video" ? saved : "photo";
  } catch {
    return "photo";
  }
})();

export function setMediaMode(mode: MediaMode) {
  mediaMode = mode;
  try {
    localStorage.setItem(MEDIA_KEY, mode);
  } catch {
    // Not remembered — the setting still holds until the page is reloaded.
  }
  mediaListeners.forEach((listener) => listener());
}

export function useMediaMode(): MediaMode {
  return useSyncExternalStore(
    (listener) => {
      mediaListeners.add(listener);
      return () => mediaListeners.delete(listener);
    },
    () => mediaMode,
  );
}

/** A stable small number per picture, so each area picks "its" clip and starts its
 *  slideshow at its own moment instead of all of them changing in step. */
export const pick = (key: string, count: number) =>
  [...key].reduce((sum, char) => sum + char.charCodeAt(0), 0) % count;
