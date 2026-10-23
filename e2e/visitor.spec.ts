import { describeStory, expect, test } from "./fixtures";

import { chooseLanguage, expectNoSidewaysScroll, openUserMenu } from "./layout";
import { signIn } from "./session";

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
  ["/1-liga/news/asvw-takes-the-lead", "site-article"],
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
  test("all 36 clubs of both divisions are listed, a page at a time", async ({ page, request }) => {
    // 36 clubs sail the 1. and 2. Liga in 2026 (app.seed), and the Junioren-Liga's real
    // field adds the clubs that sail only there — more than one page holds.
    const { total } = (await (await request.get("/api/clubs", { params: { limit: 1 } })).json()) as { total: number };
    expect(total).toBeGreaterThanOrEqual(36);
    await page.goto("/clubs");
    const cards = page.getByTestId("clubs-list").getByRole("listitem");
    // count() does not wait (docs/gotchas): the first card first.
    await expect(cards.first()).toBeVisible();
    expect(await cards.count()).toBeLessThan(total);
    await expect(page.getByTestId("clubs-pager-range")).toContainText(String(total));
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
    // are in the footer of every page — the internal screens' and the official pages'
    // (Story A-12); the account menu no longer repeats them.
    await page.goto("/clubs");
    await page.getByTestId("site-footer-legal-notice").click();
    await expect(page).toHaveURL(/\/legal-notice$/);

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

  test("on a depth page the row stays the same, and the league's pages are the sub-menu", async ({ page }) => {
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

  test("the sub-menu names the league and its pages, and stays while the page scrolls", async ({ page }) => {
    await page.goto(STANDINGS);
    const sub = page.getByTestId("site-league-pages");
    await expect(sub.getByTestId("site-sub-crumbs")).toHaveText("1. Liga");
    await expect(sub.getByTestId("site-page-standings")).toHaveAttribute("aria-current", "page");
    await page.getByTestId("site-footer").scrollIntoViewIfNeeded();
    await expect.poll(async () => (await sub.boundingBox())!.y).toBeGreaterThan(50);
    expect((await sub.boundingBox())!.y).toBeLessThan(60);
  });

  test("the overview has no sub-menu, and its picture stands still behind the top row", async ({ page }) => {
    await page.goto("/1-liga");
    await expect(page.getByTestId("site-chapter-standings")).toBeVisible();
    // The chapters are the overview's contents; the sub-menu is on the pages they lead to.
    await expect(page.getByTestId("site-league-pages")).toHaveCount(0);
    const picture = page.getByTestId("site-chapters-picture");
    // It starts at the top of the screen, behind the row.
    expect((await picture.boundingBox())!.y).toBe(0);
    await page.locator('[data-dot="news"]').click();
    await expect(page.locator('[data-dot="news"]')).toHaveAttribute("aria-current", "true");
    expect((await picture.boundingBox())!.y).toBe(0);
  });

  test("on a matchday page the sub-menu is the matchday's: where it hangs, and its tabs", async ({ page }) => {
    await page.goto(FINISHED_ACT);
    const bar = page.getByTestId("site-act-bar");
    await expect(bar.getByTestId("site-sub-crumbs").getByRole("link")).toHaveCount(2);
    await expect(bar.getByTestId("site-act-tab-results")).toHaveAttribute("aria-current", "page");
    await expect(page.getByTestId("site-league-pages")).toHaveCount(0);
    await bar.getByTestId("site-sub-crumbs").getByRole("link").nth(1).click();
    await expect(page).toHaveURL(/\/1-liga\/season$/);
  });

  test("a page deeper has a picture of its own behind it", async ({ page }) => {
    await page.goto(STANDINGS);
    const picture = page.getByTestId("site-depth-picture");
    const standings = await picture.locator("img").first().getAttribute("src");
    await page.getByTestId("site-footer").scrollIntoViewIfNeeded();
    expect((await picture.boundingBox())!.y).toBe(0);
    await page.goto("/1-liga/season");
    await expect(page.getByTestId("site-depth-picture").locator("img").first()).not.toHaveAttribute("src", standings!);
  });

  test("one column, one grid: every block spans the column, the tiles of a row are equal", async ({ page }) => {
    // Sixteen pages, each to its last request.
    test.setTimeout(120_000);
    // The concept of `components/site/Cards.tsx` ("the grid"): the width belongs to the
    // frame, never to the content. Blocks set no width of their own, so one chapter's
    // cards can no longer end where the next one's go on.
    const pages = [
      "/", "/1-liga", "/2-liga", STANDINGS, "/1-liga/season", "/1-liga/notice-board", "/1-liga/clubs",
      "/1-liga/news", "/1-liga/news/asvw-takes-the-lead", "/1-liga/media", "/1-liga/press", "/1-liga/about",
      "/about", FINISHED_ACT, `${FINISHED_ACT}/notice-board`, `${FINISHED_ACT}/crews`,
    ];
    for (const path of pages) {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      const { problems, checked } = await page.evaluate(() => {
        const found: string[] = [];
        let blocks = 0;
        const name = (el: Element) =>
          (el as HTMLElement).dataset.testid ?? `<${el.tagName.toLowerCase()} class="${el.className}">`.slice(0, 90);
        for (const column of document.querySelectorAll<HTMLElement>("[data-column]")) {
          const box = column.getBoundingClientRect();
          if (!box.height) continue;
          const style = getComputedStyle(column);
          const left = box.left + parseFloat(style.paddingLeft);
          const right = box.right - parseFloat(style.paddingRight);
          // A block's children are checked too where it only stacks them (`data-flow`).
          const check = (parent: Element) => {
            for (const el of parent.children) {
              const b = el.getBoundingClientRect();
              // A block as wide as its content (a pill switch, the "more" link) is inline-*.
              if (!b.height || getComputedStyle(el).display.startsWith("inline")) continue;
              blocks++;
              // A panel with a width of its own (`Panel width`: an article, a table) need not
              // reach both edges — but stays inside them.
              if (el.hasAttribute("data-fit")) {
                if (b.left < left - 1 || b.right > right + 1) {
                  found.push(`${name(el)} spans ${Math.round(b.left)}–${Math.round(b.right)}, beyond its column ${Math.round(left)}–${Math.round(right)}`);
                }
                continue;
              }
              if (Math.abs(b.left - left) > 1 || Math.abs(b.right - right) > 1) {
                found.push(`${name(el)} spans ${Math.round(b.left)}–${Math.round(b.right)}, its column ${Math.round(left)}–${Math.round(right)}`);
              }
              if (el.hasAttribute("data-flow")) check(el);
            }
          };
          check(column);
        }
        for (const row of document.querySelectorAll("[data-card-row]")) {
          const widths = new Set(
            [...row.children].map((c) => c.getBoundingClientRect()).filter((b) => b.height).map((b) => Math.round(b.width)),
          );
          if (widths.size > 1) found.push(`${name(row)}: tiles of ${[...widths].join(", ")} px`);
        }
        return { problems: found, checked: blocks };
      });
      // A page that marks no column would pass by checking nothing.
      expect(checked, `${path}: blocks measured`).toBeGreaterThan(0);
      expect(problems, path).toEqual([]);
    }
  });

  test("the glass blurs the picture behind it — on the chapters too", async ({ page }) => {
    // Pixels, not the computed style: a mask on the chapters' scroller once made every
    // card's blur see nothing while backdrop-filter still read blur(32px) (docs/gotchas).
    for (const [path, card] of [
      ["/1-liga", page.getByTestId("site-season-strip")],
      ["/1-liga/clubs", page.locator('[data-testid^="site-clubs-"] a').first()],
    ] as const) {
      await page.goto(path);
      await expect(card).toBeVisible();
      // Every picture loaded, or the two shots differ because the photo arrived between
      // them — which is how this test first passed with the bug in place.
      await page.waitForFunction(() =>
        [...document.querySelectorAll<HTMLImageElement>('[data-testid$="-picture"] img')].every((img) => img.complete),
      );
      const look = async (blur: string) => {
        await page.evaluate((v) => document.documentElement.style.setProperty("--site-card-blur", v), blur);
        await page.waitForTimeout(300);
        return card.screenshot({ animations: "disabled" });
      };
      const sharp = await look("0px");
      expect(Buffer.compare(sharp, await look("0px")), `${path}: the same look twice`).toBe(0);
      expect(Buffer.compare(sharp, await look("32px")), `${path}: blurred`).not.toBe(0);
    }
  });

});

describeStory("B-14: a league's page in chapters", () => {
  test("the chapters lead to their own pages, Results first and titled so while a matchday is live", async ({ page }) => {
    await page.goto("/1-liga");
    // Act 2 is being sailed, so Results is there and opens the page; the seed has no
    // earlier year, so no Archive.
    const chapters = page.getByTestId("site-chapters").locator("section[data-chapter]");
    await expect(chapters).toHaveCount(5);
    expect(await chapters.evaluateAll((els) => els.map((el) => el.getAttribute("data-chapter")))).toEqual([
      "results",
      "standings",
      "news",
      "media",
      "about",
    ]);
    await expect(page.getByTestId("site-chapter-dots").getByRole("link")).toHaveCount(5);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Results Act 2");
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
    // The juniors have teams but no matchday in the seed: nothing is live there.
    await page.goto("/junioren-liga");
    await expect(page.getByTestId("site-chapter-standings")).toBeVisible();
    await expect(page.getByTestId("site-chapter-results")).toHaveCount(0);
    // With nothing live, Standings opens the page.
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Standings");
    // The 2. Liga is a league of its own, sailing the same weekends: its act 2 is live.
    await page.goto("/2-liga");
    await expect(page.getByTestId("site-chapter-results")).toHaveCount(1);
    await expect(page.getByTestId("site-top-five-dsbl-2-2026")).toHaveCount(1);
    await expect(page.getByTestId("site-top-five-dsbl-2-2026").locator("[data-empty]")).toHaveCount(0);
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
    // At the top of the scrolling box, which starts under the top row.
    await expect
      .poll(() =>
        page.getByTestId("site-chapter-news").evaluate((el) => {
          const box = el.closest('[data-testid="site-chapters"]')!;
          // `+ 0`: a rounded -0.4 is -0, which `toBe(0)` does not accept.
          return Math.round(el.getBoundingClientRect().top - box.getBoundingClientRect().top) + 0;
        }),
      )
      .toBe(0);
    expect(page.url()).not.toContain("#");
    expect(await page.evaluate(() => history.length)).toBe(before);
  });

  test("the marked dot is the chapter in the middle of the screen, however tall", async ({ page }) => {
    await page.goto("/1-liga");
    await expect(page.getByTestId("site-chapter-standings")).toBeVisible();
    // A chapter three screens tall: at 55% visible, the rule this replaced, it could never
    // be marked.
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

  test("the chapters are filled: the season's matchdays, news with pictures, videos, facts", async ({ page }) => {
    await page.goto("/1-liga");
    // Every act of the year — at least the seed's three; the lifecycle spec adds its own.
    await expect.poll(() => page.getByTestId("site-season-strip").getByRole("listitem").count()).toBeGreaterThanOrEqual(3);
    await expect(page.getByTestId("site-news-tiles").getByRole("link").first()).toBeVisible();
    await expect(page.getByTestId("site-video-tiles").getByRole("listitem")).toHaveCount(3);
    await expect(page.getByTestId("site-about-facts").getByRole("listitem").first()).toBeVisible();
    await expect(page.getByTestId("site-live-progress")).toHaveCount(1);
    await page.goto("/");
    await expect(page.getByTestId("site-home-services").getByRole("listitem")).toHaveCount(6);
  });

  test("a news article has its own page: lead, byline, text, and more news", async ({ page }) => {
    await page.goto("/1-liga/news");
    await page.getByTestId("site-news-asvw-takes-the-lead").click();
    await expect(page).toHaveURL(/\/1-liga\/news\/asvw-takes-the-lead$/);
    await expect(page.getByTestId("site-article-lead")).toBeVisible();
    await expect(page.getByTestId("site-article-byline")).toBeVisible();
    // Invented news about real clubs says it is an example.
    await expect(page.getByTestId("site-example-note")).toBeVisible();
    await expect(page.getByTestId("site-article-related").getByRole("listitem")).toHaveCount(3);
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

  test("the pairing list's club picker is legible on the glass, open or closed", async ({ page }) => {
    await page.goto("/1-liga/2026/act-2/pairing");
    const picker = page.getByTestId("matchday-pairing-pdf-club");
    await expect(picker).toBeVisible();
    // The field is glass with white text, and the list the browser opens is dark with white
    // text — before, both were white text on the browser's white.
    const look = await picker.evaluate((el) => {
      const option = getComputedStyle(el.querySelector("option")!);
      return { scheme: getComputedStyle(el).colorScheme, text: option.color, background: option.backgroundColor };
    });
    expect(look.scheme).toBe("dark");
    expect(look.text).toBe("rgb(255, 255, 255)");
    expect(look.background).not.toBe("rgb(255, 255, 255)");
    expect(look.background).not.toBe(look.text);
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

  test("a guest gets no menu: the language and Sign in, side by side", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("layout-profile-button")).toHaveCount(0);
    await expect(page.getByTestId("layout-user-menu")).toHaveCount(0);
    await expect(page.getByTestId("layout-sign-in")).toHaveAttribute("href", "/account");

    // A small menu of its own, each language named in itself, the current one checked;
    // choosing closes it.
    const language = page.getByTestId("layout-language");
    await expect(language).toContainText("en");
    await language.click();
    await expect(page.getByTestId("language-switcher").getByRole("menuitemradio")).toHaveCount(2);
    await expect(page.getByTestId("language-switcher-en")).toHaveAttribute("aria-checked", "true");
    await expect(page.getByTestId("language-switcher-de")).toContainText("Deutsch");
    await page.getByTestId("language-switcher-de").click();
    await expect(page.getByTestId("language-switcher")).toHaveCount(0);
    await expect(page.getByTestId("layout-sign-in")).toHaveText("Anmelden");
    await expect(language).toContainText("de");
  });

  test("signed in, the account button opens what is about the reader, not the legal pages", async ({ page }) => {
    await signIn(page, "admin@sbl.example.com");
    await page.goto("/");
    await expect(page.getByTestId("layout-user-menu")).toHaveCount(0);
    await expect(page.getByTestId("layout-profile-button")).toHaveAttribute("aria-expanded", "false");
    await expect(page.getByTestId("layout-language")).toHaveCount(0);

    await openUserMenu(page);
    for (const key of ["mySpace", "profile", "admin", "help", "language"]) {
      await expect(page.getByTestId(`layout-user-menu-${key}`)).toBeVisible();
    }
    // The legal pages are the footer's (§ 5 DDG), not repeated here.
    for (const key of ["legalNotice", "privacy", "signIn"]) {
      await expect(page.getByTestId(`layout-user-menu-${key}`)).toHaveCount(0);
    }

    // The language is a submenu: closed until asked for, then one entry per language,
    // each named in its own language and the current one marked. `menuitemradio`, not
    // `listitem`: the panel is a `role="menu"`, which replaces its children's list roles.
    await expect(page.getByTestId("language-switcher")).toHaveCount(0);
    await page.getByTestId("layout-user-menu-language").click();
    await expect(page.getByTestId("language-switcher").getByRole("menuitemradio")).toHaveCount(2);
    await expect(page.getByTestId("language-switcher-de")).toHaveText("Deutsch");
    await expect(page.getByTestId("language-switcher-en")).toHaveAttribute("aria-checked", "true");
    await page.getByTestId("layout-user-menu-language").click();
    await expect(page.getByTestId("language-switcher")).toHaveCount(0);

    await page.keyboard.press("Escape");
    await expect(page.getByTestId("layout-user-menu")).toHaveCount(0);
  });
});

describeStory("B-19: switch between dark and light", () => {
  test("a guest switches to light and back, and the choice stays", async ({ page }) => {
    await page.goto("/legal-notice");
    const html = page.locator("html");
    // Dark is the default.
    await expect(html).toHaveAttribute("data-theme", "dark");
    await page.getByTestId("layout-theme").click();
    await expect(html).toHaveAttribute("data-theme", "light");
    // Remembered across a reload — set before the first paint, not after — and on the
    // next page.
    await page.reload();
    await expect(html).toHaveAttribute("data-theme", "light");
    await page.goto("/privacy");
    await expect(html).toHaveAttribute("data-theme", "light");
    await page.getByTestId("layout-theme").click();
    await expect(html).toHaveAttribute("data-theme", "dark");
  });

  test("the button sits beside the account button once signed in", async ({ page }) => {
    await signIn(page, "board@asvw.example.com");
    await page.goto("/me");
    await expect(page.getByTestId("layout-profile-button")).toBeVisible();
    await page.getByTestId("layout-theme").click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  });

  test("the official pages switch too, their pictures under a light veil", async ({ page }) => {
    await page.goto(STANDINGS);
    await page.getByTestId("layout-theme").click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    // The page's type is dark on the light theme: the colour names, not white.
    const title = page.getByRole("heading", { level: 1 });
    await expect(title).toHaveCSS("color", "rgb(15, 23, 42)");
    await page.goto(FINISHED_ACT);
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  });
});
