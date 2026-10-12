import { describeStory, expect, test } from "./fixtures";

import { chooseLanguage, expectNoSidewaysScroll, openUserMenu } from "./layout";

/** E2E cut along the user stories — see docs/userstories/.
 *
 * These are the public pages, read as a visitor with no account. They address elements by
 * `data-testid` rather than by visible text wherever a test is about structure rather than
 * wording: the site is bilingual and the copy is edited often, and a spec that breaks on a
 * reworded heading tests the translator, not the application.
 *
 * The seed (`app.seed`) is the fixture: three leagues (DSBL, Junioren-Liga, DSL-Pokal), the
 * DSBL's 1. and 2. Liga in 2026, and three acts of the 1. Liga — act 1 sailed to the end,
 * act 2 two-thirds sailed, act 3 drawn but not started. The Sailing Champions League
 * series belongs to no league, so it keeps its own page.
 */

const FINISHED_ACT = "/dsbl/2026/act-1"; // dsbl-1-2026-act-1, event 1
const PLANNED_ACT = "/dsbl/2026/act-3"; // dsbl-1-2026-act-3, event 3
const STANDINGS = "/dsbl/standings";
const UNLEAGUED_SERIES = "/series/4"; // scl-2026, in no league

/** Every public page, with the testid that means "this page has its data".
 *
 *  A list rather than a test each: adding a page should be one line, and every page has to
 *  answer the same question — does it fit the viewport it is being read on. */
const PUBLIC_PAGES: [path: string, ready: string][] = [
  ["/", "site-home-now"],
  ["/dsbl", "site-chapter-now"],
  [STANDINGS, "site-standings-dsbl-1-2026"],
  ["/dsbl/season", "site-season-act"],
  ["/dsbl/clubs", "site-clubs-dsbl-1-2026"],
  ["/dsbl/notice-board", "site-depth-page"],
  ["/dsbl/news", "site-depth-page"],
  ["/dsbl/media", "site-depth-page"],
  ["/dsbl/press", "site-depth-page"],
  ["/dsbl/about", "site-depth-page"],
  ["/about", "site-depth-page"],
  [FINISHED_ACT, "matchday-standings-table"],
  [`${PLANNED_ACT}/pairing`, "matchday-pairing-table"],
  [UNLEAGUED_SERIES, "standings-results-section"],
  ["/events", "events-list"],
  ["/clubs", "clubs-list"],
  ["/clubs/1", "club-header"],
  ["/sailors/1", "sailor-registrations-section"],
  ["/help", "help-roles-section"],
  ["/legal-notice", "legal-notice-last-updated"],
  ["/privacy", "privacy-last-updated"],
];

describeStory("B-1/B-14: as a fan I see the series standings", () => {
  const firstLiga = (page: import("@playwright/test").Page) =>
    page.getByTestId("site-standings-dsbl-1-2026").getByTestId("site-standings-row");

  test("the table lists all 18 clubs in ranks 1 to 18", async ({ page }) => {
    await page.goto(STANDINGS);
    const rows = firstLiga(page);
    await expect(rows).toHaveCount(18);
    await expect(rows.first().locator("summary")).toContainText(/^1\D/);
    await expect(rows.last().locator("summary")).toContainText(/^18\D/);
  });

  test("fewer points ranks higher", async ({ page }) => {
    await page.goto(STANDINGS);
    await expect(firstLiga(page)).toHaveCount(18);
    const points = await firstLiga(page).locator("summary span.tabular-nums").allInnerTexts();
    const numbers = points.map((text) => Number(text.replace(",", ".")));
    expect(numbers).toEqual([...numbers].sort((a, b) => a - b));
  });

  test("a row opens to its place at each act, and on to the club", async ({ page }) => {
    await page.goto(STANDINGS);
    const row = firstLiga(page).first();
    await row.locator("summary").click();
    // Two acts are sailed (one of them still running), the third is planned.
    await expect(row.getByText(/Act 1:/)).toBeVisible();
    await row.getByRole("link").click();
    await expect(page.getByTestId("club-header")).toBeVisible();
  });

  test("the league's rules mark the table, and only where they apply", async ({ page }) => {
    await page.goto(STANDINGS);
    // The 1. Liga's last four go down; it promotes nobody.
    const table = page.getByTestId("site-standings-dsbl-1-2026");
    await expect(table.getByTestId("mark-relegation")).toHaveCount(4);
    await expect(table.getByTestId("mark-promotion")).toHaveCount(0);
  });

  test("a series in no league keeps its own page", async ({ page }) => {
    // The Sailing Champions League of the seed is in no league, so there is no league
    // page to send it to (Story B-16).
    await page.goto(UNLEAGUED_SERIES);
    await expect(page.getByTestId("standings-results-section")).toBeVisible();
    await expect(page).toHaveURL(/\/series\/4$/);
  });
});

describeStory("B-2: as a fan I read up on how a matchday went", () => {
  test("the finished matchday opens on a complete set of results", async ({ page }) => {
    await page.goto(FINISHED_ACT);
    await expect(page.getByTestId("site-act-results")).toBeVisible();
    await expect(page.getByTestId("matchday-standings-table").locator("tbody tr")).toHaveCount(18);
  });

  test("a planned matchday has no results yet, but does have a draw", async ({ page }) => {
    await page.goto(PLANNED_ACT);
    // Before racing, the page opens on its notice board (Story B-15).
    await expect(page.getByTestId("site-act-notice-board")).toBeVisible();
    await page.getByTestId("site-act-tab-pairing").click();
    await expect(page).toHaveURL(/\/act-3\/pairing/);
    // 18 clubs on 6 boats is 3 races per flight, 16 flights — 48 races.
    await expect(page.getByTestId("matchday-pairing-table").locator("tbody tr")).toHaveCount(48);
  });
});

describeStory("B-3: as a sailor I see when I am on which boat", () => {
  test("the pairing list names the boats by their colour", async ({ page }) => {
    await page.goto(`${PLANNED_ACT}/pairing`);
    const header = page.getByTestId("matchday-pairing-table").locator("thead th");
    for (const colour of ["Black", "Green", "Dark blue", "Red", "Gray", "Orange"]) {
      await expect(header.filter({ hasText: colour })).toHaveCount(1);
    }
  });

  test("the three races of a flight read as one block", async ({ page }) => {
    await page.goto(`${PLANNED_ACT}/pairing`);
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
    await page.goto(`${PLANNED_ACT}/pairing`);
    const club = page.getByTestId("matchday-pairing-club-link-1-1");
    await expect(club).toBeVisible();
    await club.click();
    await expect(page.getByTestId("club-header")).toBeVisible();
  });
});

describeStory("B-4: as a visitor I find clubs and dates", () => {
  test("all 18 clubs are listed", async ({ page }) => {
    await page.goto("/clubs");
    await expect(page.getByTestId("clubs-list").getByRole("listitem")).toHaveCount(18);
  });

  test("from the calendar I get into a matchday", async ({ page }) => {
    await page.goto("/events");
    await page.getByTestId("events-list").getByRole("link").first().click();

    // Through the event's address to its act's page (Story B-16).
    await expect(page).toHaveURL(/\/dsbl\/2026\/act-\d+/);
    await expect(page.getByTestId("site-act-bar")).toBeVisible();
  });
});

test.describe("Foundations", () => {
  test("the language switcher really switches the language", async ({ page }) => {
    // English is the source language and the default; German is a full second language,
    // not a fallback (see CLAUDE.md, "Language").
    await page.goto(STANDINGS);
    await expect(page.getByTestId("site-page-season")).toHaveText("Season");
    await chooseLanguage(page, "de");
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("site-page-season")).toHaveText("Saison");
  });

  test("the former single-league standings URLs still redirect", async ({ page }) => {
    // These were the real URLs of a deployed build, so they stay — and now lead on to the
    // league's standings (Story B-16).
    await page.goto("/standings/1");
    await expect(page).toHaveURL(/\/dsbl\/2026\/standings$/);
    await page.goto("/standings");
    await expect(page).toHaveURL(/\/$/);
  });

  test("the mandatory legal pages are reachable from every page", async ({ page }) => {
    // § 5 DDG requires them to be reachable from anywhere on a German public site. They
    // are in the account menu (Story A-12), which is in the one row of every page, and in
    // the footer.
    await page.goto("/clubs");
    await openUserMenu(page);
    await page.getByTestId("layout-user-menu-legalNotice").click();
    await expect(page).toHaveURL(/\/legal-notice$/);

    await page.goto("/dsbl/season");
    // Once loaded: the loading frame has a top bar of its own, and a menu opened in it
    // closes when the page's frame replaces it.
    await expect(page.getByTestId("site-season-act").first()).toBeVisible();
    await openUserMenu(page);
    await page.getByTestId("layout-user-menu-privacy").click();
    await expect(page).toHaveURL(/\/privacy$/);

    await page.goto("/dsbl/clubs");
    await page.getByTestId("site-footer-legal-notice").click();
    await expect(page).toHaveURL(/\/legal-notice$/);
  });

  test("the page never scrolls sideways — not even with a wide table", async ({ page }, testInfo) => {
    await page.goto(`${PLANNED_ACT}/pairing`);
    await expect(page.getByTestId("matchday-pairing-row-1")).toBeVisible();
    // Via the shared helper, which also checks that the browser has not zoomed the page
    // out (docs/gotchas/, Story A-10).
    await expectNoSidewaysScroll(page, testInfo);
    await page.goto(FINISHED_ACT);
    await expect(page.getByTestId("matchday-standings-table")).toBeVisible();
    await expectNoSidewaysScroll(page, testInfo);
  });

  test("every public page fits its viewport", async ({ page }, testInfo) => {
    // One list, so a new page is one line rather than a new test — and so this runs on
    // the phone viewport too, where fitting is the whole question.
    for (const [path, ready] of PUBLIC_PAGES) {
      await page.goto(path);
      await expect(page.getByTestId(ready).first()).toBeVisible();
      await expectNoSidewaysScroll(page, testInfo);
    }
  });
});

describeStory("B-13: one row of navigation names the leagues", () => {
  test("the home page names the leagues, and has one name of its own", async ({ page }) => {
    await page.goto("/");
    // One page, one name — counted only once the page has loaded (docs/gotchas/: a
    // strict-mode locator checked straight after `goto` passes before the duplicate shows).
    await expect(page.getByTestId("site-home-now")).toBeVisible();
    await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);

    const leagues = page.getByTestId("site-leagues").getByRole("link");
    await expect(leagues).toHaveText(["DSBL", "Junioren-Liga", "DSL-Pokal"]);
    await page.getByTestId("site-league-dsbl").click();
    await expect(page).toHaveURL(/\/dsbl$/);
  });

  test("on a depth page the league is a switch, and its pages sit beside it", async ({ page }) => {
    await page.goto(STANDINGS);
    await expect(page.getByTestId("site-top-bar")).toHaveCount(1);
    const switcher = page.getByTestId("site-league-switch");
    if ((page.viewportSize()?.width ?? 0) >= 768) {
      await expect(page.getByTestId("site-league-pages")).toBeVisible();
    } else {
      // A phone's row has no room for eight links: the pill names the page and opens to them.
      await expect(page.getByTestId("site-league-pages")).toBeHidden();
      await expect(switcher.locator("summary")).toContainText("Standings");
      await switcher.locator("summary").click();
      await switcher.getByTestId("site-switch-page-season").click();
      await expect(page).toHaveURL(/\/dsbl\/season$/);
      await expect(page.getByTestId("site-season-act").first()).toBeVisible();
    }
    await switcher.locator("summary").click();
    await switcher.getByTestId("site-league-junioren-liga").click();
    await expect(page).toHaveURL(/\/junioren-liga$/);
  });

  test("a new page opens at its top", async ({ page }) => {
    await page.goto(STANDINGS);
    await expect(page.getByTestId("site-standings-row").first()).toBeVisible();
    await page.getByTestId("site-footer").scrollIntoViewIfNeeded();
    expect(await page.evaluate(() => window.scrollY)).toBeGreaterThan(0);
    await page.getByTestId("site-footer").getByRole("link", { name: "Season" }).first().click();
    await expect(page).toHaveURL(/\/dsbl\/season$/);
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
  });

  test("every page has a skip link to its content", async ({ page }) => {
    for (const path of ["/", "/dsbl", STANDINGS, FINISHED_ACT, "/clubs"]) {
      await page.goto(path);
      await expect(page.getByTestId("layout-skip-link")).toHaveCount(1);
      await expect(page.locator("main#content")).toHaveCount(1);
    }
  });

  test("a matchday page has two rows of navigation, never more", async ({ page }) => {
    await page.goto(FINISHED_ACT);
    await expect(page.getByTestId("site-act-bar")).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Breadcrumb" })).toHaveCount(0);
    await expect(page.getByTestId("site-top-bar")).toHaveCount(1);
  });

  test("the frame of a depth page is the one the DEV switch chose", async ({ page }) => {
    // The DEV button itself is only in builds with the dev tools (staging, the dev
    // server); the setting it writes is what decides the frame, so this sets it directly.
    for (const frame of ["band", "sheet", "split"]) {
      await page.addInitScript((value) => window.localStorage.setItem("site.detail", value), frame);
      await page.goto(STANDINGS);
      await expect(page.getByTestId("site-depth-page")).toHaveAttribute("data-frame", frame);
      await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
    }
  });
});

describeStory("B-14: a league's page in chapters", () => {
  test("the chapters lead to their own pages", async ({ page }) => {
    await page.goto("/dsbl");
    for (const id of ["now", "standings", "season", "clubs", "news", "media", "press", "about"]) {
      await expect(page.getByTestId(`site-chapter-${id}`)).toHaveCount(1);
    }
    await expect(page.getByTestId("site-chapter-dots").getByRole("link")).toHaveCount(8);
    // The 1. Liga's first five, from the real table.
    await expect(page.getByTestId("site-top-five-dsbl-1-2026").getByRole("listitem")).toHaveCount(5);

    await page.getByTestId("site-chapter-standings-more").click();
    await expect(page).toHaveURL(/\/dsbl\/standings$/);
  });

  test("Now is the running act", async ({ page }) => {
    await page.goto("/dsbl");
    await page.getByTestId("site-chapter-now-more").click();
    // Act 2 is being sailed, so it opens on its results.
    await expect(page).toHaveURL(/\/dsbl\/2026\/act-2$/);
    await expect(page.getByTestId("site-act-results")).toBeVisible();
  });

  test("the chapters scroll from the keyboard", async ({ page }) => {
    await page.goto("/dsbl");
    await expect(page.getByTestId("site-chapter-now")).toBeVisible();
    await page.keyboard.press("PageDown");
    await expect.poll(() => page.getByTestId("site-chapters").evaluate((el) => el.scrollTop)).toBeGreaterThan(0);
  });

  test("placeholder documents and notices say they are examples", async ({ page }) => {
    await page.goto("/dsbl/notice-board");
    await expect(page.getByTestId("site-example-note")).toBeVisible();
    await page.goto(PLANNED_ACT);
    await expect(page.getByTestId("site-act-notice-board").getByTestId("site-example-note")).toBeVisible();
  });

  test("a league with nothing published yet is a page, not an error", async ({ page }) => {
    await page.goto("/dsl-pokal");
    await expect(page.getByTestId("site-chapter-now")).toBeVisible();
    await page.goto("/dsl-pokal/standings");
    await expect(page.getByTestId("site-depth-page")).toBeVisible();
  });

  test("a path that names no league goes home", async ({ page }) => {
    await page.goto("/no-such-league");
    await expect(page).toHaveURL(/\/$/);
  });
});

describeStory("B-15: the matchday page", () => {
  test("every tab has its own address", async ({ page }) => {
    await page.goto(FINISHED_ACT);
    for (const tab of ["notice-board", "results", "pairing", "crews", "live", "media"]) {
      await page.getByTestId(`site-act-tab-${tab}`).click();
      await expect(page).toHaveURL(new RegExp(`/act-1/${tab}`));
      await expect(page.getByTestId(`site-act-${tab}`)).toBeVisible();
    }
    // A guest does not get the race committee's tab.
    await expect(page.getByTestId("site-act-tab-entry")).toHaveCount(0);
  });

  test("the live tab leads to the map", async ({ page }) => {
    await page.goto("/dsbl/2026/act-2/live");
    await page.getByTestId("matchday-live-map-link").click();
    await expect(page).toHaveURL(/\/events\/2\/live$/);
  });
});

describeStory("B-16: old addresses lead to the new pages", () => {
  test("an event's and a series' old address lead to the league's pages", async ({ page }) => {
    await page.goto("/events/1");
    await expect(page).toHaveURL(/\/dsbl\/2026\/act-1\?division=1$/);
    await page.goto("/events/3?view=pairing");
    await expect(page).toHaveURL(/\/dsbl\/2026\/act-3\/pairing\?division=3$/);
    await page.goto("/series/1");
    await expect(page).toHaveURL(/\/dsbl\/2026\/standings$/);
  });

  test("the short paths go to the running act and the last results", async ({ page }) => {
    await page.goto("/dsbl/live");
    await expect(page).toHaveURL(/\/dsbl\/2026\/act-2\/live$/);
    await page.goto("/dsbl/results");
    await expect(page).toHaveURL(/\/dsbl\/2026\/act-1\/results$/);
  });
});

describeStory("A-12: the account menu and the page's name", () => {
  test("outside the leagues a breadcrumb names the page", async ({ page }) => {
    await page.goto("/sailors/1");
    await expect(page.getByTestId("sailor-registrations-section")).toBeVisible();
    // The page states its name once, and that place is the breadcrumb's last crumb.
    const name = page.getByTestId("layout-breadcrumb").getByRole("heading", { level: 1 });
    await expect(name).toHaveText(/\S/);
    await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
  });

  test("the account button opens what is about the reader, not about the page", async ({
    page,
  }) => {
    await page.goto("/");

    // Nothing is open until it is asked for — the row carries only the leagues.
    await expect(page.getByTestId("layout-user-menu")).toHaveCount(0);
    await expect(page.getByTestId("layout-profile-button")).toHaveAttribute(
      "aria-expanded",
      "false",
    );

    await openUserMenu(page);
    // A guest's way in is "Sign in"; my space and my profile are for the signed-in.
    for (const key of ["language", "signIn", "help", "legalNotice", "privacy"]) {
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

    // A guest is offered no administration.
    await expect(page.getByTestId("layout-user-menu-admin")).toHaveCount(0);

    await page.keyboard.press("Escape");
    await expect(page.getByTestId("layout-user-menu")).toHaveCount(0);

    await openUserMenu(page);
    await page.getByTestId("layout-user-menu-help").click();
    await expect(page).toHaveURL(/\/help$/);
    await expect(page.getByTestId("layout-user-menu")).toHaveCount(0);
  });
});
