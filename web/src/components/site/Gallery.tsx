import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { GalleryPhoto } from "../../content";
import { Lightbox } from "../Lightbox";
import { tone } from "./Cards";

/** Pictures grouped by what they are of — a regatta's under its name, in the order they
 *  came (newest regatta first, `GET /api/media`) — each opening the lightbox (Story R-3). */
export function Gallery({ photos, grouped = true }: { photos: GalleryPhoto[]; grouped?: boolean }) {
  const { t } = useTranslation("site");
  const [shown, setShown] = useState<number | null>(null);
  const groups: { context: string | null; photos: { photo: GalleryPhoto; at: number }[] }[] = [];
  photos.forEach((photo, at) => {
    const last = groups[groups.length - 1];
    // Not grouped: one regatta's pictures, under the heading the page gives them.
    if (last && (!grouped || last.context === photo.context)) last.photos.push({ photo, at });
    else groups.push({ context: photo.context, photos: [{ photo, at }] });
  });
  return (
    <>
      {groups.map((group, g) => (
        <section key={`${group.context}-${g}`} className="mb-8" data-testid="site-media-group">
          {grouped && group.context && <h3 className={`mb-3 text-base font-semibold ${tone.text}`}>{group.context}</h3>}
          <ul className="grid grid-cols-[repeat(auto-fill,minmax(min(100%,14rem),1fr))] gap-3">
            {group.photos.map(({ photo, at }) => (
              <li key={photo.id}>
                <button
                  type="button"
                  onClick={() => setShown(at)}
                  className={`group block w-full overflow-hidden text-left ${tone.card}`}
                  aria-label={t("media.open", { alt: photo.alt })}
                  data-testid={`site-media-photo-${photo.id}`}
                >
                  <span className="block aspect-[3/2] overflow-hidden bg-default">
                    <img
                      src={photo.src}
                      srcSet={photo.srcset}
                      sizes="(min-width: 64rem) 18rem, (min-width: 40rem) 33vw, 100vw"
                      width={photo.width}
                      height={photo.height}
                      alt={photo.alt}
                      loading="lazy"
                      decoding="async"
                      className="block h-full w-full object-cover transition duration-500 group-hover:scale-105"
                    />
                  </span>
                  <span className={`block p-3 text-xs ${tone.muted}`}>
                    <span className={`line-clamp-1 ${tone.text}`}>{photo.alt}</span>
                    {photo.credit && <span className="line-clamp-1">© {photo.credit}</span>}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}
      <Lightbox photos={photos} index={shown} onIndex={setShown} />
    </>
  );
}
