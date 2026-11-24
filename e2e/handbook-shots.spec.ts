import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

import type { APIRequestContext, Page } from "@playwright/test";

import { clipBox, type Clip, drawMarks, hideDevSwitcher, LOCALES, type Mark, maskIbans, SCREENSHOTS } from "./capture";
import { expect, type Season, test } from "./fixtures";
import { bearer, bornIn, managedClub, seededSailors, signIn } from "./session";

/** The handbook's screenshots (`web/src/handbook/*.md`, `![…](shot:<id>)`), captured from
 * the running stack — `.claude/skills/handbook/references/screenshots.md`.
 *
 * Not a test of anything, so it covers no story and stays out of the normal run:
 *
 *   HANDBOOK_SHOTS=1 node_modules/.bin/playwright test e2e/handbook-shots.spec.ts --project chromium --workers 1
 *   HANDBOOK_SHOTS=1 node_modules/.bin/playwright test e2e/handbook-shots.spec.ts --project mobile --grep @phone --workers 1
 *
 * Each shot is taken in English and German (`<id>_<locale>.png`, on the phone
 * `<id>_<locale>_phone.png`), and the two must differ — a missing translation would
 * otherwise give the German page an English picture without anyone noticing. The dev role
 * switcher is hidden in every shot; ids come from the API, never from the seed's order.
 * Privacy: lists with their status only, never an opened scan, document or a full IBAN.
 */

const OUT = fileURLToPath(SCREENSHOTS);

const ADMIN = "admin@sbl.example.com";
const ORGANIZER = "orga@sbl.example.com";
const SITE_RACE_OFFICER = "wl@sbl.example.com";
const EDITOR = "redaktion@sbl.example.com";
const CLUB_ADMIN = "board@asvw.example.com";
const TEAM_MANAGER = "teams@asvw.example.com";
const TREASURER = "treasurer@asvw.example.com";
// The events come from the 2. Liga's practice season (`app/practice.py`, the `season2`
// fixture): its planned act is the test club's to host, its live act is racing. The seed
// has neither — its acts are sailed and named nobody.

type Ids = {
  clubId: number;
  eventId: number;
  liveEventId: number;
  sailor: string;
  /** Made by a shot's `setup`, for the shots that need it. */
  draftClaimId?: number;
};

type Shot = {
  id: string;
  as: (ids: Ids) => string;
  path: (ids: Ids) => string;
  /** Data the shot needs that the seed does not have, made through the API; what it
   * returns is added to the ids. */
  setup?: (request: APIRequestContext, ids: Ids) => Promise<Partial<Ids> | void>;
  /** Clicks after the page loaded — opening a panel. */
  open?: (page: Page, ids: Ids) => Promise<void>;
  waitFor: (ids: Ids) => string;
  clip?: (ids: Ids) => Clip;
  /** On the phone, the viewport instead of the clip. */
  phoneViewport?: boolean;
  /** Changes made to the page before the shot, for privacy. */
  redact?: (page: Page) => Promise<void>;
  /** Where to click, in the order the text names it — at most about three. */
  marks?: (ids: Ids) => Mark[];
  phone: boolean;
};

const tid = (id: string) => `[data-testid="${id}"]`;
/** A `Field` — its label above the control — so the badge does not cover the label. */
const field = (control: string) => `[data-testid^="field-"]:has(${tid(control)})`;

const SHOTS: Shot[] = [
  {
    id: "help-my-space",
    as: (d) => d.sailor,
    path: () => "/me",
    // The whole screen: the switcher, the sections and *Me › Overview* (Story Z-10).
    waitFor: () => tid("me-overview"),
    phone: true,
  },
  {
    // *Me › My clubs* (Story V-15): my clubs, and below, asking another to take me in.
    id: "help-my-clubs",
    as: (d) => d.sailor,
    path: () => "/me/profile/clubs",
    waitFor: () => tid("me-clubs-list"),
    clip: () => ({ from: tid("me-clubs") }),
    marks: () => [{ target: tid("me-clubs-list") }, { target: tid("me-clubs-search") }],
    phone: true,
  },
  {
    id: "help-waiver-card",
    as: (d) => d.sailor,
    path: () => "/me/profile/waivers",
    waitFor: () => tid("account-waivers-list"),
    clip: () => ({ from: tid("account-waivers-card") }),
    marks: () => [{ target: `${tid("account-waivers-list")} [data-testid*="-read-"]` }],
    phone: true,
  },
  {
    id: "help-account-password",
    as: (d) => d.sailor,
    path: () => "/me/profile/account",
    waitFor: () => tid("account-password-form"),
    clip: () => ({ from: tid("account-signin-methods-card") }),
    marks: () => [{ target: tid("account-password-new-input") }, { target: tid("account-password-save-button") }],
    phone: false,
  },
  {
    id: "help-profile-documents",
    as: (d) => d.sailor,
    path: () => "/me/profile/documents",
    waitFor: () => tid("my-space-document-upload"),
    clip: () => ({ from: tid("my-space-document-upload") }),
    marks: () => [
      { target: tid("my-space-document-kind") },
      { target: tid("my-space-document-file-zone") },
      { target: tid("my-space-document-submit") },
    ],
    phone: false,
  },
  {
    id: "help-claim-new",
    as: (d) => d.sailor,
    path: () => "/me/profile/claims",
    waitFor: () => tid("my-space-claim-target"),
    clip: () => ({ from: tid("my-space-claim-new") }),
    marks: () => [
      { target: tid("my-space-claim-target") },
      { target: tid("my-space-claim-title") },
      { target: tid("my-space-claim-create") },
    ],
    phone: false,
  },
  {
    id: "help-claim-items",
    as: (d) => d.sailor,
    path: () => "/me/profile/claims",
    setup: aDraftClaim,
    open: async (page, d) => {
      await page.getByTestId(`my-space-claim-toggle-${d.draftClaimId}`).click();
    },
    waitFor: (d) => tid(`my-space-claim-${d.draftClaimId}-detail`),
    clip: (d) => ({ from: tid(`my-space-claim-${d.draftClaimId}`) }),
    marks: (d) => [
      { target: tid(`my-space-claim-${d.draftClaimId}-add-kind`) },
      { target: tid(`my-space-claim-${d.draftClaimId}-add-submit`) },
      { target: tid(`my-space-claim-${d.draftClaimId}-submit`) },
    ],
    phone: false,
  },
  {
    id: "help-club-members",
    as: () => CLUB_ADMIN,
    path: (d) => `/me/club/${d.clubId}/people`,
    waitFor: () => tid("my-club-people-table"),
    clip: () => ({ from: tid("my-club-people"), maxHeight: 640 }),
    phone: false,
  },
  {
    // The dialog of *＋ Person*, someone on record by email: whom, as what, Add.
    id: "help-club-people",
    as: () => CLUB_ADMIN,
    path: (d) => `/me/club/${d.clubId}/people`,
    open: async (page, d) => {
      await page.getByTestId(`my-club-access-${d.clubId}-open`).click();
      await page.getByTestId(`my-club-access-${d.clubId}-mode-email`).check();
    },
    waitFor: (d) => tid(`my-club-access-${d.clubId}-relation-member`),
    clip: (d) => ({ from: tid(`my-club-access-${d.clubId}-dialog`), pad: 8 }),
    marks: (d) => [
      { target: `label:has(${tid(`my-club-access-${d.clubId}-email`)})` },
      { target: tid(`my-club-access-${d.clubId}-relation`) },
      { target: tid(`my-club-access-${d.clubId}-add`) },
    ],
    phone: false,
  },
  {
    id: "help-club-squad",
    as: () => TEAM_MANAGER,
    path: (d) => `/me/club/${d.clubId}/squads`,
    open: async (page) => {
      await page.locator('[data-testid^="my-club-team-toggle-"]').first().click();
    },
    waitFor: () => tid("admin-squad-management"),
    clip: () => ({ from: tid("admin-squad-management") }),
    marks: () => [
      { target: '[data-testid^="admin-squad-panes-available-row-"]' },
      { target: '[data-testid^="admin-squad-role-"]' },
      { target: tid("admin-squad-save") },
    ],
    phone: false,
  },
  {
    id: "help-club-lineup",
    as: () => TEAM_MANAGER,
    path: (d) => `/me/club/${d.clubId}/crews`,
    open: async (page, d) => {
      await page.getByTestId(`my-club-event-toggle-${d.eventId}`).click();
    },
    waitFor: (d) => tid(`my-club-lineup-${d.eventId}`),
    clip: (d) => ({ from: tid(`my-club-lineup-${d.eventId}`) }),
    marks: (d) => [
      { target: `[data-testid^="my-club-lineup-${d.eventId}-panes-available-row-"]` },
      { target: `[data-testid^="my-club-lineup-${d.eventId}-role-"]` },
      { target: tid(`my-club-lineup-${d.eventId}-save`) },
    ],
    phone: true,
  },
  {
    id: "help-club-waivers",
    as: () => TEAM_MANAGER,
    path: (d) => `/me/club/${d.clubId}/waivers`,
    waitFor: () => tid("my-club-waivers-list"),
    clip: () => ({ from: tid("my-club-waivers-list"), maxHeight: 700 }),
    phone: false,
  },
  {
    // Only the site's admin creates through the wizard.
    id: "help-event-wizard",
    as: () => ADMIN,
    path: () => "/office/events/new",
    waitFor: () => tid("admin-events-create-form"),
    clip: () => ({ from: tid("admin-events-wizard") }),
    marks: () => [{ target: tid("admin-events-title-input") }, { target: tid("admin-events-create-button") }],
    phone: false,
  },
  {
    // The planned act's Publication: its readiness (VA-8) and *Publish*. The seed's act
    // is ready, so its Overview, which shows only what is missing, would be empty.
    id: "help-event-readiness",
    as: () => ORGANIZER,
    path: (d) => `/me/event/${d.eventId}/publication`,
    waitFor: (d) => `[data-testid^="admin-readiness-"][data-testid$="-${d.eventId}"]`,
    clip: () => ({ from: tid("me-event-publication"), maxHeight: 900 }),
    phone: false,
  },
  {
    id: "help-event-checkin",
    as: () => ORGANIZER,
    path: (d) => `/me/event/${d.eventId}/check-in`,
    waitFor: (d) => tid(`admin-manage-event-waivers-summary-${d.eventId}`),
    clip: (d) => ({ from: tid(`admin-manage-event-waivers-section-${d.eventId}`), maxHeight: 700 }),
    phone: false,
  },
  {
    // The live act's closing block in its Race control — the league office's admin reaches
    // every event's context.
    id: "help-close-event",
    as: () => ADMIN,
    path: (d) => `/me/event/${d.liveEventId}/race-control`,
    waitFor: (d) => tid(`admin-manage-event-closing-${d.liveEventId}`),
    clip: (d) => ({ from: tid(`admin-manage-event-closing-${d.liveEventId}`) }),
    marks: (d) => [
      { target: tid(`admin-manage-event-finish-${d.liveEventId}`) },
      { target: tid(`admin-manage-event-cancel-${d.liveEventId}`) },
    ],
    phone: false,
  },
  {
    // The live act: the seed's race officer `regatta@` holds none of the practice acts, so
    // the league office's race officer runs this one.
    id: "help-race-control",
    as: () => SITE_RACE_OFFICER,
    path: (d) => `/events/${d.liveEventId}/race-control`,
    waitFor: () => tid("race-control-pad"),
    clip: () => ({ from: tid("race-control-heading"), to: tid("race-control-ap") }),
    marks: () => [
      { target: 'fieldset:has([data-testid^="race-control-flag-"])' },
      { target: tid("race-control-start-sequence") },
    ],
    phoneViewport: true,
    phone: true,
  },
  {
    // The correction screen of the live act: the race before, the current one, the next.
    id: "help-results-entry",
    as: () => SITE_RACE_OFFICER,
    path: (d) => `/events/${d.liveEventId}/entry`,
    waitFor: () => tid("matchday-results-table"),
    clip: () => ({ from: tid("matchday-results-focus-hint"), to: tid("matchday-results-table-frame") }),
    marks: () => {
      const current = `${tid("matchday-results-table")} tbody tr:nth-child(2)`;
      return [
        { target: `${current} [data-testid^="matchday-results-tap-"]` },
        { target: `${current} [data-testid^="matchday-results-code-select-"]` },
        { target: tid("matchday-results-show-all-toggle") },
      ];
    },
    phone: true,
  },
  {
    id: "help-claims-pending",
    as: () => TREASURER,
    path: (d) => `/me/club/${d.clubId}/decide-claims`,
    setup: aClaimToDecide,
    waitFor: () => tid("reimbursements-list"),
    // The list only — the claims approved and still to pay below it stay out.
    clip: () => ({ from: tid("reimbursements-list") }),
    redact: maskIbans,
    marks: () => {
      const claim = `${tid("reimbursements-list")} > li:first-child`;
      return [
        { target: `${claim} [data-testid$="-approve"]` },
        { target: `${claim} [data-testid$="-reject"]` },
      ];
    },
    phone: false,
  },
  {
    // The SEPA block only, in the club's Payment runs (Story Z-10).
    id: "help-payment-sepa",
    as: () => TREASURER,
    path: (d) => `/me/club/${d.clubId}/payment-runs`,
    setup: aClaimToPay,
    waitFor: (d) => tid(`reimbursements-club-${d.clubId}-sepa-create`),
    clip: (d) => ({ from: tid(`reimbursements-club-${d.clubId}-sepa`) }),
    redact: maskIbans,
    marks: (d) => [
      { target: `${tid(`reimbursements-club-${d.clubId}-sepa-claims`)} > li:first-child label` },
      { target: tid(`reimbursements-club-${d.clubId}-sepa-date`) },
      { target: tid(`reimbursements-club-${d.clubId}-sepa-create`) },
    ],
    phone: false,
  },
  {
    // The league office's sidebar and its Clubs section (the id from when it was tabs).
    id: "help-admin-tabs",
    as: () => ADMIN,
    path: () => "/office/clubs",
    waitFor: () => tid("admin-clubs-list"),
    clip: () => ({ from: tid("workspace-office"), maxHeight: 640 }),
    marks: () => [{ target: tid("admin-clubs-new-button") }],
    phone: false,
  },
  {
    id: "help-admin-series",
    as: () => ADMIN,
    path: () => "/office/series",
    waitFor: () => tid("admin-series-list"),
    clip: () => ({ from: tid("admin-series-section"), maxHeight: 520 }),
    marks: () => {
      const first = `${tid("admin-series-list")} > li:first-child`;
      return [
        { target: tid("admin-series-new-button") },
        { target: `${first} [data-testid^="admin-series-edit-button-"]` },
        { target: `${first} [data-testid^="admin-series-publish-button-"]` },
      ];
    },
    phone: false,
  },
  {
    // The sailor card down to the switch.
    id: "help-profile-public",
    as: (d) => d.sailor,
    path: () => "/me/profile/account",
    waitFor: () => tid("account-profile-public-toggle"),
    clip: () => ({ from: tid("account-profile-card"), to: `label:has(${tid("account-profile-public-toggle")})`, pad: 16 }),
    marks: () => [{ target: `label:has(${tid("account-profile-public-toggle")})` }],
    phone: false,
  },
  {
    // The organizer's menu: My space, profile, help — the league office is the site's.
    id: "help-account-menu",
    as: () => ORGANIZER,
    path: () => "/me",
    open: async (page) => {
      await page.getByTestId("layout-profile-button").click();
    },
    waitFor: () => tid("layout-user-menu"),
    clip: () => ({ from: tid("layout-profile-button"), to: tid("layout-user-menu"), pad: 16 }),
    phone: false,
  },
  {
    id: "help-news-upload-link",
    as: () => EDITOR,
    path: () => "/office/media",
    waitFor: () => tid("admin-import-key-form"),
    clip: () => ({ from: tid("admin-import-key-form"), pad: 16 }),
    marks: () => [
      { target: field("admin-import-key-label-input") },
      { target: field("admin-import-key-context-select") },
      { target: tid("admin-import-key-create-button") },
    ],
    phone: false,
  },
  {
    id: "help-news-post",
    as: () => EDITOR,
    path: () => "/office/news/new",
    waitFor: () => tid("admin-post-form"),
    clip: () => ({ from: tid("admin-post-form"), to: tid("admin-post-preview-button"), pad: 16 }),
    marks: () => [
      { target: field("admin-post-kind-select") },
      { target: field("admin-post-regatta-select") },
      { target: tid("admin-post-publish-button") },
    ],
    phone: false,
  },
];

// ------------------------------------------------------------------------- the ids

/** The event the organizer's shots show, while a shot runs — `afterEach` takes the tuple
 *  back, since other specs count what `orga@` holds on a stack that is reused. */
let organizing: string | undefined;

/** Makes `orga@` the manager of the practice season's planned act, as the seed makes them
 *  of Warnemünde 2027 — a draft with no crews, so no check-in to show. */
async function organize(request: APIRequestContext, event: number): Promise<void> {
  organizing = `event:${event}`;
  const added = await request.post("/api/auth/tuples", {
    headers: await bearer(request, ADMIN),
    data: { user: ORGANIZER, relation: "manager", object: organizing },
  });
  // A run that stopped before its undo left the tuple behind.
  if (!added.ok()) expect(await added.text()).toContain("tuple-exists");
}

test.afterEach(async ({ request }) => {
  if (!organizing) return;
  const headers = await bearer(request, ADMIN);
  const rows = (await (await request.get(`/api/auth/tuples?object=${organizing}`, { headers })).json()) as {
    id: number;
    user: string;
    relation: string;
  }[];
  for (const row of rows.filter((r) => r.user === ORGANIZER && r.relation === "manager")) {
    expect((await request.delete(`/api/auth/tuples/${row.id}`, { headers })).ok()).toBeTruthy();
  }
  organizing = undefined;
});

async function lookUp(request: APIRequestContext, season: Season): Promise<Ids> {
  const clubId = await managedClub(request, TEAM_MANAGER);
  await organize(request, season.planned);
  // An adult of the club with an account, the same one on every run.
  const adults = (await seededSailors(request, "asvw.example.com"))
    .filter((s) => bornIn(s) && bornIn(s) <= new Date().getFullYear() - 18)
    .map((s) => s.email!)
    .sort();
  expect(adults.length, "the seed gives ASVW adult sailors").toBeGreaterThan(0);
  return { clubId, eventId: season.planned, liveEventId: season.live, sailor: adults[0] };
}

// ------------------------------------------------------------------- data for a shot

type ApiResponse = Awaited<ReturnType<APIRequestContext["get"]>>;

async function ok<T = { id: number }>(response: ApiResponse): Promise<T> {
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json() as Promise<T>;
}

type PendingClaim = { id: number; payer_club_id: number | null; action: string | null; title: string };

async function pendingOfTreasurer(request: APIRequestContext): Promise<PendingClaim[]> {
  return ok<PendingClaim[]>(await request.get("/api/claims/pending", { headers: await bearer(request, TREASURER) }));
}

/** A claim on the club by one of its sailors, with two items — submitted unless `draft`.
 * The sailor's bank account is saved first: submitting copies it onto the claim. */
async function aClaim(request: APIRequestContext, ids: Ids, title: string, draft = false): Promise<number> {
  const headers = await bearer(request, ids.sailor);
  // The standard example IBAN of the German banking association — and masked in the shot.
  await ok(
    await request.put("/api/me/bank-account", {
      headers,
      data: { holder: "Bober Daberberg", iban: "DE89 3704 0044 0532 0130 00" },
    }),
  );
  const claim = await ok(await request.post("/api/claims", { headers, data: { title, club_id: ids.clubId } }));
  await ok(
    await request.post(`/api/claims/${claim.id}/items`, {
      headers,
      data: { kind: "travel_car", incurred_on: "2026-07-17", description: "Hamburg – Kiel and back", distance_km: 190 },
    }),
  );
  await ok(
    await request.post(`/api/claims/${claim.id}/items`, {
      headers,
      data: { kind: "per_diem", incurred_on: "2026-07-18", description: "Per diem, two days", amount_cents: 2800 },
    }),
  );
  if (!draft) await ok(await request.post(`/api/claims/${claim.id}/submit`, { headers }));
  return claim.id;
}

/** A submitted claim on the club waiting for the treasurer — made once; a second run
 * finds it there. */
async function aClaimToDecide(request: APIRequestContext, ids: Ids): Promise<void> {
  const pending = await pendingOfTreasurer(request);
  if (pending.some((c) => c.payer_club_id === ids.clubId && c.action === "decide")) return;
  await aClaim(request, ids, "Training weekend Kiel");
}

/** An approved claim the club still owes, and the club's own account saved, so the SEPA
 * block offers its file. */
async function aClaimToPay(request: APIRequestContext, ids: Ids): Promise<void> {
  const treasurer = await bearer(request, TREASURER);
  await ok(
    await request.put(`/api/clubs/${ids.clubId}/bank-account`, {
      headers: treasurer,
      data: { holder: "Akademischer Segelverein Warnemünde", iban: "DE02 1203 0000 0000 2020 51", bic: null },
    }),
  );
  const pending = await pendingOfTreasurer(request);
  if (pending.some((c) => c.payer_club_id === ids.clubId && c.action === "pay")) return;
  const claimId = await aClaim(request, ids, "Coach boat fuel, Kiel Week");
  await ok(await request.post(`/api/claims/${claimId}/approve`, { headers: treasurer, data: { note: null } }));
}

/** A draft claim of the sailor's own, still open to items — made once. */
async function aDraftClaim(request: APIRequestContext, ids: Ids): Promise<Partial<Ids>> {
  const title = "Matchday Warnemünde";
  const mine = await ok<{ id: number; title: string; status: string }[]>(
    await request.get("/api/me/claims", { headers: await bearer(request, ids.sailor) }),
  );
  const draft = mine.find((c) => c.title === title && c.status === "draft");
  return { draftClaimId: draft ? draft.id : await aClaim(request, ids, title, true) };
}

// -------------------------------------------------------------------------- capture

test.describe("Foundations: handbook screenshots", () => {
  test.skip(!process.env.HANDBOOK_SHOTS, "set HANDBOOK_SHOTS=1 to capture the handbook's screenshots");

  for (const shot of SHOTS) {
    test(shot.id, { tag: shot.phone ? ["@phone"] : [] }, async ({ page, request, season2 }, testInfo) => {
      const phone = testInfo.project.name === "mobile";
      test.skip(phone && !shot.phone, "no phone version of this shot");
      if (!phone) await page.setViewportSize({ width: 1280, height: 800 });

      const ids = await lookUp(request, season2);
      Object.assign(ids, (await shot.setup?.(request, ids)) ?? {});
      await signIn(page, shot.as(ids));
      mkdirSync(OUT, { recursive: true });

      // English on the first load only: Playwright leaves the order of several init
      // scripts undefined, so a second one for German is not sure to win. The marker
      // lives in sessionStorage, which survives the tab's navigations.
      await page.addInitScript((first) => {
        if (window.sessionStorage.getItem("shots.language")) return;
        window.sessionStorage.setItem("shots.language", first);
        window.localStorage.setItem("sbl.language", first);
      }, LOCALES[0]);

      const pictures: Buffer[] = [];
      for (const locale of LOCALES) {
        if (locale !== LOCALES[0]) {
          await page.evaluate((value) => window.localStorage.setItem("sbl.language", value), locale);
        }
        await page.goto(shot.path(ids));
        // The stored choice, not `<html lang>`: that attribute is synced on i18next's
        // events, which fire during the synchronous init before the listener is attached.
        expect(await page.evaluate(() => window.localStorage.getItem("sbl.language"))).toBe(locale);
        await hideDevSwitcher(page);
        if (shot.open) {
          // The panel's toggle appears with its list.
          await page.waitForLoadState("networkidle");
          await shot.open(page, ids);
        }
        await expect(page.locator(shot.waitFor(ids)).first()).toBeVisible();
        await page.waitForLoadState("networkidle");
        await shot.redact?.(page);
        const marked = await drawMarks(page, shot.marks?.(ids) ?? []);

        const file = `${OUT}${shot.id}_${locale}${phone ? "_phone" : ""}.png`;
        const picture =
          phone && shot.phoneViewport
            ? await page.screenshot({ path: file })
            : await page.screenshot({
                path: file,
                fullPage: true,
                clip: shot.clip ? await clipBox(page, shot.clip(ids), marked) : undefined,
              });
        pictures.push(picture);
      }
      expect(Buffer.compare(pictures[0], pictures[1]), `${shot.id}: en and de look the same`).not.toBe(0);
    });
  }
});
