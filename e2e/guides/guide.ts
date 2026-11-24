import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import type { APIRequestContext, Page } from "@playwright/test";

import { drawMarks, hideDevSwitcher, type Locale, LOCALES, SCREENSHOTS, settled } from "../capture";
import { expect, test } from "../fixtures";
import { signIn } from "../session";

/** Step-by-step guides for the handbook, written as Playwright scripts (proposal B of
 * 2026-11-24): a guide **clicks the real way** through the running stack as one role,
 * takes a picture before every step with the control to press marked, and writes the
 * handbook page — both languages — from what it did. A guide that no longer runs is a
 * guide that no longer matches the site, and the run says so.
 *
 * Not a test of anything, so it stays out of the normal run:
 *
 *   GUIDES=1 node_modules/.bin/playwright test e2e/guides --project chromium --workers 1
 *
 * Traceability: a guide names the journey steps it shows a person through (`steps`), and
 * the stories behind them; the page carries both in its frontmatter, and
 * `scripts/check-docs.py` holds page, script and journeys together and lists the guide
 * beside each step in `docs/traceability.md`. */

export type Text = Record<Locale, string>;

export type GuideMeta = {
  /** The page id: `web/src/handbook/<id>.<locale>.md`, pictures `<id>-<n>_<locale>.png`. */
  id: string;
  /** This file, relative to the repository — the page names it as its source. */
  source: string;
  title: Text;
  audience: string[];
  /** Unique among the handbook's guides, a multiple of 10. */
  order: number;
  stories: string[];
  /** The journey steps this guide walks one person through (`J-n.k`). */
  steps: string[];
  tags: string[];
  /** The seeded account the guide is clicked as. */
  as: string;
  /** Puts back what the last run changed, so every language starts from the same state. */
  reset?: (request: APIRequestContext) => Promise<void>;
  intro: Text;
  /** What happens afterwards, and what can go wrong — the part no script knows. */
  after: Text;
};

type Step = { text: string; shot: string };

export type GuideRun = {
  page: Page;
  locale: Locale;
  /** One step: the picture shows `mark` glowing with the step's number, then `action` does it. */
  step(text: Text, mark: string, action: () => Promise<unknown>): Promise<void>;
  /** The last picture: the result, `mark` glowing (no number of its own). */
  result(text: Text, mark: string): Promise<void>;
};

const HEADINGS = {
  steps: { en: "Step by step", de: "Schritt für Schritt" },
  after: { en: "Afterwards", de: "Danach" },
} satisfies Record<string, Text>;

const OUT = fileURLToPath(SCREENSHOTS);
const HANDBOOK = fileURLToPath(new URL("../../web/src/handbook/", import.meta.url));

export function guide(meta: GuideMeta, walk: (run: GuideRun) => Promise<void>): void {
  test.describe(`Guide: ${meta.id}`, () => {
    test.skip(!process.env.GUIDES, "set GUIDES=1 to write the step-by-step guides");

    test(meta.title.en, async ({ page, request }) => {
      await page.setViewportSize({ width: 1280, height: 800 });
      mkdirSync(OUT, { recursive: true });
      await signIn(page, meta.as);
      const written: Record<Locale, Step[]> = { en: [], de: [] };
      const pictures: Record<Locale, Buffer[]> = { en: [], de: [] };

      for (const locale of LOCALES) {
        await meta.reset?.(request);
        await page.goto("/");
        await page.evaluate((value) => window.localStorage.setItem("sbl.language", value), locale);
        const shoot = async (mark: string, n: number | undefined): Promise<string> => {
          await hideDevSwitcher(page);
          const target = page.locator(mark).first();
          await expect(target).toBeVisible();
          await target.scrollIntoViewIfNeeded();
          await settled(page, [mark]);
          await drawMarks(page, [{ target: mark, n }]);
          const shot = `${meta.id}-${written[locale].length + 1}`;
          pictures[locale].push(await page.screenshot({ path: `${OUT}${shot}_${locale}.png` }));
          await page.evaluate(() => document.getElementById("handbook-marks")?.remove());
          return shot;
        };
        await walk({
          page,
          locale,
          async step(text, mark, action) {
            const n = written[locale].length + 1;
            written[locale].push({ text: text[locale], shot: await shoot(mark, n) });
            await action();
          },
          async result(text, mark) {
            written[locale].push({ text: text[locale], shot: await shoot(mark, 0) });
          },
        });
      }

      expect(written.de.length, "both languages walk the same steps").toBe(written.en.length);
      pictures.en.forEach((picture, i) =>
        expect(Buffer.compare(picture, pictures.de[i]), `step ${i + 1}: en and de look the same`).not.toBe(0),
      );
      for (const locale of LOCALES) {
        writeFileSync(`${HANDBOOK}${meta.id}.${locale}.md`, render(meta, locale, written[locale]));
      }
    });
  });
}

/** A label as the screen shows it, in both languages — quoted from the catalogs
 * (`web/src/i18n/locales/<locale>/<namespace>.json`), never re-typed: `ui("admin",
 * "accounts.tupleButton")`. A key that is not there fails the run. */
export function ui(namespace: string, key: string): Text {
  const read = (locale: Locale) => {
    const file = fileURLToPath(new URL(`../../web/src/i18n/locales/${locale}/${namespace}.json`, import.meta.url));
    let value: unknown = JSON.parse(readFileSync(file, "utf-8"));
    for (const part of key.split(".")) value = (value as Record<string, unknown> | undefined)?.[part];
    if (typeof value !== "string") throw new Error(`no label ${namespace}:${key} in ${locale}`);
    return value;
  };
  return { en: read("en"), de: read("de") };
}

/** A text per language built from labels: `say((l) => `Click *${l.grant}*`, { grant: ui(…) })`. */
export function say<K extends string>(write: (labels: Record<K, string>, locale: Locale) => string, labels: Record<K, Text>): Text {
  const pick = (locale: Locale) =>
    Object.fromEntries(Object.entries<Text>(labels).map(([k, v]) => [k, v[locale]])) as Record<K, string>;
  return { en: write(pick("en"), "en"), de: write(pick("de"), "de") };
}

/** A picture's caption: the step's words without their emphasis. */
const plain = (text: string) => text.replace(/\*/g, "");

const list = (items: string[]) => `[${items.join(", ")}]`;

/** The handbook page: the frontmatter `check-docs.py` reads, the intro, the numbered steps
 * with their pictures, the last picture as the result, and what comes after. */
export function render(meta: GuideMeta, locale: Locale, steps: Step[]): string {
  const numbered = steps.slice(0, -1);
  const last = steps[steps.length - 1];
  return [
    "---",
    `id: ${meta.id}`,
    "type: guide",
    `order: ${meta.order}`,
    `audience: ${list(meta.audience)}`,
    `stories: ${list(meta.stories)}`,
    "journey: null",
    `steps: ${list(meta.steps)}`,
    `source: ${meta.source}`,
    "route: null",
    `tags: ${list(meta.tags)}`,
    `title: ${meta.title[locale]}`,
    "---",
    "",
    `## ${meta.title[locale]}`,
    "",
    meta.intro[locale],
    "",
    `### ${HEADINGS.steps[locale]} {#${meta.id}-steps}`,
    "",
    ...numbered.flatMap((s, i) => [`${i + 1}. ${s.text}`, "", `   ![${plain(s.text)}](shot:${s.shot})`, ""]),
    last.text,
    "",
    `![${plain(last.text)}](shot:${last.shot})`,
    "",
    `### ${HEADINGS.after[locale]} {#${meta.id}-after}`,
    "",
    meta.after[locale],
    "",
  ].join("\n");
}
