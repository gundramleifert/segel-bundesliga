import { describeStory, expect, test } from "./fixtures";
import { bearer, signIn } from "./session";

/** An act scored on SAP Sailing, set up through the organizer's screen — against a real
 *  SAP, so only when one is named: `SAP_URL` (the local one, `deploy/sap-local/`, never
 *  SAP's hosted server) and the stack's backend given SAP's account (`SBL_SAP_*`, as
 *  `tilt up` does). Without either the group is skipped, not failed.
 *
 *    SAP_URL=http://127.0.0.1:8888 pnpm exec playwright test e2e/sap-scoring.spec.ts --workers 1
 */
const SAP_URL = process.env.SAP_URL;
const SAP_AUTH = `${process.env.SAP_USER ?? "admin"}:${process.env.SAP_PASSWORD ?? "admin"}`;
const ADMIN = "admin@sbl.example.com";
const SERIES = "dsbl-1-2027"; // the seed's 1. Liga 2027, its clubs from the 2026 tables

type Item = { id: number; slug: string; matchday: number; starts_on: string | null };

describeStory("VA-14/VA-15/WL-5: an act is scored on SAP Sailing", () => {
  test.skip(!SAP_URL, "no SAP_URL — a local SAP Sailing (deploy/sap-local/) is needed");

  test("the organizer chooses SAP, sends the act and fetches its results", async ({ page }) => {
    const headers = await bearer(page.request, ADMIN);
    const series = ((await (await page.request.get("/api/admin/series?size=100", { headers })).json()).items as Item[])
      .find((s) => s.slug === SERIES)!;
    const acts = (await (await page.request.get(`/api/admin/events?series_id=${series.id}&size=100`, { headers })).json())
      .items as Item[];
    // Act 2 has no announced date, so neither a draw: arranged here as an organizer would,
    // through the API — what the screen is about is the scoring.
    const act = acts.find((a) => a.matchday === 2)!;
    const access = await (await page.request.get(`/api/events/${act.id}/access`, { headers })).json();
    test.skip(!access.sap, "the stack's backend has no SAP account (SBL_SAP_USER)");
    if (!act.starts_on) {
      await page.request.patch(`/api/admin/events/${act.id}`, {
        headers,
        data: { starts_on: "2027-05-14", ends_on: "2027-05-16" },
      });
    }
    const races = await (await page.request.get(`/api/admin/events/${act.id}/races`, { headers })).json();
    if (!races.races.length) {
      const drawn = await page.request.post(`/api/admin/events/${act.id}/pairing/from-catalog`, {
        headers,
        data: { seed: 2 },
      });
      expect(drawn.ok(), await drawn.text()).toBeTruthy();
    }

    await signIn(page, ADMIN);
    await page.goto(`/me/event/${act.id}/scoring`);
    const source = page.getByTestId("me-event-scoring-source");
    await expect(source).toBeEnabled();
    await source.selectOption("sap");
    await expect(page.getByTestId("me-event-scoring-send")).toBeVisible();

    await page.getByTestId("me-event-scoring-send").click();
    await expect(page.getByTestId("me-event-scoring-send-success")).toContainText("18");
    const leaderboard = page.getByTestId("me-event-scoring-leaderboard");
    await expect(leaderboard).toContainText("1. Segel-Bundesliga 2027");
    await expect(page.getByTestId("me-event-scoring-sap-attribution")).toBeVisible();

    // The act is at SAP now: its leaderboard, with the act's 18 teams.
    const name = (await (await page.request.get(`/api/admin/events/${act.id}`, { headers })).json()).sap_leaderboard as string;
    // Polled: right after a send SAP may still be building the leaderboard (a re-send
    // answers before SAP lists it again).
    const competitors = async () => {
      const board = await page.request.get(`${SAP_URL}/sailingserver/api/v2/leaderboards/${encodeURIComponent(name)}`, {
        headers: { Authorization: `Basic ${Buffer.from(SAP_AUTH).toString("base64")}` },
      });
      return board.ok() ? ((await board.json()).competitors as unknown[]).length : board.status();
    };
    await expect.poll(competitors, { timeout: 15_000 }).toBe(18);

    await page.getByTestId("me-event-scoring-fetch").click();
    await expect(page.getByTestId("me-event-scoring-fetch-success")).toBeVisible();

    // Race day: our race control steps aside for SAP's Race Manager app.
    await page.goto(`/me/event/${act.id}/race-control`);
    await expect(page.getByTestId("me-event-race-control-on-sap")).toBeVisible();
    await expect(page.getByTestId("me-event-race-control-screen")).toHaveCount(0);
  });
});
