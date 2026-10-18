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

/** What a big picture shows: the photo, a cross-fading or a sliding slideshow, a muted video. */
export type MediaMode = "photo" | "fade" | "slide" | "video";
export const MEDIA_MODES = ["photo", "fade", "slide", "video"] as const;
export const [useMediaMode, setMediaMode] = setting<MediaMode>("site.media", MEDIA_MODES, "photo");

/** How the glass looks over the pictures — the playground in the DEV switch. The same
 *  numbers are the defaults in `index.css`; the switch writes them onto the page as CSS
 *  variables, so a build without the dev tools shows the defaults. */
export type Look = { cardAlpha: number; cardBlur: number; shade: number; text: number };
export const LOOK_DEFAULT: Look = { cardAlpha: 0.45, cardBlur: 12, shade: 0.45, text: 0.85 };

const lookListeners = new Set<() => void>();
let look: Look = (() => {
  try {
    return { ...LOOK_DEFAULT, ...JSON.parse(localStorage.getItem("site.look") ?? "{}") };
  } catch {
    return LOOK_DEFAULT;
  }
})();

export function setLook(next: Look) {
  look = next;
  try {
    localStorage.setItem("site.look", JSON.stringify(next));
  } catch {
    // Not remembered; holds until reload.
  }
  lookListeners.forEach((listener) => listener());
}

export function useLook() {
  return useSyncExternalStore(
    (listener) => {
      lookListeners.add(listener);
      return () => lookListeners.delete(listener);
    },
    () => look,
  );
}

/** The look onto the page, as the variables `index.css` defines. */
export function applyLook(value: Look) {
  const root = document.documentElement.style;
  root.setProperty("--site-card-alpha", String(value.cardAlpha));
  root.setProperty("--site-card-blur", `${value.cardBlur}px`);
  root.setProperty("--site-shade", String(value.shade));
  root.setProperty("--site-text", String(value.text));
}

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
