import { expect, test } from "./fixtures";

/** Stories L-1, L-2 and the goal of 2026-09-15: a whole race, simulated, on a real map.
 *
 * `api/tests/stories/test_live_tracking.py` proves the analysis and the endpoints. What
 * only a browser can prove is that the picture *moves*: the emulation starts the current
 * race, the markers on the map change position without a reload, the panel ranks the
 * boats with a speed, the race finishes on its own, and the next race is announced.
 *
 * The emulation is started through the development endpoint (`SBL_DEV_LOGIN=true` on the
 * stack) rather than the page's own button, which a built bundle only shows with
 * `VITE_DEV_TOOLS=true`; the endpoint is the same thing the button calls.
 */

const LIVE_EVENT = 2; // dsbl-1-2026-act-2, live and two-thirds sailed

test.describe("L-1/L-2: as a spectator I watch a simulated race on the map", () => {
  test("the boats move, are ranked with a speed, finish, and the next race is up", async ({
    page,
    request,
  }) => {
    test.setTimeout(120_000);
    await page.goto(`/events/${LIVE_EVENT}/live`);
    await expect(page.getByTestId("live-map")).toBeVisible();
    await expect(page.getByTestId("live-badge")).toHaveAttribute("data-state", "live");

    // The committee (here: the dev endpoint) simulates the current race, fast.
    const started = await request.post("/api/dev/emulate", {
      data: { event_id: LIVE_EVENT, speed: 25, races: 1, seed: 11, leg_length_m: 200 },
    });
    expect(started.ok(), await started.text()).toBeTruthy();

    try {
      // A boat appears and moves — a real position change, on a page nobody touched.
      const boat = page.getByTestId("live-boat-marker-1");
      await expect(boat).toBeVisible({ timeout: 30_000 });
      await expect(page.getByTestId("live-race-heading")).toContainText("running", { timeout: 30_000 });
      const before = await boat.getAttribute("data-lat");
      await expect
        .poll(async () => boat.getAttribute("data-lat"), { timeout: 30_000 })
        .not.toBe(before);

      // The panel: every boat with a rank, and a speed once it is under way — the fleet
      // holds station below the line until shortly before the gun.
      const rows = page.getByTestId("live-panel").locator("tbody tr");
      await expect(rows).toHaveCount(6, { timeout: 30_000 });
      await expect(page.getByTestId("live-boat-rank-1")).not.toHaveText("–", { timeout: 30_000 });
      await expect
        .poll(async () => Number(await page.getByTestId("live-boat-speed-1").innerText()), {
          timeout: 30_000,
        })
        .toBeGreaterThan(0);

      // The finish: the race ends by itself, the detected order is shown, the next is up.
      await expect(page.getByTestId("live-race-heading")).toContainText("finished", { timeout: 90_000 });
      await expect(page.getByTestId("live-detected-order")).toBeVisible();
      await expect(page.getByTestId("live-next-race")).toBeVisible();
    } finally {
      // Whatever happened above, leave no race running: the race-control spec on the same
      // stack expects the current race to be scheduled.
      await expect
        .poll(
          async () => {
            const live = (await (await request.get(`/api/events/${LIVE_EVENT}/live`)).json()) as {
              race: { status: string } | null;
            };
            return live.race?.status ?? "none";
          },
          { timeout: 90_000 },
        )
        .not.toBe("running");
    }
  });
});
