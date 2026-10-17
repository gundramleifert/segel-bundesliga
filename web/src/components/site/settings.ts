import { useEffect, useState, useSyncExternalStore } from "react";

/** The variants of the site structure still open (`docs/site-structure.md`, Story B-13),
 *  each switched by the DEV button and decided on a real device, not in the abstract.
 *
 *  One value for the whole site, shared by every component that reads it, remembered in
 *  this browser — a convenience: storage may fail, and then the setting holds until reload.
 *  Once a variant is decided, its setting goes and the chosen branch stays. */
function setting<T extends string>(key: string, values: readonly T[], fallback: T) {
  const listeners = new Set<() => void>();
  let value: T = (() => {
    try {
      const saved = localStorage.getItem(key);
      return values.includes(saved as T) ? (saved as T) : fallback;
    } catch {
      return fallback;
    }
  })();
  const set = (next: T) => {
    value = next;
    try {
      localStorage.setItem(key, next);
    } catch {
      // Not remembered; holds until reload.
    }
    listeners.forEach((listener) => listener());
  };
  const use = () =>
    useSyncExternalStore(
      (listener) => {
        listeners.add(listener);
        return () => listeners.delete(listener);
      },
      () => value,
    );
  return [use, set] as const;
}

/** Do the chapters snap into place, or scroll freely? */
export type ChapterMode = "snap" | "free";
export const CHAPTER_MODES = ["snap", "free"] as const;
export const [useChapterMode, setChapterMode] = setting<ChapterMode>("site.chapters", CHAPTER_MODES, "snap");

/** What a big picture shows: the photo, a cross-fading or a sliding slideshow, a muted video. */
export type MediaMode = "photo" | "fade" | "slide" | "video";
export const MEDIA_MODES = ["photo", "fade", "slide", "video"] as const;
export const [useMediaMode, setMediaMode] = setting<MediaMode>("site.media", MEDIA_MODES, "photo");

/** How a depth page is framed: A a band of picture, B a sheet over a big picture, C a split
 *  with the picture and the league's pages fixed on the left. */
export type DetailMode = "band" | "sheet" | "split";
export const DETAIL_MODES = ["band", "sheet", "split"] as const;
export const [useDetailMode, setDetailMode] = setting<DetailMode>("site.detail", DETAIL_MODES, "band");

/** The site's layout: **classic** — the chapters each over their own picture, the top row
 *  over it, the league's pages in each depth frame; **submenu** — like my space: the top
 *  row solid with a sticky sub-menu under it (the league's pages, or a matchday's tabs),
 *  one fixed picture behind the chapters that the text scrolls over, fuller chapters. */
export type SiteVersion = "classic" | "submenu";
export const SITE_VERSIONS = ["classic", "submenu"] as const;
export const [useSiteVersion, setSiteVersion] = setting<SiteVersion>("site.version", SITE_VERSIONS, "submenu");

/** Which chapter is on screen — for the dots, and so only that chapter plays a video:
 *  the one that covers the **middle line** of the screen. `key` re-runs the observer when
 *  the set of chapters (or their layout) changes.
 *
 *  It used to be "the one at least 55% visible", which a chapter taller than about 1.8
 *  screens can never be — its dot was never marked, and the previous one stayed lit. The
 *  middle line is crossed by exactly one chapter at a time, whatever their heights. */
export function useActiveChapter(first: string, key = "") {
  const [active, setActive] = useState(first);
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) setActive((entry.target as HTMLElement).dataset.chapter ?? first);
        }
      },
      // A band of zero height across the middle of the screen.
      { rootMargin: "-50% 0px -50% 0px", threshold: 0 },
    );
    document.querySelectorAll("[data-chapter]").forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [first, key]);
  return active;
}
