import { describeStory, expect, test } from "./fixtures";
import { expectNoSidewaysScroll } from "./layout";
import { bearer, signIn } from "./session";

const ADMIN = "admin@sbl.example.com";

describeStory("S-9/A-15: feedback from any page, read in the league office", () => {
  test("a guest has no Feedback; signed in, it is sent from the page and read in the office", async ({ page, request }, testInfo) => {
    await page.goto("/clubs");
    await expect(page.getByTestId("layout-user-menu-feedback")).toHaveCount(0);

    // A fresh account each run: its message is found by a word only it contains.
    const tag = `fb${Date.now()}${testInfo.project.name}`;
    const email = `${tag}@example.com`;
    const made = await request.post("/api/auth/users", {
      headers: await bearer(request, ADMIN),
      data: { email, display_name: "Fee Dback", roles: [] },
    });
    expect(made.ok(), await made.text()).toBeTruthy();

    // S-9: from the account menu, on the page I am on.
    await signIn(page, email);
    await page.goto("/clubs?q=kiel");
    await page.getByTestId("layout-profile-button").click();
    await page.getByTestId("layout-user-menu-feedback").click();
    await expect(page.getByTestId("feedback-dialog")).toBeVisible();
    await expect(page.getByTestId("feedback-send")).toBeDisabled();
    await page.getByTestId("feedback-category").selectOption("feature");
    await page.getByTestId("feedback-message").fill(`Please show the venue ${tag}`);
    await page.getByTestId("feedback-send").click();
    await expect(page.getByTestId("feedback-success")).toBeVisible();
    await expect(page.getByTestId("feedback-dialog")).toHaveCount(0);

    // A-15: the site's admin reads it, with the page as a link.
    await signIn(page, ADMIN);
    await page.goto(`/office/feedback?q=${tag}`);
    const section = page.getByTestId("admin-feedback-section");
    await expect(section).toContainText(`Please show the venue ${tag}`);
    await expect(section).toContainText(email);
    const link = section.locator('[data-testid^="admin-feedback-path-"]').first();
    await expect(link).toHaveAttribute("href", "/clubs?q=kiel");
    await expectNoSidewaysScroll(page, testInfo);

    const toggle = section.locator('[data-testid^="admin-feedback-toggle-"]').first();
    const state = section.locator('[data-testid^="admin-feedback-state-"]').first();
    const open = await state.textContent();
    await toggle.click();
    await expect(state).not.toHaveText(open ?? "");
  });
});
