import { describeStory, expect, test } from "./fixtures";
import { signIn } from "./session";

// The seed's planned act of the 2. Liga, whose race officer is `regatta@` (app/seed_users.py).
const BOARD = "/2-liga/2026/act-3/notice-board";
const OFFICER = "regatta@sbl.example.com";

describeStory("VA-11: the race committee publishes an announcement on the notice board", () => {
  test("the race officer publishes, a guest reads it, the officer retracts it", async ({ page, browser }, testInfo) => {
    const title = `First warning signal 10:30 · ${testInfo.project.name} ${Date.now()}`;
    await signIn(page, OFFICER);
    await page.goto(BOARD);

    const form = page.getByTestId("site-act-publish");
    await expect(form).toBeVisible();
    await form.getByTestId("site-act-publish-title").fill(title);
    await form.getByTestId("site-act-publish-body").fill("Racing area A. Briefing for helms at 09:00.");
    await form.getByTestId("site-act-publish-submit").click();
    await expect(page.getByTestId("site-act-publish-message-success")).toBeVisible();
    const notice = page.getByTestId("site-act-announcements").locator("details", { hasText: title });
    await expect(notice).toBeVisible();
    // Numbered, and signed by whoever put it up.
    const id = (await notice.getAttribute("data-testid"))!.replace("site-act-notice-", "");
    await expect(page.getByTestId(`notice-number-${id}`)).toHaveText(/^No\. \d+$/);
    await expect(page.getByTestId(`notice-author-${id}`)).toHaveText("Malte Rackow");

    // A guest sees it, and no form.
    const guest = await browser.newPage();
    await guest.goto(BOARD);
    await expect(guest.getByTestId("site-act-announcements").getByText(title)).toBeVisible();
    await expect(guest.getByTestId("site-act-publish")).toHaveCount(0);
    await guest.close();

    // Retract: two clicks, and it is gone.
    await page.getByTestId(`site-act-notice-retract-${id}`).click();
    await page.getByTestId(`site-act-notice-retract-${id}-confirm`).click();
    await expect(page.getByTestId(`site-act-notice-${id}`)).toHaveCount(0);
  });
});
