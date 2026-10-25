import { describeStory, expect, test } from "./fixtures";
import { bearer, managedClub, signIn } from "./session";

/** Story VA-13: a club enters more than one team — the option is in the event's clubs
 *  block. `api/tests/stories/test_teams_per_club.py` proves the rules; this proves the
 *  organizer can reach them: raise *Teams per club*, give one club two teams, save. */

const ADMIN = "admin@sbl.example.com";
const TEAM_MANAGER = "teams@asvw.example.com";

describeStory("VA-13: a club enters more than one team", () => {
  test("the organizer gives a club a second team in the clubs block", async ({ page, request }, testInfo) => {
    const headers = await bearer(request, ADMIN);
    const asvw = await managedClub(request, TEAM_MANAGER);
    const series = (await (await request.get("/api/admin/series?limit=50", { headers })).json()) as {
      items: { id: number; slug: string }[];
    };
    const second = series.items.find((s) => s.slug === "dsbl-2-2026")!;
    // No act number: the server takes the next free one, so a second run on the same
    // stack (or the other browser project) makes its own act.
    const title = `Two teams e2e ${testInfo.project.name} ${Date.now()}`;
    const created = await request.post("/api/admin/events", {
      headers,
      data: { title, series: second.id },
    });
    expect(created.ok(), await created.text()).toBeTruthy();
    const event = (await created.json()) as { id: number; teams_per_club: number };
    expect(event.teams_per_club).toBe(1);

    await signIn(page, ADMIN);
    await page.goto("/office/events");
    await page.getByTestId(`admin-manage-event-toggle-${event.id}`).click();
    const block = `admin-manage-event-clubs-${event.id}`;
    // The series' clubs are adopted on creation, ASVW among them.
    await page.getByTestId(`${block}-teams-per-club`).fill("2");
    const count = page.getByTestId(`${block}-team-count-${asvw}`);
    await expect(count).toBeVisible();
    await count.selectOption("2");
    await page.getByTestId(`admin-manage-event-save-clubs-${event.id}`).click();

    await expect
      .poll(async () => {
        const response = await request.get(`/api/admin/events/${event.id}/clubs`, { headers });
        const teams = (await response.json()) as { club: { id: number }; name: string }[];
        return teams.filter((t) => t.club.id === asvw).map((t) => t.name).sort();
      })
      .toEqual(["ASVW", "ASVW 2"]);

    // The organizer's parameter, changed back: one save takes the second team away and
    // then lowers the number.
    await page.getByTestId(`${block}-teams-per-club`).fill("1");
    await page.getByTestId(`admin-manage-event-save-clubs-${event.id}`).click();
    await expect
      .poll(async () => {
        // Drafts are only in the admin list; found by the act's unique title.
        const response = await request.get("/api/admin/events", { headers, params: { q: title } });
        const page = (await response.json()) as { items: { id: number; teams_per_club: number }[] };
        return page.items.find((e) => e.id === event.id)?.teams_per_club;
      })
      .toBe(1);
  });
});
