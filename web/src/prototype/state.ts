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

/** A development setting: one value for the whole prototype, shared by every component
 *  that reads it, remembered in this browser (a convenience — storage may fail, and then
 *  the setting holds until reload). */
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
export const [useChapterMode, setChapterMode] = setting<ChapterMode>("prototype.chapters", ["snap", "free"], "snap");

/** How a depth page is laid out: a slim picture band, a sheet over a big picture, or a
 *  split with the page's picture and its siblings fixed on the left. */
export type DetailMode = "band" | "sheet" | "split";
export const [useDetailMode, setDetailMode] = setting<DetailMode>("prototype.detail", ["band", "sheet", "split"], "band");

/** Where layout A puts a depth page's title: on the picture, or on white below it. (A
 *  third place, collapsing into a sticky row, went when that row did — three rows of
 *  navigation were too many.) */
export type TitleMode = "picture" | "below";
export const [useTitleMode, setTitleMode] = setting<TitleMode>("prototype.title", ["picture", "below"], "picture");

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
