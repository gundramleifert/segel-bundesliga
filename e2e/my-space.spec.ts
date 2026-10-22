import type { Page } from "@playwright/test";

import { describeStory, expect, test } from "./fixtures";
import { openUserMenu } from "./layout";
import { bearer, bornIn, devUsers, managedClub, seededSailors, signIn } from "./session";

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
// The test club, the one with accounts (`app/seed_users.py`); each browser project takes
// its own person.
const CLUB_DOMAIN = "asvw.example.com";
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

/** The seeded club admin and the club they hold `admin` on. */
async function aClubAdmin(request: import("@playwright/test").APIRequestContext) {
  const admin = (await devUsers(request)).find(
    (u) => u.roles.includes("club_admin") && u.email.endsWith("@asvw.example.com"),
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
    await openUserMenu(page);
    await page.getByTestId("layout-user-menu-mySpace").click();
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
    for (const tab of ["members", "events", "series", "waivers", "claims", "money"]) {
      await expect(page.getByTestId(`me-context-${tab}-tab`)).toBeVisible();
    }
    await page.getByTestId("me-context-money-tab").click();
    await expect(page.getByTestId(`reimbursements-club-${clubId}`)).toBeVisible();

    // The tabs are the page's sub-menu, in the header row beside its name; the
    // breadcrumb before that name leads back to the overview.
    await expect(page.getByTestId("layout-header").getByTestId("me-context-tabs")).toBeVisible();
    await page.getByTestId("layout-breadcrumb").getByRole("link", { name: "My space" }).click();
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

describeStory("V-3: a club's admin keeps the club's crest on the club's page", () => {
  test("the admin uploads and removes it; a plain member sees no control", async ({ page, request }) => {
    const { email, clubId } = await aClubAdmin(request);
    await signIn(page, email);
    await page.goto(`/me/club/${clubId}?tab=members`);

    const edit = page.getByTestId(`my-club-crest-edit-${clubId}`);
    await expect(edit).toBeVisible();
    await page.getByTestId(`my-club-crest-input-${clubId}`).setInputFiles({
      name: "crest.png",
      mimeType: "image/png",
      buffer: Buffer.from(PNG, "base64"),
    });
    await expect(page.getByTestId(`my-club-crest-${clubId}`)).toBeVisible();
    // Leave the club as it was: the other browser project, and other specs, read it.
    await page.getByTestId(`my-club-crest-remove-${clubId}`).click();
    await expect(page.getByTestId(`my-club-crest-${clubId}`)).toHaveCount(0);

    const member = (await devUsers(request)).find(
      (u) => u.email.endsWith("@asvw.example.com") && !u.roles.includes("club_admin"),
    )!;
    await signIn(page, member.email);
    await page.goto(`/me/club/${clubId}?tab=members`);
    await expect(page.getByTestId("my-club-members")).toBeVisible();
    await expect(page.getByTestId(`my-club-crest-${clubId}-section`)).toHaveCount(0);
  });
});

describeStory("S-1/Z-8/V-14: an unsigned waiver is a notice with its button, a badge, and a line in the club's list", () => {
  // The test club. Its adults 0 and 1 sign in `waiver.spec.ts`; these take 2 and 3, one
  // per browser project, still unsigned.
  const DOMAIN = "asvw.example.com";

  test("the sailor sees the badge, accepts in the notice, and the notice is gone", async ({ page, request }, testInfo) => {
    const adults = (await seededSailors(request, DOMAIN)).filter((s) => bornIn(s) > 0 && bornIn(s) <= 2004);
    const email = adults[testInfo.project.name === "mobile" ? 3 : 2]!.email!;

    await signIn(page, email);
    await page.goto("/");
    await expect(page.getByTestId("layout-profile-badge")).toBeVisible();

    await page.goto("/me");
    const card = page.locator('a[data-testid^="me-card-series-"]').filter({
      has: page.locator('[data-testid$="-needs-waiver"]'),
    });
    await card.first().click();

    // No waiver tab: the notice above the tabs holds the whole row.
    await expect(page.getByTestId("me-context-waiver-tab")).toHaveCount(0);
    const notice = page.getByTestId("me-context-waiver-notice");
    const row = notice.locator('[data-testid^="account-waiver-series-"]');
    await expect(row).toHaveAttribute("data-status", "missing");
    const id = (await row.getAttribute("data-testid"))!.replace("account-waiver-", "");
    await notice.getByTestId(`account-waiver-read-${id}`).click();
    await notice.getByTestId(`account-waiver-agree-${id}`).check();
    await notice.getByTestId(`account-waiver-confirm-${id}`).click();

    // Signed, nothing on this page needs me any more.
    await expect(notice).toHaveCount(0);
    await expect(page.locator('[data-testid$="-needs-waiver"]')).toHaveCount(0);
  });

  test("the team manager sees, per competition, who has signed", async ({ page, request }) => {
    const manager = (await devUsers(request)).find(
      (u) => u.roles.includes("team_manager") && u.email.endsWith(`@${DOMAIN}`),
    )!;
    const clubId = await managedClub(request, manager.email);

    await signIn(page, manager.email);
    await page.goto(`/me/club/${clubId}?tab=waivers`);
    const blocks = page.getByTestId("my-club-waivers-list").locator(':scope > li');
    await expect(blocks.first()).toBeVisible();
    await expect(blocks.first().locator('[data-testid$="-summary"]')).toContainText(/\d+ of \d+ cleared/);
    await expect(blocks.first().locator("[data-status]").first()).toBeVisible();
  });
});

describeStory("F-2: the people who work an event claim their costs on it", () => {
  test("the jury of the test event starts a claim on it — its host club pays", async ({ page }) => {
    // The test event is hosted by the test club (`app.seed`), so the jury has somewhere
    // to claim: the complaint that started this was a jury with nothing to choose.
    await signIn(page, "jury@sbl.example.com");
    await page.goto("/me/profile?tab=claims");
    const target = page.getByTestId("my-space-claim-target");
    await expect(target.locator("option", { hasText: "Act 3" })).toHaveCount(1);
    await expect(page.getByTestId("my-space-claim-unavailable")).toHaveCount(0);
  });
});
