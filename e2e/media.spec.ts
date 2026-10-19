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
  test("editorial makes a link, a photographer sends pictures, they arrive with the credit", async ({ page, browser }, testInfo) => {
    const label = `Photos ${testInfo.project.name} ${Date.now()}`;
    await signIn(page, EDITOR);
    await page.goto("/admin?tab=media");
    await page.getByTestId("admin-import-key-label-input").fill(label);
    await page.getByTestId("admin-import-key-create-button").click();
    const link = await page.getByTestId("admin-import-key-link").inputValue();
    expect(link).toMatch(/\/upload#key=sbl_imp_/);

    // The photographer: another browser, nobody signed in.
    const photographer = await browser.newContext({ locale: "en-US" });
    const phone = await photographer.newPage();
    await phone.goto(link);
    await expect(phone.getByTestId("upload-for")).toContainText(label);
    await phone.getByTestId("upload-credit-input").fill("C. Photographer");
    await choosePictures(phone, 2);
    await expect(phone.getByTestId("upload-summary")).toHaveText("2 of 2 pictures received");

    // Editorial: in the library, with the credit.
    await page.reload();
    const first = page.getByTestId("admin-media-grid").getByRole("listitem").first();
    await expect(first).toContainText("C. Photographer");
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

  test("a link without its key says what to do", async ({ page }) => {
    await page.goto("/upload");
    await expect(page.getByTestId("upload-no-key")).toBeVisible();
  });
});
