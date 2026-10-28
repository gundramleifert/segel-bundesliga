import { describeStory, expect, test } from "./fixtures";
import { bearer, managedClub, signIn } from "./session";

const BOARD = "board@asvw.example.com"; // ASVW's admin

describeStory("V-16: a club's admin invites someone without an account", () => {
  test("an unknown address turns into the invitation, sent only after what follows is shown", async ({ page, request }) => {
    const asvw = await managedClub(request, BOARD);
    const email = `v16-${Date.now()}-${test.info().project.name}@example.com`;

    await signIn(page, BOARD);
    await page.goto(`/me/club/${asvw}/people`);
    const panel = `my-club-access-${asvw}`;
    await page.getByTestId(`${panel}-open`).click();
    await page.getByTestId(`${panel}-mode-email`).check();
    await page.getByTestId(`${panel}-email`).fill(email);
    await page.getByTestId(`${panel}-add`).click();

    // Journey step J-3.14: nobody has the address — the dialog offers the invitation.
    await expect(page.getByTestId("my-club-invite-unknown")).toContainText(email);
    await page.getByTestId("my-club-invite-first-name-input").fill("Ina");
    await page.getByTestId("my-club-invite-last-name-input").fill("Vite");
    await page.getByTestId("my-club-invite-next").click();
    // Nothing is sent before the admin has seen what follows.
    await expect(page.getByTestId("my-club-invite-consequences")).toContainText(email);
    await page.getByTestId("my-club-invite-send").click();
    await expect(page.getByTestId(`${panel}-dialog`)).toHaveCount(0);

    // The person is pending in People, with the invitation's actions on their row.
    await page.getByTestId("my-club-people-search-input").fill(email);
    const people = await request.get(`/api/clubs/${asvw}/people?q=${encodeURIComponent(email)}`, {
      headers: await bearer(request, BOARD),
    });
    const row = ((await people.json()) as { items: { person_id: number }[] }).items[0];
    await expect(page.getByTestId(`my-club-member-pending-person-${row.person_id}`)).toBeVisible();
    await page.getByTestId(`my-club-member-actions-${row.person_id}`).click();
    await expect(page.getByTestId(`my-club-member-invitation-resend-${row.person_id}`)).toBeVisible();

    // Withdrawn, the person made only for the invitation is gone again.
    await page.getByTestId(`my-club-member-invitation-withdraw-${row.person_id}`).click();
    await expect(page.getByTestId(`my-club-member-pending-person-${row.person_id}`)).toHaveCount(0);
  });

  test("a link that is not valid says so", async ({ page }) => {
    await page.goto("/invitation/not-a-real-token");
    await expect(page.getByTestId("invitation-header")).toBeVisible();
    await expect(page.getByTestId("invitation-error")).toBeVisible();
    await expect(page.getByTestId("invitation-accept")).toHaveCount(0);
  });
});
