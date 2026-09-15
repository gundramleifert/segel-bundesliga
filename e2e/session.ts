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
