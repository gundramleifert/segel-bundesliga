import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

import type { APIRequestContext, Page } from "@playwright/test";

import { expect, test } from "./fixtures";
import { bearer, bornIn, managedClub, seededSailors, signIn } from "./session";

/** The handbook's screenshots (`web/src/handbook/*.md`, `![…](shot:<id>)`), captured from
 * the running stack — `.claude/skills/handbook/references/screenshots.md`.
 *
 * Not a test of anything, so it covers no story and stays out of the normal run:
 *
 *   HANDBOOK_SHOTS=1 node_modules/.bin/playwright test e2e/handbook-shots.spec.ts --project chromium
 *   HANDBOOK_SHOTS=1 node_modules/.bin/playwright test e2e/handbook-shots.spec.ts --project mobile --grep @phone
 *
 * Each shot is taken in English and German (`<id>_<locale>.png`, on the phone
 * `<id>_<locale>_phone.png`), and the two must differ — a missing translation would
 * otherwise give the German page an English picture without anyone noticing. The dev role
 * switcher is hidden in every shot; ids come from the API, never from the seed's order.
 * Privacy: lists with their status only, never an opened scan, document or a full IBAN.
 */

const OUT = fileURLToPath(new URL("../web/public/handbook/screenshots/", import.meta.url));
const LOCALES = ["en", "de"] as const;

const ADMIN = "admin@sbl.example.com";
const ORGANIZER = "orga@sbl.example.com";
const SITE_RACE_OFFICER = "wl@sbl.example.com";
const CLUB_ADMIN = "board@nrv.example.com";
const TEAM_MANAGER = "teams@nrv.example.com";
const TREASURER = "treasurer@nrv.example.com";
const TEST_SERIES = "dsbl-1-2026";
const TEST_EVENT = "dsbl-1-2026-act-3"; // the seed's planned act (app/seed_users.py)

type Ids = { clubId: number; eventId: number; liveEventId: number; sailor: string };

/** Where a shot's picture is cut from: one element, or the span from one to another,
 * at most `maxHeight` tall. No clip: the viewport as the person sees it. */
type Clip = { from: string; to?: string; maxHeight?: number };

type Shot = {
  id: string;
  as: (ids: Ids) => string;
  path: (ids: Ids) => string;
  /** Data the shot needs that the seed does not have, made through the API. */
  setup?: (request: APIRequestContext, ids: Ids) => Promise<void>;
  /** Clicks after the page loaded — opening a panel. */
  open?: (page: Page, ids: Ids) => Promise<void>;
  waitFor: (ids: Ids) => string;
  clip?: (ids: Ids) => Clip;
  /** On the phone, the viewport instead of the clip. */
  phoneViewport?: boolean;
  /** Changes made to the page before the shot, for privacy. */
  redact?: (page: Page) => Promise<void>;
  phone: boolean;
};

const tid = (id: string) => `[data-testid="${id}"]`;

const SHOTS: Shot[] = [
  {
    id: "help-my-space",
    as: (d) => d.sailor,
    path: () => "/me",
    waitFor: () => tid("me-overview"),
    clip: () => ({ from: tid("me-overview") }),
    phone: true,
  },
  {
    id: "help-waiver-card",
    as: (d) => d.sailor,
    path: () => "/me/profile?tab=waivers",
    waitFor: () => tid("account-waivers-list"),
    clip: () => ({ from: tid("account-waivers-card") }),
    phone: true,
  },
  {
    id: "help-club-members",
    as: () => CLUB_ADMIN,
    path: (d) => `/me/club/${d.clubId}?tab=members`,
    waitFor: () => tid("my-club-members-list"),
    clip: () => ({ from: tid("my-club-members"), maxHeight: 640 }),
    phone: false,
  },
  {
    id: "help-club-squad",
    as: () => TEAM_MANAGER,
    path: (d) => `/me/club/${d.clubId}?tab=series`,
    open: async (page) => {
      await page.locator('[data-testid^="my-club-team-toggle-"]').first().click();
    },
    waitFor: () => tid("admin-squad-management"),
    clip: () => ({ from: tid("admin-squad-management") }),
    phone: false,
  },
  {
    id: "help-club-lineup",
    as: () => TEAM_MANAGER,
    path: (d) => `/me/club/${d.clubId}?tab=events`,
    open: async (page, d) => {
      await page.getByTestId(`my-club-event-toggle-${d.eventId}`).click();
    },
    waitFor: (d) => tid(`my-club-lineup-${d.eventId}`),
    clip: (d) => ({ from: tid(`my-club-lineup-${d.eventId}`) }),
    phone: true,
  },
  {
    id: "help-club-waivers",
    as: () => TEAM_MANAGER,
    path: (d) => `/me/club/${d.clubId}?tab=waivers`,
    waitFor: () => tid("my-club-waivers-list"),
    clip: () => ({ from: tid("my-club-waivers-list"), maxHeight: 700 }),
    phone: false,
  },
  {
    // Only the site's admin creates through the wizard.
    id: "help-event-wizard",
    as: () => ADMIN,
    path: () => "/admin/events/new",
    waitFor: () => tid("admin-events-create-form"),
    clip: () => ({ from: tid("admin-events-wizard") }),
    phone: false,
  },
  {
    id: "help-event-readiness",
    as: () => ADMIN,
    path: () => "/admin?tab=events",
    open: async (page, d) => {
      await page.getByTestId(`admin-manage-event-toggle-${d.eventId}`).click();
    },
    waitFor: (d) => `${tid(`admin-manage-event-panel-${d.eventId}`)} [data-testid^="admin-readiness-"]`,
    // The event's row through the draw: what is missing, the clubs, the pairing list.
    clip: (d) => ({
      from: tid(`admin-manage-event-row-${d.eventId}`),
      to: tid(`admin-manage-event-draw-${d.eventId}`),
      maxHeight: 1100,
    }),
    phone: false,
  },
  {
    id: "help-event-checkin",
    as: () => ORGANIZER,
    path: () => "/admin?tab=events",
    open: async (page, d) => {
      await page.getByTestId(`admin-manage-event-toggle-${d.eventId}`).click();
    },
    waitFor: (d) => tid(`admin-manage-event-waivers-summary-${d.eventId}`),
    clip: (d) => ({ from: tid(`admin-manage-event-waivers-section-${d.eventId}`), maxHeight: 700 }),
    phone: false,
  },
  {
    // The live act: the seed's race officer `regatta@` holds the planned one only, so the
    // league office's race officer runs this one.
    id: "help-race-control",
    as: () => SITE_RACE_OFFICER,
    path: (d) => `/events/${d.liveEventId}/race-control`,
    waitFor: () => tid("race-control-pad"),
    clip: () => ({ from: tid("race-control-heading"), to: tid("race-control-ap") }),
    phoneViewport: true,
    phone: true,
  },
  {
    id: "help-claims-pending",
    as: () => TREASURER,
    path: (d) => `/me/club/${d.clubId}?tab=money`,
    setup: aClaimToDecide,
    waitFor: () => tid("reimbursements-list"),
    // The list only — the club's bank-account form below it stays out.
    clip: () => ({ from: tid("reimbursements-list") }),
    redact: maskIbans,
    phone: false,
  },
  {
    id: "help-admin-tabs",
    as: () => ADMIN,
    path: () => "/admin",
    waitFor: () => tid("admin-clubs-list"),
    clip: () => ({ from: tid("admin-tabs"), to: tid("admin-panel-clubs"), maxHeight: 640 }),
    phone: false,
  },
];

// ------------------------------------------------------------------------- the ids

async function lookUp(request: APIRequestContext): Promise<Ids> {
  const clubId = await managedClub(request, TEAM_MANAGER);
  const headers = await bearer(request, ADMIN);
  const response = await request.get("/api/events", { headers });
  expect(response.ok(), await response.text()).toBeTruthy();
  const body = (await response.json()) as unknown;
  const events = (Array.isArray(body) ? body : (body as { items: unknown[] }).items) as {
    id: number;
    slug: string;
    status: string;
  }[];
  const planned = events.find((e) => e.slug === TEST_EVENT);
  const live = events.find((e) => e.slug.startsWith(`${TEST_SERIES}-`) && e.status === "live");
  expect(planned, `the seed has ${TEST_EVENT}`).toBeTruthy();
  expect(live, `the seed has a live act of ${TEST_SERIES}`).toBeTruthy();
  // An adult of the club with an account, the same one on every run.
  const adults = (await seededSailors(request, "nrv.example.com"))
    .filter((s) => bornIn(s) && bornIn(s) <= new Date().getFullYear() - 18)
    .map((s) => s.email!)
    .sort();
  expect(adults.length, "the seed gives NRV adult sailors").toBeGreaterThan(0);
  return { clubId, eventId: planned!.id, liveEventId: live!.id, sailor: adults[0] };
}

// ------------------------------------------------------------------- data for a shot

/** A submitted claim on the club, from one of its sailors, waiting for the treasurer —
 * made once; a second run finds it there. */
async function aClaimToDecide(request: APIRequestContext, ids: Ids): Promise<void> {
  const treasurer = await bearer(request, TREASURER);
  const pending = (await (await request.get("/api/claims/pending", { headers: treasurer })).json()) as {
    payer_club_id: number | null;
    action: string | null;
  }[];
  if (pending.some((c) => c.payer_club_id === ids.clubId && c.action === "decide")) return;

  const headers = await bearer(request, ids.sailor);
  const ok = async (response: Awaited<ReturnType<APIRequestContext["get"]>>) => {
    expect(response.ok(), await response.text()).toBeTruthy();
    return response.json() as Promise<{ id: number }>;
  };
  // The standard example IBAN of the German banking association — and masked in the shot.
  await ok(
    await request.put("/api/me/bank-account", {
      headers,
      data: { holder: "Bober Daberberg", iban: "DE89 3704 0044 0532 0130 00" },
    }),
  );
  const claim = await ok(
    await request.post("/api/claims", { headers, data: { title: "Training weekend Kiel", club_id: ids.clubId } }),
  );
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
  await ok(await request.post(`/api/claims/${claim.id}/submit`, { headers }));
}

/** Never a full IBAN in a picture: the country and the last four, the rest dotted out. */
async function maskIbans(page: Page): Promise<void> {
  await page.evaluate(() => {
    const iban = /\b([A-Z]{2}\d{2})((?:\s?[0-9A-Z]){8,30}?)((?:\s?[0-9A-Z]){4})\b/g;
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const text = node.textContent ?? "";
      if (/[A-Z]{2}\d{2}/.test(text)) {
        node.textContent = text.replace(iban, (_m, head: string, middle: string, tail: string) =>
          `${head} ${middle.replace(/\s/g, "").replace(/./g, "•").replace(/(.{4})/g, "$1 ").trim()} ${tail.replace(/\s/g, "")}`,
        );
      }
    }
  });
}

// -------------------------------------------------------------------------- capture

/** The clip in page coordinates, so a panel below the fold is cut from the full page. */
async function clipBox(page: Page, clip: Clip) {
  return page.evaluate(({ from, to, maxHeight }) => {
    const box = (selector: string) => {
      const element = document.querySelector(selector);
      if (!element) throw new Error(`no element ${selector}`);
      const r = element.getBoundingClientRect();
      return { left: r.left + scrollX, top: r.top + scrollY, right: r.right + scrollX, bottom: r.bottom + scrollY };
    };
    const a = box(from);
    const b = to ? box(to) : a;
    const pad = 8;
    const left = Math.max(0, Math.min(a.left, b.left) - pad);
    const top = Math.max(0, Math.min(a.top, b.top) - pad);
    const right = Math.min(document.documentElement.scrollWidth, Math.max(a.right, b.right) + pad);
    let bottom = Math.max(a.bottom, b.bottom) + pad;
    if (maxHeight) bottom = Math.min(bottom, top + maxHeight);
    return { x: left, y: top, width: right - left, height: bottom - top };
  }, clip);
}

test.describe("Foundations: handbook screenshots", () => {
  test.skip(!process.env.HANDBOOK_SHOTS, "set HANDBOOK_SHOTS=1 to capture the handbook's screenshots");

  for (const shot of SHOTS) {
    test(shot.id, { tag: shot.phone ? ["@phone"] : [] }, async ({ page, request }, testInfo) => {
      const phone = testInfo.project.name === "mobile";
      test.skip(phone && !shot.phone, "no phone version of this shot");
      if (!phone) await page.setViewportSize({ width: 1280, height: 800 });

      const ids = await lookUp(request);
      await shot.setup?.(request, ids);
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
        await page.addStyleTag({ content: '[data-testid="dev-role-switcher"] { display: none !important; }' });
        if (shot.open) {
          // The panel's toggle appears with its list.
          await page.waitForLoadState("networkidle");
          await shot.open(page, ids);
        }
        await expect(page.locator(shot.waitFor(ids)).first()).toBeVisible();
        await page.waitForLoadState("networkidle");
        await shot.redact?.(page);

        const file = `${OUT}${shot.id}_${locale}${phone ? "_phone" : ""}.png`;
        const picture =
          phone && shot.phoneViewport
            ? await page.screenshot({ path: file })
            : await page.screenshot({
                path: file,
                fullPage: true,
                clip: shot.clip ? await clipBox(page, shot.clip(ids)) : undefined,
              });
        pictures.push(picture);
      }
      expect(Buffer.compare(pictures[0], pictures[1]), `${shot.id}: en and de look the same`).not.toBe(0);
    });
  }
});
