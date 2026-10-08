import type { Page } from "@playwright/test";

import { describeStory, expect, test } from "./fixtures";
import { openNavigation } from "./layout";
import { bearer, signIn } from "./session";

/** Stories Z-8 and S-7: my space — every club, series and event I am part of, and my
 * page in each — and Story S-5: a person's licences, dropped onto the page.
 *
 * `api/tests/stories/test_my_space.py` proves what counts as mine and what needs me;
 * here the browser proves the way through: one entry in the navigation, a card per
 * thing, and a page that shows the sections my relations allow — no more, no fewer.
 *
 * For S-5, a person's licences, uploaded by dropping the file onto the page.
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
    await page.goto("/me/profile?tab=documents");
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

type DevUser = { email: string; roles: string[] };

async function devUsers(request: import("@playwright/test").APIRequestContext): Promise<DevUser[]> {
  const response = await request.get("/api/dev/users");
  expect(response.ok(), "is SBL_DEV_LOGIN=true?").toBeTruthy();
  return (await response.json()) as DevUser[];
}

/** The seeded club admin and the club they hold `admin` on. */
async function aClubAdmin(request: import("@playwright/test").APIRequestContext) {
  const admin = (await devUsers(request)).find(
    (u) => u.roles.includes("club_admin") && u.email.endsWith("@nrv.example.com"),
  )!;
  const clubs = (await (
    await request.get("/api/clubs/mine", { headers: await bearer(request, admin.email) })
  ).json()) as { club: { id: number }; may_admin: boolean }[];
  return { email: admin.email, clubId: clubs.find((c) => c.may_admin)!.club.id };
}

describeStory("Z-8/S-7: my space — one card per thing I am part of, and my page in it", () => {
  test("a club's admin reaches the club from the navigation, with every section of theirs", async ({
    page,
    request,
  }) => {
    const { email, clubId } = await aClubAdmin(request);
    await signIn(page, email);
    await page.goto("/");
    await openNavigation(page);
    await page.getByTestId("layout-nav-mySpace").click();
    await expect(page).toHaveURL(/\/me$/);

    // The person first, then what they are part of — with what they are to it.
    await expect(page.getByTestId("me-card-me")).toBeVisible();
    const card = page.getByTestId(`me-card-club-${clubId}`);
    await expect(card.getByTestId(`me-card-club-${clubId}-relations-member`)).toBeVisible();
    await expect(card.getByTestId(`me-card-club-${clubId}-relations-admin`)).toBeVisible();

    await card.click();
    await expect(page).toHaveURL(new RegExp(`/me/club/${clubId}`));
    // An organizer who is a member: the club's people, its matchdays and squads, their
    // own claims to it, and its money.
    for (const tab of ["members", "events", "series", "claims", "money"]) {
      await expect(page.getByTestId(`me-context-${tab}-tab`)).toBeVisible();
    }
    await page.getByTestId("me-context-money-tab").click();
    await expect(page.getByTestId(`reimbursements-club-${clubId}`)).toBeVisible();

    await page.getByTestId("me-context-back").click();
    await expect(page.getByTestId("me-overview")).toBeVisible();
  });

  test("a helper sees the event they help at, and nothing on it but their claims", async ({ page }) => {
    // Seeded: `helper` on the planned matchday and nothing else — the person the old
    // screens had no door for. Their only event is over, so it is not folded away.
    await signIn(page, "helfer@sbl.example.com");
    await page.goto("/me");
    // The card is the link; its chip list shares the testid prefix.
    const card = page.locator('a[data-testid^="me-card-event-"]').filter({
      has: page.locator('[data-testid$="-relations-helper"]'),
    });
    await expect(card).toHaveCount(1);
    await expect(page.getByTestId("me-group-clubs")).toHaveCount(0);

    await card.click();
    await expect(page.getByTestId("me-context-claims-tab")).toBeVisible();
    await expect(page.getByTestId("me-context-tabs").getByRole("tab")).toHaveCount(1);
    // On the event's page a claim is filed on the event — nothing to choose.
    await expect(page.getByTestId("my-space-claim-new")).toBeVisible();
    await expect(page.getByTestId("my-space-claim-target")).toHaveCount(0);
  });

  test("the old addresses lead to the new pages, and a page not mine is not found", async ({
    page,
    request,
  }) => {
    const { email, clubId } = await aClubAdmin(request);
    await signIn(page, email);

    await page.goto(`/club?club=${clubId}&tab=series`);
    await expect(page).toHaveURL(new RegExp(`/me/club/${clubId}\\?tab=series`));
    await expect(page.getByTestId("me-context-series-tab")).toHaveAttribute("aria-selected", "true");

    await page.goto("/reimbursements");
    await expect(page).toHaveURL(/\/me$/);

    await page.goto("/account");
    await expect(page).toHaveURL(/\/me\/profile/);
    await expect(page.getByTestId("account-signin-methods-card")).toBeVisible();

    // A club this person has nothing to do with.
    await page.goto("/me/club/999999");
    await expect(page.getByTestId("me-context-not-found")).toBeVisible();
  });
});
