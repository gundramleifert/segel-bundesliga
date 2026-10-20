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
async function choosePictures(page: import("@playwright/test").Page, count: number, input = "upload-input") {
  await page.getByTestId(input).evaluate(async (input: HTMLInputElement, n) => {
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
    // Value and label read together: other specs add events, and the list re-renders.
    const { value, event } = await option.evaluate((o: HTMLOptionElement) => ({ value: o.value, event: o.text.trim() }));
    await contextSelect.selectOption(value);
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

    // Selected in the text, it shows the library's alt text, and correcting it there
    // corrects the library's entry.
    await content.getByRole("img").first().click();
    const alt = page.getByTestId("admin-post-editor-image-alt-input");
    await expect(alt).toHaveValue(name);
    await alt.fill(`${name} at the start`);
    await page.getByTestId("admin-post-editor-image-alt-save").click();
    await expect(page.getByTestId("admin-post-editor-image-alt-state")).toHaveAttribute("data-state", "saved");
    await expect(content.getByRole("img").first()).toHaveAttribute("alt", `${name} at the start`);

    await page.getByTestId("admin-post-photo-library-button").click();
    const cover = page.getByTestId("admin-post-photo-picker");
    await cover.getByTestId("admin-post-photo-picker-search").fill(name);
    await cover.getByTestId("admin-post-photo-picker-grid").getByRole("button").first().click();
    await expect(page.getByTestId("admin-post-photo-preview")).toHaveAttribute("src", src!);
  });

  test("editorial uploads a batch on the Media tab, without a link, for an event", async ({ page }) => {
    await signIn(page, EDITOR);
    await page.goto("/admin?tab=media");
    await page.getByTestId("admin-media-upload-toggle").click();
    const select = page.getByTestId("admin-media-upload-context");
    const option = select.locator('option[value^="e"]').first();
    await expect(option).toBeAttached();
    // Value and label read together: other specs add events, and the list re-renders.
    const { value, event } = await option.evaluate((o: HTMLOptionElement) => ({ value: o.value, event: o.text.trim() }));
    await select.selectOption(value);
    await page.getByTestId("admin-media-upload-credit-input").fill("E. Editor");
    await choosePictures(page, 2, "admin-media-upload-input");
    await expect(page.getByTestId("admin-media-upload-summary")).toHaveText("2 of 2 pictures received");

    // In the library at once — the list is refreshed as each one arrives.
    const first = page.getByTestId("admin-media-grid").getByRole("listitem").first();
    await expect(first).toContainText("E. Editor");
    await expect(first).toContainText(event);
  });

  test("signed in as editorial, the upload page needs no link", async ({ page }) => {
    await signIn(page, EDITOR);
    await page.goto("/upload");
    await expect(page.getByTestId("upload-signed-in")).toBeVisible();
    await choosePictures(page, 1);
    await expect(page.getByTestId("upload-summary")).toHaveText("1 of 1 picture received");
  });

  test("a link without its key says what to do", async ({ page }) => {
    await page.goto("/upload");
    await expect(page.getByTestId("upload-no-key")).toBeVisible();
  });
});

describeStory("R-2: editorial changes many pictures at once", () => {
  /** Uploads `count` new pictures on the Media tab and answers their tiles' ids, newest first. */
  async function uploadOnMediaTab(page: import("@playwright/test").Page, count: number): Promise<string[]> {
    await page.goto("/admin?tab=media");
    await page.getByTestId("admin-media-upload-toggle").click();
    await choosePictures(page, count, "admin-media-upload-input");
    const plural = count === 1 ? "picture" : "pictures";
    await expect(page.getByTestId("admin-media-upload-summary")).toHaveText(`${count} of ${count} ${plural} received`);
    // An arrived picture is shown by the library's small copy, no longer by the file.
    await expect(page.getByTestId("admin-media-upload-item-0-preview")).toHaveAttribute("src", /^\/api\/media\/[0-9a-f]{32}-480\.webp$/);
    const tiles = page.getByTestId("admin-media-grid").getByRole("listitem");
    await expect(tiles.first().getByTestId(/^admin-media-tile-\d+$/)).toBeVisible();
    const ids: string[] = [];
    for (let i = 0; i < count; i++) {
      const testId = await tiles.nth(i).getByTestId(/^admin-media-tile-\d+$/).getAttribute("data-testid");
      ids.push(testId!.replace("admin-media-tile-", ""));
    }
    return ids;
  }

  test("a picture whose alt text is still its file name is marked and found", async ({ page }) => {
    await signIn(page, EDITOR);
    const [id] = await uploadOnMediaTab(page, 1);
    await expect(page.getByTestId(`admin-media-tile-${id}`).getByTestId("admin-media-tile-alt-missing")).toBeVisible();

    await page.getByTestId("admin-media-alt-missing-filter").check();
    await expect(page.getByTestId(`admin-media-tile-${id}`)).toBeVisible();
    await page.getByTestId(`admin-media-tile-${id}`).click();
    await page.getByTestId("admin-media-alt-input").fill("A J/70 crossing the line");
    await page.getByTestId("admin-media-save-button").click();
    // Described now: no longer among those without alt text.
    await expect(page.getByTestId("admin-media-grid").getByTestId(`admin-media-tile-${id}`)).toHaveCount(0);
  });

  test("two pictures get one credit together, then are deleted together", async ({ page }) => {
    await signIn(page, EDITOR);
    const ids = await uploadOnMediaTab(page, 2);
    await page.getByTestId("admin-media-select-toggle").click();
    for (const id of ids) {
      await page.getByTestId(`admin-media-tile-${id}`).click();
      await expect(page.getByTestId(`admin-media-tile-${id}-check`)).toBeChecked();
    }
    await expect(page.getByTestId("admin-media-bulk-count")).toHaveText("2 pictures selected");

    await page.getByTestId("admin-media-bulk-credit-input").fill("S. Selected");
    await page.getByTestId("admin-media-bulk-credit-apply").click();
    await expect(page.getByTestId("admin-media-bulk-updated")).toHaveText("2 pictures changed.");
    for (const id of ids) await expect(page.getByTestId(`admin-media-tile-${id}`)).toContainText("S. Selected");

    await page.getByTestId("admin-media-bulk-delete").click();
    await page.getByTestId("admin-media-bulk-delete-confirm").click();
    await expect(page.getByTestId("admin-media-bulk-deleted")).toContainText("2 pictures deleted.");
    for (const id of ids) await expect(page.getByTestId(`admin-media-tile-${id}`)).toHaveCount(0);
  });
});
