import type { APIRequestContext, Page } from "@playwright/test";

import { expect, test } from "./fixtures";
import { bearer, signIn } from "./session";

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
const CLUB_DOMAIN = "nrv.example.com"; // fields a first-league team and a juniors team
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
  "base64",
);

type SailorRow = { id: number; email: string | null; birth_date: string | null };

/** The seeded sailors of one club: adults sail the first league, teenagers the juniors. */
async function sailorsOf(request: APIRequestContext, domain: string): Promise<SailorRow[]> {
  const headers = await bearer(request, ADMIN);
  const response = await request.get(`/api/admin/sailors?q=${domain}&limit=100`, { headers });
  expect(response.ok(), await response.text()).toBeTruthy();
  return ((await response.json()) as { items: SailorRow[] }).items.filter((s) => s.email);
}

function bornIn(row: SailorRow): number {
  return Number(row.birth_date?.slice(0, 4) ?? 0);
}

async function openAccount(page: Page): Promise<void> {
  await page.goto("/account");
  await expect(page.getByTestId("account-waivers-card")).toBeVisible();
  await expect(page.getByTestId("account-waivers-list")).toBeVisible();
}

let adult: SailorRow;
let junior: SailorRow;

test.beforeAll(async ({ request }, testInfo) => {
  const sailors = await sailorsOf(request, CLUB_DOMAIN);
  // Each browser project takes its own pair: the two projects can share one stack, and a
  // waiver confirmed by the first run would already be "cleared" for the second.
  const nth = testInfo.project.name === "mobile" ? 1 : 0;
  adult = sailors.filter((s) => bornIn(s) > 0 && bornIn(s) <= 2004)[nth]!;
  junior = sailors.filter((s) => bornIn(s) >= 2009)[nth]!;
  expect(adult, "a seeded adult of the club").toBeTruthy();
  expect(junior, "a seeded junior of the club").toBeTruthy();
});

test.describe("S-1: as a sailor I submit the liability waiver from my account", () => {
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

test.describe("VA-5: as the organizer I only check off what is on file", () => {
  test("the event panel lists the squads' waivers and opens a minor's form", async ({
    page,
    request,
  }, testInfo) => {
    // A juniors event, so that the minor's row is on someone's check-in list. Creating it
    // adopts the series' registrations as participants (CLAUDE.md, Domain decisions).
    const headers = await bearer(request, ADMIN);
    const series = (await (await request.get("/api/admin/series?limit=50", { headers })).json()) as {
      items: { id: number; slug: string }[];
    };
    const juniors = series.items.find((s) => s.slug === "junioren-2026")!;
    // One act per browser project: the two can share a stack, and an act number is unique
    // within its series.
    const matchday = testInfo.project.name === "mobile" ? 78 : 77;
    const created = await request.post("/api/admin/events", {
      headers,
      data: {
        title: `Juniors check-in e2e ${matchday}`,
        starts_on: "2026-08-15",
        series: juniors.id,
        matchday,
      },
    });
    expect(created.ok(), await created.text()).toBeTruthy();
    const eventId = ((await created.json()) as { id: number }).id;

    await signIn(page, ADMIN);
    await page.goto("/admin?tab=events");
    await expect(page.getByTestId("admin-manage-events-list")).toBeVisible();
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
