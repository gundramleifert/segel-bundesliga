import { expect, test } from "@playwright/test";

/** E2E nach User-Storys geschnitten — siehe docs/userstories.md. */

test.describe("B-1: Als Fan sehe ich die Ligatabelle", () => {
  test("die Tabelle listet alle 18 Mannschaften auf den Plätzen 1 bis 18", async ({ page }) => {
    await page.goto("/tabelle");

    const zeilen = page.locator("table tbody tr");
    await expect(zeilen).toHaveCount(18);
    await expect(zeilen.first().locator("td").first()).toHaveText("1");
    await expect(zeilen.last().locator("td").first()).toHaveText("18");
  });

  test("weniger Punkte steht weiter oben", async ({ page }) => {
    await page.goto("/tabelle");
    await expect(page.locator("table tbody tr")).toHaveCount(18);

    const punkte = await page
      .locator("table tbody tr td:nth-child(3)")
      .allInnerTexts();
    const zahlen = punkte.map((t) => Number(t.replace(",", ".")));
    expect(zahlen).toEqual([...zahlen].sort((a, b) => a - b));
  });
});

test.describe("B-2: Als Fan lese ich nach, wie ein Spieltag ausging", () => {
  test("der beendete Spieltag zeigt eine vollständige Tageswertung", async ({ page }) => {
    await page.goto("/spieltage/1-liga-2026-spieltag-1");

    await expect(page.getByRole("heading", { level: 1 })).toContainText("Spieltag");
    await expect(page.getByText("48 von 48 Wettfahrten gewertet")).toBeVisible();
    await expect(page.locator("table tbody tr")).toHaveCount(18);
  });

  test("ein geplanter Spieltag hat noch keine Ergebnisse, aber eine Auslosung", async ({
    page,
  }) => {
    await page.goto("/spieltage/1-liga-2026-spieltag-3");

    await expect(page.getByText("Es wurde noch nicht gesegelt.")).toBeVisible();

    await page.getByRole("tab", { name: "Pairing-Liste" }).click();
    await expect(page.locator("table tbody tr")).toHaveCount(48);
  });
});

test.describe("B-3: Als Seglerin sehe ich, wann ich auf welchem Boot sitze", () => {
  test("die Pairing-Liste weist die Boote mit ihrer Farbe aus", async ({ page }) => {
    await page.goto("/spieltage/1-liga-2026-spieltag-3");
    await page.getByRole("tab", { name: "Pairing-Liste" }).click();

    const kopfzeile = page.locator("table thead th");
    for (const farbe of ["Schwarz", "Grün", "Dunkelblau", "Rot", "Grau", "Orange"]) {
      await expect(kopfzeile.filter({ hasText: farbe })).toHaveCount(1);
    }
  });

  test("jede Wettfahrt besetzt alle sechs Boote", async ({ page }) => {
    await page.goto("/spieltage/1-liga-2026-spieltag-3");
    await page.getByRole("tab", { name: "Pairing-Liste" }).click();

    const ersteZeile = page.locator("table tbody tr").first();
    // Nummer, Flight, dann sechs Boote.
    await expect(ersteZeile.locator("td")).toHaveCount(8);
    for (let i = 3; i <= 8; i++) {
      await expect(ersteZeile.locator(`td:nth-child(${i})`)).not.toHaveText("–");
    }
  });
});

test.describe("B-4: Als Besucherin finde ich Vereine und Termine", () => {
  test("alle 18 Vereine sind gelistet", async ({ page }) => {
    await page.goto("/vereine");
    await expect(page.getByRole("listitem")).toHaveCount(18);
  });

  test("von den Terminen komme ich in den Spieltag", async ({ page }) => {
    await page.goto("/termine");
    await page.getByRole("link").filter({ hasText: "Spieltag" }).first().click();

    await expect(page).toHaveURL(/\/spieltage\//);
    await expect(page.getByRole("tab", { name: "Tageswertung" })).toBeVisible();
  });
});

test.describe("Grundlagen", () => {
  test("die Startseite führt in die Tabelle", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Deutsche Segel-Bundesliga" })).toBeVisible();

    await page.getByRole("link", { name: "Vollständige Tabelle" }).click();
    await expect(page).toHaveURL(/\/tabelle$/);
  });

  test("die Seite scrollt nie waagerecht — auch nicht mit breiten Tabellen", async ({
    page,
  }) => {
    await page.goto("/spieltage/1-liga-2026-spieltag-3");
    await page.getByRole("tab", { name: "Pairing-Liste" }).click();
    await expect(page.locator("table tbody tr").first()).toBeVisible();

    const ueberbreite = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(ueberbreite).toBeLessThanOrEqual(1);
  });
});
