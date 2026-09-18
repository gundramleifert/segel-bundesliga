import { readFileSync } from "node:fs";

import type { Page, TestInfo } from "@playwright/test";

import { expect, test } from "./fixtures";

import { expectNoSidewaysScroll, openNavigation } from "./layout";
import { bearer, signIn } from "./session";

/** Story VA-9: running an event, in a real browser.
 *
 * `api/tests/stories/test_complete_lifecycle.py` already proves the sequence through the
 * HTTP API. What it cannot prove is that the sequence is *reachable* — that the buttons
 * exist, that they are enabled at the right moment and disabled at the wrong one, and that
 * what the readiness panel says matches what the server would refuse with. That gap is
 * exactly what this file covers, and it is the gap the manage panel was built to close:
 * before it, everything after "create" was reachable only with a REST client.
 *
 * Signing in is `e2e/session.ts`'s `signIn` — straight to `/api/dev/login`, no role switcher.
 */

const ADMIN = "admin@sbl.example.com";

/** The seeded series with the league's own 18 clubs registered to it.
 *
 *  Selected **by name**, never by index: the admin series list is ordered by year
 *  descending, so any series a previous run created for a later year sorts above this one —
 *  and picking it by position quietly tested an empty series instead. */
const LEAGUE_SERIES = "1. Segel-Bundesliga 2026";

/** A title nothing else in the database can collide with. */
function uniqueTitle(prefix: string): string {
  return `${prefix} ${Date.now()}-${Math.floor(Math.random() * 1000)}`;
}

type AdminTab = "clubs" | "series" | "events" | "sailors" | "accounts";

/** The element that proves a tab's panel has finished loading, per tab (Story A-11).
 *
 *  One per tab because only the selected panel is mounted now: waiting for the clubs list
 *  while the events tab is open waits forever, and waiting for nothing at all is the race
 *  described on `openAdmin`. Deliberately a list or a populated <select> rather than a
 *  heading — a heading renders before its query answers, so it proves nothing. */
const TAB_READY: Record<AdminTab, string> = {
  clubs: "admin-clubs-list",
  series: "admin-series-list",
  // The list comes first and the wizard opens from the "＋" after it, so the button is
  // the tab's own ready signal; `createEvent` waits for the wizard's catalog select.
  events: "admin-events-new-button",
  sailors: "admin-sailors-table",
  accounts: "admin-accounts-table",
};

/** Opens one tab of the admin page and waits until its data has actually arrived.
 *
 *  Not ceremony: filling a form the instant `/admin` responds submits while the page's own
 *  queries are still in flight, and the list then renders the pre-submit response — a state
 *  no person reaches, because nobody types faster than the first paint. Waiting for the
 *  lists makes the test do what a user does. (Once the list has loaded, a create *is*
 *  reflected immediately — verified separately.)
 *
 *  The tab goes in the URL rather than being clicked: `?tab=` is part of the contract
 *  (Story A-11), so navigating straight to it exercises the deep link every time this
 *  helper is used, and a test about creating an event does not spend its first assertion
 *  on the tab strip. The strip itself is covered by its own test. */
async function openAdmin(
  page: Page,
  testInfo: TestInfo,
  tab: AdminTab = "events",
): Promise<void> {
  await page.goto(`/admin?tab=${tab}`);
  await expect(page.getByTestId(`admin-${tab}-tab`)).toHaveAttribute("aria-selected", "true");
  await expect(page.getByTestId(TAB_READY[tab])).toBeVisible();
  if (tab === "events") {
    await expect(page.getByTestId("admin-manage-events-list")).toBeVisible();
  }
  // Story A-10: the admin page was unusable on a phone because it was too wide, and the
  // symptom was clicks landing on the wrong element rather than anything visibly broken.
  await expectNoSidewaysScroll(page, testInfo);
}

/** The row of the manage list belonging to a freshly created event, opened.
 *
 * The event id isn't known to the test, so the row is found by its title and the id is
 * read back off the row's own testid — every control in the panel is keyed by it.
 */
async function openPanel(page: Page, title: string): Promise<string> {
  const row = page
    .getByTestId("admin-manage-events-list")
    .getByRole("listitem")
    .filter({ hasText: title });
  await expect(row).toHaveCount(1);
  const testId = await row.getAttribute("data-testid");
  const eventId = testId!.replace("admin-manage-event-row-", "");
  await page.getByTestId(`admin-manage-event-toggle-${eventId}`).click();
  return eventId;
}

/** Step 1 of the wizard: fills the general data, creates, and waits for step 2.
 *
 *  The event exists after this — the create request *is* step 1's submit (Story VA-6) —
 *  so every test that only needs an event to exist stops here and skips the rest. */
async function createEvent(
  page: Page,
  title: string,
  options: { series?: string; startsOn?: string } = {},
): Promise<void> {
  // The wizard opens from the "＋" after the list — unless it is already open, which is
  // the case right after "Create another event".
  if (!(await page.getByTestId("admin-events-title-input").isVisible())) {
    await page.getByTestId("admin-events-new-button").click();
  }
  // The catalog select is the "form is ready" signal: the create button cannot be used
  // as one, because it is also disabled while the title is empty.
  await expect(page.getByTestId("admin-events-catalog-select")).toBeVisible();
  await page.getByTestId("admin-events-title-input").fill(title);
  if (options.startsOn) await page.getByTestId("admin-events-starts-input").fill(options.startsOn);
  if (options.series) {
    await page.getByTestId("admin-events-series-select").selectOption({ label: options.series });
  }
  const create = page.getByTestId("admin-events-create-button");
  await expect(create).toBeEnabled();
  await create.click();
  await expect(page.getByTestId("admin-events-create-message-success")).toBeVisible();
  await expect(page.getByTestId("admin-events-steps-2")).toHaveAttribute("data-state", "current");
}

/** Leaves the wizard from step 2 without entering clubs or drawing: the closing screen. */
async function skipToTheEnd(page: Page): Promise<void> {
  await page.getByTestId("admin-events-clubs-skip-button").click();
  await expect(page.getByTestId("admin-events-ready")).toBeVisible();
}

test.describe("VA-6: creating an event in three steps", () => {
  test("the steps are walked in order, and each later one can be left for the panel", async ({ page }, testInfo) => {
    await signIn(page, ADMIN);
    const title = uniqueTitle("E2E Stepwise Cup");

    await openAdmin(page, testInfo);
    // The list of events comes first; the wizard opens from the "＋" after it, and until
    // it is pressed no form is on the screen.
    await expect(page.getByTestId("admin-events-title-input")).toHaveCount(0);
    await page.getByTestId("admin-events-new-button").click();
    // Before anything is typed: step 1 is current and the others are ahead.
    await expect(page.getByTestId("admin-events-steps-1")).toHaveAttribute("data-state", "current");
    await expect(page.getByTestId("admin-events-steps-3")).toHaveAttribute("data-state", "upcoming");

    await createEvent(page, title, { series: LEAGUE_SERIES, startsOn: "2027-08-21" });
    await expect(page.getByTestId("admin-events-steps-1")).toHaveAttribute("data-state", "done");

    // Step 2 → 3 saves the entries; 3 → 2 is a plain step back, nothing is lost.
    await page.getByTestId("admin-events-clubs-next-button").click();
    await expect(page.getByTestId("admin-events-steps-3")).toHaveAttribute("data-state", "current");
    await page.getByTestId("admin-events-draw-back-button").click();
    await expect(page.getByTestId("admin-events-steps-2")).toHaveAttribute("data-state", "current");
    await page.getByTestId("admin-events-clubs-next-button").click();
    await expect(page.getByTestId("admin-events-steps-3")).toHaveAttribute("data-state", "current");

    // The draw can be left for later. The closing screen then says exactly that — and
    // that is the only thing it says is missing, because the rest is complete.
    await page.getByTestId("admin-events-draw-skip-button").click();
    const ready = page.getByTestId("admin-events-ready");
    await expect(ready).toHaveAttribute("data-ready", "false");
    await expect(page.getByTestId("admin-events-ready-missing-pairing")).toBeVisible();
    await expect(page.getByTestId("admin-events-ready-reasons").getByRole("listitem")).toHaveCount(1);

    // Public after the general step, with the field and the draw still to come: the
    // calendar entry precedes the pairing list (Story VA-8), and publishing locks nothing.
    await page.getByTestId("admin-events-publish-button").click();
    await expect(page.getByTestId("admin-events-publication")).toHaveText("Public");
    await expect(page.getByTestId("admin-events-pairing-pdf-link")).toHaveCount(0);

    // Back to the list closes the wizard and leaves the "＋" — and the event is in the
    // list, where the draw is still offered.
    await page.getByTestId("admin-events-close-button").click();
    await expect(page.getByTestId("admin-events-new-button")).toBeVisible();
    const eventId = await openPanel(page, title);
    await expect(page.getByTestId(`admin-readiness-ready-${eventId}`)).toBeVisible();
    await expect(page.getByTestId(`admin-manage-event-draw-${eventId}`)).toBeEnabled();
  });
});

test.describe("VA-8/VA-9: from a draft to a running event", () => {
  test("an event with only a title is savable, and the panel says what is missing", async ({ page }, testInfo) => {
    await signIn(page, ADMIN);
    const title = uniqueTitle("E2E Draft Cup");

    await openAdmin(page, testInfo);
    // Deliberately nothing else: no date, no series, no host. This is the normal early
    // state of an event, and the create button has to be enabled for it.
    await createEvent(page, title);

    // Step 3 is refused visibly while the setup is incomplete — the same reasons the
    // server answers with — rather than fired blind and reported as an error.
    await page.getByTestId("admin-events-clubs-skip-button").click();
    await expect(page.getByTestId("admin-events-ready")).toHaveAttribute("data-ready", "false");
    await expect(page.getByTestId("admin-events-ready-reason-event-dates-missing")).toBeVisible();

    const eventId = await openPanel(page, title);

    // The draft is on the admin list but not in the public calendar.
    await expect(page.getByTestId(`admin-manage-event-publication-${eventId}`)).toHaveText(
      "Draft",
    );

    // Readiness is a list of reasons, not a flag: the organizer has to be told what is
    // missing, and these are the same codes the draw and the start refuse with.
    const reasons = page.getByTestId(`admin-readiness-reasons-${eventId}`);
    await expect(reasons).toBeVisible();
    await expect(page.getByTestId("admin-readiness-reason-event-dates-missing")).toBeVisible();
    await expect(
      page.getByTestId("admin-readiness-reason-pairing-team-count-mismatch"),
    ).toBeVisible();

    // And the draw is refused while they stand — the button is disabled, so the refusal
    // never has to be discovered by pressing it.
    await expect(page.getByTestId(`admin-manage-event-draw-${eventId}`)).toBeDisabled();
    await expect(page.getByTestId(`admin-manage-event-start-${eventId}`)).toBeDisabled();
  });

  test("the date can follow later, and publishing does not require it", async ({ page }, testInfo) => {
    await signIn(page, ADMIN);
    const title = uniqueTitle("E2E Dateless Cup");

    await openAdmin(page, testInfo);
    await createEvent(page, title);
    await skipToTheEnd(page);

    const eventId = await openPanel(page, title);

    // Publishing an incomplete event is allowed on purpose: the calendar entry is often
    // what makes people ask about the missing pieces (Story VA-8).
    await page.getByTestId(`admin-manage-event-publish-${eventId}`).click();
    await expect(page.getByTestId(`admin-manage-event-publication-${eventId}`)).toHaveText(
      "Public",
    );

    // The date arrives once the host confirms the weekend.
    await page.getByTestId(`admin-manage-event-starts-${eventId}`).fill("2027-05-14");
    await page.getByTestId(`admin-manage-event-ends-${eventId}`).fill("2027-05-16");
    await page.getByTestId(`admin-manage-event-save-dates-${eventId}`).click();
    await expect(
      page.getByTestId(`admin-manage-event-dates-message-${eventId}-success`),
    ).toBeVisible();

    // ...and the reason for it is gone from the panel.
    await expect(
      page.getByTestId("admin-readiness-reason-event-dates-missing"),
    ).toHaveCount(0);

    // A published event stays fully editable — publishing locks nothing.
    await expect(page.getByTestId(`admin-manage-event-starts-${eventId}`)).toBeEditable();
  });

  test("a standalone event takes any club, a series event only the series' own", async ({ page }, testInfo) => {
    await signIn(page, ADMIN);
    const standalone = uniqueTitle("E2E Open Regatta");

    await openAdmin(page, testInfo);
    await createEvent(page, standalone);
    // No series, so every club in the database is a candidate and none is entered yet.
    // That is the case that makes this site a service to clubs outside the association's
    // own series. The seed has 18 clubs; this spec may have added more on earlier runs, so
    // the claim is "at least the league's 18", not an exact count.
    const openList = page.getByTestId("admin-events-clubs-available-list");
    await expect(openList.getByRole("listitem").first()).toBeVisible();
    expect(await openList.getByRole("listitem").count()).toBeGreaterThanOrEqual(18);
    await expect(page.getByTestId("admin-events-clubs-mismatch")).toBeVisible();

    // Now one inside a series. Its registrations were adopted at creation, so the clubs are
    // already on the selected side rather than waiting to be picked.
    await skipToTheEnd(page);
    await page.getByTestId("admin-events-another-button").click();
    await expect(page.getByTestId("admin-events-steps-1")).toHaveAttribute("data-state", "current");
    const inSeries = uniqueTitle("E2E Series Act");
    await createEvent(page, inSeries, { series: LEAGUE_SERIES });

    // The precise claim, and the reason this test exists: the candidate pool for a series
    // event is the series' **own 18 registered clubs** and nothing else — never every club
    // in the database, which is the rule `app/services/participation.py` enforces on the
    // way in. All 18 were adopted at creation, so they are all on the selected side and
    // the available side is empty. `toHaveCount` auto-waits; a bare `count()` would read
    // the list mid-load.
    await expect(
      page.getByTestId("admin-events-clubs-selected-list").getByRole("listitem"),
    ).toHaveCount(18);
    // ...and nothing is left to pick. Asserted via the empty-state row, not a count of 0:
    // `ClubSelector` renders one "none available" <li> when the side is empty, so the
    // listitem count is 1 even when there is no club in it.
    await expect(page.getByTestId("admin-events-clubs-available-empty")).toBeVisible();
    await expect(page.getByTestId("admin-events-clubs-mismatch")).toHaveCount(0);
  });

  test("a complete event can be drawn, published and started", async ({ page }, testInfo) => {
    await signIn(page, ADMIN);
    const title = uniqueTitle("E2E Ready Act");

    await openAdmin(page, testInfo);
    // This series has the league's own 18 clubs, so the default 18/6/16 setup and its
    // registrations agree with each other from the start.
    await createEvent(page, title, { series: LEAGUE_SERIES, startsOn: "2027-06-12" });

    // Step 2 confirms the 18 adopted clubs; step 3 draws — enabled, because the setup is
    // complete, and the draw endpoint itself answers in well under a second.
    await page.getByTestId("admin-events-clubs-next-button").click();
    const draw = page.getByTestId("admin-events-draw-button");
    await expect(draw).toBeEnabled();
    await draw.click();
    await expect(page.getByTestId("admin-events-ready")).toHaveAttribute("data-ready", "true");

    // Publishing makes the list public — and only then can it be printed, because the
    // PDF is a public page and a draft answers 404 there (Story VA-8). The link appears
    // only where the server can print; a stack without Java fails here, loudly, rather
    // than passing by skipping the download (Story B-3).
    await page.getByTestId("admin-events-publish-button").click();
    await expect(page.getByTestId("admin-events-publication")).toHaveText("Public");
    const pdfLink = page.getByTestId("admin-events-pairing-pdf-link");
    await expect(pdfLink).toBeVisible();
    const [download] = await Promise.all([page.waitForEvent("download"), pdfLink.click()]);
    expect(download.suggestedFilename()).toMatch(/pairing-list\.pdf$/);
    expect(await download.failure()).toBeNull();
    const bytes = readFileSync(await download.path());
    expect(bytes.subarray(0, 4).toString()).toBe("%PDF");

    const eventId = await openPanel(page, title);
    await expect(page.getByTestId(`admin-readiness-ready-${eventId}`)).toBeVisible();

    // Nothing has been sailed, so a redraw is still allowed — the point of being able to
    // draw twice while the fleet is at the dock.
    await page.getByTestId(`admin-manage-event-seed-${eventId}`).fill("4711");
    await page.getByTestId(`admin-manage-event-draw-${eventId}`).click();
    await expect(page.getByTestId(`admin-manage-event-draw-message-${eventId}-success`)).toBeVisible();

    // Published from the wizard already; the panel shows the same fact.
    await expect(page.getByTestId(`admin-manage-event-publication-${eventId}`)).toHaveText(
      "Public",
    );

    // Starting is an explicit decision by someone on site, never a date passing.
    const start = page.getByTestId(`admin-manage-event-start-${eventId}`);
    await expect(start).toBeEnabled();
    await start.click();
    await expect(page.getByTestId(`admin-manage-event-lifecycle-message-${eventId}-success`)).toBeVisible();
    // Lowercase, as `common:status.live` defines it — the badge shows the label, not a
    // capitalised version of the enum.
    await expect(page.getByTestId(`admin-manage-event-status-${eventId}`)).toHaveText("live");

    // The pairing list is reachable from here, which is where the race committee goes next.
    await page.getByTestId(`admin-manage-event-results-link-${eventId}`).click();
    await expect(page).toHaveURL(new RegExp(`/events/${eventId}$`));
    await expect(page.getByTestId("matchday-tabs")).toBeVisible();
  });
});

test.describe("VA-10: closing an event, and taking it back", () => {
  test("a running event is declared over, then resumed", async ({ page }, testInfo) => {
    await signIn(page, ADMIN);
    const title = uniqueTitle("E2E Closing Act");

    await openAdmin(page, testInfo);
    await createEvent(page, title, { series: LEAGUE_SERIES, startsOn: "2027-07-03" });
    await page.getByTestId("admin-events-clubs-next-button").click();
    await page.getByTestId("admin-events-draw-button").click();
    await expect(page.getByTestId("admin-events-ready")).toHaveAttribute("data-ready", "true");

    const eventId = await openPanel(page, title);

    // Nothing has started, so there is nothing to declare over — and the panel says which
    // of the two is still open to the organizer rather than offering a dead button.
    await expect(page.getByTestId(`admin-manage-event-finish-${eventId}`)).toBeDisabled();
    await expect(page.getByTestId(`admin-manage-event-cancel-${eventId}`)).toBeEnabled();
    await expect(page.getByTestId(`admin-manage-event-reopen-${eventId}`)).toHaveCount(0);

    await page.getByTestId(`admin-manage-event-start-${eventId}`).click();
    await expect(page.getByTestId(`admin-manage-event-status-${eventId}`)).toHaveText("live");

    // Racing is over. Deliberately with no results entered at all: finishing must not
    // require a complete race list, or the button would be unusable on the days the wind
    // dies (Story VA-10).
    const finish = page.getByTestId(`admin-manage-event-finish-${eventId}`);
    await expect(finish).toBeEnabled();
    await finish.click();
    await expect(page.getByTestId(`admin-manage-event-status-${eventId}`)).toHaveText("final");

    // A closed event offers exactly one transition, and it is the one that undoes this.
    await expect(page.getByTestId(`admin-manage-event-finish-${eventId}`)).toHaveCount(0);
    await expect(page.getByTestId(`admin-manage-event-cancel-${eventId}`)).toHaveCount(0);

    // Closing freezes nothing: the dates are still editable while the event is `final`,
    // because a protest heard weeks later still has to land on it.
    await expect(page.getByTestId(`admin-manage-event-starts-${eventId}`)).toBeEditable();

    await page.getByTestId(`admin-manage-event-reopen-${eventId}`).click();
    await expect(page.getByTestId(`admin-manage-event-status-${eventId}`)).toHaveText("live");
  });

  test("a day called off before the start goes back to planned", async ({ page }, testInfo) => {
    await signIn(page, ADMIN);
    const title = uniqueTitle("E2E Called Off");

    await openAdmin(page, testInfo);
    await createEvent(page, title);
    await skipToTheEnd(page);

    const eventId = await openPanel(page, title);

    // Cancelling works from `planned` — a forecast is often bad enough to call a weekend
    // off days before anyone leaves the dock — and needs none of the readiness the draw
    // and the start insist on.
    await page.getByTestId(`admin-manage-event-cancel-${eventId}`).click();
    await expect(page.getByTestId(`admin-manage-event-status-${eventId}`)).toHaveText("cancelled");

    // ...and a cancellation that turns out to be premature costs nothing: a reinstated
    // event returns to `planned`, because it is prepared again rather than resumed.
    await page.getByTestId(`admin-manage-event-reopen-${eventId}`).click();
    await expect(page.getByTestId(`admin-manage-event-status-${eventId}`)).toHaveText("planned");
  });
});

test.describe("A-11: the admin screen is organized in tabs", () => {
  test("the tab is in the URL, survives a reload, and mounts only its own area", async ({
    page,
  }, testInfo) => {
    await signIn(page, ADMIN);
    await openAdmin(page, testInfo, "clubs");

    // The point of the split: the other four areas are not on the page at all. This is
    // also what makes it cheap — an unmounted panel issues none of its queries.
    await expect(page.getByTestId("admin-manage-events-list")).toHaveCount(0);
    await expect(page.getByTestId("admin-sailors-table")).toHaveCount(0);

    // Clicking a tab is a navigation, so the URL follows...
    await page.getByTestId("admin-events-tab").click();
    await expect(page).toHaveURL(/[?&]tab=events/);
    await expect(page.getByTestId("admin-manage-events-list")).toBeVisible();
    await expect(page.getByTestId("admin-clubs-list")).toHaveCount(0);

    // ...which means Back steps between tabs rather than leaving the screen.
    await page.goBack();
    await expect(page.getByTestId("admin-clubs-list")).toBeVisible();

    // A reload comes back to the same tab. Without the URL it would come back to the
    // first one, which is the thing that makes tabbed admin screens annoying.
    await page.goForward();
    await page.reload();
    await expect(page.getByTestId("admin-manage-events-list")).toBeVisible();

    // An unknown tab opens the first one instead of erroring.
    await page.goto("/admin?tab=nonsense");
    await expect(page.getByTestId("admin-clubs-list")).toBeVisible();

    // Five tabs do not fit across a phone; the strip scrolls inside its own box rather
    // than widening the page (Story A-10 is what happens when it does not).
    await expect(page.getByTestId("admin-tabs")).toBeVisible();
    await expectNoSidewaysScroll(page, testInfo);
  });
});

test.describe("A-13: every long list pages, sorts and searches — in the URL", () => {
  test("a page, a sort and a search can be linked and survive a reload", async ({
    page,
  }, testInfo) => {
    await signIn(page, ADMIN);
    await openAdmin(page, testInfo, "sailors");

    const table = page.getByTestId("admin-sailors-table");
    // The name cell, not the whole row: the row also carries the email and the number of
    // registrations, and reading a name out of all three is how this test first searched
    // the sailor list for the word "registration".
    const firstName = () => table.locator("tbody tr").first().locator("td").first();

    // The seed registers a couple of hundred sailors, so there is a second page at all.
    await expect(page.getByTestId("admin-sailors-pager")).toBeVisible();
    const firstOnPageOne = await firstName().textContent();

    // Paging is a URL change, so the page someone is on can be sent to someone else.
    await page.getByTestId("admin-sailors-pager-next").click();
    await expect(page).toHaveURL(/[?&]page=2/);
    await expect(firstName()).not.toHaveText(firstOnPageOne ?? "");

    // ...and it survives a reload, which is the whole reason it is in the URL and not in
    // component state.
    const onPageTwo = await firstName().textContent();
    await page.reload();
    await expect(page).toHaveURL(/[?&]page=2/);
    await expect(firstName()).toHaveText(onPageTwo ?? "");

    // Sorting is the server's, announced to a screen reader, and lands in the URL too.
    await page.getByTestId("admin-sailors-sort-last_name").click();
    await expect(page).toHaveURL(/[?&]sort=last_name/);
    // A new sort goes back to the first page: page two of the old order means nothing.
    await expect(page).not.toHaveURL(/[?&]page=2/);
    await expect(
      table.locator("th").filter({ hasText: /./ }).first(),
    ).toHaveAttribute("aria-sort", "ascending");

    // Clicking the same column again turns it around rather than clearing it.
    await page.getByTestId("admin-sailors-sort-last_name").click();
    await expect(page).toHaveURL(/[?&]sort=-last_name/);

    // Searching is the server's as well — the result may be a single row out of hundreds,
    // which a client-side filter over one page could never find.
    const someone = (await firstName().textContent())?.trim().split(/\s+/).pop() ?? "";
    await page.getByTestId("admin-sailors-search-input").fill(someone);
    await expect(page).toHaveURL(new RegExp(`[?&]q=${encodeURIComponent(someone)}`));
    await expect(firstName()).toContainText(someone);

    // A deep link carries all three at once — the state this story exists for.
    await page.goto(`/admin?tab=sailors&sort=-last_name&q=${encodeURIComponent(someone)}`);
    await expect(page.getByTestId("admin-sailors-search-input")).toHaveValue(someone);
    await expect(firstName()).toContainText(someone);

    await expectNoSidewaysScroll(page, testInfo);
  });
});

test.describe("V-12: a club manager manages their own squad", () => {
  /** A seeded account holding `club_manager`, found rather than hardcoded.
   *
   *  The seed builds its names from a generated list, so `roden.nanisberg1@nrv.example.com`
   *  is stable only until someone touches `app/seed_users.py`. `/api/dev/users` is the same
   *  list the role switcher reads, and asking it keeps this spec pinned to the *role*
   *  rather than to one person's name. */
  async function aClubManager(page: Page): Promise<string> {
    const response = await page.request.get("/api/dev/users");
    expect(response.ok(), "is SBL_DEV_LOGIN=true?").toBeTruthy();
    const accounts = (await response.json()) as { email: string; roles: string[] }[];
    const manager = accounts.find((account) => account.roles.includes("club_manager"));
    expect(manager, "the seed creates one club_manager per club").toBeTruthy();
    return manager!.email;
  }

  test("reaches the squad without ever touching an admin route", async ({ page }, testInfo) => {
    await signIn(page, await aClubManager(page));

    // The defect this story fixes: the permission existed and there was no door. So the
    // claim is about the nav, not about typing a URL.
    await page.goto("/");
    await openNavigation(page);
    const link = page.getByTestId("layout-nav-myClub");
    await expect(link).toBeVisible();
    await link.click();
    await expect(page).toHaveURL(/\/club/);

    // One club, so no sub-entries in the navigation. The breadcrumb is where a page
    // states its name now (Story A-12), so that is what says the right screen arrived;
    // the squads sit under the Series tab, Members opens first.
    await expect(page.getByTestId("layout-breadcrumb")).toBeVisible();
    await expect(page.getByTestId("layout-nav-myClub-select")).toHaveCount(0);
    await page.getByTestId("my-club-series-tab").click();
    await page.locator('[data-testid^="my-club-team-toggle-"]').first().click();
    await expect(page.getByTestId("admin-squad-management")).toBeVisible();
    await expect(page.getByTestId("admin-squad-panes-selected-list")).toBeVisible();

    // Ten is guidance the screen shows, never a rule (Story V-1) — so the hint is there
    // and the panel is usable regardless of what it says.
    await expect(page.getByTestId("admin-squad-size-hint")).toBeVisible();

    // The left pane is a search over the register, and every row says where the person
    // already sails. Not decoration: a person may be registered in several clubs at once,
    // eighteen people in this data share a surname, and the row is the only thing that
    // tells them apart (Story V-1). Whoever is already in this series for another club is
    // shown with that reason and cannot be moved, so the one clicked is an addable one.
    // The seeded squad sits at the series' maximum, so nobody on the left is addable —
    // the limit is set per series and enforced (Story V-1). Raise it the way the league
    // office would, then add one.
    const selected = page.getByTestId("admin-squad-panes-selected-list").getByRole("listitem");
    const squad = (await (
      await page.request.get(
        `/api/admin/teams/${new URL(page.url()).searchParams.get("team")}/members`,
        { headers: await bearer(page.request, ADMIN) },
      )
    ).json()) as { series_id: number; squad_max: number; members: unknown[] };
    const raised = await page.request.patch(`/api/admin/series/${squad.series_id}`, {
      headers: await bearer(page.request, ADMIN),
      data: { squad_max: squad.squad_max + 5 },
    });
    expect(raised.ok(), await raised.text()).toBeTruthy();
    await page.reload();
    await expect(selected.first()).toBeVisible();
    const before = await selected.count();
    await page.getByTestId("admin-squad-panes-filter-input").fill("a");
    const addable = page.getByTestId("admin-squad-panes-available-list").locator("button").first();
    await expect(addable).toBeVisible();
    await addable.click();
    await expect(selected).toHaveCount(before + 1);
    // Moved, not yet written — Save is what writes the list, as for the clubs of an event.
    await expect(page.getByTestId("admin-squad-unsaved")).toBeVisible();
    await page.getByTestId("admin-squad-save").click();
    await expect(page.getByTestId("admin-squad-message-success")).toBeVisible();

    // Story A-10: this screen is used on a phone at least as often as the admin one.
    await expectNoSidewaysScroll(page, testInfo);
  });

  test("the admin screen is still refused, which is the point of the separate route", async ({
    page,
  }) => {
    await signIn(page, await aClubManager(page));
    await page.goto("/admin");
    // Not a redirect and not a blank page — the message says the area is not theirs, and
    // /club is where their work actually is.
    await expect(page.getByTestId("admin-access-error")).toBeVisible();
    await openNavigation(page);
    await expect(page.getByTestId("layout-nav-admin")).toHaveCount(0);
  });
});

test.describe("A-1/V-3: clubs and their crests", () => {
  test("a created club appears in the admin list and is not public yet", async ({ page }, testInfo) => {
    await signIn(page, ADMIN);
    const name = uniqueTitle("E2E Sailing Club");

    await openAdmin(page, testInfo, "clubs");
    await page.getByTestId("admin-clubs-name-input").fill(name);
    // Unique, because the club's URL is built from its abbreviation: a fixed one collides
    // with the club a previous run created and the create fails with a 409.
    await page.getByTestId("admin-clubs-short-name-input").fill(`E${Date.now() % 100000}`);
    await page.getByTestId("admin-clubs-city-input").fill("Kiel");
    await page.getByTestId("admin-clubs-create-button").click();

    await expect(page.getByTestId("admin-clubs-create-message-success")).toBeVisible();
    const row = page
      .getByTestId("admin-clubs-list")
      .getByRole("listitem")
      .filter({ hasText: name });
    await expect(row).toHaveCount(1);
    // The upload button is there whether or not a crest exists — a club without one has
    // no placeholder invented for it (Story V-3).
    await expect(row.getByRole("button").first()).toBeVisible();

    // A club appears publicly only when enrolled in a current series, so the one just
    // created must not be in the public list. Asserting a *count* here would drift as soon
    // as this spec has ever run before; asserting this club's absence is the real claim.
    await page.goto("/clubs");
    await expect(page.getByTestId("clubs-list")).toBeVisible();
    await expect(page.getByTestId("clubs-list").getByText(name, { exact: true })).toHaveCount(0);
  });
});

test.describe("VA-8: a series is published the same way", () => {
  test("a new series starts as a draft and the row publishes it", async ({ page }, testInfo) => {
    await signIn(page, ADMIN);
    const name = uniqueTitle("E2E Trophy");

    await openAdmin(page, testInfo, "series");
    // The list first, the form from the "＋" after it — the same shape as the events tab.
    await page.getByTestId("admin-series-new-button").click();
    await page.getByTestId("admin-series-name-input").fill(name);
    await page.getByTestId("admin-series-year-input").fill("2027");
    await page.getByTestId("admin-series-create-button").click();
    await expect(page.getByTestId("admin-series-create-message-success")).toBeVisible();

    const row = page
      .getByTestId("admin-series-list")
      .getByRole("listitem")
      .filter({ hasText: name });
    await expect(row).toHaveCount(1);
    const seriesId = (await row.getAttribute("data-testid"))!.replace("admin-series-row-", "");

    await expect(page.getByTestId(`admin-series-publication-${seriesId}`)).toHaveText("Draft");
    await page.getByTestId(`admin-series-publish-button-${seriesId}`).click();
    await expect(page.getByTestId(`admin-series-publication-${seriesId}`)).toHaveText("Public");
  });
});
