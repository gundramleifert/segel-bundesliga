import { describeStory, expect, test } from "./fixtures";
import { openSection } from "./layout";
import { bearer, signIn } from "./session";

/** Story R-1: editorial writes news and press releases on the site.
 *
 * `api/tests/stories/test_posts.py` proves the rules — drafts invisible, the slug kept,
 * the text cleaned, who may write. What only a browser can prove is the walk: the *News*
 * section of the league office, the editor's toolbar making formatted text, publishing,
 * and the article on its league's page showing exactly that formatting.
 */

const EDITOR = "redaktion@sbl.example.com";
const MANAGER = "teams@asvw.example.com";

describeStory("R-1: editorial writes news and press releases", () => {
  test("write an article with the editor, publish it, read it on the league's page", async ({ page }, testInfo) => {
    // Each browser project writes its own article: the two can share one stack.
    const title = `Harbour day ${testInfo.project.name} ${Date.now()}`;
    await signIn(page, EDITOR);
    await page.goto("/office/news");
    await expect(page.getByTestId("workspace-content-office-news")).toBeVisible();
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
    await expect(page).toHaveURL(/\/office\/news\/\d+$/);
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

  test("a picture is pasted into the text or dropped onto the cover, a link is Ctrl+K", async ({ page }) => {
    await signIn(page, EDITOR);
    await page.goto("/office/news/new");
    await page.getByTestId("admin-post-title-input").fill("Pictures and links");
    const content = page.getByTestId("admin-post-editor-content");
    await content.click();
    await page.keyboard.type("Read more at ");

    // Pasted: uploaded, and in the text where the cursor was.
    await content.evaluate(async (el) => {
      const data = new DataTransfer();
      data.items.add(await picture("pasted.png"));
      el.dispatchEvent(new ClipboardEvent("paste", { clipboardData: data, bubbles: true, cancelable: true }));
      async function picture(name: string) {
        const canvas = Object.assign(document.createElement("canvas"), { width: 40, height: 30 });
        canvas.getContext("2d")!.fillRect(0, 0, 40, 30);
        const blob = await new Promise<Blob>((done) => canvas.toBlob((b) => done(b!), "image/png"));
        return new File([blob], name, { type: "image/png" });
      }
    });
    await expect(content.getByRole("img")).toHaveAttribute("src", /^\/api\/media\//);
    await expect(content.getByRole("img")).toHaveAttribute("alt", "pasted");

    // Dropped onto the cover's preview: it becomes the post's picture.
    await page.getByTestId("admin-post-photo-dropzone").evaluate(async (el) => {
      const canvas = Object.assign(document.createElement("canvas"), { width: 60, height: 40 });
      const blob = await new Promise<Blob>((done) => canvas.toBlob((b) => done(b!), "image/png"));
      const data = new DataTransfer();
      data.items.add(new File([blob], "cover.png", { type: "image/png" }));
      el.dispatchEvent(new DragEvent("drop", { dataTransfer: data, bubbles: true, cancelable: true }));
    });
    await expect(page.getByTestId("admin-post-photo-preview")).toHaveAttribute("src", /^\/api\/media\//);

    // Ctrl+K with nothing selected: the address and a text of its own, linked.
    await content.getByText("Read more at").click();
    await page.keyboard.press("End");
    await page.keyboard.press("ControlOrMeta+k");
    await page.getByTestId("admin-post-editor-link-input").fill("deutsche-segelliga.de");
    await page.getByTestId("admin-post-editor-link-text-input").fill("the association");
    await page.keyboard.press("Enter");
    const link = content.getByRole("link", { name: "the association" });
    await expect(link).toHaveAttribute("href", "https://deutsche-segelliga.de");

    // The cursor in the link says where it leads, and removes it.
    await link.click();
    await expect(page.getByTestId("admin-post-editor-link-info-href")).toHaveText("https://deutsche-segelliga.de");
    await page.getByTestId("admin-post-editor-link-remove").click();
    await expect(content.getByRole("link")).toHaveCount(0);
    await expect(content).toContainText("the association");
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

  test("the title is set in the form: a text that starts with it again cannot be saved", async ({ page }) => {
    await signIn(page, EDITOR);
    await page.goto("/office/news/new");
    await page.getByTestId("admin-post-title-input").fill("Harbour day");
    // The editor has a paragraph and one heading — nothing for a title.
    const style = page.getByTestId("admin-post-editor-style");
    await expect(style.locator("option")).toHaveCount(2);

    const content = page.getByTestId("admin-post-editor-content");
    await content.click();
    await style.selectOption("h2");
    await page.keyboard.type("Harbour day");
    await expect(page.getByTestId("admin-post-title-in-text")).toBeVisible();
    await expect(page.getByTestId("admin-post-save-button")).toBeDisabled();

    await page.keyboard.type(": the programme");
    await expect(page.getByTestId("admin-post-title-in-text")).toHaveCount(0);
    await expect(page.getByTestId("admin-post-save-button")).toBeEnabled();
  });

  test("leaving a post with unsaved changes asks first", async ({ page }) => {
    await signIn(page, EDITOR);
    await page.goto("/office/news/new");
    const back = page.getByTestId("admin-post-back-link");

    // Nothing written yet: the link just goes.
    await back.click();
    await expect(page).toHaveURL(/\/office\/news$/);

    await page.goto("/office/news/new");
    await page.getByTestId("admin-post-title-input").fill("Harbour day");
    const asked: string[] = [];
    page.once("dialog", (dialog) => {
      asked.push(dialog.type());
      void dialog.dismiss();
    });
    await back.click();
    expect(asked).toEqual(["confirm"]);
    await expect(page).toHaveURL(/\/office\/news\/new/);
    await expect(page.getByTestId("admin-post-title-input")).toHaveValue("Harbour day");

    page.once("dialog", (dialog) => void dialog.accept());
    await back.click();
    await expect(page).toHaveURL(/\/office\/news$/);
  });

  test("a draft is previewed as readers will see it, without saving", async ({ page }) => {
    await signIn(page, EDITOR);
    await page.goto("/office/news/new");
    await page.getByTestId("admin-post-title-input").fill("A preview of Sunday");
    await page.getByTestId("admin-post-editor-content").click();
    await page.keyboard.type("Six wins and no fouls.");
    // On a draft, Publish is the primary action and Save draft the quiet one.
    await expect(page.getByTestId("admin-post-publish-button")).toBeVisible();

    await page.getByTestId("admin-post-preview-button").click();
    const article = page.getByTestId("admin-post-preview-article");
    await expect(article).toContainText("A preview of Sunday");
    await expect(article).toContainText("Six wins and no fouls.");
    await page.getByTestId("admin-post-preview-back").first().click();
    await expect(page.getByTestId("admin-post-title-input")).toHaveValue("A preview of Sunday");
    await expect(page.getByTestId("admin-post-editor-content")).toContainText("Six wins and no fouls.");
  });

  test("unsaved changes are kept on the device and offered back", async ({ page }) => {
    await signIn(page, EDITOR);
    await page.goto("/office/news/new");
    await page.getByTestId("admin-post-title-input").fill("Kept on this phone");
    await page.waitForTimeout(700); // kept after a short pause in typing
    page.on("dialog", (dialog) => void dialog.accept());
    await page.reload();

    await expect(page.getByTestId("admin-post-kept")).toBeVisible();
    await expect(page.getByTestId("admin-post-title-input")).toHaveValue("");
    await page.getByTestId("admin-post-kept-restore").click();
    await expect(page.getByTestId("admin-post-title-input")).toHaveValue("Kept on this phone");

    // Discarded, it is gone for good.
    await page.getByTestId("admin-post-title-input").fill("Kept, then discarded");
    await page.waitForTimeout(700);
    await page.reload();
    await page.getByTestId("admin-post-kept-discard").click();
    await expect(page.getByTestId("admin-post-kept")).toHaveCount(0);
    await page.reload();
    await expect(page.getByTestId("admin-post-kept")).toHaveCount(0);
  });

  test("a picture pasted from another site is never linked", async ({ page }) => {
    await signIn(page, EDITOR);
    await page.goto("/office/news/new");
    const content = page.getByTestId("admin-post-editor-content");
    await content.click();
    // An address that cannot be fetched: the picture is taken out again, with the reason.
    await content.evaluate((element) => {
      const data = new DataTransfer();
      data.setData("text/html", '<p>From the web</p><img src="https://pictures.invalid/boat.jpg" alt="">');
      element.dispatchEvent(new ClipboardEvent("paste", { clipboardData: data, bubbles: true, cancelable: true }));
    });
    await expect(content).toContainText("From the web");
    await expect(page.getByTestId("admin-post-editor-adopt-error")).toBeVisible();
    await expect(content.getByRole("img")).toHaveCount(0);
  });

  test("the list filters by league and state", async ({ page }) => {
    await signIn(page, EDITOR);
    await page.goto("/office/news");
    await page.getByTestId("admin-posts-state-filter").selectOption("published");
    await page.getByTestId("admin-posts-league-filter").selectOption("2-liga");
    const list = page.getByTestId("admin-posts-section");
    await expect(list.getByRole("link", { name: /Promotion race/ })).toHaveCount(1);
    await expect(list.getByRole("link", { name: /ASVW takes the lead/ })).toHaveCount(0);
    await expect(page).toHaveURL(/state=published/);
  });

  test("a club's team manager has no league office, and no post page", async ({ page }) => {
    await signIn(page, MANAGER);
    await page.goto("/office/news");
    await expect(page.getByTestId("office-not-found")).toBeVisible();
    await page.goto("/office/news/new");
    await expect(page.getByTestId("admin-access-error")).toBeVisible();
  });
});

describeStory("R-1/Z-2: a series' editor writes about that series and organizes nothing", () => {
  test("Paula Presse has no office, writes in My space, and her post lands in the series' league", async ({ page }, testInfo) => {
    // The seed's editor of the 2. Liga 2026 (`app/seed_users.py`). Holding nothing on the
    // site, she has no league office (Story A-11, #32); her post page is in My space, and
    // the office's address passes her on to it.
    await signIn(page, "presse@sbl.example.com");
    await page.goto("/office");
    await expect(page.getByTestId("office-not-found")).toBeVisible();

    const title = `Matchday report ${testInfo.project.name} ${Date.now()}`;
    await page.goto("/office/news/new");
    await expect(page).toHaveURL(/\/me\/news\/new$/);
    await page.getByTestId("admin-post-title-input").fill(title);
    // The regattas offered are hers alone: the series, then its acts.
    const regatta = page.getByTestId("admin-post-regatta-select");
    await expect(regatta.locator("optgroup")).toHaveCount(1);
    await regatta.selectOption({ index: 1 });
    await page.getByTestId("admin-post-editor-content").click();
    await page.keyboard.type("Three days of racing.");
    await page.getByTestId("admin-post-save-button").click();
    await expect(page).toHaveURL(/\/me\/news\/\d+$/);
    await page.getByTestId("admin-post-publish-button").click();
    await expect(page.getByTestId("admin-post-save-success")).toBeVisible();
    await page.getByTestId("admin-post-view-link").click();
    await expect(page).toHaveURL(/\/2-liga\/news\//);
  });
});

describeStory("R-1/R-2/Z-10: each editor works where they write", () => {
  test("Paula Presse writes in her series' News & pictures and finds it again under Me › News", async ({
    page,
    request,
  }, testInfo) => {
    const PRESSE = "presse@sbl.example.com";
    const mine = (await (
      await request.get("/api/me/contexts", { headers: await bearer(request, PRESSE) })
    ).json()) as { contexts: { kind: string; id: number; relations: string[] }[] };
    const series = mine.contexts.find((c) => c.kind === "series" && c.relations.includes("editor"))!;

    await signIn(page, PRESSE);
    await page.goto(`/me/series/${series.id}`);
    await openSection(page, "series", "news");
    await expect(page.getByTestId(`me-series-news-posts`)).toBeVisible();
    // The library is the series' — no regatta to choose, no import keys.
    await expect(page.getByTestId("admin-media-section")).toBeVisible();
    await expect(page.getByTestId("admin-media-context-filter")).toHaveCount(0);

    // A new post starts about this series.
    await page.getByTestId("admin-posts-new-button").click();
    await expect(page).toHaveURL(new RegExp(`/me/news/new\\?series=${series.id}$`));
    const title = `Series note ${testInfo.project.name} ${Date.now()}`;
    await page.getByTestId("admin-post-title-input").fill(title);
    await page.getByTestId("admin-post-editor-content").click();
    await page.keyboard.type("A note.");
    await page.getByTestId("admin-post-save-button").click();
    await expect(page).toHaveURL(/\/me\/news\/\d+$/);
    const id = Number(page.url().split("/").pop());

    // Listed in the series' section, and over all her regattas under Me › News.
    await page.goto(`/me/series/${series.id}/news`);
    await expect(page.getByTestId(`admin-posts-link-${id}`)).toBeVisible();
    await page.goto("/me/profile/news");
    await expect(page.getByTestId(`admin-posts-link-${id}`)).toHaveAttribute("href", `/me/news/${id}`);
  });
});
