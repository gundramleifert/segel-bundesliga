import { describeStory, expect, test } from "./fixtures";

import { chooseLanguage, expectNoSidewaysScroll, openUserMenu } from "./layout";

/** E2E cut along the user stories — see docs/userstories/.
 *
 * These are the public pages, read as a visitor with no account. They address elements by
 * `data-testid` rather than by visible text wherever a test is about structure rather than
 * wording: the site is bilingual and the copy is edited often, and a spec that breaks on a
 * reworded heading tests the translator, not the application.
 *
 * The seed (`app.seed`) is the fixture: four leagues (1. Liga, 2. Liga, Junioren, DSL-Pokal),
 * a 2026 series in each of the first three, and three acts of the 1. Liga — act 1 sailed to the end,
 * act 2 two-thirds sailed, act 3 drawn but not started. The Sailing Champions League
 * series belongs to no league, so it keeps its own page.
 */

const FINISHED_ACT = "/1-liga/2026/act-1"; // dsbl-1-2026-act-1, event 1
const PLANNED_ACT = "/1-liga/2026/act-3"; // dsbl-1-2026-act-3, event 3
const STANDINGS = "/1-liga/standings";
const UNLEAGUED_SERIES = "/series/4"; // scl-2026, in no league

/** Every public page, with the testid that means "this page has its data".
 *
 *  A list rather than a test each: adding a page should be one line, and every page has to
 *  answer the same question — does it fit the viewport it is being read on. */
const PUBLIC_PAGES: [path: string, ready: string][] = [
  ["/", "site-home-now"],
  ["/1-liga", "site-chapter-standings"],
  ["/2-liga", "site-chapter-standings"],
  [STANDINGS, "site-standings-dsbl-1-2026"],
  ["/1-liga/season", "site-season-act"],
  ["/1-liga/clubs", "site-clubs-dsbl-1-2026"],
  ["/1-liga/notice-board", "site-depth-page"],
  ["/1-liga/news", "site-depth-page"],
  ["/1-liga/media", "site-depth-page"],
  ["/1-liga/press", "site-depth-page"],
  ["/1-liga/about", "site-depth-page"],
  ["/about", "site-depth-page"],
  [FINISHED_ACT, "matchday-standings-table"],
  [`${PLANNED_ACT}/pairing`, "matchday-pairing-table"],
  [UNLEAGUED_SERIES, "standings-results-section"],
  ["/events", "events-list"],
  ["/clubs", "clubs-list"],
  ["/clubs/1", "club-header"],
  ["/sailors/1", "sailor-registrations-section"],
  // The handbook is internal (Story B-18): a guest gets the sign-in prompt.
  ["/help", "help-sign-in"],
  ["/legal-notice", "legal-notice-last-updated"],
  ["/privacy", "privacy-last-updated"],
];

describeStory("B-1/B-14: as a fan I see the series standings", () => {
  const firstLiga = (page: import("@playwright/test").Page) =>
    page.getByTestId("site-standings-dsbl-1-2026").getByTestId("site-standings-table").locator("tbody tr");

  test("the table lists all 18 clubs in ranks 1 to 18", async ({ page }) => {
    await page.goto(STANDINGS);
    const rows = firstLiga(page);
    await expect(rows).toHaveCount(18);
    await expect(rows.first().locator("td").first()).toHaveText("1");
    await expect(rows.last().locator("td").first()).toHaveText("18");
  });

  test("fewer points ranks higher", async ({ page }) => {
    await page.goto(STANDINGS);
    await expect(firstLiga(page)).toHaveCount(18);
    const points = await firstLiga(page).locator("td:nth-child(3)").allInnerTexts();
    const numbers = points.map((text) => Number(text.replace(",", ".")));
    expect(numbers).toEqual([...numbers].sort((a, b) => a - b));
  });

  test("a column per act, and each heading leads to its matchday", async ({ page }) => {
    await page.goto(STANDINGS);
    const table = page.getByTestId("site-standings-dsbl-1-2026").getByTestId("site-standings-table");
    // At least the three acts the seed sails — other stories add acts to this same series
    // (docs/gotchas: a count against a seed event is green alone and red in the suite).
    await expect(table.getByRole("columnheader").getByRole("link").nth(2)).toBeVisible();
    await table.getByRole("columnheader").getByRole("link").first().click();
    await expect(page).toHaveURL(/\/1-liga\/2026\/act-1\/results$/);
    await expect(page.getByTestId("matchday-standings-table")).toBeVisible();
  });

  test("a short club name carries its full name in a tooltip", async ({ page }) => {
    await page.goto(STANDINGS);
    const club = page.getByTestId("site-standings-dsbl-1-2026").getByTestId(/site-standings-club-link-/).first();
    await expect(club).toBeVisible();
    const short = (await club.textContent())!.trim();
    expect(short.length).toBeLessThan(12);
    await expect(page.getByTestId("tooltip")).toHaveCount(0);
    await club.hover();
    const tip = page.getByTestId("tooltip");
    await expect(tip).toBeVisible();
    expect((await tip.textContent())!.length).toBeGreaterThan(short.length);
  });

  test("the league's rules mark the table, and only where they apply", async ({ page }) => {
    await page.goto(STANDINGS);
    // The 1. Liga's last four go down; it promotes nobody.
    const table = page.getByTestId("site-standings-dsbl-1-2026");
    await expect(firstLiga(page)).toHaveCount(18);
    await expect(table.locator('tr[data-mark="relegation"]')).toHaveCount(4);
    await expect(table.locator('tr[data-mark="promotion"]')).toHaveCount(0);
    await expect(table.getByTestId("site-standings-legend")).toContainText("Relegation");
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
    await expect(page).toHaveURL(/\/1-liga\/2026\/act-\d+/);
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
    await expect(page).toHaveURL(/\/1-liga\/2026\/standings$/);
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

    await page.goto("/1-liga/season");
    // Once loaded: the loading frame has a top bar of its own, and a menu opened in it
    // closes when the page's frame replaces it.
    await expect(page.getByTestId("site-season-act").first()).toBeVisible();
    await openUserMenu(page);
    await page.getByTestId("layout-user-menu-privacy").click();
    await expect(page).toHaveURL(/\/privacy$/);

    await page.goto("/1-liga/clubs");
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
  /** Follows an entry of the top row — on a phone it is in the menu (Story B-13). */
  async function follow(page: import("@playwright/test").Page, key: string) {
    if ((page.viewportSize()?.width ?? 0) < 768) {
      await page.getByTestId("site-menu").locator("summary").click();
      await page.getByTestId(`site-menu-${key}`).click();
    } else {
      await page.getByTestId(`site-${key}`).click();
    }
  }

  test("the row names the association and every league, and the home page one name", async ({ page }) => {
    await page.goto("/");
    // One page, one name — counted only once the page has loaded (docs/gotchas/: a
    // strict-mode locator checked straight after `goto` passes before the duplicate shows).
    await expect(page.getByTestId("site-home-now")).toBeVisible();
    await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);

    const names = ["Association", "1. Liga", "2. Liga", "Junioren", "DSL-Pokal"];
    if ((page.viewportSize()?.width ?? 0) < 768) {
      await expect(page.getByTestId("site-leagues")).toBeHidden();
      await expect(page.getByTestId("site-menu").locator("summary")).toContainText("Association");
      await page.getByTestId("site-menu").locator("summary").click();
      await expect(page.getByTestId("site-menu").getByRole("link")).toHaveText(names);
      await page.getByTestId("site-menu").locator("summary").click();
    } else {
      await expect(page.getByTestId("site-menu")).toBeHidden();
      await expect(page.getByTestId("site-leagues").getByRole("link")).toHaveText(names);
      await expect(page.getByTestId("site-association")).toHaveAttribute("aria-current", "page");
    }
    await follow(page, "league-2-liga");
    await expect(page).toHaveURL(/\/2-liga$/);
    await expect(page.getByTestId("site-league-2-liga")).toHaveAttribute("aria-current", "page");
    await follow(page, "association");
    await expect(page).toHaveURL(/\/$/);
  });

  test("on a depth page the row stays the same, and the league's pages sit under the picture", async ({ page }) => {
    await page.goto(STANDINGS);
    await expect(page.getByTestId("site-top-bar")).toHaveCount(1);
    await expect(page.getByTestId("site-league-1-liga")).toHaveAttribute("aria-current", "page");
    await page.getByTestId("site-league-pages").getByTestId("site-page-season").click();
    await expect(page).toHaveURL(/\/1-liga\/season$/);
    await expect(page.getByTestId("site-season-act").first()).toBeVisible();
    await follow(page, "league-junioren-liga");
    await expect(page).toHaveURL(/\/junioren-liga$/);
  });

  test("a new page opens at its top", async ({ page }) => {
    await page.goto(STANDINGS);
    await expect(page.getByTestId("site-standings-table").first()).toBeVisible();
    await page.getByTestId("site-footer").scrollIntoViewIfNeeded();
    expect(await page.evaluate(() => window.scrollY)).toBeGreaterThan(0);
    await page.getByTestId("site-footer").getByRole("link", { name: "Season" }).first().click();
    await expect(page).toHaveURL(/\/1-liga\/season$/);
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
  });

  test("every page has a skip link to its content", async ({ page }) => {
    for (const path of ["/", "/1-liga", STANDINGS, FINISHED_ACT, "/clubs"]) {
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
  test("the chapters lead to their own pages, Standings first and titled so", async ({ page }) => {
    await page.goto("/1-liga");
    // Act 2 is being sailed, so Results is there; the seed has no earlier year, so no Archive.
    for (const id of ["standings", "results", "news", "media", "about"]) {
      await expect(page.getByTestId(`site-chapter-${id}`)).toHaveCount(1);
    }
    await expect(page.getByTestId("site-chapter-dots").getByRole("link")).toHaveCount(5);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Standings");
    await expect(page.getByTestId("site-chapter-archive")).toHaveCount(0);
    // The 1. Liga's first five, from the real table.
    await expect(page.getByTestId("site-top-five-dsbl-1-2026").getByRole("listitem")).toHaveCount(5);

    await page.getByTestId("site-chapter-standings-more").click();
    await expect(page).toHaveURL(/\/1-liga\/standings$/);
  });

  test("Results is the running act", async ({ page }) => {
    await page.goto("/1-liga");
    await page.getByTestId("site-chapter-results-more").click();
    await expect(page).toHaveURL(/\/1-liga\/2026\/act-2\/results$/);
    await expect(page.getByTestId("site-act-results")).toBeVisible();
  });

  test("Results is there only while a matchday is live; About names the clubs", async ({ page }) => {
    // The 2. Liga is a league of its own; nothing of it is being sailed in the seed.
    await page.goto("/2-liga");
    await expect(page.getByTestId("site-chapter-standings")).toBeVisible();
    await expect(page.getByTestId("site-chapter-results")).toHaveCount(0);
    await expect(page.getByTestId("site-top-five-dsbl-2-2026")).toHaveCount(1);
    await page.goto("/1-liga");
    await expect(page.getByTestId("site-about-clubs").getByRole("listitem").first()).toBeVisible();
  });

  test("the chapters scroll from the keyboard", async ({ page }) => {
    await page.goto("/1-liga");
    await expect(page.getByTestId("site-chapter-standings")).toBeVisible();
    await page.keyboard.press("PageDown");
    await expect.poll(() => page.getByTestId("site-chapters").evaluate((el) => el.scrollTop)).toBeGreaterThan(0);
  });

  test("the dots claim their own column and nothing more", async ({ page }) => {
    await page.goto("/1-liga");
    const dots = page.getByTestId("site-chapter-dots");
    await expect(dots.getByRole("link")).toHaveCount(5);
    // The names are laid over the chapter; the touch area is the dots. It was 145 px of a
    // 412 px phone, and every swipe that started there jumped chapters.
    expect((await dots.boundingBox())!.width).toBeLessThan(64);
  });

  test("a tap on a dot scrolls there, and leaves the address and the history alone", async ({ page }) => {
    await page.goto("/1-liga");
    await expect(page.getByTestId("site-chapter-standings")).toBeVisible();
    const before = await page.evaluate(() => history.length);
    await page.locator('[data-dot="news"]').click();
    await expect(page.locator('[data-dot="news"]')).toHaveAttribute("aria-current", "true");
    await expect.poll(() => page.getByTestId("site-chapter-news").evaluate((el) => Math.round(el.getBoundingClientRect().top))).toBe(0);
    expect(page.url()).not.toContain("#");
    expect(await page.evaluate(() => history.length)).toBe(before);
  });

  test("the marked dot is the chapter in the middle of the screen, however tall", async ({ page }) => {
    await page.goto("/1-liga");
    await expect(page.getByTestId("site-chapter-standings")).toBeVisible();
    // A chapter three screens tall: at 55% visible, the rule this replaced, it could never
    // be marked. Free mode, so the box can stop inside it.
    await page.evaluate(() => {
      localStorage.setItem("site.chapters", "free");
    });
    await page.reload();
    const tall = page.getByTestId("site-chapter-standings");
    await tall.evaluate((el) => (el.style.minHeight = "300vh"));
    await page.getByTestId("site-chapters").evaluate((box) => {
      const el = document.getElementById("standings")!;
      box.scrollTop = el.offsetTop + window.innerHeight;
    });
    await expect(page.locator('[data-dot="standings"]')).toHaveAttribute("aria-current", "true");
  });

  test("a thumb sliding along the dots is followed by its height, even when it drifts", async ({ page, isMobile }) => {
    test.skip(!isMobile, "a touch gesture — the phone project's");
    await page.goto("/1-liga");
    await expect(page.getByTestId("site-chapter-standings")).toBeVisible();
    const box = (dot: string) => page.locator(`[data-dot="${dot}"]`).boundingBox();
    const start = (await box("standings"))!;
    const end = (await box("about"))!;
    const cdp = await page.context().newCDPSession(page);
    const x = start.x + start.width / 2;
    await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x, y: start.y + start.height / 2 }] });
    // Down the column — and off it to the left, the way a thumb drifts.
    for (let i = 1; i <= 10; i++) {
      const y = start.y + ((end.y - start.y) * i) / 10 + start.height / 2;
      await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x: x - i * 15, y }] });
    }
    await expect(page.getByTestId("site-chapter-dots")).toHaveAttribute("data-scrubbing", "");
    await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
    await expect(page.getByTestId("site-chapter-dots")).not.toHaveAttribute("data-scrubbing", "");
    await expect(page.locator('[data-dot="about"]')).toHaveAttribute("aria-current", "true");
  });

  test("placeholder documents and notices say they are examples", async ({ page }) => {
    await page.goto("/1-liga/notice-board");
    await expect(page.getByTestId("site-example-note")).toBeVisible();
    await page.goto(PLANNED_ACT);
    await expect(page.getByTestId("site-act-notice-board").getByTestId("site-example-note")).toBeVisible();
  });

  test("a league with nothing published yet is a page, not an error", async ({ page }) => {
    await page.goto("/dsl-pokal");
    await expect(page.getByTestId("site-chapter-standings")).toBeVisible();
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
    await page.goto("/1-liga/2026/act-2/live");
    await page.getByTestId("matchday-live-map-link").click();
    await expect(page).toHaveURL(/\/events\/2\/live$/);
  });
});

describeStory("B-16: old addresses lead to the new pages", () => {
  test("an event's and a series' old address lead to the league's pages", async ({ page }) => {
    await page.goto("/events/1");
    await expect(page).toHaveURL(/\/1-liga\/2026\/act-1\?division=1$/);
    await page.goto("/events/3?view=pairing");
    await expect(page).toHaveURL(/\/1-liga\/2026\/act-3\/pairing\?division=3$/);
    await page.goto("/series/1");
    await expect(page).toHaveURL(/\/1-liga\/2026\/standings$/);
  });

  test("the DSBL's addresses lead to the same page of the 1. Liga", async ({ page }) => {
    await page.goto("/dsbl");
    await expect(page).toHaveURL(/\/1-liga$/);
    await page.goto("/dsbl/standings");
    await expect(page).toHaveURL(/\/1-liga\/standings$/);
    await page.goto("/dsbl/2026/act-3/pairing?division=3");
    await expect(page).toHaveURL(/\/1-liga\/2026\/act-3\/pairing\?division=3$/);
  });

  test("the short paths go to the running act and the last results", async ({ page }) => {
    await page.goto("/1-liga/live");
    await expect(page).toHaveURL(/\/1-liga\/2026\/act-2\/live$/);
    await page.goto("/1-liga/results");
    await expect(page).toHaveURL(/\/1-liga\/2026\/act-1\/results$/);
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
    // A guest's way in is "Sign in"; my space, my profile and the help (internal, Story
    // B-18) are for the signed-in.
    await expect(page.getByTestId("layout-user-menu-help")).toHaveCount(0);
    for (const key of ["language", "signIn", "legalNotice", "privacy"]) {
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
    await page.getByTestId("layout-user-menu-legalNotice").click();
    await expect(page).toHaveURL(/\/legal-notice$/);
    await expect(page.getByTestId("layout-user-menu")).toHaveCount(0);
  });
});
