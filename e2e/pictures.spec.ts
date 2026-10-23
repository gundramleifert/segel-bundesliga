import type { Page } from "@playwright/test";

import { describeStory, expect, test } from "./fixtures";

/** Story R-3: every picture behind a page comes from the media library (decided
 *  2026-10-23), and pictures may be deleted from it at any time. So a page must stand
 *  without them: an empty library, a failing request, a picture whose file is gone — each
 *  a plain background, never an error. The library's answer is replaced here, so the test
 *  holds whatever the seed put into it. */

/** Pages that draw a picture behind them, with the test id that means "this page is here". */
const PAGES: [path: string, ready: string][] = [
  ["/", "site-home-now"],
  ["/1-liga", "site-chapter-standings"],
  ["/1-liga/news", "site-depth-page"],
  ["/1-liga/media", "site-depth-page"],
  ["/1-liga/news/asvw-takes-the-lead", "site-article"],
];

type Library = "empty" | "failing" | "files-gone";

async function library(page: Page, state: Library): Promise<void> {
  // The list of pictures: none, or an error.
  await page.route(/\/api\/media(\?|$)/, (route) =>
    state === "failing"
      ? route.fulfill({ status: 500, contentType: "application/problem+json", body: '{"type":"/errors/unknown"}' })
      : state === "empty"
        ? route.fulfill({ json: { items: [], total: 0, limit: 12, offset: 0 } })
        : route.continue(),
  );
  // The files themselves: gone, as after a deletion the list has not caught up with.
  if (state === "files-gone") await page.route(/\/api\/media\/[^/?]+\.webp/, (route) => route.fulfill({ status: 404 }));
}

describeStory("R-3: a page stands without its pictures", () => {
  for (const state of ["empty", "failing", "files-gone"] as const) {
    test(`with the library ${state}, every page still renders`, async ({ page }) => {
      const errors: string[] = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await library(page, state);
      for (const [path, ready] of PAGES) {
        await page.goto(path);
        await expect(page.getByTestId(ready).first(), path).toBeVisible();
        // No picture is drawn where there is none to draw; a broken one is hidden.
        if (state !== "files-gone") {
          await expect(page.locator('[data-testid="site-depth-picture"] img'), path).toHaveCount(0);
        }
      }
      expect(errors).toEqual([]);
    });
  }
});
