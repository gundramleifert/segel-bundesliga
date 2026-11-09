import type { Page } from "@playwright/test";

import { describeStory, expect, test } from "./fixtures";
import { bearer } from "./session";

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
  // and an article without a cover of its own — `article` below makes one.
];

/** A published 1. Liga article with no cover photo: its picture behind is the library's.
 *  The seed's photo-less ones are invented examples, drafts since the demo went. */
async function article(page: Page): Promise<string> {
  const headers = await bearer(page.request, "redaktion@sbl.example.com");
  const league = (await (await page.request.get("/api/leagues/1-liga")).json()) as { league: { id: number } };
  const made = await page.request.post("/api/admin/posts", {
    headers,
    data: {
      title: `No cover ${Date.now()}`,
      teaser: "A report with no picture of its own.",
      body: "<p>The library alone decides what is behind it.</p>",
      league_id: league.league.id,
      published: true,
    },
  });
  expect(made.ok(), await made.text()).toBeTruthy();
  return `/1-liga/news/${((await made.json()) as { slug: string }).slug}`;
}

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
      for (const [path, ready] of [...PAGES, [await article(page), "site-article"]]) {
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
