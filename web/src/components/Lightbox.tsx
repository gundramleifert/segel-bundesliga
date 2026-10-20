import { useEffect, useRef, type KeyboardEvent, type PointerEvent } from "react";
import { useTranslation } from "react-i18next";

/** A picture the lightbox can show: the library's sizes when it has them. */
export type LightboxPhoto = { src: string; srcset?: string; alt: string; credit?: string };

/** How far a finger has to travel sideways before it counts as a swipe, in pixels. */
const SWIPE = 50;

/** A picture full screen, one of several — Story R-3. A tap on a gallery's tile opens it;
 *  the arrows, a swipe or the arrow keys go to the next and the previous, Escape or the
 *  close button ends it. While it is open the page behind does not scroll, and the focus
 *  stays inside; it goes back to where it was when the lightbox closes.
 *
 *  Controlled: `index` is the picture shown, `null` closed — the gallery owns it, so a
 *  page can open the lightbox on any of its pictures. */
export function Lightbox({
  photos,
  index,
  onIndex,
  testId = "site-lightbox",
}: {
  photos: LightboxPhoto[];
  index: number | null;
  onIndex: (index: number | null) => void;
  testId?: string;
}) {
  const { t } = useTranslation("site");
  const box = useRef<HTMLDivElement>(null);
  const close = useRef<HTMLButtonElement>(null);
  const down = useRef<number | null>(null);
  const open = index !== null && index >= 0 && index < photos.length;

  useEffect(() => {
    if (!open) return;
    const before = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    close.current?.focus();
    return () => {
      document.body.style.overflow = overflow;
      before?.focus?.();
    };
  }, [open]);

  if (!open) return null;
  const photo = photos[index];
  const go = (step: number) => onIndex((index + step + photos.length) % photos.length);
  const several = photos.length > 1;

  const keys = (event: KeyboardEvent) => {
    if (event.key === "Escape") onIndex(null);
    else if (event.key === "ArrowRight" && several) go(1);
    else if (event.key === "ArrowLeft" && several) go(-1);
    else if (event.key === "Tab") {
      // Round inside the lightbox: its buttons are all there is to reach.
      const reachable = [...(box.current?.querySelectorAll<HTMLElement>("button") ?? [])];
      const at = reachable.indexOf(document.activeElement as HTMLElement);
      const next = (at + (event.shiftKey ? -1 : 1) + reachable.length) % reachable.length;
      reachable[next]?.focus();
    } else return;
    event.preventDefault();
  };
  const press = (event: PointerEvent) => {
    down.current = event.clientX;
  };
  const release = (event: PointerEvent) => {
    if (down.current === null || !several) return;
    const moved = event.clientX - down.current;
    down.current = null;
    if (Math.abs(moved) >= SWIPE) go(moved < 0 ? 1 : -1);
  };

  const button = "flex size-11 items-center justify-center rounded-full bg-white/10 text-2xl text-white hover:bg-white/20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-white";
  return (
    <div
      ref={box}
      role="dialog"
      aria-modal="true"
      aria-label={photo.alt || t("lightbox.label")}
      onKeyDown={keys}
      className="fixed inset-0 z-50 flex flex-col bg-black/95 text-white"
      data-testid={testId}
    >
      <div className="flex items-center justify-between gap-4 p-3">
        <span className="text-sm text-white/70" data-testid={`${testId}-position`}>
          {several ? t("lightbox.position", { at: index + 1, count: photos.length }) : ""}
        </span>
        <button ref={close} type="button" onClick={() => onIndex(null)} className={button} aria-label={t("lightbox.close")} data-testid={`${testId}-close-button`}>
          ×
        </button>
      </div>
      <div
        className="relative flex min-h-0 flex-1 touch-pan-y items-center justify-center px-2"
        onPointerDown={press}
        onPointerUp={release}
        onPointerCancel={() => (down.current = null)}
      >
        <img
          key={photo.src}
          src={photo.src}
          srcSet={photo.srcset}
          sizes={photo.srcset ? "100vw" : undefined}
          alt={photo.alt}
          draggable={false}
          className="max-h-full max-w-full select-none object-contain"
          data-testid={`${testId}-image`}
        />
        {several && (
          <>
            <button type="button" onClick={() => go(-1)} className={`${button} absolute left-2 top-1/2 -translate-y-1/2`} aria-label={t("lightbox.previous")} data-testid={`${testId}-previous-button`}>
              ‹
            </button>
            <button type="button" onClick={() => go(1)} className={`${button} absolute right-2 top-1/2 -translate-y-1/2`} aria-label={t("lightbox.next")} data-testid={`${testId}-next-button`}>
              ›
            </button>
          </>
        )}
      </div>
      <p className="p-4 text-center text-sm" data-testid={`${testId}-caption`}>
        {photo.alt}
        {photo.credit && <span className="text-white/60"> · © {photo.credit}</span>}
      </p>
    </div>
  );
}
