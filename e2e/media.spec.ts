import { describeStory, expect, test } from "./fixtures";
import { signIn } from "./session";

/** Story R-2: the picture library, fed by an import API.
 *
 * `api/tests/stories/test_media.py` proves the rules — one entry per picture, keys
 * hashed and refused once revoked, the delete guard. What only a browser can prove is the
 * walk: editorial makes an upload link, a photographer with no account sends pictures
 * from it, and they arrive in the *Media* tab with the photographer's credit.
 */

const EDITOR = "redaktion@sbl.example.com";

/** Picks pictures no run has sent before — the library would answer those as known. */
async function choosePictures(page: import("@playwright/test").Page, count: number) {
  await page.getByTestId("upload-input").evaluate(async (input: HTMLInputElement, n) => {
    const data = new DataTransfer();
    for (let i = 0; i < n; i++) {
      const canvas = Object.assign(document.createElement("canvas"), { width: 80, height: 60 });
      const context = canvas.getContext("2d")!;
      context.fillStyle = `hsl(${Math.random() * 360} 70% 50%)`;
      context.fillRect(0, 0, 80, 60);
      context.fillText(String(Date.now() + i), 4, 30);
      const blob = await new Promise<Blob>((done) => canvas.toBlob((b) => done(b!), "image/png"));
      data.items.add(new File([blob], `regatta-${i + 1}.png`, { type: "image/png" }));
    }
    input.files = data.files;
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }, count);
}

describeStory("R-2: a picture library fed by upload links", () => {
  test("editorial makes a link for an event, a photographer sends pictures, they arrive there", async ({ page, browser }, testInfo) => {
    const label = `Photos ${testInfo.project.name} ${Date.now()}`;
    await signIn(page, EDITOR);
    await page.goto("/admin?tab=media");
    await page.getByTestId("admin-import-key-label-input").fill(label);
    // The first event on offer (values `e<id>`; a series is `s<id>`): its pictures.
    const contextSelect = page.getByTestId("admin-import-key-context-select");
    await expect(contextSelect.locator('option[value^="e"]').first()).toBeAttached();
    const option = contextSelect.locator('option[value^="e"]').first();
    await contextSelect.selectOption((await option.getAttribute("value"))!);
    const event = (await option.textContent())!.trim();
    await page.getByTestId("admin-import-key-create-button").click();
    const link = await page.getByTestId("admin-import-key-link").inputValue();
    expect(link).toMatch(/\/upload#key=sbl_imp_/);

    // The photographer: another browser, nobody signed in.
    const photographer = await browser.newContext({ locale: "en-US" });
    const phone = await photographer.newPage();
    await phone.goto(link);
    await expect(phone.getByTestId("upload-for")).toContainText(label);
    await expect(phone.getByTestId("upload-for")).toContainText(event);
    await phone.getByTestId("upload-credit-input").fill("C. Photographer");
    await choosePictures(phone, 2);
    await expect(phone.getByTestId("upload-summary")).toHaveText("2 of 2 pictures received");

    // Editorial: in the library, with the credit, and found by the event.
    await page.reload();
    await page.getByTestId("admin-media-context-filter").selectOption({ label: event });
    const first = page.getByTestId("admin-media-grid").getByRole("listitem").first();
    await expect(first).toContainText("C. Photographer");
    await expect(first).toContainText(event);
    await first.getByRole("button").click();
    await expect(page.getByTestId("admin-media-credit-input")).toHaveValue("C. Photographer");
    await expect(page.getByTestId("admin-media-used-in")).toHaveText("Not used in any post.");

    // Revoked, the link stops working — and says so.
    const row = page.getByTestId("admin-import-keys-list").getByRole("listitem").filter({ hasText: label });
    await row.getByTestId(/-revoke$/).click();
    await row.getByTestId(/-revoke-confirm$/).click();
    await expect(row.getByTestId(/-state$/)).toHaveText("revoked");
    await phone.reload();
    await expect(phone.getByTestId("upload-key-error")).toContainText("not valid");
    await photographer.close();
  });

  test("a post takes its pictures from the library — in the text and as its own picture", async ({ page }, testInfo) => {
    const name = `harbour ${testInfo.project.name} ${Date.now()}`;
    await signIn(page, EDITOR);
    // A picture of its own in the library, uploaded through the Media path of the picker.
    await page.goto("/admin/news/new");
    await page.getByTestId("admin-post-title-input").fill("Pictures from the library");
    await page.getByTestId("admin-post-editor-content").click();
    await page.getByTestId("admin-post-editor-image").click();
    const picker = page.getByTestId("admin-post-editor-picker");
    await expect(picker).toBeVisible();
    await picker.getByTestId("admin-post-editor-picker-input").evaluate(async (input: HTMLInputElement, file) => {
      const canvas = Object.assign(document.createElement("canvas"), { width: 90, height: 60 });
      const context = canvas.getContext("2d")!;
      context.fillStyle = `hsl(${Math.random() * 360} 60% 40%)`;
      context.fillRect(0, 0, 90, 60);
      context.fillText(String(Date.now()), 4, 30);
      const blob = await new Promise<Blob>((done) => canvas.toBlob((b) => done(b!), "image/png"));
      const data = new DataTransfer();
      // A PNG named .jpg: the content decides, not the name.
      data.items.add(new File([blob], `${file.replaceAll(" ", "-")}.jpg`, { type: "image/jpeg" }));
      input.files = data.files;
      input.dispatchEvent(new Event("change", { bubbles: true }));
    }, name);
    const content = page.getByTestId("admin-post-editor-content");
    await expect(content.getByRole("img")).toHaveAttribute("src", /^\/api\/media\//);
    await expect(content.getByRole("img")).toHaveAttribute("alt", name);
    await expect(picker).toHaveCount(0);
    const src = await content.getByRole("img").getAttribute("src");

    // Picked again, from the library's grid: once more into the text, and as the cover.
    await page.getByTestId("admin-post-editor-image").click();
    await picker.getByTestId("admin-post-editor-picker-search").fill(name);
    await picker.getByTestId("admin-post-editor-picker-grid").getByRole("button").first().click();
    await expect(content.getByRole("img")).toHaveCount(2);

    await page.getByTestId("admin-post-photo-library-button").click();
    const cover = page.getByTestId("admin-post-photo-picker");
    await cover.getByTestId("admin-post-photo-picker-search").fill(name);
    await cover.getByTestId("admin-post-photo-picker-grid").getByRole("button").first().click();
    await expect(page.getByTestId("admin-post-photo-preview")).toHaveAttribute("src", src!);
  });

  test("a link without its key says what to do", async ({ page }) => {
    await page.goto("/upload");
    await expect(page.getByTestId("upload-no-key")).toBeVisible();
  });
});
