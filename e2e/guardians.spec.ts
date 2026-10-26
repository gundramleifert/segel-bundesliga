import type { APIRequestContext } from "@playwright/test";

import { describeStory, expect, test } from "./fixtures";
import { bearer, signIn } from "./session";

/** Stories V-13 and S-8: the club links a parent to a young sailor, and the parent
 * accepts the waiver for the child online.
 *
 * `api/tests/stories/test_guardians.py` proves the rules — who may link, the adult ward,
 * what my space says. What only a browser proves is the two screens a real person uses:
 * the Guardians section on the club's Members tab, and *My children* on the parent's
 * waiver tab, the child's row going from missing to cleared.
 *
 * Its own juniors of the club (the third and fourth), so it never meets `waiver.spec.ts`,
 * which takes the first two; and a fresh parent per browser project.
 */

const ADMIN = "admin@sbl.example.com";
const CLUB_DOMAIN = "asvw.example.com"; // fields a first-league team and a juniors team

type SailorRow = { id: number; email: string | null; birth_date: string | null; first_name: string };
type DevUser = { email: string; roles: string[] };

async function aJunior(request: APIRequestContext, nth: number): Promise<SailorRow> {
  const headers = await bearer(request, ADMIN);
  const response = await request.get(`/api/admin/people?q=${CLUB_DOMAIN}&limit=100`, { headers });
  expect(response.ok(), await response.text()).toBeTruthy();
  const juniors = ((await response.json()) as { items: SailorRow[] }).items.filter(
    (s) => s.email && Number(s.birth_date?.slice(0, 4) ?? 0) >= 2009,
  );
  expect(juniors.length, "seeded juniors of the club").toBeGreaterThan(nth);
  return juniors[nth]!;
}

async function theClubAdmin(request: APIRequestContext): Promise<{ email: string; clubId: number }> {
  const users = (await (await request.get("/api/dev/users")).json()) as DevUser[];
  const email = users.find((u) => u.roles.includes("club_admin") && u.email.endsWith(`@${CLUB_DOMAIN}`))!
    .email;
  const clubs = (await (
    await request.get("/api/clubs/mine", { headers: await bearer(request, email) })
  ).json()) as { club: { id: number }; may_admin: boolean }[];
  return { email, clubId: clubs.find((c) => c.may_admin)!.club.id };
}

describeStory("V-13/S-8: a parent the club linked accepts the waiver for their child", () => {
  test("the club links the parent; the parent clears the child online", async ({ page, request }, testInfo) => {
    const junior = await aJunior(request, testInfo.project.name === "mobile" ? 3 : 2);
    const parent = `parent-${testInfo.project.name}-${Date.now()}@example.com`;
    const created = await request.post("/api/auth/users", {
      headers: await bearer(request, ADMIN),
      data: { email: parent, display_name: "Pat Parent" },
    });
    expect(created.ok(), await created.text()).toBeTruthy();

    // The club's admin links the parent under Minors & guardians (Story Z-10).
    const { email, clubId } = await theClubAdmin(request);
    await signIn(page, email);
    await page.goto(`/me/club/${clubId}/minors`);
    const row = page.getByTestId(`my-club-guardians-row-${junior.id}`);
    await expect(row).toBeVisible();
    await page.getByTestId(`my-club-guardians-add-${junior.id}`).click();
    await page.getByTestId(`my-club-guardians-email-${junior.id}`).fill(parent);
    await page.getByTestId(`my-club-guardians-submit-${junior.id}`).click();
    await expect(row.getByText("Pat Parent")).toBeVisible();

    // The parent finds the child on their own waiver tab, and accepts for them.
    await signIn(page, parent);
    await page.goto("/me/profile/waivers");
    const ward = page.getByTestId(`account-ward-${junior.id}`);
    await expect(ward).toBeVisible();
    const prefix = `account-ward-waiver-${junior.id}`;
    const competition = ward.locator(`[data-testid^="${prefix}-series-"][data-status]`).first();
    await expect(competition).toHaveAttribute("data-status", "missing");
    const id = (await competition.getAttribute("data-testid"))!.replace(`${prefix}-`, "");

    // No paper for the parent: the form and the scan are the child's and the club's way.
    await expect(page.getByTestId(`${prefix}-download-${id}`)).toHaveCount(0);
    await page.getByTestId(`${prefix}-read-${id}`).click();
    await page.getByTestId(`${prefix}-agree-${id}`).check();
    await page.getByTestId(`${prefix}-confirm-${id}`).click();
    await expect(competition).toHaveAttribute("data-status", "cleared");
  });
});
