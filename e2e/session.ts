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
 * the first league, teenagers the juniors. */
export async function seededSailors(request: APIRequestContext, domain: string): Promise<SeededSailor[]> {
  const headers = await bearer(request, "admin@sbl.example.com");
  const response = await request.get(`/api/admin/people?q=${domain}&limit=100`, { headers });
  expect(response.ok(), await response.text()).toBeTruthy();
  return ((await response.json()) as { items: SeededSailor[] }).items.filter((s) => s.email);
}

export function bornIn(sailor: SeededSailor): number {
  return Number(sailor.birth_date?.slice(0, 4) ?? 0);
}
