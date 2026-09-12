import { defineConfig, devices } from "@playwright/test";

/** E2E tests run against the actually running application.
 *
 * Prerequisites: the backend on 8000 and Vite on 5173. Neither is started here on purpose,
 * so that a failing test is never misread as "the server wasn't there" —
 * `reuseExistingServer` would paper over exactly that.
 *
 * The locale is pinned to `en-US`. English is the source language, so pinning it keeps the
 * assertions comparing against strings that live in `en/*.json` rather than against a
 * translation; the language switcher gets its own test instead (`visitor.spec.ts`).
 */
export default defineConfig({
  testDir: "./e2e",
  // Deliberately **not** parallel, and one worker. Every spec talks to one server backed by
  // one SQLite file, and `lifecycle.spec.ts` writes to it — clubs, series, events. Run in
  // parallel and the writes land while another spec is reading the same lists, which shows
  // up as tests failing on counts that were right a moment earlier. Postgres would not make
  // this safe either: the shared *data* is the problem, not the engine.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : [["list"]],
  use: {
    baseURL: "http://127.0.0.1:5173",
    locale: "en-US",
    // An automated run has no business animating. The site's own smooth scrolling is
    // already behind `prefers-reduced-motion` (see `web/src/index.css`), and this is the
    // browser stating that preference: without it, every scroll-into-view is an animation
    // and the element under the click point keeps changing while Playwright waits for the
    // target to be "stable" — which is how a working button looks like a broken one.
    // Under `contextOptions`: as of Playwright 1.62 that is where this lives, and a
    // top-level `reducedMotion` is accepted by the config loader but has no effect.
    contextOptions: { reducedMotion: "reduce" },
    trace: "on-first-retry",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    // The site is read mostly on phones — that belongs in the tests. And the admin screens
    // are used on one too: `lifecycle.spec.ts` runs here as well, which is what keeps Story
    // A-10 closed. It was skipped here for exactly as long as the admin rows were unusable
    // at 412 px (every click refused with "…intercepts pointer events"); putting it back is
    // the fix's own regression test.
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
});
