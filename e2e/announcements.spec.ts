import type { APIRequestContext } from "@playwright/test";

import { describeStory, expect, test } from "./fixtures";
import { bearer, signIn } from "./session";

const ADMIN = "admin@sbl.example.com";
const OFFICER = "regatta@sbl.example.com";

/** Makes the seed's race officer `regatta@` the race officer of `event` — published, which
 *  their seeded event (a 2027 draft) is not, so a guest can read its board. Returns the
 *  undo: other specs count what `regatta@` holds. */
async function raceOfficerOn(request: APIRequestContext, event: number) {
  const admin = await bearer(request, ADMIN);
  const object = `event:${event}`;
  const added = await request.post("/api/auth/tuples", {
    headers: admin,
    data: { user: OFFICER, relation: "race_officer", object },
  });
  // A run that stopped before its undo left the tuple behind.
  if (!added.ok()) expect(await added.text()).toContain("tuple-exists");
  return async () => {
    const rows = (await (await request.get(`/api/auth/tuples?object=${object}`, { headers: admin })).json()) as {
      id: number;
      user: string;
      relation: string;
    }[];
    for (const row of rows.filter((r) => r.user === OFFICER && r.relation === "race_officer")) {
      expect((await request.delete(`/api/auth/tuples/${row.id}`, { headers: admin })).ok()).toBeTruthy();
    }
  };
}

describeStory("VA-11: the race committee publishes an announcement on the notice board", () => {
  test("the race officer publishes, a guest reads it, the officer retracts it", async ({ page, browser, request, season2 }, testInfo) => {
    // The practice season's planned act (`app/practice.py`), in the league `practice`.
    const BOARD = `/practice/2026/act-3/notice-board?division=${season2.planned}`;
    const undo = await raceOfficerOn(request, season2.planned);
    try {
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
      await expect(page.getByTestId(`notice-author-${id}`)).toHaveText("Willy Wettfahrtleiter");

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
    } finally {
      await undo();
    }
  });
});
