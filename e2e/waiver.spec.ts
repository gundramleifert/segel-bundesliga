import type { Page } from "@playwright/test";

import { describeStory, expect, test } from "./fixtures";
import { bearer, newSquad, signIn, type SeededSailor } from "./session";

/** Stories S-1 and VA-5: the liability waiver, from the sailor's own account.
 *
 * `api/tests/stories/test_waiver.py` proves the rules. What only a browser can prove is
 * the two paths a real person walks: an adult reads the wording on the page, ticks the
 * box and is cleared; a minor downloads the form (a real PDF answer to a token-bearing
 * fetch), uploads the signed scan and is cleared; and the organizer's panel shows both.
 *
 * Serial, on one worker: the three tests share the sailors they pick, and the organizer's
 * test looks at what the first two did.
 */

test.describe.configure({ mode: "serial" });

const ADMIN = "admin@sbl.example.com";
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
  "base64",
);

async function openAccount(page: Page): Promise<void> {
  // My waivers are a tab of my own page in my space (Story S-7).
  await page.goto("/me/profile/waivers");
  await expect(page.getByTestId("account-waivers-card")).toBeVisible();
  await expect(page.getByTestId("account-waivers-list")).toBeVisible();
}

let adult: SeededSailor;
let junior: SeededSailor;
let seriesId: number;

test.beforeAll(async ({ request }, testInfo) => {
  // An adult and a junior who have signed nothing, and a third who never will: the
  // organizer's list shows them as missing.
  const squad = await newSquad(request, `Waiver e2e ${testInfo.project.name}`, ["1990-05-01", "2012-05-01", "1992-05-01"]);
  seriesId = squad.series;
  [adult, junior] = squad.people as [SeededSailor, SeededSailor];
});

describeStory("S-1: as a sailor I submit the liability waiver from my account", () => {
  test("an adult reads the wording and confirms it online", async ({ page }) => {
    await signIn(page, adult.email!);
    await openAccount(page);

    const row = page.locator('[data-testid^="account-waiver-series-"]').first();
    await expect(row).toHaveAttribute("data-status", "missing");
    const id = (await row.getAttribute("data-testid"))!.replace("account-waiver-", "");

    // The text is on the page before anything can be ticked.
    await page.getByTestId(`account-waiver-read-${id}`).click();
    await expect(page.getByTestId(`account-waiver-text-${id}`)).toBeVisible();
    await expect(page.getByTestId(`account-waiver-confirm-${id}`)).toBeDisabled();
    await page.getByTestId(`account-waiver-agree-${id}`).check();
    await page.getByTestId(`account-waiver-confirm-${id}`).click();

    await expect(page.getByTestId(`account-waiver-message-${id}-success`)).toBeVisible();
    await expect(row).toHaveAttribute("data-status", "cleared");
    await expect(page.getByTestId(`account-waiver-status-${id}`)).toContainText("Cleared");
  });

  test("a minor downloads the form and uploads the guardian's signed scan", async ({ page }) => {
    await signIn(page, junior.email!);
    await openAccount(page);

    const row = page.locator('[data-testid^="account-waiver-series-"]').first();
    await expect(row).toHaveAttribute("data-status", "missing");
    const id = (await row.getAttribute("data-testid"))!.replace("account-waiver-", "");

    // No online path for a minor — the read button is absent, the guardian's tools are there.
    await expect(page.getByTestId(`account-waiver-read-${id}`)).toHaveCount(0);

    // The form: a PDF, fetched with the token, saved by the browser.
    const [formResponse, download] = await Promise.all([
      page.waitForResponse((r) => r.url().includes("/api/waiver/form")),
      page.waitForEvent("download"),
      page.getByTestId(`account-waiver-download-${id}`).click(),
    ]);
    expect(formResponse.status()).toBe(200);
    expect(formResponse.headers()["content-type"]).toBe("application/pdf");
    expect(download.suggestedFilename()).toMatch(/\.pdf$/);

    // The signed scan, with the guardian's name.
    await page.getByTestId(`account-waiver-guardian-${id}`).fill("R. Ver (parent)");
    await page.getByTestId(`account-waiver-upload-${id}`).setInputFiles({
      name: "signed.png",
      mimeType: "image/png",
      buffer: PNG,
    });
    await expect(page.getByTestId(`account-waiver-message-${id}-success`)).toBeVisible();
    await expect(row).toHaveAttribute("data-status", "cleared");
    await expect(page.getByTestId(`account-waiver-scan-${id}`)).toBeVisible();
  });
});

describeStory("VA-5: as the organizer I only check off what is on file", () => {
  test("the event panel lists the squads' waivers and opens a minor's form", async ({
    page,
    request,
  }, testInfo) => {
    // An act of the spec's own series, so that the minor's row is on someone's check-in
    // list. Creating it adopts the series' registrations as participants (CLAUDE.md).
    const headers = await bearer(request, ADMIN);
    const title = `Check-in e2e ${testInfo.project.name} ${Date.now()}`;
    const created = await request.post("/api/admin/events", {
      headers,
      data: { title, starts_on: "2026-08-15", series: seriesId, matchday: 1 },
    });
    expect(created.ok(), await created.text()).toBeTruthy();
    const eventId = ((await created.json()) as { id: number }).id;

    await signIn(page, ADMIN);
    await page.goto("/office/events");
    await expect(page.getByTestId("admin-manage-events-list")).toBeVisible();
    // Searched for, not scrolled to: the list is paged, and with the real 2026 season in
    // the seed this act is not on the first page (Story A-13).
    await page.getByTestId("admin-manage-events-search-input").fill(title);
    await page.getByTestId(`admin-manage-event-toggle-${eventId}`).click();

    await expect(page.getByTestId(`admin-manage-event-waivers-summary-${eventId}`)).toBeVisible();
    const juniorRow = page.getByTestId(`admin-manage-event-waiver-row-${eventId}-${junior.id}`);
    await expect(juniorRow).toHaveAttribute("data-status", "cleared");
    await expect(juniorRow).toContainText("under 18");

    // The scan opens in a new tab, fetched with the token — a 200 with the image.
    const [scanResponse] = await Promise.all([
      page.waitForResponse((r) => r.url().includes("/waiver/confirmations/")),
      page.getByTestId(`admin-manage-event-waiver-scan-${eventId}-${junior.id}`).click(),
    ]);
    expect(scanResponse.status()).toBe(200);
    expect(scanResponse.headers()["content-type"]).toBe("image/png");

    // Someone who never signed is listed as missing — the list is the whole squad.
    const missing = page.locator(
      `[data-testid^="admin-manage-event-waiver-row-${eventId}-"][data-status="missing"]`,
    );
    await expect(missing.first()).toBeVisible();
  });
});
