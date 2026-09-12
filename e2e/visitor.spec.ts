import { expect, test } from "@playwright/test";

import { expectNoSidewaysScroll } from "./layout";

/** E2E cut along the user stories — see docs/userstories.md.
 *
 * These are the public pages, read as a visitor with no account. They address elements by
 * `data-testid` rather than by visible text wherever a test is about structure rather than
 * wording: the site is bilingual and the copy is edited often, and a spec that breaks on a
 * reworded heading tests the translator, not the application.
 *
 * The seed (`app.seed`) is the fixture: four series in 2026, and three matchdays of the
 * 1st Segel-Bundesliga — act 1 sailed to the end, act 2 two-thirds sailed, act 3 drawn but
 * not started.
 */

const FINISHED_EVENT = "/events/1"; // dsbl-1-2026-act-1
const PLANNED_EVENT = "/events/3"; // dsbl-1-2026-act-3
const FIRST_SERIES = "/series/1"; // dsbl-1-2026

/** Every public page, with the testid that means "this page has its data".
 *
 *  A list rather than a test each: adding a page should be one line, and every page has to
 *  answer the same question — does it fit the viewport it is being read on. */
const PUBLIC_PAGES: [path: string, ready: string][] = [
  ["/", "start-events-section"],
  ["/series", "series-list"],
  [FIRST_SERIES, "standings-table"],
  ["/events", "events-list"],
  [FINISHED_EVENT, "matchday-header"],
  ["/clubs", "clubs-list"],
  ["/clubs/1", "club-header"],
  ["/sailors/1", "sailor-registrations-section"],
  ["/help", "help-roles-section"],
  ["/legal-notice", "legal-notice-header"],
  ["/privacy", "privacy-header"],
];

test.describe("B-1: as a fan I see the series standings", () => {
  test("the table lists all 18 clubs in ranks 1 to 18", async ({ page }) => {
    await page.goto(FIRST_SERIES);

    const rows = page.getByTestId("standings-table").locator("tbody tr");
    await expect(rows).toHaveCount(18);
    await expect(rows.first().locator("td").first()).toHaveText("1");
    await expect(rows.last().locator("td").first()).toHaveText("18");
  });

  test("fewer points ranks higher", async ({ page }) => {
    const table = page.getByTestId("standings-table");
    await page.goto(FIRST_SERIES);
    await expect(table.locator("tbody tr")).toHaveCount(18);

    const points = await table.locator("tbody tr td:nth-child(3)").allInnerTexts();
    const numbers = points.map((text) => Number(text.replace(",", ".")));
    expect(numbers).toEqual([...numbers].sort((a, b) => a - b));
  });

  test("several series run at once, so the way in is an overview", async ({ page }) => {
    // Before the overview existed, the navigation went straight to whichever series
    // happened to be first for the year and the others were reachable only by URL.
    await page.goto("/series");

    // `toHaveCount` retries; a bare `count()` does not auto-wait and reads whatever is
    // on the page at that instant — which, mid-load, is nothing.
    const cards = page.getByTestId("series-list").getByRole("listitem");
    await expect(cards).toHaveCount(4);

    await page.getByTestId("series-card-1").click();
    await expect(page).toHaveURL(/\/series\/1$/);
    await expect(page.getByTestId("standings-table")).toBeVisible();
  });
});

test.describe("B-2: as a fan I read up on how a matchday went", () => {
  test("the finished matchday shows a complete set of results", async ({ page }) => {
    await page.goto(FINISHED_EVENT);

    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.getByTestId("matchday-standings-table").locator("tbody tr")).toHaveCount(18);
  });

  test("a planned matchday has no results yet, but does have a draw", async ({ page }) => {
    await page.goto(PLANNED_EVENT);

    await page.getByTestId("matchday-pairing-tab").click();
    // 18 clubs on 6 boats is 3 races per flight, 16 flights — 48 races.
    await expect(page.getByTestId("matchday-pairing-table").locator("tbody tr")).toHaveCount(48);
  });
});

test.describe("B-3: as a sailor I see when I am on which boat", () => {
  test("the pairing list names the boats by their colour", async ({ page }) => {
    await page.goto(PLANNED_EVENT);
    await page.getByTestId("matchday-pairing-tab").click();

    const header = page.getByTestId("matchday-pairing-table").locator("thead th");
    for (const colour of ["Black", "Green", "Dark blue", "Red", "Gray", "Orange"]) {
      await expect(header.filter({ hasText: colour })).toHaveCount(1);
    }
  });

  test("every race fills all six boats", async ({ page }) => {
    await page.goto(PLANNED_EVENT);
    await page.getByTestId("matchday-pairing-tab").click();

    const firstRow = page.getByTestId("matchday-pairing-row-1");
    // Number, flight, then six boats.
    await expect(firstRow.locator("td")).toHaveCount(8);
    for (let column = 3; column <= 8; column++) {
      await expect(firstRow.locator(`td:nth-child(${column})`)).not.toHaveText("–");
    }
  });
});

test.describe("B-4: as a visitor I find clubs and dates", () => {
  test("all 18 clubs are listed", async ({ page }) => {
    await page.goto("/clubs");
    await expect(page.getByTestId("clubs-list").getByRole("listitem")).toHaveCount(18);
  });

  test("from the calendar I get into a matchday", async ({ page }) => {
    await page.goto("/events");
    await page.getByTestId("events-list").getByRole("link").first().click();

    await expect(page).toHaveURL(/\/events\/\d+$/);
    await expect(page.getByTestId("matchday-tabs")).toBeVisible();
  });
});

test.describe("Foundations", () => {
  test("the home page leads into a series", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

    await page.getByTestId("start-series-card-1").click();
    await expect(page).toHaveURL(/\/series\/1$/);
  });

  test("the language switcher really switches the language", async ({ page }) => {
    // English is the source language and the default; German is a full second language,
    // not a fallback (see CLAUDE.md, "Language").
    await page.goto("/");
    const nav = page.getByTestId("layout-nav-clubs");
    await expect(nav).toHaveText("Clubs");

    await page.getByTestId("language-switcher-de").click();
    await expect(page.getByTestId("layout-nav-clubs")).toHaveText("Vereine");
  });

  test("the former single-league standings URLs still redirect", async ({ page }) => {
    // These were the real URLs of a deployed build, so they stay. The pre-rename German
    // paths were never public and are gone; the catch-all answers those.
    await page.goto("/standings");
    await expect(page).toHaveURL(/\/series$/);

    await page.goto("/standings/1");
    await expect(page).toHaveURL(/\/series\/1$/);
  });

  test("the mandatory legal pages are reachable from the footer of every page", async ({
    page,
  }) => {
    // § 5 DDG requires them to be reachable from anywhere on a German public site, which
    // is why they live in the footer rather than the main nav.
    await page.goto("/clubs");
    await page.getByTestId("layout-footer-legal-notice").click();
    await expect(page).toHaveURL(/\/legal-notice$/);

    await page.goto("/events");
    await page.getByTestId("layout-footer-privacy").click();
    await expect(page).toHaveURL(/\/privacy$/);
  });

  test("the page never scrolls sideways — not even with a wide table", async ({ page }, testInfo) => {
    await page.goto(PLANNED_EVENT);
    await page.getByTestId("matchday-pairing-tab").click();
    await expect(page.getByTestId("matchday-pairing-row-1")).toBeVisible();

    // Via the shared helper, which also checks that the browser has not zoomed the page
    // out — the check this test used to make could not see that, and passed for weeks
    // while the admin screens were unusable (docs/gotchas/, Story A-10).
    await expectNoSidewaysScroll(page, testInfo);
  });

  test("every public page fits its viewport", async ({ page }, testInfo) => {
    // One list, so a new page is one line rather than a new test — and so this runs on
    // the phone viewport too, where fitting is the whole question.
    for (const [path, ready] of PUBLIC_PAGES) {
      await page.goto(path);
      await expect(page.getByTestId(ready)).toBeVisible();
      await expectNoSidewaysScroll(page, testInfo);
    }
  });
});
