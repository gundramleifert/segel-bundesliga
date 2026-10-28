import { describeStory, expect, test } from "./fixtures";
import { bearer } from "./session";

/** Story R-3: a league's media page shows the library — and Story R-1's paged news.
 *
 * `api/tests/stories/test_media_public.py` proves which pictures a league
 * shows. What only a browser can prove is the page: a picture delivered for an act is on
 * its league's media page under the act's name, and a tap shows it full screen, with the
 * keyboard to go on and to close.
 */

const EDITOR = "redaktion@sbl.example.com";
const ACT = 3; // demo-1-2026-act-3 (published on test stacks)

describeStory("R-3: the league's media page shows the library", () => {
  test("a picture delivered for an act is on the league's media page, full screen on a tap", async ({ page }, testInfo) => {
    const headers = await bearer(page.request, EDITOR);
    const alt = `Media page ${testInfo.project.name} ${Date.now()}`;
    await page.goto("/demo/media");
    // Two pictures, made in the browser, uploaded as editorial — the second one first, so
    // the newest is the first tile.
    const ids = await page.evaluate(
      async ({ alt, act, authorization }) => {
        const made: number[] = [];
        for (const n of [2, 1]) {
          const canvas = Object.assign(document.createElement("canvas"), { width: 900, height: 600 });
          const context = canvas.getContext("2d")!;
          context.fillStyle = `hsl(${Math.random() * 360} 60% 45%)`;
          context.fillRect(0, 0, 900, 600);
          context.fillText(`${alt} ${n}`, 20, 300);
          const blob = await new Promise<Blob>((done) => canvas.toBlob((b) => done(b!), "image/jpeg"));
          const form = new FormData();
          form.append("file", new File([blob], `regatta-${n}.jpg`, { type: "image/jpeg" }));
          form.append("alt", `${alt} ${n}`);
          form.append("credit", "E2E Photographer");
          form.append("event_id", String(act));
          const answer = await fetch("/api/admin/media", { method: "POST", body: form, headers: { Authorization: authorization } });
          made.push(((await answer.json()) as { id: number }).id);
        }
        return made;
      },
      { alt, act: ACT, authorization: headers.Authorization },
    );

    await page.reload();
    const tile = page.getByTestId(`site-media-photo-${ids[1]}`);
    await expect(tile).toBeVisible();
    await expect(tile).toContainText("E2E Photographer");
    await tile.click();

    const lightbox = page.getByTestId("site-lightbox");
    await expect(lightbox).toBeVisible();
    await expect(page.getByTestId("site-lightbox-caption")).toContainText(`${alt} 1`);
    await expect(page.getByTestId("site-lightbox-close-button")).toBeFocused();
    await page.keyboard.press("ArrowRight");
    await expect(page.getByTestId("site-lightbox-caption")).not.toContainText(`${alt} 1`);
    await page.keyboard.press("ArrowLeft");
    await expect(page.getByTestId("site-lightbox-caption")).toContainText(`${alt} 1`);
    await page.keyboard.press("Escape");
    await expect(lightbox).toHaveCount(0);
  });

  test("the news page shows older news on asking", async ({ page }, testInfo) => {
    const headers = await bearer(page.request, EDITOR);
    const stamp = `${testInfo.project.name}-${Date.now()}`;
    // A page's worth of old news: the oldest is then past the first page whatever else
    // the league has.
    let oldest = "";
    for (let day = 12; day >= 1; day--) {
      const made = await page.request.post("/api/admin/posts", {
        headers,
        data: { title: `Older news ${stamp} ${day}`, published_on: `2001-01-${String(day).padStart(2, "0")}`, published: true },
      });
      expect(made.ok()).toBeTruthy();
      oldest = ((await made.json()) as { slug: string }).slug;
    }

    await page.goto("/1-liga/news");
    await expect(page.getByTestId(`site-news-${oldest}`)).toHaveCount(0);
    // As many pages as it takes: other specs write news too.
    const more = page.getByTestId("site-news-more-button");
    const last = page.getByTestId(`site-news-${oldest}`);
    await expect(more).toBeVisible();
    // Until it shows or there is nothing more — the button goes once the last page is in.
    for (let i = 0; i < 10 && !(await last.isVisible()) && (await more.isVisible()); i++) {
      await more.click({ timeout: 5_000 }).catch(() => undefined);
      await expect(more).toBeEnabled({ timeout: 5_000 }).catch(() => undefined);
    }
    await expect(last).toBeVisible();
  });
});

describeStory("R-1: a report ends with its regatta's photos", () => {
  test("a post about an act shows the act's pictures, each opening full screen", async ({ page }, testInfo) => {
    const headers = await bearer(page.request, EDITOR);
    const alt = `Report gallery ${testInfo.project.name} ${Date.now()}`;
    await page.goto("/1-liga/news");
    const id = await page.evaluate(
      async ({ alt, act, authorization }) => {
        const canvas = Object.assign(document.createElement("canvas"), { width: 900, height: 600 });
        const context = canvas.getContext("2d")!;
        context.fillStyle = `hsl(${Math.random() * 360} 60% 45%)`;
        context.fillRect(0, 0, 900, 600);
        context.fillText(alt, 20, 300);
        const blob = await new Promise<Blob>((done) => canvas.toBlob((b) => done(b!), "image/jpeg"));
        const form = new FormData();
        form.append("file", new File([blob], "report.jpg", { type: "image/jpeg" }));
        form.append("alt", alt);
        form.append("event_id", String(act));
        const answer = await fetch("/api/admin/media", { method: "POST", body: form, headers: { Authorization: authorization } });
        return ((await answer.json()) as { id: number }).id;
      },
      { alt, act: ACT, authorization: headers.Authorization },
    );
    const league = (await (await page.request.get("/api/leagues/1-liga")).json()) as { league: { id: number } };
    const post = await page.request.post("/api/admin/posts", {
      headers,
      data: { title: `Act ${ACT} report ${Date.now()}`, league_id: league.league.id, event_id: ACT, published: true },
    });
    expect(post.ok()).toBeTruthy();
    const { slug } = (await post.json()) as { slug: string };

    await page.goto(`/1-liga/news/${slug}`);
    const gallery = page.getByTestId("site-article-gallery");
    await expect(gallery).toBeVisible();
    await gallery.getByTestId(`site-media-photo-${id}`).click();
    await expect(page.getByTestId("site-lightbox-caption")).toContainText(alt);
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("site-lightbox")).toHaveCount(0);
  });
});
