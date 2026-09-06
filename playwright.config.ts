import { defineConfig, devices } from "@playwright/test";

/** E2E-Tests laufen gegen die tatsächlich laufende Anwendung.
 *
 * Voraussetzung: Backend auf 8000 und Vite auf 5173. Beide starten hier nicht automatisch,
 * damit ein fehlgeschlagener Test nicht als „Server war nicht da" missverstanden wird —
 * `reuseExistingServer` würde das verschleiern.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : [["list"]],
  use: {
    baseURL: "http://127.0.0.1:5173",
    locale: "de-DE",
    trace: "on-first-retry",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    // Die Seite wird überwiegend auf Handys gelesen — das gehört mitgetestet.
    { name: "handy", use: { ...devices["Pixel 7"] } },
  ],
});
