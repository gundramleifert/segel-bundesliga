import { expect, test } from "./fixtures";
import { bearer, signIn } from "./session";

/** Story WL-3: start, recall and finish races from one screen, in a real browser.
 *
 * `api/tests/stories/test_race_control.py` proves the state machine. What only a browser
 * can prove is that the screen offers the right transition at the right moment: Start on a
 * scheduled race, the pad and Finish on a running one — Finish disabled until every boat
 * has a place — and that after the finish the next race is the one on screen, without a
 * reload.
 *
 * The seeded second act of the 1st Segel-Bundesliga is live and two-thirds sailed, so it
 * has a current race. Running this leaves that race finished, which is the state the
 * other specs' assumptions about the seed still hold under (an open race remains).
 */

const LIVE_EVENT = 2; // dsbl-1-2026-act-2
const COMMITTEE = "admin@sbl.example.com";

test.describe("WL-3: as race committee I run one race at a time", () => {
  test("start, tap every boat in finish order, finish — and the next race is up", async ({
    page,
  }) => {
    await signIn(page, COMMITTEE);
    await page.goto(`/events/${LIVE_EVENT}/race-control`);

    const heading = page.getByTestId("race-control-heading");
    await expect(heading).toBeVisible();
    const before = await heading.innerText();
    await expect(page.getByTestId("race-control-status")).toHaveAttribute("data-status", "scheduled");

    // The gun.
    await page.getByTestId("race-control-start").click();
    await expect(page.getByTestId("race-control-status")).toHaveAttribute("data-status", "running");
    const finish = page.getByTestId("race-control-finish");
    await expect(finish).toBeDisabled();

    // Every boat of the event, in the order they cross the line. Sized by the event, not
    // by a league's six: the pad has as many chips as the event has boats.
    const chips = page.getByTestId("race-control-pad").locator("button");
    const count = await chips.count();
    expect(count).toBeGreaterThan(1);
    for (let i = 0; i < count; i += 1) {
      await chips.nth(i).click();
      await expect(chips.nth(i)).toHaveAttribute("data-mark", String(i + 1));
    }
    // Undo and redo the last one: the place is freed and taken again.
    await chips.nth(count - 1).click();
    await expect(chips.nth(count - 1)).toHaveAttribute("data-mark", "");
    await expect(finish).toBeDisabled();
    await chips.nth(count - 1).click();
    await expect(chips.nth(count - 1)).toHaveAttribute("data-mark", String(count));

    await expect(finish).toBeEnabled();
    await finish.click();

    // The next race slides in: a new heading, scheduled, and the banner names the old one.
    await expect(page.getByTestId("race-control-banner")).toBeVisible();
    await expect(heading).not.toHaveText(before);
    await expect(page.getByTestId("race-control-status")).toHaveAttribute("data-status", "scheduled");
  });

  test("a general recall puts the race back and keeps nothing", async ({ page, request }) => {
    await signIn(page, COMMITTEE);
    await page.goto(`/events/${LIVE_EVENT}/race-control`);
    await expect(page.getByTestId("race-control-status")).toHaveAttribute("data-status", "scheduled");

    await page.getByTestId("race-control-start").click();
    await expect(page.getByTestId("race-control-status")).toHaveAttribute("data-status", "running");
    const chips = page.getByTestId("race-control-pad").locator("button");
    await chips.first().click();
    await expect(chips.first()).toHaveAttribute("data-mark", "1");

    await page.getByTestId("race-control-recall").click();
    await expect(page.getByTestId("race-control-status")).toHaveAttribute("data-status", "scheduled");
    await expect(chips.first()).toHaveAttribute("data-mark", "");

    // Nothing is running afterwards — the other specs rely on that.
    const headers = await bearer(request, COMMITTEE);
    const races = (await (
      await request.get(`/api/admin/events/${LIVE_EVENT}/races`, { headers })
    ).json()) as { races: { status: string }[] };
    expect(races.races.some((race) => race.status === "running")).toBeFalsy();
  });

  test("a guest is told the screen is for the committee", async ({ page }) => {
    await page.goto(`/events/${LIVE_EVENT}/race-control`);
    await expect(page.getByTestId("race-control-forbidden")).toBeVisible();
  });
});
