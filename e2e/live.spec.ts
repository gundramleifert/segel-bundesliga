import type { APIRequestContext } from "@playwright/test";

import { expect, test } from "./fixtures";
import { bearer } from "./session";

/** Story B-5: follow live updates, in a real browser.
 *
 * `api/tests/stories/test_live_updates.py` proves the stream frames. What only a browser
 * can prove is the story's first criterion: a spectator's page changes when the race
 * committee enters a result, **without anyone reloading**. So: one browser context reads
 * the matchday as a guest, a second one — the committee — writes a result through the API
 * (the results tab's own taps are WL-2's business), and the first page's race count moves
 * on its own.
 *
 * The seeded second act of the 1st Segel-Bundesliga is live and two-thirds sailed, so it
 * has a stream and open races. The result is taken back at the end, so the other specs
 * find the seed the way they expect it.
 */

const LIVE_EVENT = 2; // dsbl-1-2026-act-2
const COMMITTEE = "admin@sbl.example.com";

interface AdminRace {
  id: number;
  entries: { boat_number: number; code: string | null }[];
}

test.describe("B-5: as a spectator I follow live updates", () => {
  test("a result entered elsewhere changes the page without a reload", async ({
    browser,
    page,
    baseURL,
  }) => {
    // The spectator: a guest, one tab, never reloaded.
    await page.goto(`/events/${LIVE_EVENT}`);
    const badge = page.getByTestId("matchday-live-badge");
    await expect(badge).toHaveAttribute("data-state", "live");
    const count = page.getByTestId("matchday-races-count");
    const before = await count.innerText();

    // The race committee, in a second browser context.
    const committee = await browser.newContext({ baseURL });
    const api = committee.request;
    const headers = await bearer(api, COMMITTEE);
    const races = (await (
      await api.get(`/api/admin/events/${LIVE_EVENT}/races`, { headers })
    ).json()) as { races: AdminRace[] };
    const open = races.races.find((race) => race.entries.some((entry) => entry.code === null));
    expect(open, "the seeded live act should still have an open race").toBeTruthy();

    const entered = await api.put(
      `/api/admin/events/${LIVE_EVENT}/races/${open!.id}/result`,
      {
        headers,
        data: {
          results: open!.entries.map((entry, index) => ({
            boat_number: entry.boat_number,
            code: "FINISHED",
            finish_position: index + 1,
          })),
        },
      },
    );
    expect(entered.ok(), await entered.text()).toBeTruthy();

    try {
      // The proof: the count changes on a page nobody touched.
      await expect(count).not.toHaveText(before);
      await expect(badge).toHaveAttribute("data-state", "live");
    } finally {
      // Back to the seed: `code: null` clears a boat's result (Story WL-2).
      const cleared = await api.put(
        `/api/admin/events/${LIVE_EVENT}/races/${open!.id}/result`,
        {
          headers,
          data: { results: open!.entries.map((entry) => ({ boat_number: entry.boat_number, code: null })) },
        },
      );
      expect(cleared.ok(), await cleared.text()).toBeTruthy();
      await committee.close();
    }
  });

  test("/live leads to the running event", async ({ page }) => {
    await page.goto("/live");
    await expect(page).toHaveURL(new RegExp(`/events/${LIVE_EVENT}$`));
    await expect(page.getByTestId("matchday-live-badge")).toBeVisible();
  });
});
