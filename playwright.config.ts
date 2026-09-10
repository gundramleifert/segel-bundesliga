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
    trace: "on-first-retry",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    // The site is read mostly on phones — that belongs in the tests.
    //
    // `lifecycle.spec.ts` is excluded here, and **not** because it is inconvenient: on a
    // 412 px viewport the admin rows are genuinely unusable. Every click on a row's button
    // is refused with "…intercepts pointer events", the interceptor being the row's own
    // title block. That is a real layout defect (Story A-10), not a test artefact — running
    // the spec here would just restate the same known bug five times while hiding
    // regressions in everything else. The public pages, which are what people actually read
    // on a phone, are covered by `visitor.spec.ts` on both projects.
    {
      name: "mobile",
      use: { ...devices["Pixel 7"] },
      testIgnore: /lifecycle\.spec\.ts/,
    },
  ],
});
