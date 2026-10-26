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
  test("the team manager has People, Racing and Money, not the club's page", async ({ page, request }) => {
    const club = await managedClub(request, TEAM_MANAGER);
    await signIn(page, TEAM_MANAGER);
    await page.goto(`/me/club/${club}`);
    const sections = await listedSections(page, "club");
    for (const section of [
      "people", "minors", "waivers", // People
      "squads", "crews", "hosting", // Racing
      "decide-claims", "payment-runs", "bank-account", // Money
    ]) {
      expect(sections, `the manager has ${section}`).toContain(section);
    }
    expect(sections).not.toContain("club-page");
    await page.keyboard.press("Escape");

    // The address of a section that is not theirs leads to the club's overview.
    await page.goto(`/me/club/${club}/club-page`);
    await expect(page.getByTestId("workspace-content-club-overview")).toBeVisible();

    // *People*: the club's people, and the way to add one (#45).
    await openSection(page, "club", "people");
    await expect(page.getByTestId("my-club-people-table")).toBeVisible();
    await expect(page.getByTestId(`my-club-access-${club}-open`)).toBeVisible();
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
