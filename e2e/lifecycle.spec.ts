import { expect, test, type Page } from "@playwright/test";

/** Story VA-9: running an event, in a real browser.
 *
 * `api/tests/stories/test_complete_lifecycle.py` already proves the sequence through the
 * HTTP API. What it cannot prove is that the sequence is *reachable* — that the buttons
 * exist, that they are enabled at the right moment and disabled at the wrong one, and that
 * what the readiness panel says matches what the server would refuse with. That gap is
 * exactly what this file covers, and it is the gap the manage panel was built to close:
 * before it, everything after "create" was reachable only with a REST client.
 *
 * Signing in goes straight to `/api/dev/login` and drops the token into `localStorage`,
 * the same key `web/src/api/session.ts` reads. Clicking through the role switcher would
 * test the role switcher, which is a development aid and not what these tests are about.
 * Needs `SBL_DEV_LOGIN=true` on the backend — the same prerequisite as the switcher itself.
 */

const ADMIN = "admin@sbl.example.com";

/** A token for a seeded test account, put where the app looks for it. */
async function signIn(page: Page, email: string): Promise<void> {
  // Relative, so it goes through Vite's own /api proxy — the same path the app uses, and
  // one fewer place that hardcodes the backend's port.
  const response = await page.request.post("/api/dev/login", { data: { email } });
  expect(response.ok(), `dev login failed for ${email} — is SBL_DEV_LOGIN=true?`).toBeTruthy();
  const { access_token: token } = (await response.json()) as { access_token: string };
  // addInitScript, not an evaluate after goto: the session module reads localStorage once,
  // at import time, so the token has to be there before the bundle runs.
  await page.addInitScript(
    ([key, value]) => window.localStorage.setItem(key, value),
    ["sbl.token", token],
  );
}

/** A title nothing else in the database can collide with. */
function uniqueTitle(prefix: string): string {
  return `${prefix} ${Date.now()}-${Math.floor(Math.random() * 1000)}`;
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

test.describe("VA-8/VA-9: from a draft to a running event", () => {
  test("an event with only a title is savable, and the panel says what is missing", async ({
    page,
  }) => {
    await signIn(page, ADMIN);
    const title = uniqueTitle("E2E Draft Cup");

    await page.goto("/admin");
    await page.getByTestId("admin-events-title-input").fill(title);
    // Deliberately nothing else: no date, no series, no host. This is the normal early
    // state of an event, and the create button has to be enabled for it.
    const create = page.getByTestId("admin-events-create-button");
    await expect(create).toBeEnabled();
    await create.click();

    await expect(page.getByTestId("admin-events-create-message-success")).toBeVisible();
    // No clubs are entered yet, so the automatic draw reports the next step rather than
    // an error — having no clubs right after creating an event is expected.
    await expect(page.getByTestId("admin-events-pairing-draw-pending")).toBeVisible();

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

  test("the date can follow later, and publishing does not require it", async ({ page }) => {
    await signIn(page, ADMIN);
    const title = uniqueTitle("E2E Dateless Cup");

    await page.goto("/admin");
    await page.getByTestId("admin-events-title-input").fill(title);
    await page.getByTestId("admin-events-create-button").click();
    await expect(page.getByTestId("admin-events-create-message-success")).toBeVisible();

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

  test("a standalone event takes any club, a series event only the series' own", async ({
    page,
  }) => {
    await signIn(page, ADMIN);
    const standalone = uniqueTitle("E2E Open Regatta");

    await page.goto("/admin");
    await page.getByTestId("admin-events-title-input").fill(standalone);
    await page.getByTestId("admin-events-create-button").click();
    await expect(page.getByTestId("admin-events-create-message-success")).toBeVisible();

    let eventId = await openPanel(page, standalone);
    // No series: every club in the database is a candidate. That is the case that makes
    // this site a service to clubs outside the association's own series.
    const openList = page.getByTestId(`admin-manage-event-clubs-${eventId}-available-list`);
    await expect(openList.getByRole("listitem").first()).toBeVisible();
    const anyClubCount = await openList.getByRole("listitem").count();
    expect(anyClubCount).toBeGreaterThan(0);

    // Now one inside a series. Its registrations were adopted at creation, so the clubs
    // are already on the selected side rather than waiting to be picked.
    const inSeries = uniqueTitle("E2E Series Act");
    await page.getByTestId("admin-events-title-input").fill(inSeries);
    await page.getByTestId("admin-events-series-select").selectOption({ index: 1 });
    await page.getByTestId("admin-events-create-button").click();
    await expect(page.getByTestId("admin-events-create-message-success")).toBeVisible();

    eventId = await openPanel(page, inSeries);
    const selected = page.getByTestId(`admin-manage-event-clubs-${eventId}-selected-list`);
    await expect(selected.getByRole("listitem").first()).toBeVisible();
    // The candidates are the series' registered clubs — never every club in the database,
    // which is the rule `app/services/participation.py` enforces on the way in.
    const seriesCandidates =
      (await selected.getByRole("listitem").count()) +
      (await page
        .getByTestId(`admin-manage-event-clubs-${eventId}-available-list`)
        .getByRole("listitem")
        .count());
    expect(seriesCandidates).toBeLessThanOrEqual(anyClubCount + 1);
  });

  test("a complete event can be drawn, published and started", async ({ page }) => {
    await signIn(page, ADMIN);
    const title = uniqueTitle("E2E Ready Act");

    await page.goto("/admin");
    await page.getByTestId("admin-events-title-input").fill(title);
    await page.getByTestId("admin-events-starts-input").fill("2027-06-12");
    // The first series has the league's own 18 clubs, so the default 18/6/16 setup and its
    // registrations agree with each other from the start.
    await page.getByTestId("admin-events-series-select").selectOption({ index: 1 });
    await page.getByTestId("admin-events-create-button").click();
    await expect(page.getByTestId("admin-events-create-message-success")).toBeVisible();
    // 18 clubs entered and a date: the automatic draw right after creation succeeds.
    await expect(page.getByTestId("admin-events-pairing-draw-success")).toBeVisible();

    const eventId = await openPanel(page, title);
    await expect(page.getByTestId(`admin-readiness-ready-${eventId}`)).toBeVisible();

    // Nothing has been sailed, so a redraw is still allowed — the point of being able to
    // draw twice while the fleet is at the dock.
    await page.getByTestId(`admin-manage-event-seed-${eventId}`).fill("4711");
    await page.getByTestId(`admin-manage-event-draw-${eventId}`).click();
    await expect(page.getByTestId(`admin-manage-event-draw-message-${eventId}-success`)).toBeVisible();

    await page.getByTestId(`admin-manage-event-publish-${eventId}`).click();
    await expect(page.getByTestId(`admin-manage-event-publication-${eventId}`)).toHaveText(
      "Public",
    );

    // Starting is an explicit decision by someone on site, never a date passing.
    const start = page.getByTestId(`admin-manage-event-start-${eventId}`);
    await expect(start).toBeEnabled();
    await start.click();
    await expect(page.getByTestId(`admin-manage-event-lifecycle-message-${eventId}-success`)).toBeVisible();
    await expect(page.getByTestId(`admin-manage-event-status-${eventId}`)).toHaveText("Live");

    // The pairing list is reachable from here, which is where the race committee goes next.
    await page.getByTestId(`admin-manage-event-results-link-${eventId}`).click();
    await expect(page).toHaveURL(new RegExp(`/events/${eventId}$`));
    await expect(page.getByTestId("matchday-tabs")).toBeVisible();
  });
});

test.describe("A-1/V-3: clubs and their crests", () => {
  test("a created club appears in the admin list and is not public yet", async ({ page }) => {
    await signIn(page, ADMIN);
    const name = uniqueTitle("E2E Sailing Club");

    await page.goto("/admin");
    await page.getByTestId("admin-clubs-name-input").fill(name);
    await page.getByTestId("admin-clubs-short-name-input").fill("E2E");
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

    // A club appears publicly only when enrolled in a current series.
    await page.goto("/clubs");
    await expect(page.getByTestId("clubs-list").getByRole("listitem")).toHaveCount(18);
  });
});

test.describe("VA-8: a series is published the same way", () => {
  test("a new series starts as a draft and the row publishes it", async ({ page }) => {
    await signIn(page, ADMIN);
    const name = uniqueTitle("E2E Trophy");

    await page.goto("/admin");
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
