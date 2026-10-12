/** A picture with where it comes from — every photo on the site says whose it is. */
export type Photo = { src: string; alt: string; credit: string; license: string; page: string };

const DSBL_UPLOADS = "https://deutsche-segelbundesliga.de/wp-content/uploads";

const dsbl = (path: string, alt: string, credit = "Deutsche Segel-Bundesliga"): Photo => ({
  src: `${DSBL_UPLOADS}/${path}`,
  alt,
  credit,
  license: "all rights reserved",
  page: "https://deutsche-segelbundesliga.de/media/",
});

// The league's own pictures, from deutsche-segelbundesliga.de. **Linked, never copied**:
// this repository is public, and they are not freely licensed (docs/site-structure.md).
export const DSBL_PHOTOS = {
  race: dsbl("2026/07/DSC06520-1536x1024.jpg", "J/70 racing upwind"),
  aerial: dsbl("2025/03/BundelLiga_Berlin_Day1_HR@Adam.Burdylo-115.jpg", "J/70 fleet from above, Berlin", "Adam Burdylo"),
  podium: dsbl("2026/08/DSC07807-1536x1024.jpg", "A podium of three clubs"),
  swimmer: dsbl("2025/03/SBL211971411-0964-1536x1024.jpg", "A sailor in the water beside the league's mark"),
  studio: dsbl("2025/03/SBL182931401-6308-2.jpg", "The live broadcast studio"),
  camera: dsbl("2025/03/SBL182911202-2694.jpg", "A cameraman filming from a RIB"),
} satisfies Record<string, Photo>;

const own = (file: string, alt: string): Photo => ({
  src: `/media/${file}`,
  alt,
  credit: "Deutsche Segel-Liga e.V.",
  license: "the association's own",
  page: "https://deutsche-segelliga.de/",
});

// From deutsche-segelliga.de — the user's own site, so these are copied, not linked.
export const OWN_PHOTOS = {
  title: own("titelbild.jpg", "J/70 racing close, spray flying"),
  chair: own("DSF4018-2.jpg", "Peter Weichsel"),
  viceChair: own("DSF3979.jpg", "Markus Westerwalbesloh"),
  treasurer: own("DSF4037.jpg", "Tom Lukas Voigt"),
} satisfies Record<string, Photo>;

/** What a slideshow takes turns with. */
export const SLIDES: Photo[] = [DSBL_PHOTOS.race, OWN_PHOTOS.title, DSBL_PHOTOS.aerial, DSBL_PHOTOS.podium];
