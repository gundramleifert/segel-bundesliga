import type { Page } from "@playwright/test";

import { describeStory, expect, test } from "./fixtures";
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

describeStory("WL-3: as race committee I run one race at a time", () => {
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

  test("the 3-2-1-0 sequence: what to do next, the count-in, the sounds, and the start", async ({
    page,
  }) => {
    await spyOnTones(page);
    // Half a minute past the minute: "at the next full minute" waits 30 seconds.
    await page.clock.install({ time: new Date(Math.floor(Date.now() / 60_000) * 60_000 + 30_000) });
    await signIn(page, COMMITTEE);
    await page.goto(`/events/${LIVE_EVENT}/race-control`);
    await expect(page.getByTestId("race-control-status")).toHaveAttribute("data-status", "scheduled");

    const club = page.getByTestId("race-control-flag-up-club");
    const prep = page.getByTestId("race-control-flag-up-preparatory");
    const next = page.getByTestId("race-control-next-signal");
    const countdown = page.getByTestId("race-control-countdown");
    const signals = async () => (await tones(page)).filter((t) => t.length > 0.3).map((t) => t.length);
    const beeps = async () => (await tones(page)).filter((t) => t.length <= 0.3);
    // One second at a time, so the page renders between ticks as it does on a real phone.
    const advance = async (seconds: number) => {
      for (let i = 0; i < seconds; i += 1) await page.clock.runFor(1000);
    };

    // In 15 s, then abort: back to choosing.
    await page.getByTestId("race-control-start-sequence").click();
    await expect(next).toHaveAttribute("data-action", "clubUp");
    await expect(countdown).toHaveText("0:15");
    await page.getByTestId("race-control-cancel-sequence").click();
    await expect(page.getByTestId("race-control-sequence")).toHaveCount(0);

    await page.getByTestId("race-control-sequence-minute").click();
    await expect(next).toHaveAttribute("data-action", "clubUp");
    await expect(club).toHaveAttribute("data-up", "false");

    await advance(30); // 3: club flag up, after a count-in of five beeps
    await expect(club).toHaveAttribute("data-up", "true");
    await expect(prep).toHaveAttribute("data-up", "false");
    await expect(next).toHaveAttribute("data-action", "preparatoryUp");
    await expect.poll(async () => (await signals()).length).toBe(1);
    expect(await beeps()).toHaveLength(5);

    await advance(60); // 2: preparatory flag up
    await expect(prep).toHaveAttribute("data-up", "true");
    await expect(next).toHaveAttribute("data-action", "preparatoryDown");
    await expect.poll(async () => (await signals()).length).toBe(2);

    await advance(60); // 1: preparatory flag down, one long sound
    await expect(prep).toHaveAttribute("data-up", "false");
    await expect(next).toHaveAttribute("data-action", "start");
    await expect.poll(async () => (await signals()).length).toBe(3);
    const [short, , long] = await signals();
    expect(long).toBeGreaterThan(short * 2);

    await advance(60); // 0: club flag down — the start, recorded by itself
    await expect(page.getByTestId("race-control-status")).toHaveAttribute("data-status", "running");
    await expect.poll(async () => (await signals()).length).toBe(4);
    expect(await beeps()).toHaveLength(20);

    // Nothing left running — the other specs rely on that.
    await page.getByTestId("race-control-recall").click();
    await expect(page.getByTestId("race-control-status")).toHaveAttribute("data-status", "scheduled");
  });

  test("the count-in keeps time: beeps one second apart, the signal on the second", async ({
    page,
  }) => {
    // Real time, no fake clock: what is checked is when the tones sound on the audio clock.
    // Booked on the page's timers instead, they came out uneven ("dd....d....d").
    await spyOnTones(page);
    await signIn(page, COMMITTEE);
    await page.goto(`/events/${LIVE_EVENT}/race-control`);
    await expect(page.getByTestId("race-control-status")).toHaveAttribute("data-status", "scheduled");

    await page.getByTestId("race-control-start-sequence").click(); // first signal in 15 s
    // A busy phone: the page's main thread blocked for 300 ms out of every 700. A tone
    // played when a timer gets round to it comes out late; one booked ahead does not.
    await page.evaluate(() => {
      window.setInterval(() => {
        const until = performance.now() + 300;
        while (performance.now() < until) {
          // busy
        }
      }, 700);
    });
    await expect
      .poll(async () => (await tones(page)).filter((t) => t.length > 0.3).length, { timeout: 20_000 })
      .toBe(1);
    await page.getByTestId("race-control-cancel-sequence").click();

    const played = await tones(page);
    expect(played.map((t) => (t.length > 0.3 ? "signal" : "beep"))).toEqual([
      "beep", "beep", "beep", "beep", "beep", "signal",
    ]);
    const gaps = played.slice(1).map((t, i) => t.at - played[i].at);
    for (const gap of gaps) expect(Math.abs(gap - 1)).toBeLessThan(0.02);
  });

  test("AP: up now with two sounds; down in 15 s with one; the club flag a minute after", async ({
    page,
  }) => {
    await spyOnTones(page);
    await page.clock.install({ time: new Date(Math.floor(Date.now() / 60_000) * 60_000 + 10_000) });
    await signIn(page, COMMITTEE);
    await page.goto(`/events/${LIVE_EVENT}/race-control`);
    await expect(page.getByTestId("race-control-status")).toHaveAttribute("data-status", "scheduled");
    await page.getByTestId("race-control-flag-I").click();
    const signals = async () => (await tones(page)).filter((t) => t.length > 0.3);

    const ap = page.getByTestId("race-control-ap");
    const hoisted = page.getByTestId("race-control-signal");
    await ap.click(); // AP up, no sequence running: now, two sounds
    await expect(hoisted).toBeVisible();
    expect(await signals()).toHaveLength(2);

    // Hoisting AP changed the race and the card remounted: the I chosen before survived.
    await expect(page.getByTestId("race-control-flag-I")).toHaveAttribute("aria-pressed", "true");

    await ap.click(); // AP down: a signal of the sequence, 15 s away
    const next = page.getByTestId("race-control-next-signal");
    await expect(next).toHaveAttribute("data-action", "apDown");
    await expect(page.getByTestId("race-control-countdown")).toHaveText("0:15");
    await expect(hoisted).toBeVisible();
    await expect(ap).toBeDisabled(); // the screen hauls it down itself

    await advance(page, 15);
    await expect(hoisted).toHaveCount(0);
    await expect(next).toHaveAttribute("data-action", "clubUp");
    await expect(page.getByTestId("race-control-countdown")).toHaveText("1:00");
    await expect(page.getByTestId("race-control-flag-up-preparatory")).toContainText("I");
    await expect.poll(async () => (await signals()).length).toBe(3);

    await advance(page, 60);
    await expect(page.getByTestId("race-control-flag-up-club")).toHaveAttribute("data-up", "true");
    await page.getByTestId("race-control-cancel-sequence").click();
    await expect(page.getByTestId("race-control-sequence")).toHaveCount(0);
  });

  test("AP during a sequence: at the latest 3 s before the start, not at all in the last 8 s", async ({
    page,
  }) => {
    await spyOnTones(page);
    await page.clock.install({ time: new Date(Math.floor(Date.now() / 60_000) * 60_000 + 10_000) });
    await signIn(page, COMMITTEE);
    await page.goto(`/events/${LIVE_EVENT}/race-control`);
    await expect(page.getByTestId("race-control-status")).toHaveAttribute("data-status", "scheduled");
    const ap = page.getByTestId("race-control-ap");
    const next = page.getByTestId("race-control-next-signal");
    const hoisted = page.getByTestId("race-control-signal");

    // The fake clock also runs on by itself, so every step is measured from the sequence's
    // own start time, read where the screen keeps it.
    // 8.5 s to go: AP still possible. 7.5 s to go: closed (5 s to prepare + 3 s).
    await page.getByTestId("race-control-start-sequence").click();
    await advanceTo(page, -8500);
    await expect(ap).toBeEnabled();
    await page.clock.runFor(1000);
    await expect(ap).toBeDisabled();

    // Again, and AP at 10 s to go: it goes up 3 s before the start, not 15 s after the tap.
    await page.getByTestId("race-control-start-sequence").click();
    await advanceTo(page, -10_000);
    await ap.click();
    await expect(next).toHaveAttribute("data-action", "apUp");
    await expect(page.getByTestId("race-control-countdown")).toHaveText("0:07");
    await expect(page.getByTestId("race-control-flag-up-club")).toHaveAttribute("data-up", "true");

    await advance(page, 7);
    await expect(hoisted).toBeVisible();
    await expect(page.getByTestId("race-control-sequence")).toHaveCount(0);
    await advance(page, 5);
    await expect(page.getByTestId("race-control-status")).toHaveAttribute("data-status", "scheduled");
    const last = (await tones(page)).filter((t) => t.length > 0.3).slice(-2);
    expect(last.map((t) => t.length < 1)).toEqual([true, true]); // two short sounds

    // Leave AP down for the other specs: down in 15 s, then abort the sequence it starts.
    await ap.click();
    await advance(page, 15);
    await expect(hoisted).toHaveCount(0);
    await page.getByTestId("race-control-cancel-sequence").click();
  });

  test("a guest is told the screen is for the committee", async ({ page }) => {
    await page.goto(`/events/${LIVE_EVENT}/race-control`);
    await expect(page.getByTestId("race-control-forbidden")).toBeVisible();
  });
});

/** Every tone the page plays — when it sounds on the audio clock and for how long, in
 *  seconds — by spying on the horn's oscillators. */
async function spyOnTones(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const played: { at: number; length: number }[] = [];
    (window as unknown as { __tones: typeof played }).__tones = played;
    const start = OscillatorNode.prototype.start;
    const stop = OscillatorNode.prototype.stop;
    OscillatorNode.prototype.start = function (when?: number) {
      (this as unknown as { __at: number }).__at = when ?? 0;
      return start.call(this, when);
    };
    OscillatorNode.prototype.stop = function (when?: number) {
      // Only the booking counts; a stop() without a time is an abort cancelling it.
      if (when !== undefined) {
        const at = (this as unknown as { __at: number }).__at;
        played.push({ at, length: when - at });
      }
      return stop.call(this, when);
    };
  });
}

/** The fake clock, one second at a time, so the page renders between ticks as it does on
 *  a real phone. */
async function advance(page: Page, seconds: number): Promise<void> {
  for (let i = 0; i < seconds; i += 1) await page.clock.runFor(1000);
}

/** Advances the fake clock in one-second steps until `offset` ms from the armed
 *  sequence's start (negative: before it), as the screen stored it on the device. */
async function advanceTo(page: Page, offset: number): Promise<void> {
  const remaining = await page.evaluate((offset) => {
    for (let i = 0; i < window.localStorage.length; i += 1) {
      const key = window.localStorage.key(i)!;
      if (!key.startsWith("sbl.start-sequence.")) continue;
      const state = JSON.parse(window.localStorage.getItem(key)!) as {
        kind: string;
        warningAt: number;
      };
      if (state.kind === "armed") return state.warningAt + 180_000 + offset - Date.now();
    }
    throw new Error("no armed sequence on this device");
  }, offset);
  const whole = Math.floor(remaining / 1000);
  await advance(page, whole);
  await page.clock.runFor(Math.max(0, Math.round(remaining - whole * 1000)));
}

async function tones(page: Page): Promise<{ at: number; length: number }[]> {
  return page.evaluate(() => (window as unknown as { __tones: { at: number; length: number }[] }).__tones);
}
