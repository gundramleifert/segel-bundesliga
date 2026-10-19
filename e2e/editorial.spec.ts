import { describeStory, expect, test } from "./fixtures";
import { signIn } from "./session";

/** Story R-1: editorial writes news and press releases on the site.
 *
 * `api/tests/stories/test_posts.py` proves the rules — drafts invisible, the slug kept,
 * the text cleaned, who may write. What only a browser can prove is the walk: the *News*
 * tab, the editor's toolbar making formatted text, publishing, and the article on its
 * league's page showing exactly that formatting.
 */

const EDITOR = "redaktion@sbl.example.com";
const MANAGER = "teams@nrv.example.com";

describeStory("R-1: editorial writes news and press releases", () => {
  test("write an article with the editor, publish it, read it on the league's page", async ({ page }, testInfo) => {
    // Each browser project writes its own article: the two can share one stack.
    const title = `Harbour day ${testInfo.project.name} ${Date.now()}`;
    await signIn(page, EDITOR);
    await page.goto("/admin?tab=news");
    await expect(page.getByTestId("admin-panel-news")).toBeVisible();
    await page.getByTestId("admin-posts-new-button").click();

    await page.getByTestId("admin-post-title-input").fill(title);
    await page.getByTestId("admin-post-league-select").selectOption({ label: "1. Liga" });
    await page.getByTestId("admin-post-teaser-input").fill("Open doors at the club house.");

    const content = page.getByTestId("admin-post-editor-content");
    await content.click();
    await page.getByTestId("admin-post-editor-style").selectOption("h2");
    await page.keyboard.type("Programme");
    await page.keyboard.press("Enter");
    await page.getByTestId("admin-post-editor-bold").click();
    await page.keyboard.type("Ten o'clock");
    await page.getByTestId("admin-post-editor-bold").click();
    await page.keyboard.type(" — the boats are open to visitors.");
    await expect(content.locator("h2")).toHaveText("Programme");
    await expect(content.locator("strong")).toHaveText("Ten o'clock");

    await page.getByTestId("admin-post-save-button").click();
    // The first save makes the post its own page — as a draft.
    await expect(page).toHaveURL(/\/admin\/news\/\d+$/);
    await expect(page.getByTestId("admin-post-publish-button")).toBeVisible();
    await expect(page.getByTestId("admin-post-view-link")).toHaveCount(0);

    await page.getByTestId("admin-post-publish-button").click();
    await expect(page.getByTestId("admin-post-save-success")).toBeVisible();
    await page.getByTestId("admin-post-view-link").click();

    await expect(page).toHaveURL(/\/1-liga\/news\//);
    await expect(page.getByTestId("site-article-lead")).toHaveText("Open doors at the club house.");
    const body = page.getByTestId("site-article-body");
    await expect(body.locator("h2")).toHaveText("Programme");
    await expect(body.locator("strong")).toHaveText("Ten o'clock");
  });

  test("the press centre reads a release's text when it is opened", async ({ page }) => {
    // The list carries dates and titles only; each text comes from the release's own address.
    await page.goto("/1-liga/press");
    const releases = page.getByTestId(/^site-press-release-/);
    await expect(releases.first()).toBeVisible();
    expect(await releases.count()).toBeGreaterThan(1);
    const slugOf = async (i: number) =>
      ((await releases.nth(i).getAttribute("data-testid")) ?? "").replace("site-press-release-", "");

    // The newest is open from the start, with its text.
    await expect(page.getByTestId(`site-press-text-${await slugOf(0)}`)).not.toBeEmpty();
    const second = await slugOf(1);
    await expect(page.getByTestId(`site-press-text-${second}`)).toHaveCount(0);
    await releases.nth(1).click(); // closed, it is only its summary line
    await expect(page.getByTestId(`site-press-text-${second}`)).not.toBeEmpty();
  });

  test("a club's team manager has no News tab", async ({ page }) => {
    await signIn(page, MANAGER);
    await page.goto("/admin");
    await expect(page.getByTestId("admin-news-tab")).toHaveCount(0);
  });
});
