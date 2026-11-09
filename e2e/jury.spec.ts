import { describeStory, expect, test } from "./fixtures";
import { expectNoSidewaysScroll } from "./layout";
import { bearer, signIn } from "./session";

const ADMIN = "admin@sbl.example.com"; // the site's admin is jury organizer too (JU-1)

describeStory("JU-1/JU-2/JU-3/JU-4/JU-5: the jury organizer staffs an event from the pool of judges", () => {
  test("added to the pool, asked, answering and approved", async ({ page, request }, testInfo) => {
    const admin = await bearer(request, ADMIN);
    // A fresh account each run, so the pool and its requests start empty for them.
    const email = `ju-${Date.now()}-${test.info().project.name}@example.com`;
    const made = await request.post("/api/auth/users", { headers: admin, data: { email, display_name: "Jule Richter", roles: [] } });
    expect(made.ok(), await made.text()).toBeTruthy();
    const userId = ((await made.json()) as { id: number }).id;
    const events = (await (await request.get("/api/jury/events?limit=100", { headers: admin })).json()) as {
      items: { id: number }[];
    };
    const event = events.items[0].id;

    // JU-1: the organizer finds the account and puts it in the pool.
    await signIn(page, ADMIN);
    await page.goto(`/office/jury?q=${encodeURIComponent(email)}`);
    await page.getByTestId("office-jury-add-open").click();
    await page.getByTestId("office-jury-candidate-search").fill(email);
    await page.getByTestId(`office-jury-candidate-add-${userId}`).click();
    // Escape inside the dialog: the added candidate's button is gone, and with it the focus.
    await page.getByTestId("office-jury-candidate-search").press("Escape");
    await expect(page.getByTestId("office-jury-candidate-search")).toHaveCount(0);
    await expect(page.getByTestId(`office-jury-row-${userId}`)).toBeVisible();

    // JU-3: the event a column, the judge ticked and asked.
    await page.getByTestId("office-jury-pick").selectOption(String(event));
    await expect(page.getByTestId(`office-jury-${event}-${userId}-state`)).toHaveText("—");
    await page.getByTestId(`office-jury-tick-${userId}`).check();
    await page.getByTestId("office-jury-note").fill("Bitte bis Freitag.");
    await page.getByTestId("office-jury-invite").click();
    await expect(page.getByTestId("office-jury-invite-success")).toBeVisible();
    await expect(page.getByTestId(`office-jury-${event}-${userId}-state`)).toHaveText(/asked/i);
    await expectNoSidewaysScroll(page, testInfo);

    // JU-2, JU-4: the judge says their licences and answers — a to-do until then.
    await signIn(page, email);
    await page.goto("/me/profile/jury");
    await page.getByTestId("me-jury-licence-umpire").check();
    await page.getByTestId("me-jury-licences-save").click();
    await expect(page.getByTestId("me-jury-licences-success")).toBeVisible();
    await page.getByTestId(`me-jury-available-${event}`).click();
    await expect(page.getByTestId(`me-jury-state-${event}`)).toHaveText(/available/i);
    await expectNoSidewaysScroll(page, testInfo);

    // JU-5: the organizer filters by the answer and approves; the judge sees it.
    await signIn(page, ADMIN);
    await page.goto(`/office/jury?q=${encodeURIComponent(email)}&events=${event}&at_${event}=available&licence=umpire`);
    await page.getByTestId(`office-jury-${event}-${userId}-approve`).click();
    // Approved, they no longer match "available" — the filter that found them.
    await expect(page.getByTestId(`office-jury-row-${userId}`)).toHaveCount(0);
    await page.goto(`/office/jury?q=${encodeURIComponent(email)}&events=${event}&at_${event}=approved`);
    await expect(page.getByTestId(`office-jury-${event}-${userId}-state`)).toHaveText(/approved/i);

    await signIn(page, email);
    await page.goto("/me/profile/jury");
    await expect(page.getByTestId(`me-jury-state-${event}`)).toHaveText(/approved/i);
    await expect(page.getByTestId(`me-jury-available-${event}`)).toHaveCount(0);

    // Leave the seeded event's jury as it was.
    await request.delete(`/api/jury/events/${event}/judges/${userId}`, { headers: admin });
  });
});
