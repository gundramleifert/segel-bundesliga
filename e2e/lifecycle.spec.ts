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

/** The seeded series with the league's own 18 clubs registered to it.
 *
 *  Selected **by name**, never by index: the admin series list is ordered by year
 *  descending, so any series a previous run created for a later year sorts above this one —
 *  and picking it by position quietly tested an empty series instead. */
const LEAGUE_SERIES = "1. Segel-Bundesliga 2026";

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

/** Opens the admin page and waits until its data has actually arrived.
 *
 *  Not ceremony: filling a form the instant `/admin` responds submits while the page's own
 *  queries are still in flight, and the list then renders the pre-submit response — a state
 *  no person reaches, because nobody types faster than the first paint. Waiting for the
 *  lists makes the test do what a user does. (Once the list has loaded, a create *is*
 *  reflected immediately — verified separately.)
 *
 *  The catalog select is the "form is ready" signal: the create button cannot be used as
 *  one, because it is also disabled while the title is empty. */
async function openAdmin(page: Page): Promise<void> {
  await page.goto("/admin");
  await expect(page.getByTestId("admin-clubs-list")).toBeVisible();
  await expect(page.getByTestId("admin-manage-events-list")).toBeVisible();
  await expect(page.getByTestId("admin-events-catalog-select")).toBeVisible();
  await expectNoZoomOut(page);
}

/** Fails if the browser had to zoom the page out to fit its own content.
 *
 * This is the guard for Story A-10, and it earns its place: while the admin page overflowed
 * horizontally, mobile Chromium answered by scaling the whole page down — a 412px viewport
 * laid out as 754px — and every click then landed on a neighbouring element. The symptom
 * read as "these buttons are broken", not as "this page is too wide", which cost an
 * afternoon. `window.innerWidth` is the layout viewport, so comparing it against the
 * viewport Playwright actually configured catches the zoom-out directly, and
 * `scrollWidth` catches the overflow that causes it before it gets that far.
 */
async function expectNoZoomOut(page: Page): Promise<void> {
  const configured = page.viewportSize()!.width;
  const measured = await page.evaluate(() => ({
    innerWidth: window.innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(
    measured.innerWidth,
    `the page was zoomed out to fit its content: laid out at ${measured.innerWidth}px in a ${configured}px viewport`,
  ).toBe(configured);
  expect(
    measured.scrollWidth,
    `the page overflows horizontally (${measured.scrollWidth}px of content in ${configured}px) — a wide table has to scroll inside its own box, not widen the page`,
  ).toBeLessThanOrEqual(configured);
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

    await openAdmin(page);
    await page.getByTestId("admin-events-title-input").fill(title);
    // Deliberately nothing else: no date, no series, no host. This is the normal early
    // state of an event, and the create button has to be enabled for it.
    const create = page.getByTestId("admin-events-create-button");
    await expect(create).toBeEnabled();
    await create.click();

    await expect(page.getByTestId("admin-events-create-message-success")).toBeVisible();
    // No clubs are entered yet, so the automatic draw reports the next step rather than
    // an error — having no clubs right after creating an event is expected.
    //
    // The longer timeout is deliberate and measured, not padding. This notice is the end
    // of a chain: the create succeeds, its `onSuccess` invalidates four queries *and*
    // fires the draw, the server refuses it (409 in ~150ms — verified in the access log),
    // and only the re-render after that shows the notice. Under the `mobile` project's
    // device emulation that last render is repeatedly slower than the 5s default, so the
    // assertion failed on roughly one run in five while the application was behaving
    // correctly. The notice always arrives; what varies is when. If it genuinely never
    // came, this still fails — just later.
    await expect(page.getByTestId("admin-events-pairing-draw-pending")).toBeVisible({
      timeout: 20_000,
    });

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

    await openAdmin(page);
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

    await openAdmin(page);
    await page.getByTestId("admin-events-title-input").fill(standalone);
    await page.getByTestId("admin-events-create-button").click();
    await expect(page.getByTestId("admin-events-create-message-success")).toBeVisible();

    let eventId = await openPanel(page, standalone);
    // No series, so every club in the database is a candidate and none is entered yet.
    // That is the case that makes this site a service to clubs outside the association's
    // own series. The seed has 18 clubs; this spec may have added more on earlier runs, so
    // the claim is "at least the league's 18", not an exact count.
    const openList = page.getByTestId(`admin-manage-event-clubs-${eventId}-available-list`);
    await expect(openList.getByRole("listitem").first()).toBeVisible();
    expect(await openList.getByRole("listitem").count()).toBeGreaterThanOrEqual(18);

    // Now one inside a series. Its registrations were adopted at creation, so the clubs are
    // already on the selected side rather than waiting to be picked.
    const inSeries = uniqueTitle("E2E Series Act");
    await page.getByTestId("admin-events-title-input").fill(inSeries);
    await page.getByTestId("admin-events-series-select").selectOption({ label: LEAGUE_SERIES });
    await page.getByTestId("admin-events-create-button").click();
    await expect(page.getByTestId("admin-events-create-message-success")).toBeVisible();

    eventId = await openPanel(page, inSeries);
    // The precise claim, and the reason this test exists: the candidate pool for a series
    // event is the series' **own 18 registered clubs** and nothing else — never every club
    // in the database, which is the rule `app/services/participation.py` enforces on the
    // way in. All 18 were adopted at creation, so they are all on the selected side and
    // the available side is empty. `toHaveCount` auto-waits; a bare `count()` would read
    // the list mid-load.
    await expect(
      page.getByTestId(`admin-manage-event-clubs-${eventId}-selected-list`).getByRole("listitem"),
    ).toHaveCount(18);
    // ...and nothing is left to pick. Asserted via the empty-state row, not a count of 0:
    // `ClubSelector` renders one "none available" <li> when the side is empty, so the
    // listitem count is 1 even when there is no club in it.
    await expect(
      page.getByTestId(`admin-manage-event-clubs-${eventId}-available-empty`),
    ).toBeVisible();
  });

  test("a complete event can be drawn, published and started", async ({ page }) => {
    await signIn(page, ADMIN);
    const title = uniqueTitle("E2E Ready Act");

    await openAdmin(page);
    await page.getByTestId("admin-events-title-input").fill(title);
    await page.getByTestId("admin-events-starts-input").fill("2027-06-12");
    // This series has the league's own 18 clubs, so the default 18/6/16 setup and its
    // registrations agree with each other from the start.
    await page.getByTestId("admin-events-series-select").selectOption({ label: LEAGUE_SERIES });
    await page.getByTestId("admin-events-create-button").click();
    await expect(page.getByTestId("admin-events-create-message-success")).toBeVisible();
    // 18 clubs entered and a date: the automatic draw right after creation succeeds.
    //
    // A long timeout on purpose. The draw endpoint itself answers in well under a second
    // (measured), but it is fired from the create mutation's `onSuccess` *after* four query
    // invalidations, so in a dev build it lands behind their refetches and the confirmation
    // can take several seconds to appear. Worth improving in the app — a user watching this
    // line has no idea the work is already done — but it is latency, not a failure.
    await expect(page.getByTestId("admin-events-pairing-draw-success")).toBeVisible({
      timeout: 20_000,
    });

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
    // Lowercase, as `common:status.live` defines it — the badge shows the label, not a
    // capitalised version of the enum.
    await expect(page.getByTestId(`admin-manage-event-status-${eventId}`)).toHaveText("live");

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

    await openAdmin(page);
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
  test("a new series starts as a draft and the row publishes it", async ({ page }) => {
    await signIn(page, ADMIN);
    const name = uniqueTitle("E2E Trophy");

    await openAdmin(page);
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
