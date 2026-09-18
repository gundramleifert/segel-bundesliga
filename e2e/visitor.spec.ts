import { expect, test } from "./fixtures";

import {
  chooseLanguage,
  closeNavigation,
  expectNoSidewaysScroll,
  openNavigation,
  openUserMenu,
} from "./layout";

/** E2E cut along the user stories — see docs/userstories/.
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
  [FINISHED_EVENT, "matchday-tabs"],
  ["/clubs", "clubs-list"],
  ["/clubs/1", "club-header"],
  ["/sailors/1", "sailor-registrations-section"],
  ["/help", "help-roles-section"],
  ["/legal-notice", "legal-notice-last-updated"],
  ["/privacy", "privacy-last-updated"],
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

  test("the ranking comes first, the events below it", async ({ page }) => {
    await page.goto(FIRST_SERIES);
    await expect(page.getByTestId("standings-table")).toBeVisible();
    await expect(page.getByTestId("standings-events-list")).toBeVisible();

    // Order is the point of this test: the ranking is what a league table is opened for,
    // and it used to start below a grid of cards and a series blurb. The blurb is gone;
    // the cards moved below.
    const table = (await page.getByTestId("standings-results-section").boundingBox())!;
    const events = (await page.getByTestId("standings-events-section").boundingBox())!;
    expect(events.y).toBeGreaterThan(table.y);
    await expect(page.getByTestId("standings-description")).toHaveCount(0);
  });

  test("each act column leads to its matchday", async ({ page }) => {
    await page.goto(FIRST_SERIES);
    await expect(page.getByTestId("standings-table")).toBeVisible();

    const columns = page.getByTestId("standings-table").getByRole("columnheader");
    const actLink = columns.getByRole("link").first();
    await expect(actLink).toBeVisible();
    await actLink.click();
    await expect(page).toHaveURL(/\/events\/\d+$/);
    await expect(page.getByTestId("matchday-tabs")).toBeVisible();
  });

  test("a short club name carries its full name in a tooltip", async ({ page }) => {
    await page.goto(FIRST_SERIES);
    const club = page.getByTestId("standings-table").getByTestId(/standings-club-link-/).first();
    await expect(club).toBeVisible();

    // The cell shows the abbreviation — the column's width is set by eighteen of these,
    // and a standings reader knows them.
    const short = (await club.textContent())!.trim();
    expect(short.length).toBeLessThan(12);

    // Hovering names the club in full, in our own tooltip rather than the browser's.
    await expect(page.getByTestId("tooltip")).toHaveCount(0);
    await club.hover();
    const tip = page.getByTestId("tooltip");
    await expect(tip).toBeVisible();
    await expect(tip).toHaveAttribute("role", "tooltip");
    expect((await tip.textContent())!.length).toBeGreaterThan(short.length);
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

  test("the three races of a flight read as one block", async ({ page }) => {
    await page.goto(PLANNED_EVENT);
    await page.getByTestId("matchday-pairing-tab").click();
    await expect(page.getByTestId("matchday-pairing-row-1")).toBeVisible();

    // The flight is named where it starts and nowhere else — 48 rows each repeating their
    // flight number is what made the grouping invisible. Races 1-3 are flight 1, 4-6
    // flight 2.
    const flightCell = (sequence: number) =>
      page.getByTestId(`matchday-pairing-row-${sequence}`).locator("td:nth-child(2)");
    await expect(flightCell(1)).toHaveText("1");
    await expect(flightCell(2)).toHaveText("");
    await expect(flightCell(3)).toHaveText("");
    await expect(flightCell(4)).toHaveText("2");
  });

  test("each club in the draw leads to its own page", async ({ page }) => {
    await page.goto(PLANNED_EVENT);
    await page.getByTestId("matchday-pairing-tab").click();

    // The first boat of the first race — an abbreviation, so the full name has to be
    // reachable some other way, and the club page is where a sailor goes next.
    const club = page.getByTestId("matchday-pairing-club-link-1-1");
    await expect(club).toBeVisible();
    await club.click();
    await expect(page.getByTestId("club-header")).toBeVisible();
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
    await openNavigation(page);
    await expect(page.getByTestId("layout-nav-clubs")).toHaveText("Clubs");
    // Closed again before touching the account button: on a phone the open drawer puts a
    // backdrop over the rest of the frame, deliberately — while it is open, it is the
    // only thing on the page.
    await closeNavigation(page);

    // The language lives in the account menu now, as a submenu of its own (Story A-12).
    await chooseLanguage(page, "de");
    await page.keyboard.press("Escape");

    await openNavigation(page);
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

  test("the mandatory legal pages are reachable from every page", async ({ page }) => {
    // § 5 DDG requires them to be reachable from anywhere on a German public site. They
    // are in the account menu (Story A-12), which is in the frame of every page — that
    // is what let the footer go.
    await page.goto("/clubs");
    await openUserMenu(page);
    await page.getByTestId("layout-user-menu-legalNotice").click();
    await expect(page).toHaveURL(/\/legal-notice$/);

    await page.goto("/events");
    await openUserMenu(page);
    await page.getByTestId("layout-user-menu-privacy").click();
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

test.describe("A-12: the navigation moves with the viewport", () => {
  test("wide screens get a left column and a breadcrumb, phones get a burger", async ({
    page,
  }, testInfo) => {
    await page.goto("/series");

    // Which arrangement this project gets is decided by its own viewport, so the test
    // asserts the *pair*: exactly one of the two exists. Counts, not visibility — the
    // point is that only one is in the document, because rendering both and hiding one
    // with `hidden lg:flex` leaves two navigations and two breadcrumbs behind.
    const wide = (page.viewportSize()?.width ?? 0) >= 1024;
    await expect(page.getByTestId("layout-sidebar")).toHaveCount(wide ? 1 : 0);
    await expect(page.getByTestId("layout-menu-button")).toHaveCount(wide ? 0 : 1);
    await expect(page.getByTestId("layout-breadcrumb")).toHaveCount(1);

    // The breadcrumb says where you are, in both. On a section's own landing page that is
    // one crumb — repeating "Series › Series" would say nothing twice.
    const crumb = page.getByTestId("layout-breadcrumb");
    await expect(crumb).toBeVisible();
    await expect(crumb.getByRole("listitem")).toHaveCount(1);

    // ...and two once you are inside it, the second being the page's own name. Which is
    // the whole point of the crumb now: the page states its name here and nowhere else,
    // so this asserts the name is a real one rather than the section repeated.
    await page.goto("/series");
    await page.getByTestId("series-list").getByRole("link").first().click();
    await expect(crumb.getByRole("listitem")).toHaveCount(2);
    // Polled, not read once: the crumb re-renders as the page's own query resolves, and a
    // read between two renders came back with one item after the count had seen two.
    const crumbs = await expect
      .poll(async () => crumb.getByRole("listitem").allInnerTexts(), { timeout: 10_000 })
      .toHaveLength(2)
      .then(() => crumb.getByRole("listitem").allInnerTexts());
    const page_name = crumbs[1].replace("›", "").trim();
    expect(page_name.length).toBeGreaterThan(0);
    expect(page_name).not.toEqual(crumbs[0].trim());

    // The first crumb leads back to the section.
    await crumb.getByRole("link").first().click();
    await expect(page).toHaveURL(/\/series$/);
  });

  test("the account button opens what is about the reader, not about the page", async ({
    page,
  }) => {
    await page.goto("/");

    // Nothing is open until it is asked for — the frame carries only the navigation.
    await expect(page.getByTestId("layout-user-menu")).toHaveCount(0);
    await expect(page.getByTestId("layout-profile-button")).toHaveAttribute(
      "aria-expanded",
      "false",
    );

    await openUserMenu(page);
    for (const key of ["language", "profile", "help", "legalNotice", "privacy"]) {
      await expect(page.getByTestId(`layout-user-menu-${key}`)).toBeVisible();
    }

    // The language is a submenu: closed until asked for, then one entry per language,
    // each named in its own language and the current one marked.
    await expect(page.getByTestId("language-switcher")).toHaveCount(0);
    await page.getByTestId("layout-user-menu-language").click();
    // `menuitemradio`, not `listitem`: the panel is a `role="menu"`, which replaces its
    // children's implicit list roles — and radio is what these are, a set of alternatives
    // of which exactly one holds.
    const languages = page
      .getByTestId("language-switcher")
      .getByRole("menuitemradio");
    await expect(languages).toHaveCount(2);
    await expect(page.getByTestId("language-switcher-de")).toHaveText("Deutsch");
    await expect(page.getByTestId("language-switcher-en")).toHaveAttribute(
      "aria-checked",
      "true",
    );
    await page.getByTestId("layout-user-menu-language").click();
    await expect(page.getByTestId("language-switcher")).toHaveCount(0);

    // It opens for a guest too: the language and the legal pages belong to a visitor as
    // much as to anybody.
    await expect(page.getByTestId("layout-nav-help")).toHaveCount(0);

    await page.keyboard.press("Escape");
    await expect(page.getByTestId("layout-user-menu")).toHaveCount(0);

    await openUserMenu(page);
    await page.getByTestId("layout-user-menu-help").click();
    await expect(page).toHaveURL(/\/help$/);
    await expect(page.getByTestId("layout-user-menu")).toHaveCount(0);
  });

  test("the burger opens the links, and closes again on Escape and on a click", async ({
    page,
  }) => {
    await page.goto("/");
    const burger = page.getByTestId("layout-menu-button");
    test.skip(!(await burger.isVisible()), "wide layout has no burger — its own test above");

    await expect(page.getByTestId("layout-nav")).toHaveCount(0);
    await expect(burger).toHaveAttribute("aria-expanded", "false");

    await burger.click();
    await expect(page.getByTestId("layout-menu")).toBeVisible();
    await expect(burger).toHaveAttribute("aria-expanded", "true");

    await page.keyboard.press("Escape");
    await expect(page.getByTestId("layout-menu")).toHaveCount(0);

    // A menu left open over the page it just navigated to reads as a broken link.
    await burger.click();
    await page.getByTestId("layout-nav-clubs").click();
    await expect(page).toHaveURL(/\/clubs$/);
    await expect(page.getByTestId("layout-menu")).toHaveCount(0);
  });
});
