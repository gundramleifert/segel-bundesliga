import { describeStory, expect, test } from "./fixtures";
import { bearer, signIn } from "./session";

/** Story Z-9: a password, set on the account page and used to sign in.
 *
 * `api/tests/stories/test_password_login.py` proves the rules — length, lockout, the one
 * answer for every wrong combination. What only a browser can prove is the walk: the
 * account page sets the password, signing out lands on the sign-in card, and its password
 * tab signs back in to the same account.
 */

const ADMIN = "admin@sbl.example.com";
// A club no other spec touches; each browser project takes its own sailor, because the
// two projects can share one stack.
const CLUB_DOMAIN = "fsc.example.com";
const PASSWORD = "lee-side of the pontoon";

describeStory("Z-9: as a sailor I sign in with a password I set myself", () => {
  test("set a password, sign out, sign in with it", async ({ page, request }, testInfo) => {
    const headers = await bearer(request, ADMIN);
    const listed = await request.get(`/api/auth/users?q=${CLUB_DOMAIN}&limit=2`, { headers });
    expect(listed.ok(), await listed.text()).toBeTruthy();
    const nth = testInfo.project.name === "mobile" ? 1 : 0;
    const email = ((await listed.json()) as { items: { email: string }[] }).items[nth]!.email;
    // A rerun against the same stack starts from "no password" again.
    await request.delete("/api/auth/password", { headers: await bearer(request, email) });

    await signIn(page, email);
    await page.goto("/account");
    const card = page.getByTestId("account-signin-methods-card");
    await expect(card).toBeVisible();
    await expect(page.getByTestId("account-signin-method-password")).toHaveCount(0);

    await page.getByTestId("account-password-new-input").fill(PASSWORD);
    await page.getByTestId("account-password-save-button").click();
    await expect(page.getByTestId("account-password-message")).toBeVisible();
    await expect(page.getByTestId("account-signin-method-password")).toBeVisible();

    await page.getByTestId("account-signout-button").click();
    await expect(page.getByTestId("account-signin-card")).toBeVisible();

    // The password tab is the first one where passwords are open.
    await expect(page.getByTestId("account-signin-tab-password")).toBeVisible();
    await page.getByTestId("account-signin-email-input").fill(email);
    await page.getByTestId("account-signin-password-input").fill(PASSWORD);
    await page.getByTestId("account-signin-password-button").click();

    await expect(page.getByTestId("account-info-card")).toContainText(email);
  });
});
