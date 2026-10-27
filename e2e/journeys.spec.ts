import { describeJourney, expect, step, test } from "./fixtures";

/** Journeys walked in the browser — `docs/journeys/`, one `describeJourney` each.
 *
 * A walk here is the stakeholder's half of a journey: the same steps its pytest walk
 * proves through the API, shown on the screens someone actually taps, so an evidence run
 * (`EVIDENCE=1`) leaves a video of the whole way with each step a chapter of the trace.
 */

describeJourney("J-9: a fan follows an act", () => {
  // Read-only, on the seed (`app.seed`): the 1. Liga's 2026 act 1 sailed, act 2 under way
  // with every crew named, act 3 drawn. Its branches (a hidden profile, a missed act) have
  // nothing in the seed to point at; the pytest walk takes them.
  test("from the league's page to the standings", async ({ page }) => {
    await step("J-9.1", "a fan opens the league's page — the act being sailed comes first", async () => {
      await page.goto("/1-liga");
      await expect(page.getByTestId("site-chapter-results")).toBeVisible();
      await expect(page.getByRole("heading", { level: 1 })).toHaveText("Results Act 2");
    });

    await step("J-9.2", "the fan opens the act's page — its tab in the address", async () => {
      await page.getByTestId("site-chapter-results-more").click();
      await expect(page).toHaveURL(/\/1-liga\/2026\/act-2\/results$/);
      await expect(page.getByTestId("site-act-tab-results")).toHaveAttribute("aria-current", "page");
    });

    await step("J-9.3", "the fan reads the interim results, by flight", async () => {
      await expect(page.getByTestId("site-act-results")).toBeVisible();
      await expect(page.getByTestId("matchday-standings-table").locator("tbody tr")).toHaveCount(18);
    });

    await step("J-9.4", "the fan looks up the pairing list — which boat, which race", async () => {
      await page.getByTestId("site-act-tab-pairing").click();
      await expect(page).toHaveURL(/\/act-2\/pairing$/);
      await expect(page.getByTestId("matchday-pairing-table").locator("tbody tr")).toHaveCount(48);
    });

    await step("J-9.5", "the fan sees who sails for each team", async () => {
      await page.getByTestId("site-act-tab-crews").click();
      await expect(page).toHaveURL(/\/act-2\/crews$/);
      await expect(page.getByTestId("matchday-crew-list").locator(":scope > li")).toHaveCount(18);
    });

    await step("J-9.6", "the fan follows a name to the sailor's page", async () => {
      // A link only where the profile is public (Story S-4) — `a`, not the plain-text span.
      await page.locator('a[data-testid^="matchday-crew-sailor-link-"]').first().click();
      await expect(page).toHaveURL(/\/people\/\d+$/);
      await expect(page.getByTestId("sailor-registrations-section")).toBeVisible();
      // This act is among the matchdays they are lined up for (event 2 in the seed).
      await expect(page.getByTestId("sailor-lineup-row-2")).toBeVisible();
    });

    await step("J-9.8", "the fan opens the year's standings — the running act counts", async () => {
      await page.goto("/1-liga");
      await page.getByTestId("site-chapter-standings-more").click();
      await expect(page).toHaveURL(/\/1-liga\/standings$/);
      const table = page.getByTestId("site-standings-dsbl-1-2026");
      await expect(table.getByTestId("site-standings-table").locator("tbody tr")).toHaveCount(18);
      // The act's column heading leads back to the act.
      await table.getByTestId("site-standings-event-link-2").click();
      await expect(page).toHaveURL(/\/1-liga\/2026\/act-2\/results$/);
    });
  });
});
