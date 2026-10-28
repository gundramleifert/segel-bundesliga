import type { APIRequestContext } from "@playwright/test";

import { describeStory, expect, test } from "./fixtures";
import { listedSections, openSection, openSwitcher } from "./layout";
import { bearer, managedClub, signIn } from "./session";

/** Story Z-10 (#32): a club's and a series' administration in their own contexts — the
 *  sections the club's organizers and the series' manager get, by what they hold there.
 *  Reads only; what each section does is the older specs' business (club, guardians, my
 *  space). */

const TEAM_MANAGER = "teams@asvw.example.com"; // ASVW's manager — not its admin
const CLUB_ADMIN = "board@asvw.example.com"; // ASVW's admin, and a member
const SERIES_MANAGER = "serie@sbl.example.com"; // the 2. Segel-Bundesliga 2026's manager

/** A series the person manages — the published one first (the seed's 2026). */
async function managedSeries(request: APIRequestContext, email: string): Promise<number> {
  const answer = (await (await request.get("/api/me/contexts", { headers: await bearer(request, email) })).json()) as {
    contexts: { kind: string; id: number; relations: string[]; published?: boolean | null }[];
  };
  const mine = answer.contexts.filter((c) => c.kind === "series" && c.relations.includes("manager"));
  expect(mine.length, "the seed gives the series manager a series").toBeGreaterThan(0);
  return (mine.find((c) => c.published) ?? mine[0]).id;
}

describeStory("Z-10: the club's sections follow what I hold on the club", () => {
  test("the team manager has People and Racing, not the club's money or page", async ({ page, request }) => {
    const club = await managedClub(request, TEAM_MANAGER);
    await signIn(page, TEAM_MANAGER);
    await page.goto(`/me/club/${club}`);
    const sections = await listedSections(page, "club");
    for (const section of [
      "people", "minors", "waivers", // People
      "squads", "crews", "hosting", // Racing
    ]) {
      expect(sections, `the manager has ${section}`).toContain(section);
    }
    // The money is the treasurer's (and the admin's), decided 2026-10-26.
    for (const section of ["decide-claims", "payment-runs", "bank-account", "club-page"]) {
      expect(sections, `the manager has no ${section}`).not.toContain(section);
    }
    await page.keyboard.press("Escape");

    // The address of a section that is not theirs leads to the club's overview.
    await page.goto(`/me/club/${club}/club-page`);
    await expect(page.getByTestId("workspace-content-club-overview")).toBeVisible();

    // *People*: the club's people (#45) — and no way to add one: who is in the club is
    // its admin's to decide, the team manager's only who sails (Story V-4, 2026-10-28).
    await openSection(page, "club", "people");
    await expect(page.getByTestId("my-club-people-table")).toBeVisible();
    await expect(page.getByTestId(`my-club-access-${club}-open`)).toHaveCount(0);
    // A filter sits in the header of the column it narrows, and lands in the address —
    // the server narrows, the table keeps its header when nothing is left.
    await page.getByTestId("my-club-people-filter-birth_date").click();
    await page.getByTestId("my-club-people-filter-birth_date-no_birth_date-true").click();
    await expect(page).toHaveURL(/[?&]no_birth_date=true/);
    await expect(page.getByTestId("my-club-people-filter-birth_date")).toHaveAttribute("data-active", "true");
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("my-club-people-table")).toBeVisible();
    // The old addresses of *Members* and *Sailors* lead there.
    await page.goto(`/me/club/${club}/sailors?no_birth_date=true`);
    await expect(page).toHaveURL(new RegExp(`/me/club/${club}/people\\?no_birth_date=true$`));
  });

  test("the club's admin opens Minors & guardians and Payment runs", async ({ page, request }) => {
    const club = await managedClub(request, CLUB_ADMIN);
    await signIn(page, CLUB_ADMIN);
    await page.goto(`/me/club/${club}`);
    expect(await listedSections(page, "club")).toContain("club-page");
    await page.keyboard.press("Escape");

    await openSection(page, "club", "minors");
    await expect(page).toHaveURL(new RegExp(`/me/club/${club}/minors$`));
    await expect(page.getByTestId(`my-club-guardians-${club}`)).toBeVisible();

    await openSection(page, "club", "payment-runs");
    await expect(page).toHaveURL(new RegExp(`/me/club/${club}/payment-runs$`));
    await expect(page.getByTestId(`reimbursements-club-${club}`)).toBeVisible();
    await expect(page.getByTestId(`reimbursements-club-${club}-books`)).toBeVisible();
  });
});

describeStory("Z-10: the series is organized in its own context", () => {
  test("the series manager opens the series' Clubs & registrations", async ({ page, request }) => {
    const series = await managedSeries(request, SERIES_MANAGER);
    await signIn(page, SERIES_MANAGER);
    await page.goto("/me");
    await openSwitcher(page);
    await page.getByTestId(`workspace-switcher-series-${series}`).click();
    await expect(page).toHaveURL(new RegExp(`/me/series/${series}`));

    const sections = await listedSections(page, "series");
    for (const section of ["events", "standings", "registrations", "dates", "scoring", "officials"]) {
      expect(sections, `the manager has ${section}`).toContain(section);
    }
    await page.keyboard.press("Escape");

    await openSection(page, "series", "registrations");
    await expect(page).toHaveURL(new RegExp(`/me/series/${series}/registrations$`));
    await expect(page.getByTestId(`me-series-clubs-${series}`)).toBeVisible();
    await expect(page.getByTestId(`admin-series-save-clubs-button-${series}`)).toBeVisible();
  });
});

describeStory("S-5: the club's organizers reach a member's documents from the list", () => {
  test("the club's admin has Documents beside a member; the treasurer has none", async ({ page, request }) => {
    const club = await managedClub(request, CLUB_ADMIN);
    const people = (await (
      await request.get(`/api/clubs/${club}/people?q=${encodeURIComponent(TEAM_MANAGER)}`, {
        headers: await bearer(request, CLUB_ADMIN),
      })
    ).json()) as { items: { user_id: number | null }[] };
    const manager = people.items[0].user_id!;
    const documents = `my-club-member-documents-${manager}-button`;

    await signIn(page, CLUB_ADMIN);
    await page.goto(`/me/club/${club}/people?q=${encodeURIComponent(TEAM_MANAGER)}`);
    await expect(page.getByTestId(documents)).toBeVisible();

    // Not an organizer: the button would only lead to a refusal (#11).
    await signIn(page, "treasurer@asvw.example.com");
    await page.goto(`/me/club/${club}/people?q=Voigt`);
    await expect(page.getByTestId(`my-club-member-relation-${manager}-manager`)).toBeVisible();
    await expect(page.getByTestId(documents)).toHaveCount(0);
  });
});

describeStory("V-5: the team manager applies for a series from the club's Squads", () => {
  test("applying puts it on the list as waiting; withdrawing takes it off", async ({ page, request }) => {
    const club = await managedClub(request, TEAM_MANAGER);
    await signIn(page, TEAM_MANAGER);
    await page.goto(`/me/club/${club}/squads`);
    const select = page.getByTestId(`my-club-apply-series-${club}`);
    await expect(select).toBeVisible();
    const choice = await select.locator("option").nth(1).getAttribute("value");
    await select.selectOption(choice!);
    await page.getByTestId(`my-club-apply-${club}`).click();

    const applications = page.getByTestId(`my-club-applications-${club}`);
    const row = applications.locator("[data-testid^='my-club-application-'][data-testid$='-status']");
    await expect(row).toHaveText(/waiting/);
    // The series is no longer offered, and the application can be withdrawn.
    await expect(select.locator(`option[value="${choice}"]`)).toHaveCount(0);
    await applications.locator("[data-testid$='-withdraw']").click();
    await expect(row).toHaveCount(0);
  });
});

describeStory("VA-6: the series manager adds an act from the series' Events", () => {
  test("New event leads to My space's wizard", async ({ page, request }) => {
    const series = await managedSeries(request, SERIES_MANAGER);
    await signIn(page, SERIES_MANAGER);
    await page.goto(`/me/series/${series}/events`);
    await page.getByTestId("me-series-new-event").click();
    await expect(page).toHaveURL(/\/me\/event\/new$/);
  });
});
