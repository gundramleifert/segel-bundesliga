import { expect, type Page, type TestInfo } from "@playwright/test";

/** Shared layout assertions.
 *
 * These live outside any spec because the same two numbers decide whether *any* page of
 * this site is usable on a phone, and because getting them right took an afternoon once
 * (see `docs/gotchas/an-overflow-assertion-cannot-see-its-own-symptom.md`). Writing the
 * check a fourth time by hand is how the fourth version ends up subtly weaker than the
 * third.
 */

/** The layout viewport this project asked for, read off the project rather than hardcoded.
 *
 *  `testInfo.project.use.viewport` is the configured size; a spec that calls
 *  `page.setViewportSize` afterwards changes it, so the live value wins when present. */
function expectedWidth(page: Page, testInfo: TestInfo): number {
  return page.viewportSize()?.width ?? testInfo.project.use.viewport!.width;
}

/** Names the boxes whose own content does not fit them — the sources of overflow.
 *
 *  Deliberately not every element wider than the viewport: in a grid, siblings *stretch*
 *  to the widest item, so a dozen innocent boxes report a wide rect and the real culprit
 *  is indistinguishable among them. A box whose `scrollWidth` exceeds its own
 *  `clientWidth` is actually overflowing. Boxes that scroll on purpose are excluded —
 *  a results table scrolling inside its own container is correct here, by design
 *  (`.table-scroll` in `web/src/index.css`). */
async function overflowSources(page: Page): Promise<string[]> {
  return page.evaluate(() =>
    Array.from(document.querySelectorAll<HTMLElement>("*"))
      .filter((el) => el.scrollWidth > el.clientWidth + 1)
      .filter((el) => {
        const overflowX = getComputedStyle(el).overflowX;
        return overflowX !== "auto" && overflowX !== "scroll";
      })
      .map(
        (el) =>
          `${el.scrollWidth}px in ${el.clientWidth}px — ${el.tagName.toLowerCase()}` +
          `[${el.getAttribute("data-testid") ?? ""}] .${(el.className || "").toString().slice(0, 80)}`,
      )
      .slice(0, 12),
  );
}

/** Fails if the page is wider than its viewport — in either of the two ways it can be.
 *
 * **Two assertions, not one, and the order matters.** Honest overflow shows up as
 * `scrollWidth > clientWidth`. But mobile Chromium answers horizontal overflow by *zooming
 * the page out to fit it*, and once it has, `scrollWidth === clientWidth` again — so an
 * overflow-only check goes green on exactly the page it was written to protect. That is
 * not hypothetical: it is what let the admin screens stay unusable on a phone for weeks
 * while a "never scrolls sideways" test passed (Story A-10). Comparing `window.innerWidth`
 * against the viewport we configured is what catches the zoom-out.
 *
 * On failure it names the boxes that actually overflow, so nobody has to write the probe
 * that found them the first time.
 */
export async function expectNoSidewaysScroll(page: Page, testInfo: TestInfo): Promise<void> {
  const configured = expectedWidth(page, testInfo);
  const measured = await page.evaluate(() => ({
    innerWidth: window.innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));

  if (measured.innerWidth !== configured || measured.scrollWidth > measured.clientWidth + 1) {
    const sources = await overflowSources(page);
    const detail = sources.length ? `\noverflowing boxes:\n  ${sources.join("\n  ")}` : "";
    expect(
      { innerWidth: measured.innerWidth, scrollWidth: measured.scrollWidth },
      `${page.url()} does not fit its ${configured}px viewport.\n` +
        `The browser zooms the page out when content is too wide, so a layout viewport ` +
        `wider than ${configured}px means the page is rendered shrunk and every tap ` +
        `lands off-target.${detail}`,
    ).toEqual({ innerWidth: configured, scrollWidth: measured.clientWidth });
  }
}
