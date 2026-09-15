import type { APIRequestContext, Page } from "@playwright/test";

import { expect, test } from "./fixtures";
import { openNavigation } from "./layout";
import { bearer, signIn } from "./session";

/** Stories V-12 and V-2: the club manager's own screen, with the matchdays and the lineup.
 *
 * `api/tests/stories/test_lineup.py` proves the rule (the crew comes from the squad);
 * `test_my_clubs.py` proves the list. What a browser adds: a club manager finds their
 * club's matchdays on `/club` without any admin route, names a crew there, and the public
 * matchday page shows it; and a person in two clubs picks the one they act for and the
 * choice survives a reload, on `/club` and on `/account` alike.
 */

test.describe.configure({ mode: "serial" });

const ADMIN = "admin@sbl.example.com";
const PLANNED_ACT = 3; // dsbl-1-2026-act-3, planned — the one still to be lined up

type Account = { id: number; email: string; roles: string[] };

async function aClubManager(request: APIRequestContext): Promise<Account> {
  const response = await request.get("/api/dev/users");
  expect(response.ok(), "is SBL_DEV_LOGIN=true?").toBeTruthy();
  const accounts = (await response.json()) as Account[];
  // The seed creates one manager per club; NRV's is in every seeded series' squads too.
  const manager = accounts.find(
    (a) => a.roles.includes("club_manager") && a.email.endsWith("@nrv.example.com"),
  );
  expect(manager, "the seed creates one club_manager per club").toBeTruthy();
  return manager!;
}

async function openMyClub(
  page: Page,
  tab: "members" | "events" | "series" = "events",
  clubId?: number,
): Promise<void> {
  // `club=` explicitly where it matters: the account remembers the last club chosen, and
  // an earlier test may have left it on one where this person is a plain member.
  await page.goto(`/club?tab=${tab}${clubId ? `&club=${clubId}` : ""}`);
  await expect(page.getByTestId("layout-breadcrumb")).toBeVisible();
  await expect(page.getByTestId(`my-club-${tab}-tab`)).toHaveAttribute("aria-selected", "true");
}

test.describe("V-2/V-12: as a club manager I name the crew for a matchday from /club", () => {
  test("the matchdays are listed and a crew is named from the squad", async ({ page, request }) => {
    const manager = await aClubManager(request);
    // The second test below leaves the account acting for another club, and the two
    // browser projects share one stack — so start from "no club chosen" explicitly.
    const reset = await request.patch("/api/auth/me", {
      headers: await bearer(request, manager.email),
      data: { club_id: null },
    });
    expect(reset.ok(), await reset.text()).toBeTruthy();
    await signIn(page, manager.email);
    await openMyClub(page);
    await expect(page.getByTestId("my-club-events-list")).toBeVisible();

    // Every seeded act of the first league is there — "these three", not "exactly three":
    // the lifecycle spec adds events to this series on the same stack (see docs/gotchas).
    for (const act of [1, 2, 3]) {
      await expect(page.getByTestId(`my-club-event-${act}`)).toBeVisible();
    }

    await page.getByTestId(`my-club-event-toggle-${PLANNED_ACT}`).click();
    const prefix = `my-club-lineup-${PLANNED_ACT}`;
    await expect(page.getByTestId(prefix)).toBeVisible();
    await expect(page.getByTestId(`${prefix}-size-hint`)).toBeVisible();

    // The squad is on the left, not a search over everyone; a click moves a person to the
    // right, where their role for the day sits beside them; Save writes the list.
    const panes = `${prefix}-panes`;
    const available = page.getByTestId(`${panes}-available-list`).getByRole("listitem");
    await expect(available.first()).toBeVisible();
    const before = await available.count();
    const firstId = (await available.first().locator("button").getAttribute("data-testid"))!.replace(
      `${panes}-available-`,
      "",
    );
    await page.getByTestId(`${panes}-available-${firstId}`).click();
    await expect(page.getByTestId(`${panes}-selected-${firstId}`)).toBeVisible();
    await expect(available).toHaveCount(before - 1);
    await page.getByTestId(`${prefix}-role-${firstId}`).selectOption("substitute");
    await expect(page.getByTestId(`${prefix}-unsaved`)).toBeVisible();
    await page.getByTestId(`${prefix}-save`).click();
    await expect(page.getByTestId(`${prefix}-message-success`)).toBeVisible();

    // The lineup survives a reload — it was written, not kept in the page.
    await page.reload();
    await expect(page.getByTestId(`${panes}-selected-${firstId}`)).toBeVisible();
    await expect(page.getByTestId(`${prefix}-role-${firstId}`)).toHaveValue("substitute");

    // And the public matchday page shows the same person in the crew tab.
    const teams = (await (await request.get(`/api/events/${PLANNED_ACT}/crew`)).json()) as {
      teams: { team: { id: number }; crew: { id: number }[] }[];
    };
    const named = teams.teams.find((t) => t.crew.some((c) => c.id === Number(firstId)));
    expect(named, "the crew is on the public matchday").toBeTruthy();
    await page.goto(`/events/${PLANNED_ACT}?view=crew`);
    await expect(
      page.getByTestId(`matchday-crew-row-${named!.team.id}-${firstId}`),
    ).toBeVisible();
  });

  test("a person in two clubs picks the one they act for, and it is remembered", async ({
    page,
    request,
  }) => {
    const manager = await aClubManager(request);
    // Make them a member of a second club as well. Membership is mutual consent (Story
    // V-7): the club invites, the person accepts.
    const admin = await bearer(request, ADMIN);
    const clubs = (await (await request.get("/api/admin/clubs?limit=50", { headers: admin })).json()) as {
      items: { id: number; slug: string; name: string }[];
    };
    const second = clubs.items.find((c) => c.slug === "kyc")!;
    const invited = await request.post(`/api/admin/clubs/${second.id}/members`, {
      headers: admin,
      data: { email: manager.email },
    });
    if (invited.ok()) {
      const membershipId = ((await invited.json()) as { id: number }).id;
      const accepted = await request.post(`/api/club-memberships/${membershipId}/accept`, {
        headers: await bearer(request, manager.email),
      });
      expect(accepted.ok(), await accepted.text()).toBeTruthy();
    } else {
      // The other browser project ran first on this stack and the membership exists.
      expect(invited.status(), await invited.text()).toBe(409);
    }

    await signIn(page, manager.email);
    await openMyClub(page, "series");
    // Two clubs: "Our club" in the navigation has one sub-entry per club (Story V-12).
    await openNavigation(page);
    const subEntry = page.getByTestId(`layout-nav-myClub-${second.id}`);
    await expect(subEntry).toBeVisible();
    await subEntry.click();
    await expect(page).toHaveURL(new RegExp(`club=${second.id}`));
    // A member, not an organizer, of the second club: the squad is shown read-only.
    await page.getByTestId("my-club-series-tab").click();
    await page.locator('[data-testid^="my-club-team-toggle-"]').first().click();
    await expect(page.getByTestId("admin-squad-management")).toBeVisible();
    await expect(page.getByTestId("admin-squad-add-search-input")).toHaveCount(0);

    // Remembered: a fresh visit without the URL parameter opens the chosen club, and
    // the account page names it.
    await page.goto("/club");
    await expect(page).toHaveURL(new RegExp(`club=${second.id}`));
    await expect(page.getByTestId(`my-club-role-${second.id}`)).toBeVisible();
    await page.goto("/account");
    await expect(page.getByTestId("account-active-club-select")).toHaveValue(String(second.id));
  });
});

test.describe("V-8/Z-5/A-8: the Members tab — invite, accept on the club page, make organizer", () => {
  test("an organizer invites someone, they accept on the club page, and become an organizer", async ({
    page,
    request,
  }) => {
    const manager = await aClubManager(request);
    const guest = "gast@sbl.example.com"; // seeded, no club, no role
    const clubs = (await (await request.get("/api/clubs/mine", { headers: await bearer(request, manager.email) })).json()) as {
      club: { id: number };
      may_manage: boolean;
    }[];
    const club = clubs.find((c) => c.may_manage)!.club;

    // Clean slate for the guest with this club, whatever an earlier project run left.
    const guestHeaders = await bearer(request, guest);
    const own = (await (await request.get("/api/club-memberships", { headers: guestHeaders })).json()) as {
      id: number;
      club: { id: number };
    }[];
    for (const row of own.filter((r) => r.club.id === club.id)) {
      await request.delete(`/api/club-memberships/${row.id}`, { headers: guestHeaders });
    }

    // The organizer invites by email on the Members tab.
    await signIn(page, manager.email);
    await openMyClub(page, "members", club.id);
    await expect(page.getByTestId("my-club-members")).toBeVisible();
    await page.getByTestId("my-club-invite-email").fill(guest);
    await page.getByTestId("my-club-invite-button").click();
    await expect(page.getByTestId("my-club-invite-message-success")).toBeVisible();
    await expect(page.locator('[data-testid^="my-club-invited-"]').filter({ hasText: guest })).toBeVisible();

    // The guest finds the invitation on the club's public page and accepts.
    await page.context().clearCookies();
    await signIn(page, guest);
    await page.goto(`/clubs/${club.id}`);
    await expect(page.getByTestId("club-join-status")).toBeVisible();
    await page.getByTestId("club-join-accept").click();
    await expect(page.getByTestId("club-join-open")).toBeVisible();
    // A member now: "Our club" is in the navigation and the roster lists them.
    await page.getByTestId("club-join-open").click();
    await expect(page.getByTestId("my-club-members-list")).toBeVisible();
    const guestId = ((await (await request.get("/api/auth/me", { headers: guestHeaders })).json()) as { id: number }).id;
    await expect(page.getByTestId(`my-club-member-${guestId}`)).toBeVisible();
    // No invite form for a plain member, but the way out.
    await expect(page.getByTestId("my-club-invite-email")).toHaveCount(0);
    await expect(page.getByTestId("my-club-leave")).toBeVisible();

    // Back as the organizer: promote them.
    await signIn(page, manager.email);
    await openMyClub(page, "members", club.id);
    await page.getByTestId(`my-club-member-organizer-${guestId}`).click();
    await expect(page.getByTestId(`my-club-member-organizer-badge-${guestId}`)).toBeVisible();
    // And take it back, so the seed's one-manager-per-club still holds for other specs.
    await page.getByTestId(`my-club-member-organizer-${guestId}`).click();
    await expect(page.getByTestId(`my-club-member-organizer-badge-${guestId}`)).toHaveCount(0);
    await page.getByTestId(`my-club-member-remove-${guestId}`).click();
    await expect(page.getByTestId(`my-club-member-${guestId}`)).toHaveCount(0);
  });
});
