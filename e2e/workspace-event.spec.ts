import type { APIRequestContext } from "@playwright/test";

import { describeStory, expect, test } from "./fixtures";
import { listedSections, openSection, openSwitcher } from "./layout";
import { bearer, signIn } from "./session";

/** Story Z-10 (#32): an event's own administration as the sections of its context — *Set
 * up* and *Race day* — rather than a panel in the administration's Events tab.
 *
 * `api/tests/stories/test_event_lifecycle.py` proves who may read the event and its
 * readiness there; here the browser proves the way: the event's manager finds it in the
 * switcher and gets the set-up and the race day, and the series' manager reaches the same
 * event from inside — not listed, but opened with the relations the model gives there.
 */

const ORGA = "orga@sbl.example.com";
const SERIES_MANAGER = "serie@sbl.example.com";

type Context = { kind: string; id: number; status?: string; relations: string[] };

/** Act 3 of the 2. Liga — the seeded event `orga@` organizes, still planned. */
async function act3(request: APIRequestContext): Promise<number> {
  const response = await request.get("/api/me/contexts", { headers: await bearer(request, ORGA) });
  expect(response.ok(), await response.text()).toBeTruthy();
  const { contexts } = (await response.json()) as { contexts: Context[] };
  const event = contexts.find((c) => c.kind === "event" && c.relations.includes("manager") && c.status === "planned");
  expect(event, "orga@ organizes a planned event in the seed").toBeTruthy();
  return event!.id;
}

const SET_UP = ["general", "clubs", "boats", "pairing", "publication", "people"];
const RACE_DAY = ["check-in", "race-control", "results", "notice-board"];

describeStory("Z-10: the event's set-up and race day are sections of its context", () => {
  test("the event's manager opens the event from the switcher and works its sections", async ({ page, request }) => {
    const eventId = await act3(request);
    await signIn(page, ORGA);
    await page.goto("/me");
    await openSwitcher(page);
    await page.getByTestId(`workspace-switcher-event-${eventId}`).click();
    await expect(page.getByTestId("workspace-content-event-overview")).toBeVisible();

    // Before the start: Set up first, then Race day, then the money — each once.
    const sections = await listedSections(page, "event");
    expect(sections.slice(0, 1 + SET_UP.length + RACE_DAY.length)).toEqual(["overview", ...SET_UP, ...RACE_DAY]);
    expect(sections).toContain("decide-claims");
    // Built only what has a screen: no trackers yet; editorial is not theirs.
    expect(sections).not.toContain("trackers");
    expect(sections).not.toContain("news");
    await page.keyboard.press("Escape");

    // The administration's own blocks, with their test ids.
    await openSection(page, "event", "general");
    await expect(page.getByTestId("me-event-general-form")).toBeVisible();
    await expect(page.getByTestId(`admin-manage-event-save-dates-${eventId}`)).toBeVisible();
    await openSection(page, "event", "pairing");
    await expect(page.getByTestId(`admin-manage-event-draw-${eventId}`)).toBeVisible();
    await openSection(page, "event", "publication");
    await expect(page.getByTestId(`admin-manage-event-publish-${eventId}`)).toBeVisible();
    await openSection(page, "event", "race-control");
    await expect(page.getByTestId("me-event-race-control-screen-link")).toHaveAttribute(
      "href",
      `/events/${eventId}/race-control`,
    );
    await expect(page.getByTestId(`admin-manage-event-closing-${eventId}`)).toBeVisible();
    await openSection(page, "event", "check-in");
    await expect(page.getByTestId("workspace-content-event-check-in")).toBeVisible();
  });

  test("the series' manager reaches the same event from inside and sets it up", async ({ page, request }) => {
    const eventId = await act3(request);
    await signIn(page, SERIES_MANAGER);
    await page.goto(`/me/event/${eventId}`);
    await expect(page.getByTestId("workspace-content-event-overview")).toBeVisible();
    const sections = await listedSections(page, "event");
    for (const section of SET_UP) expect(sections).toContain(section);
    await page.keyboard.press("Escape");
    await openSection(page, "event", "clubs");
    await expect(page.getByTestId(`admin-manage-event-clubs-${eventId}`)).toBeVisible();
  });
});

describeStory("VA-8: what was set at creation is changed in the event's own sections", () => {
  test("the event's manager renames the event and a boat", async ({
    page,
    request,
  }, testInfo) => {
    const eventId = await act3(request);
    await signIn(page, ORGA);
    await page.goto(`/me/event/${eventId}/general`);
    const title = page.getByTestId("me-event-general-title");
    await expect(title).toBeVisible();
    const renamed = `Act 3 (${testInfo.project.name} ${Date.now() % 100000})`;
    await title.fill(renamed);
    await page.getByTestId("me-event-general-save").click();
    await expect(page.getByTestId("me-event-general-message-success")).toBeVisible();
    const stored = await request.get(`/api/admin/events/${eventId}`, { headers: await bearer(request, ORGA) });
    expect(((await stored.json()) as { title: string }).title).toBe(renamed);

    await openSection(page, "event", "boats");
    const name = page.getByTestId("admin-events-boat-name-input-0");
    const boatName = `Boat one ${testInfo.project.name} ${Date.now() % 100000}`;
    await name.fill(boatName);
    await page.getByTestId("me-event-boats-save").click();
    await expect(page.getByTestId("me-event-boats-message-success")).toBeVisible();
    const boats = await request.get(`/api/admin/events/${eventId}/boats`, { headers: await bearer(request, ORGA) });
    expect(((await boats.json()) as { name: string }[])[0]!.name).toBe(boatName);
  });
});
