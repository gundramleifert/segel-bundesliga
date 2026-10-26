import type { APIRequestContext } from "@playwright/test";

import { describeStory, expect, test } from "./fixtures";
import { bearer, managedClub, signIn } from "./session";

const ADMIN = "admin@sbl.example.com";
const BOARD = "board@asvw.example.com"; // ASVW's admin
const GUEST = "gast@sbl.example.com"; // seeded, in no club

type Member = { person_id: number; user_id: number | null; status: string };

async function roster(request: APIRequestContext, club: number): Promise<Member[]> {
  const response = await request.get(`/api/clubs/${club}/members`, { headers: await bearer(request, ADMIN) });
  expect(response.ok(), await response.text()).toBeTruthy();
  return (await response.json()) as Member[];
}

/** Ends whatever row the account has in the club — a run before this one may have left it. */
async function clear(request: APIRequestContext, club: number, email: string) {
  const headers = await bearer(request, email);
  const me = (await (await request.get("/api/auth/me", { headers })).json()) as { id: number };
  for (const row of (await roster(request, club)).filter((m) => m.user_id === me.id)) {
    await request.delete(`/api/clubs/${club}/members/${row.person_id}`, { headers: await bearer(request, ADMIN) });
  }
}

describeStory("V-15: a second club takes someone in only with consent, either way round", () => {
  test("the club invites someone from another club, who accepts in My clubs", async ({ page, request }) => {
    const asvw = await managedClub(request, BOARD);
    const admin = await bearer(request, ADMIN);
    const clubs = (await (await request.get("/api/admin/clubs?limit=50", { headers: admin })).json()) as {
      items: { id: number; slug: string }[];
    };
    const kyc = clubs.items.find((c) => c.slug === "kyc-sh")!.id;

    // Someone of KYC with an account — the league office makes them, fresh each run.
    const email = `v15-${Date.now()}-${test.info().project.name}@example.com`;
    const made = await request.post("/api/auth/users", { headers: admin, data: { email, display_name: "Vera Zweiklub", roles: [] } });
    expect(made.ok(), await made.text()).toBeTruthy();
    const joined = await request.post(`/api/clubs/${kyc}/members`, { headers: admin, data: { email } });
    expect(joined.ok(), await joined.text()).toBeTruthy();

    // ASVW's admin adds them by email: they are in another club, so it is an invitation.
    await signIn(page, BOARD);
    await page.goto(`/me/club/${asvw}/people`);
    const panel = `my-club-access-${asvw}`;
    await page.getByTestId(`${panel}-open`).click();
    await page.getByTestId(`${panel}-mode-email`).check();
    await page.getByTestId(`${panel}-email`).fill(email);
    await page.getByTestId(`${panel}-add`).click();
    await expect(page.getByTestId(`${panel}-dialog`)).toHaveCount(0);
    const person = (await roster(request, asvw)).find((m) => m.status === "invited" && m.user_id !== null)!;
    await page.getByTestId("my-club-people-search").fill(email);
    await expect(page.getByTestId(`my-club-member-pending-${person.user_id}`)).toBeVisible();

    // They find it in Me › My clubs — a to-do — and accept.
    await signIn(page, email);
    await page.goto("/me/profile/clubs");
    await expect(page.getByTestId(`me-club-status-${asvw}`)).toBeVisible();
    await page.getByTestId(`me-club-accept-${asvw}`).click();
    await expect(page.getByTestId(`me-club-leave-${asvw}`)).toBeVisible();
    await expect(page.getByTestId(`me-club-leave-${kyc}`)).toBeVisible();

    // Back as the admin: a member now, no longer waiting.
    await signIn(page, BOARD);
    await page.goto(`/me/club/${asvw}/people?q=${encodeURIComponent(email)}`);
    await expect(page.getByTestId(`my-club-member-relation-${person.user_id}-member`)).toBeVisible();
    await expect(page.getByTestId(`my-club-member-pending-${person.user_id}`)).toHaveCount(0);

    // Leave nothing behind for the specs that count ASVW's people.
    await request.delete(`/api/clubs/${asvw}/members/${person.person_id}`, { headers: admin });
  });

  test("someone asks to join from the club page, and the club's admin accepts", async ({ page, request }) => {
    const asvw = await managedClub(request, BOARD);
    await clear(request, asvw, GUEST);

    await signIn(page, GUEST);
    await page.goto(`/clubs/${asvw}`);
    await page.getByTestId("club-ask-to-join").click();
    await expect(page.getByTestId("club-ask-to-join-requested")).toBeVisible();

    const asked = (await roster(request, asvw)).find((m) => m.status === "requested")!;
    // The request is the club's to-do, and it lands on the list narrowed to requests.
    await signIn(page, BOARD);
    await page.goto(`/me/club/${asvw}`);
    await page.getByTestId(`me-context-club-${asvw}-todo-membership_requested`).click();
    await expect(page).toHaveURL(/\/people\?status=requested$/);
    await expect(page.getByTestId(`my-club-member-pending-${asked.user_id}`)).toBeVisible();
    await page.getByTestId(`my-club-member-accept-${asked.person_id}`).click();
    // A member now: gone from the requests, on the list of members.
    await expect(page.getByTestId(`my-club-member-pending-${asked.user_id}`)).toHaveCount(0);
    await page.goto(`/me/club/${asvw}/people?q=${encodeURIComponent(GUEST)}`);
    await expect(page.getByTestId(`my-club-member-relation-${asked.user_id}-member`)).toBeVisible();

    await clear(request, asvw, GUEST);
  });
});
