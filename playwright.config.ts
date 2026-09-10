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
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : [["list"]],
  use: {
    baseURL: "http://127.0.0.1:5173",
    locale: "en-US",
    trace: "on-first-retry",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    // The site is read mostly on phones — that belongs in the tests.
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
});
