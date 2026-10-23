import { useEffect, useState } from "react";

import { VIDEOS, useBackdrops, type Photo } from "../../content";
import { tone } from "./Cards";
import { useMediaMode } from "./settings";

/** A photo that fills its box, crediting its source in the tooltip. One that fails to load
 *  — deleted from the library while a page still lists it — hides instead of showing a
 *  broken-image sign. */
export function Img({ photo, className = "" }: { photo: Photo; className?: string }) {
  return (
    <img
      onError={(event) => {
        event.currentTarget.style.visibility = "hidden";
      }}
      src={photo.src}
      srcSet={photo.srcset}
      sizes={photo.srcset ? "100vw" : undefined}
      alt={photo.alt}
      title={`© ${photo.credit}`}
      loading="lazy"
      className={`block h-full w-full object-cover ${className}`}
    />
  );
}

/** A stable small number per picture, so slideshows on one page do not change in step. */
const pick = (key: string, count: number) =>
  count > 0 ? [...key].reduce((sum, c) => sum + c.charCodeAt(0), 0) % count : 0;

/** A page's picture from the media library (Story R-3): the one given, else one of the
 *  league's — or of every league's — chosen by `seed`, so a page keeps its picture across
 *  visits. With none in the library, nothing: the page's plain background, never a broken
 *  page (decided 2026-10-23 — pictures may be deleted at any time). */
export function Backdrop({ league, photo, seed = "" }: { league?: string | null; photo?: Photo; seed?: string }) {
  const pictures = useBackdrops(league);
  const chosen = photo ?? pictures[pick(seed, pictures.length)];
  if (!chosen) return null;
  return <Picture photo={chosen} slides={pictures} />;
}

/** The page's one big picture: the photo, a slideshow (fading or sliding) through
 *  `slides`, or a muted YouTube loop — as the DEV switch says (Story B-13). */
export function Picture({ photo, slides = [] }: { photo: Photo; slides?: Photo[] }) {
  const mode = useMediaMode();
  const box = "absolute inset-0 overflow-hidden";
  // No slide marks: on a chapter they read as a second set of dots beside the chapter dots.
  if (mode === "fade") return <Slideshow key="fade" photo={photo} others={slides} className={box} kind="fade" />;
  if (mode === "slide") return <Slideshow key="push" photo={photo} others={slides} className={box} kind="push" />;
  if (mode === "video") return <YouTubeBackground photo={photo} className={box} />;
  return <Img photo={photo} className={box} />;
}

/** Pictures that take turns in one box: cross-fading with a slow zoom, or pushed in from
 *  the right. Starts from the box's own photo. */
function Slideshow({
  photo,
  others,
  className,
  kind,
}: {
  photo: Photo;
  others: Photo[];
  className: string;
  kind: "fade" | "push";
}) {
  const slides = [photo, ...others.filter((p) => p.src !== photo.src)].slice(0, 4);
  const [index, setIndex] = useState(0);
  useEffect(() => {
    let timer: number | undefined;
    const start = window.setTimeout(
      () => {
        setIndex((i) => (i + 1) % slides.length);
        timer = window.setInterval(() => setIndex((i) => (i + 1) % slides.length), 5000);
      },
      3000 + pick(photo.src, 5) * 400,
    );
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
          place = i === index ? "scale-110 opacity-100 duration-[6000ms]" : "scale-100 opacity-0 duration-1000";
        } else {
          // The one showing sits at 0, the one before slides out to the left; every other
          // waits off the right edge without animating, so the jump back is never seen.
          const previous = (index - 1 + slides.length) % slides.length;
          place =
            i === index ? "translate-x-0 duration-700" : i === previous ? "-translate-x-full duration-700" : "translate-x-full duration-0";
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
    </div>
  );
}

function YouTubeBackground({ photo, className }: { photo: Photo; className: string }) {
  const clip = VIDEOS[0];
  const params = new URLSearchParams({
    autoplay: "1",
    mute: "1",
    loop: "1",
    playlist: clip.id,
    controls: "0",
    playsinline: "1",
    rel: "0",
    modestbranding: "1",
    start: String(clip.start),
  });
  return (
    // `container-type: size` lets the frame cover the box like `object-fit: cover`.
    <div className={`${className} [container-type:size]`}>
      <Img photo={photo} className="absolute inset-0" />
      <iframe
        title={clip.title}
        src={`https://www.youtube-nocookie.com/embed/${clip.id}?${params}`}
        allow="autoplay; encrypted-media; picture-in-picture"
        tabIndex={-1}
        className="pointer-events-none absolute left-1/2 top-1/2 h-[max(100cqh,56.25cqw)] w-[max(100cqw,177.78cqh)] -translate-x-1/2 -translate-y-1/2 border-0"
      />
    </div>
  );
}

/** A YouTube player with controls, for the media pages — a card like every other. */
export function YouTubePlayer({ id, title }: { id: string; title: string }) {
  return (
    <figure className={`${tone.card} h-full overflow-hidden`}>
      <iframe
        title={title}
        src={`https://www.youtube-nocookie.com/embed/${id}?rel=0`}
        allow="encrypted-media; picture-in-picture; fullscreen"
        loading="lazy"
        className="block aspect-video w-full border-0 bg-default"
      />
      <figcaption className={`p-4 text-sm font-semibold ${tone.text}`}>{title}</figcaption>
    </figure>
  );
}
