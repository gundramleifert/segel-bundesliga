/** A picture with where it comes from — every photo on the site says whose it is. */
export type Photo = {
  src: string;
  alt: string;
  credit: string;
  license: string;
  page: string;
  /** The library's sizes (Story R-2) — the site's own pictures have one size and none. */
  srcset?: string;
};

const own = (file: string, alt: string): Photo => ({
  src: `/media/${file}`,
  alt,
  credit: "Deutsche Segel-Liga e.V.",
  license: "the association's own",
  page: "https://deutsche-segelliga.de/",
});

// From deutsche-segelliga.de — the user's own site, so these are copied, not linked. The
// board's portraits only (decided 2026-10-23): every other picture on the site comes from
// the media library (`useBackdrops`), never from a list in the code.
export const OWN_PHOTOS = {
  chair: own("DSF4018-2.jpg", "Peter Weichsel"),
  viceChair: own("DSF3979.jpg", "Markus Westerwalbesloh"),
  treasurer: own("DSF4037.jpg", "Tom Lukas Voigt"),
} satisfies Record<string, Photo>;
