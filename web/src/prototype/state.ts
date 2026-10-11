import { useEffect, useState, useSyncExternalStore } from "react";
import { useParams } from "react-router-dom";

import { findLeague } from "./data";

export const BASE = "/prototype";

/** The option-E URL scheme (issue #14), under the prototype's prefix. */
export const href = {
  home: () => BASE,
  league: (league: string) => `${BASE}/${league}`,
  standings: (league: string) => `${BASE}/${league}/standings`,
  season: (league: string) => `${BASE}/${league}/season`,
  noticeBoard: (league: string) => `${BASE}/${league}/notice-board`,
  clubs: (league: string) => `${BASE}/${league}/clubs`,
  news: (league: string) => `${BASE}/${league}/news`,
  article: (league: string, slug: string) => `${BASE}/${league}/news/${slug}`,
  media: (league: string) => `${BASE}/${league}/media`,
  press: (league: string) => `${BASE}/${league}/press`,
  act: (league: string, year: number, act: string, tab?: string) =>
    `${BASE}/${league}/${year}/${act}${tab ? `/${tab}` : ""}`,
  live: (league: string) => `${BASE}/${league}/live`,
  results: (league: string) => `${BASE}/${league}/results`,
  about: (league?: string) => (league ? `${BASE}/${league}/about` : `${BASE}/about`),
};

export function useLeague() {
  const { league } = useParams();
  return findLeague(league);
}

/** Development switch: do the chapters snap into place, or scroll freely? One setting for
 *  the whole prototype, remembered in this browser (a convenience — storage may fail). */
export type ChapterMode = "snap" | "free";

const KEY = "prototype.chapters";
const listeners = new Set<() => void>();
let chapterMode: ChapterMode = (() => {
  try {
    return localStorage.getItem(KEY) === "free" ? "free" : "snap";
  } catch {
    return "snap";
  }
})();

export function setChapterMode(mode: ChapterMode) {
  chapterMode = mode;
  try {
    localStorage.setItem(KEY, mode);
  } catch {
    // Not remembered; holds until reload.
  }
  listeners.forEach((listener) => listener());
}

export function useChapterMode(): ChapterMode {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => chapterMode,
  );
}

/** Which chapter fills most of the screen — for the dots, and so only that chapter plays
 *  a video. `key` re-runs the observer when the set of chapters (or their layout) changes. */
export function useActiveChapter(first: string, key = "") {
  const [active, setActive] = useState(first);
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) setActive((entry.target as HTMLElement).dataset.chapter ?? first);
        }
      },
      { threshold: 0.55 },
    );
    document.querySelectorAll("[data-chapter]").forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [first, key]);
  return active;
}
