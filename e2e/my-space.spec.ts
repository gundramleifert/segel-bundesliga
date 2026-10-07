import type { Page } from "@playwright/test";

import { describeStory, expect, test } from "./fixtures";
import { bearer, signIn } from "./session";

/** Story S-5: a person's licences, uploaded by dropping the file onto the page.
 *
 * `api/tests/stories/test_personal_space.py` proves the rules — the labels, the types,
 * who sees what. What only a browser can prove is the dropzone: a file dragged onto it is
 * taken like one chosen in the dialog, a file of the wrong type is refused on the spot,
 * and the jury licence is a label of its own.
 */

const ADMIN = "admin@sbl.example.com";
// A club no other spec touches; each browser project takes its own person.
const CLUB_DOMAIN = "dtyc.example.com";
const PNG =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==";

/** Drags a file onto an element and drops it — what a person does with a file manager. */
async function dropFile(page: Page, testId: string, name: string, type: string, base64: string) {
  const dataTransfer = await page.evaluateHandle(
    ({ name, type, base64 }) => {
      const transfer = new DataTransfer();
      const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
      transfer.items.add(new File([bytes], name, { type }));
      return transfer;
    },
    { name, type, base64 },
  );
  const zone = page.getByTestId(testId);
  await zone.dispatchEvent("dragover", { dataTransfer });
  await expect(zone).toHaveAttribute("data-over", "true");
  await zone.dispatchEvent("drop", { dataTransfer });
}

describeStory("S-5: as a sailor I drop my licences onto my space", () => {
  test("a jury licence, dropped; a text file, refused", async ({ page, request }, testInfo) => {
    const headers = await bearer(request, ADMIN);
    const listed = await request.get(`/api/auth/users?q=${CLUB_DOMAIN}&limit=2`, { headers });
    expect(listed.ok(), await listed.text()).toBeTruthy();
    const nth = testInfo.project.name === "mobile" ? 1 : 0;
    const email = ((await listed.json()) as { items: { email: string }[] }).items[nth]!.email;
    const fileName = `jury-${testInfo.project.name}-${Date.now()}.png`;

    await signIn(page, email);
    await page.goto("/me");
    await expect(page.getByTestId("my-space-document-upload")).toBeVisible();

    // The wrong type is refused where it was dropped, before anything is sent.
    await dropFile(page, "my-space-document-file-zone", "notes.txt", "text/plain", btoa("hello"));
    await expect(page.getByTestId("my-space-document-file-refused")).toContainText("notes.txt");
    await expect(page.getByTestId("my-space-document-submit")).toBeDisabled();

    await page.getByTestId("my-space-document-kind").selectOption("jury_licence");
    await dropFile(page, "my-space-document-file-zone", fileName, "image/png", PNG);
    await expect(page.getByTestId("my-space-document-file-selected")).toHaveText(fileName);
    await expect(page.getByTestId("my-space-document-file-refused")).toHaveCount(0);
    await page.getByTestId("my-space-document-submit").click();

    const row = page.getByTestId("my-space-documents-list").locator("li", { hasText: fileName });
    await expect(row).toContainText("Jury licence");
    // The zone is empty again for the next document.
    await expect(page.getByTestId("my-space-document-file-selected")).toHaveCount(0);
  });
});
