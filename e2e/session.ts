import { readFile } from "node:fs/promises";

import type { APIRequestContext, Page } from "@playwright/test";

import { expect } from "./fixtures";

/** Signing in, for specs that act as someone.
 *
 * Every signed-in spec goes straight to `/api/dev/login` and drops the token where the app
 * looks for it, rather than clicking through the role switcher — that would test the role
 * switcher, a development aid, instead of the story at hand. Needs `SBL_DEV_LOGIN=true` on
 * the backend, which `scripts/dev-stack.sh` sets. Used by the lifecycle, live and
 * race-control specs; it lived in `lifecycle.spec.ts` until the third copy was about to be
 * written.
 */

/** A token for a seeded test account, from the same `/api` path the app uses. */
export async function devToken(request: APIRequestContext, email: string): Promise<string> {
  const response = await request.post("/api/dev/login", { data: { email } });
  expect(response.ok(), `dev login failed for ${email} — is SBL_DEV_LOGIN=true?`).toBeTruthy();
  const { access_token: token } = (await response.json()) as { access_token: string };
  return token;
}

/** Puts a seeded account's token where `web/src/api/session.ts` reads it.
 *
 * `addInitScript`, not an `evaluate` after `goto`: the session module reads `localStorage`
 * once, at import time, so the token has to be there before the bundle runs. */
export async function signIn(page: Page, email: string): Promise<void> {
  const token = await devToken(page.request, email);
  await page.addInitScript(
    ([key, value]) => window.localStorage.setItem(key, value),
    ["sbl.token", token],
  );
}

/** Headers for API calls made by the spec itself as a signed-in account. */
export async function bearer(
  request: APIRequestContext,
  email: string,
): Promise<Record<string, string>> {
  return { Authorization: `Bearer ${await devToken(request, email)}` };
}

// ----------------------------------------------------------------- Finding seeded people
//
// Specs find the person a story is about rather than hardcode them: the seed's accounts
// are stable only until someone touches `app/seed_users.py`.

export type DevUser = { id: number; email: string; roles: string[] };

/** Every seeded account with its summary roles (`/api/dev/users`). */
export async function devUsers(request: APIRequestContext): Promise<DevUser[]> {
  const response = await request.get("/api/dev/users");
  expect(response.ok(), "is SBL_DEV_LOGIN=true?").toBeTruthy();
  return (await response.json()) as DevUser[];
}

/** The club this person organizes — the one a club screen is about for them. */
export async function managedClub(request: APIRequestContext, email: string): Promise<number> {
  const clubs = (await (await request.get("/api/clubs/mine", { headers: await bearer(request, email) })).json()) as {
    club: { id: number };
    may_manage: boolean;
  }[];
  return clubs.find((c) => c.may_manage)!.club.id;
}

export type SeededSailor = { id: number; email: string | null; birth_date: string | null };

/** The seeded sailors of one club, by its address domain (`asvw.example.com`): adults sail
 * the first league, teenagers the juniors. Only people with a date of birth: every account
 * has a person too (#40) — the club's officials' carry the club's domain and no date. */
export async function seededSailors(request: APIRequestContext, domain: string): Promise<SeededSailor[]> {
  const headers = await bearer(request, "admin@sbl.example.com");
  const response = await request.get(`/api/admin/people?q=${domain}&limit=100`, { headers });
  expect(response.ok(), await response.text()).toBeTruthy();
  return ((await response.json()) as { items: SeededSailor[] }).items.filter((s) => s.email && s.birth_date);
}

export function bornIn(sailor: SeededSailor): number {
  return Number(sailor.birth_date?.slice(0, 4) ?? 0);
}

// ----------------------------------------------------------------- A squad of new people

/** A series of its own with the test club ASVW registered and a squad of people new to the
 *  site, one per date of birth — nobody has signed anything for them. For a spec that
 *  changes what a sailor has on file (a waiver confirmed stays confirmed): built fresh
 *  each run, so it runs again on the same stack, and never touches the seeded squads,
 *  which are full and which other specs read. */
export async function newSquad(
  request: APIRequestContext,
  label: string,
  births: string[],
): Promise<{ series: number; clubId: number; people: SeededSailor[] }> {
  const headers = await bearer(request, "admin@sbl.example.com");
  const clubId = await managedClub(request, "teams@asvw.example.com");
  const stamp = `${label} ${Date.now()}`;
  const response = await request.post("/api/admin/series", {
    headers,
    data: { name: stamp, year: 2026, starts_on: "2026-05-01", clubs: [clubId] },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  const series = (await response.json()) as { id: number; clubs: { team_id: number }[] };
  const people: SeededSailor[] = [];
  for (const [i, birth_date] of births.entries()) {
    const email = `${stamp.replaceAll(" ", "-").toLowerCase()}-${i}@asvw.example.com`;
    const created = await request.post("/api/admin/people", {
      headers,
      data: { first_name: `Sailor ${i + 1}`, last_name: label, email, birth_date, club_id: clubId },
    });
    expect(created.ok(), await created.text()).toBeTruthy();
    people.push((await created.json()) as SeededSailor);
  }
  const squad = await request.put(`/api/admin/teams/${series.clubs[0]!.team_id}/members`, {
    headers,
    data: { members: people.map((p) => ({ person_id: p.id })) },
  });
  expect(squad.ok(), await squad.text()).toBeTruthy();
  return { series: series.id, clubId, people };
}

// ----------------------------------------------------------------- A picture in the library

/** Puts the site's own photos (`web/public/media/`) into a series' library, as an editor
 *  would — for a spec about the pictures behind a page, which needs more than one to see
 *  two pages pick different ones. The seed brings no picture that is not Sven Jürgensen's
 *  (docs/PLAN_SEEDING.md), so a stack may have none. Repeatable: the library answers a
 *  picture it already holds with that entry. */
export async function picturesFor(request: APIRequestContext, seriesSlug: string): Promise<void> {
  const series = (await (await request.get("/api/series")).json()) as { id: number; slug: string }[];
  const target = series.find((s) => s.slug === seriesSlug);
  expect(target, `a published series ${seriesSlug}`).toBeTruthy();
  const headers = await bearer(request, "redaktion@sbl.example.com");
  for (const name of ["DSF3979.jpg", "DSF4018-2.jpg", "DSF4037.jpg"]) {
    const buffer = await readFile(new URL(`../web/public/media/${name}`, import.meta.url));
    const response = await request.post("/api/admin/media", {
      headers,
      multipart: {
        file: { name, mimeType: "image/jpeg", buffer },
        alt: "A test picture",
        series_id: String(target!.id),
      },
    });
    expect(response.ok(), await response.text()).toBeTruthy();
  }
}
