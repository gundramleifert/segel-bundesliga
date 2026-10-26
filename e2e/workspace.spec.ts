import type { APIRequestContext } from "@playwright/test";

import { describeStory, expect, test } from "./fixtures";
import { bearer, devUsers, signIn } from "./session";

/** Story Z-10, issue #34: the search at the top of the context switcher.
 *
 * `web/tests/test_workspace.ts` proves the matching — which sections a word finds, for
 * whom, in which language. Here the browser proves the way through: the box is there, a
 * word offers the section, the keyboard opens it, and the league office reaches a club
 * that is not "mine" by typing its name.
 */

const ADMIN = "admin@sbl.example.com";

/** ASVW's admin (`board@`), and their club. */
async function aClubAdmin(request: APIRequestContext) {
  const admin = (await devUsers(request)).find(
    (u) => u.roles.includes("club_admin") && u.email.endsWith("@asvw.example.com"),
  )!;
  const clubs = (await (
    await request.get("/api/clubs/mine", { headers: await bearer(request, admin.email) })
  ).json()) as { club: { id: number }; may_admin: boolean }[];
  return { email: admin.email, clubId: clubs.find((c) => c.may_admin)!.club.id };
}

type Tuple = { id: number; user: string; relation: string };

/** Makes `email` a helper on `count` events, so their switcher reaches the 8 entries the
 *  search box appears from — nobody in the seed has that many. Returns the undo. */
async function helpOnEvents(request: APIRequestContext, email: string, count: number) {
  const admin = await bearer(request, ADMIN);
  const events = (await (await request.get(`/api/admin/events?limit=${count}`, { headers: admin })).json()) as {
    items: { id: number }[];
  };
  const objects = events.items.map((e) => `event:${e.id}`);
  for (const object of objects) {
    const added = await request.post("/api/auth/tuples", { headers: admin, data: { user: email, relation: "helper", object } });
    // A run that stopped before its undo left the tuple behind.
    if (!added.ok()) expect(await added.text()).toContain("tuple-exists");
  }
  return async () => {
    for (const object of objects) {
      const rows = (await (await request.get(`/api/auth/tuples?object=${object}`, { headers: admin })).json()) as Tuple[];
      for (const row of rows.filter((r) => r.user === email && r.relation === "helper")) {
        expect((await request.delete(`/api/auth/tuples/${row.id}`, { headers: admin })).ok()).toBeTruthy();
      }
    }
  };
}

describeStory("Z-10: the switcher's search — my sections by their words, anything for the league office", () => {
  test("a club's admin types a section's words and lands on it", async ({ page, request }) => {
    const { email, clubId } = await aClubAdmin(request);
    const undo = await helpOnEvents(request, email, 6);
    try {
      await signIn(page, email);
      await page.goto(`/me/club/${clubId}`);
      await page.getByTestId("workspace-switcher").click();
      const search = page.getByTestId("workspace-switcher-search");
      await expect(search).toBeFocused();

      // A section by its words — one the sidebar may not list yet is still found (#34).
      await search.fill("minors");
      await expect(page.getByTestId(`workspace-switcher-search-hit-club-${clubId}-minors`)).toBeVisible();
      // Of the helper's events only their claims, never the organizers' sections.
      await search.fill("results");
      await expect(page.getByTestId("workspace-switcher-search-empty")).toBeVisible();

      // By keyboard: the first hit is marked, Enter opens it.
      // "Hosting" — a word only the club's section has (an event of ASVW's also has *People*).
      await search.fill("hosting");
      await expect(page.getByTestId(`workspace-switcher-search-hit-club-${clubId}-hosting`)).toHaveAttribute(
        "aria-selected",
        "true",
      );
      await search.press("Enter");
      await expect(page).toHaveURL(new RegExp(`/me/club/${clubId}/hosting$`));
      await expect(page.getByTestId("workspace-content-club-hosting")).toBeVisible();
      await expect(page.getByTestId("workspace-switcher-panel")).toHaveCount(0);

      // Escape closes the list.
      await page.getByTestId("workspace-switcher").click();
      await expect(page.getByTestId("workspace-switcher-search")).toBeFocused();
      await page.keyboard.press("Escape");
      await expect(page.getByTestId("workspace-switcher-panel")).toHaveCount(0);
    } finally {
      await undo();
    }
  });

  test("the league office finds a club that is not theirs by its name", async ({ page, request }) => {
    const admin = await bearer(request, ADMIN);
    const clubs = (await (await request.get("/api/admin/clubs?limit=100", { headers: admin })).json()) as {
      items: { id: number; slug: string; name: string }[];
    };
    const club = clubs.items.find((c) => c.slug === "kyc-sh")!;

    await signIn(page, ADMIN);
    await page.goto("/me");
    // Two entries only — Me and the league office — and still the box: the office always has it.
    await page.getByTestId("workspace-switcher").click();
    await page.getByTestId("workspace-switcher-search").fill(club.name);
    const hit = page.getByTestId(`workspace-switcher-search-hit-club-${club.id}`);
    await expect(hit).toBeVisible();
    await hit.click();
    await expect(page).toHaveURL(new RegExp(`/me/club/${club.id}`));
  });
});
