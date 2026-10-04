import { defineConfig } from "allure";

/** The Allure report of both suites (`scripts/allure-report.sh`).
 *
 * Grouped by **story** — the labels `api/tests/conftest.py` and `e2e/fixtures.ts` set from
 * `docs/stories.json` — so the tree reads like `docs/userstories/`, not like the test
 * files; a test that covers three stories appears under each of them, and the tests that
 * name none are one group, "(no story)". Role (`epic`) and phase (`feature`) are on every
 * test too, as filters, but deliberately **not** grouping levels: Allure combines label
 * lists crosswise, so a test naming an organizer story and an administration story would
 * also appear under the administration role with the organizer story.
 */
export default defineConfig({
  name: "Deutsche Segel-Liga — user stories",
  output: "./allure-report",
  plugins: {
    awesome: {
      options: {
        groupBy: ["story"],
        reportLanguage: "en",
      },
    },
  },
});
