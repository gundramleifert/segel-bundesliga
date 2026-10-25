import { readdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describeStory, expect, test } from "./fixtures";
import { chooseLanguage, expectNoSidewaysScroll, openUserMenu } from "./layout";
import { bearer, bornIn, managedClub, seededSailors, signIn } from "./session";

/** Story B-18: the help for what I do — the `/help` viewer over `web/src/handbook/`.
 *
 * The handbook is internal: every signed-in account reads all of it, a guest gets a
 * sign-in prompt and nothing else — the public site must explain itself.
 *
 * The pages are written by the `handbook` skill and change often, so this spec asserts
 * the viewer's structure — tiles, anchors, links, languages — and reads which journey
 * pages exist from the store itself rather than listing them twice. The reserved pages
 * (`roles` with `#roles-matrix`, the `start-<audience>` pages, `terms`) are the fixed
 * points it relies on (`.claude/skills/handbook/references/content-model.md`).
 */

const STORE = fileURLToPath(new URL("../web/src/handbook/", import.meta.url));
const AUDIENCES = [
  "sailor",
  "club",
  "event-organizer",
  "race-committee",
  "treasurer",
  "administration",
];
const TEAM_MANAGER = "teams@asvw.example.com";
// An account with no relation at all: the handbook is for every signed-in account.
const ANYONE = "gast@sbl.example.com";

/** The English pages of the store, by id, with their raw text. */
function storePages(): Map<string, string> {
  const pages = new Map<string, string>();
  for (const file of readdirSync(STORE)) {
    const match = /^([a-z0-9-]+)\.en\.md$/.exec(file);
    if (match) pages.set(match[1], readFileSync(STORE + file, "utf8"));
  }
  return pages;
}

const typeOf = (text: string) => /^type:\s*(\S+)/m.exec(text)?.[1];

describeStory("B-18: as a guest I am asked to sign in for the help", () => {
  for (const path of ["/help", "/help/roles#roles-matrix"]) {
    test(`${path} shows a sign-in prompt and no page content`, async ({ page }) => {
      await page.goto(path);
      await expect(page.getByTestId("help-sign-in")).toBeVisible();
      await expect(page.getByTestId("help-sign-in-link")).toHaveAttribute("href", "/account");
      await expect(page.locator('[data-testid^="help-audience-"]')).toHaveCount(0);
      await expect(page.getByTestId("help-search")).toHaveCount(0);
      await expect(page.locator('[data-testid^="help-article-"]')).toHaveCount(0);
      await expect(page.locator("#roles-matrix")).toHaveCount(0);
    });
  }

  test("a guest is offered no help in the top row", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("layout-sign-in")).toBeVisible();
    await expect(page.getByTestId("layout-user-menu-help")).toHaveCount(0);
  });
});

describeStory("B-18: as anyone signed in I find the help for what I do", () => {
  test.beforeEach(async ({ page }) => {
    // A test about one person signs in again as them; the later init script wins.
    await signIn(page, ANYONE);
  });

  test("the landing shows a tile per audience and a card per journey", async ({ page }) => {
    await page.goto("/help");
    const tiles = page.locator('a[data-testid^="help-audience-"]');
    await expect(tiles).toHaveCount(AUDIENCES.length);
    // An account with no relation has nothing marked, and sees the usual order.
    await expect(tiles.first()).toHaveAttribute("data-testid", "help-audience-sailor");
    await expect(page.locator('[data-testid$="-mine"]')).toHaveCount(0);
    for (const audience of AUDIENCES) {
      await expect(page.getByTestId(`help-audience-${audience}`)).toHaveAttribute(
        "href",
        `/help/start-${audience}`,
      );
    }
    const journeys = [...storePages()].filter(([, text]) => typeOf(text) === "journey").map(([id]) => id);
    for (const id of journeys) await expect(page.getByTestId(`help-journey-${id}`)).toBeVisible();
    await expect(page.getByTestId("help-page-roles")).toBeVisible();
    await expect(page.getByTestId("help-page-terms")).toBeVisible();
  });

  test("a signed-in team manager sees the club's help first, marked as theirs", async ({ page }) => {
    await signIn(page, TEAM_MANAGER);
    await page.goto("/help");
    await expect(page.getByTestId("help-audience-club-mine")).toBeVisible();
    const tiles = page.locator('a[data-testid^="help-audience-"]');
    await expect(tiles).toHaveCount(AUDIENCES.length);
    // Theirs first — the club among them — and every audience still there.
    const order = await tiles.evaluateAll((els) => els.map((el) => el.getAttribute("data-testid")));
    const marked = await page.locator('[data-testid^="help-audience-"][data-testid$="-mine"]').count();
    expect(order.slice(0, marked)).toContain("help-audience-club");
  });

  test("a parent the club linked as guardian sees the sailor's help marked as theirs", async ({
    page,
    request,
  }, testInfo) => {
    // A guardian holds nothing my space lists — the link sits on the child — so this is
    // the one audience that comes from the wards rather than from the contexts.
    const admin = await bearer(request, "admin@sbl.example.com");
    const parent = `help-parent-${testInfo.project.name}-${Date.now()}@example.com`;
    const created = await request.post("/api/auth/users", {
      headers: admin,
      data: { email: parent, display_name: "Pat Parent" },
    });
    expect(created.ok(), await created.text()).toBeTruthy();
    const sailors = await request.get("/api/admin/sailors?q=asvw.example.com&limit=1", { headers: admin });
    const child = ((await sailors.json()) as { items: { id: number }[] }).items[0]!;
    const linked = await request.post(`/api/sailors/${child.id}/guardians`, {
      headers: admin,
      data: { email: parent },
    });
    expect(linked.ok(), await linked.text()).toBeTruthy();

    await signIn(page, parent);
    await page.goto("/help");
    await expect(page.getByTestId("help-audience-sailor-mine")).toBeVisible();
    await expect(page.locator('a[data-testid^="help-audience-"]').first()).toHaveAttribute(
      "data-testid",
      "help-audience-sailor",
    );
  });

  test("an audience tile opens that audience's starting page", async ({ page }) => {
    await page.goto("/help");
    await page.getByTestId("help-audience-club").click();
    await expect(page).toHaveURL(/\/help\/start-club$/);
    await expect(page.getByTestId("help-article-start-club")).toBeVisible();
  });

  test("/help/roles#roles-matrix loads in a fresh tab and lands on the matrix", async ({ page }) => {
    await page.goto("/help/roles#roles-matrix");
    await expect(page.getByTestId("help-article-roles")).toBeVisible();
    await expect(page.locator("#roles-matrix")).toBeInViewport();
    await expect(page.locator("h1")).toHaveCount(1);
  });

  test("a link inside a page opens the page it points to, without a reload", async ({ page }) => {
    await page.goto("/help/start-club");
    await expect(page.getByTestId("help-article-start-club")).toBeVisible();
    await page.evaluate(() => ((window as unknown as { helpMarker: number }).helpMarker = 1));
    const link = page.getByTestId("help-article-start-club").locator('a[href^="/help/"]').first();
    const href = (await link.getAttribute("href"))!;
    const [target, anchor] = href.replace("/help/", "").split("#");
    await link.click();
    await expect(page).toHaveURL(new RegExp(`/help/${target}`));
    await expect(page.getByTestId(`help-article-${target}`)).toBeVisible();
    if (anchor) await expect(page.locator(`#${anchor}`)).toBeInViewport();
    expect(await page.evaluate(() => (window as unknown as { helpMarker?: number }).helpMarker)).toBe(1);
  });

  test("in German the same page comes in German, with the same anchors", async ({ page }) => {
    await page.goto("/help/roles");
    const article = page.getByTestId("help-article-roles");
    await expect(article).toHaveAttribute("data-locale", "en");
    await chooseLanguage(page, "de");
    await expect(article).toHaveAttribute("data-locale", "de");
    for (const anchor of ["roles-list", "roles-matrix", "roles-getting"]) {
      await expect(page.locator(`#${anchor}`)).toHaveCount(1);
    }
  });

  test("the search finds a page by a German word in either language", async ({ page }) => {
    await page.goto("/help");
    await page.getByTestId("help-search").fill("rollen");
    await expect(page.getByTestId("help-result-roles")).toBeVisible();
    await page.getByTestId("help-search").fill("zzzz-nothing");
    await expect(page.locator('[data-testid^="help-result-"]')).toHaveCount(0);
  });

  test("the widest page does not scroll sideways", async ({ page }, testInfo) => {
    await page.goto("/help/roles");
    await expect(page.getByTestId("help-article-roles").locator("table").first()).toBeVisible();
    await expectNoSidewaysScroll(page, testInfo);
  });

  test("a screenshot is shown, or a pending box — never a broken image", async ({ page }) => {
    const withShot = [...storePages()].find(([, text]) => /\]\(shot:[a-z0-9-]+\)/.test(text));
    test.skip(!withShot, "no page in the store has a screenshot yet");
    const [id, text] = withShot!;
    const shot = /\]\(shot:([a-z0-9-]+)\)/.exec(text)![1];
    await page.goto(`/help/${id}`);
    const figure = page.getByTestId(`help-shot-${shot}`).first();
    await expect(figure).toBeVisible();
    // Settled either way: an image that loaded, or the pending box. Read in one evaluate
    // on the figure — the <img> is replaced while a missing phone version falls back, and
    // a locator on it would wait for an element that is gone.
    await expect
      .poll(() =>
        figure.evaluate((el) => {
          if (el.getAttribute("data-state") === "pending") return "settled";
          const img = el.querySelector("img");
          return img && img.complete && img.naturalWidth > 0 ? "settled" : "loading";
        }),
      )
      .toBe("settled");
  });

  test("an unknown page says so and leads back", async ({ page }) => {
    await page.goto("/help/no-such-page");
    await expect(page.getByTestId("help-not-found")).toBeVisible();
  });

  test("help for this page on the club's page opens the club's guide", async ({ page, request }) => {
    const club = await managedClub(request, TEAM_MANAGER);
    await signIn(page, TEAM_MANAGER);
    await page.goto(`/me/club/${club}`);
    await openUserMenu(page);
    await expect(page.getByTestId("help-for-this-page")).toBeVisible();
    await page.getByTestId("layout-user-menu-help").click();
    await expect(page).toHaveURL(/\/help\/club-members$/);
    await expect(page.getByTestId("help-article-club-members")).toBeVisible();
  });

  test("on a public screen, Help opens the overview — a public page explains itself", async ({ page }) => {
    await page.goto("/legal-notice");
    await openUserMenu(page);
    await expect(page.getByTestId("help-for-this-page")).toHaveCount(0);
    await page.getByTestId("layout-user-menu-help").click();
    await expect(page).toHaveURL(/\/help$/);
  });
});

/** The places a page names (`place:<id>`, `web/src/handbook/places.ts`): a link to the
 *  screen and tab for whoever can use it there, plain words for whoever cannot. */
describeStory("B-18: a click path in the help opens that place, for the reader who can use it", () => {
  const BOARD = "board@asvw.example.com";
  const TREASURER = "treasurer@asvw.example.com";

  /** One ASVW sailor with an account and no organizing relation — a plain member. */
  async function plainSailor(request: Parameters<typeof seededSailors>[0]): Promise<string> {
    const sailors = await seededSailors(request, "asvw.example.com");
    return sailors.find((s) => s.email && bornIn(s) < new Date().getFullYear() - 19)!.email!;
  }

  test("a sailor reading the waiver page opens the Waivers section of their profile", async ({ page, request }) => {
    await signIn(page, await plainSailor(request));
    await page.goto("/help/waiver");
    const place = page.getByTestId("help-place-profile.waivers").first();
    await expect(place).toHaveAttribute("data-reachable", "true");
    await expect(place).toHaveAttribute("href", "/me/profile/waivers");
    await place.click();
    await expect(page).toHaveURL(/\/me\/profile\/waivers$/);
    await expect(page.getByTestId("workspace-content-me-waivers")).toBeVisible();
  });

  for (const who of [BOARD, TREASURER]) {
    test(`${who.split("@")[0]} gets a link to their club's money`, async ({ page, request }) => {
      const club = await clubOf(request, who);
      await signIn(page, who);
      await page.goto("/help/decide-claims");
      const place = page.getByTestId("help-place-club.money").first();
      await expect(place).toHaveAttribute("data-reachable", "true");
      await expect(place).toHaveAttribute("href", `/me/club/${club}/decide-claims`);
      await place.click();
      await expect(page.getByTestId("workspace-content-club-decide-claims")).toBeVisible();
    });
  }

  test("a plain sailor reads the Money path as words, not as a link", async ({ page, request }) => {
    await signIn(page, await plainSailor(request));
    await page.goto("/help/decide-claims");
    const place = page.getByTestId("help-place-club.money").first();
    await expect(place).toHaveAttribute("data-reachable", "false");
    await expect(place.locator("a")).toHaveCount(0);
    await expect(place).not.toHaveAttribute("href", /./);
    // The same sailor is a member, so the Members tab of their club is theirs to open.
    await page.goto("/help/club-members");
    await expect(page.getByTestId("help-place-club.members").first()).toHaveAttribute("data-reachable", "true");
  });
});

/** The club in this person's space — from the contexts, because a treasurer who is not a
 *  member is not in `/api/clubs/mine`. */
async function clubOf(request: Parameters<typeof bearer>[0], email: string): Promise<number> {
  const response = await request.get("/api/me/contexts", { headers: await bearer(request, email) });
  const { contexts } = (await response.json()) as { contexts: { kind: string; id: number }[] };
  return contexts.find((c) => c.kind === "club")!.id;
}
