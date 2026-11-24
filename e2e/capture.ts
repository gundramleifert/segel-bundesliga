import type { Page } from "@playwright/test";

/** Taking the handbook's pictures from the running stack — shared by the screenshot spec
 * (`handbook-shots.spec.ts`) and the step-by-step guides (`e2e/guides/`): the marks drawn
 * over the controls the text names, waiting for a page to settle, the clip, and the
 * privacy redactions. `.claude/skills/handbook/references/screenshots.md`. */

/** Both languages of the help, English first (the source). */
export const LOCALES = ["en", "de"] as const;
export type Locale = (typeof LOCALES)[number];

/** Where the pictures go — the viewer reads `shot:<id>` from here. */
export const SCREENSHOTS = new URL("../web/public/handbook/screenshots/", import.meta.url);

/** The dev role switcher (bottom right) never appears in a picture. */
export async function hideDevSwitcher(page: Page): Promise<void> {
  await page.addStyleTag({ content: '[data-testid="dev-role-switcher"] { display: none !important; }' });
}

/** Where a shot's picture is cut from: one element, or the span from one to another,
 * at most `maxHeight` tall. No clip: the viewport as the person sees it. */
export type Clip = { from: string; to?: string; maxHeight?: number; pad?: number };

/** A control the handbook's text tells the reader to press: framed, with a numbered badge
 * the text refers to as ①②③. `n` defaults to the mark's place in the list, from 1. */
export type Mark = { target: string; n?: number };  // n: 0 → no badge

/** Never a full IBAN in a picture: the country and the last four, the rest dotted out. */
export async function maskIbans(page: Page): Promise<void> {
  await page.evaluate(() => {
    const iban = /\b([A-Z]{2}\d{2})((?:\s?[0-9A-Z]){8,30}?)((?:\s?[0-9A-Z]){4})\b/g;
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const text = node.textContent ?? "";
      if (/[A-Z]{2}\d{2}/.test(text)) {
        node.textContent = text.replace(iban, (_m, head: string, middle: string, tail: string) =>
          `${head} ${middle.replace(/\s/g, "").replace(/./g, "•").replace(/(.{4})/g, "$1 ").trim()} ${tail.replace(/\s/g, "")}`,
        );
      }
    }
  });
}

export type Box = { left: number; top: number; right: number; bottom: number };

/** Draws the shot's marks over the page and returns the box they cover, in page
 * coordinates — or throws when a target is missing or invisible: a mark the text refers
 * to and the picture lacks is worse than no mark.
 *
 * Each mark is a soft amber glow around the control — no frame or ring: the glow alone
 * reads on a white card and on the dark glass pages, and does not box the control in —
 * and a filled amber badge with its number just outside its top-left corner. Absolutely
 * positioned in the document, so a full-page clip carries it; pointer-events none. */
export async function drawMarks(page: Page, marks: Mark[]): Promise<Box | null> {
  if (!marks.length) return null;
  await settled(page, marks.map((m) => m.target));
  return page.evaluate((list) => {
    const AMBER = "#f59e0b";
    const INK = "#111827";
    const PAD = 5;
    const BADGE = 26;
    document.getElementById("handbook-marks")?.remove();
    const layer = document.createElement("div");
    layer.id = "handbook-marks";
    Object.assign(layer.style, {
      position: "absolute", left: "0", top: "0", width: "0", height: "0",
      zIndex: "2147483647", pointerEvents: "none",
    });
    document.body.appendChild(layer);
    const badges: HTMLElement[] = [];
    const cover = { left: Infinity, top: Infinity, right: -Infinity, bottom: -Infinity };
    list.forEach((mark, index) => {
      const element = document.querySelector(mark.target);
      if (!element) throw new Error(`mark ${index + 1}: no element ${mark.target}`);
      const r = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      if (r.width === 0 || r.height === 0 || style.visibility === "hidden" || style.display === "none") {
        throw new Error(`mark ${index + 1}: ${mark.target} is not visible`);
      }
      const left = r.left + scrollX - PAD;
      const top = r.top + scrollY - PAD;
      const width = r.width + 2 * PAD;
      const height = r.height + 2 * PAD;
      const frame = document.createElement("div");
      Object.assign(frame.style, {
        position: "absolute", left: `${left}px`, top: `${top}px`,
        width: `${width}px`, height: `${height}px`, boxSizing: "border-box",
        borderRadius: "12px",
        // Two layers of glow, an inner strong one and a wide soft one; nothing drawn on
        // the control's own edge.
        boxShadow: "0 0 10px 4px rgba(245,158,11,.9), 0 0 28px 12px rgba(245,158,11,.55)",
      });
      layer.appendChild(frame);
      // Up and left of the corner, overlapping the frame only a little, so a small
      // control (a checkbox, a label) is not hidden under its own number.
      const badgeLeft = Math.max(2, left - BADGE + 7);
      const badgeTop = Math.max(2, top - BADGE + 7);
      const badge = document.createElement("div");
      badge.textContent = String(mark.n ?? index + 1);
      Object.assign(badge.style, {
        position: "absolute", left: `${badgeLeft}px`, top: `${badgeTop}px`,
        width: `${BADGE}px`, height: `${BADGE}px`, boxSizing: "border-box",
        borderRadius: "50%", background: AMBER, color: INK, border: "2px solid #fff",
        boxShadow: "0 0 0 1px rgba(17,24,39,.6), 0 2px 6px rgba(0,0,0,.45)",
        font: "700 14px/22px system-ui, sans-serif", textAlign: "center",
      });
      // `n: 0` is a glow alone — a result to look at, nothing to press.
      if (mark.n !== 0) badges.push(badge);
      const glow = 34;
      cover.left = Math.min(cover.left, badgeLeft, left - glow);
      cover.top = Math.min(cover.top, badgeTop, top - glow);
      cover.right = Math.max(cover.right, left + width + glow);
      cover.bottom = Math.max(cover.bottom, top + height + glow);
    });
    // Over every frame: a badge beside a neighbour's frame must not vanish under it.
    for (const badge of badges) layer.appendChild(badge);
    return cover;
  }, marks);
}

/** Waits until the targets stop moving: a list that lands late pushes everything below
 * it down, and a mark drawn before that sits beside its control in the picture. */
export async function settled(page: Page, targets: string[]): Promise<void> {
  const where = () =>
    page.evaluate(
      (list) =>
        list
          .map((selector) => {
            const r = document.querySelector(selector)?.getBoundingClientRect();
            return r ? `${r.left + scrollX},${r.top + scrollY},${r.width},${r.height}` : "-";
          })
          .join(";"),
      targets,
    );
  let before = await where();
  for (let i = 0; i < 20; i++) {
    await page.waitForTimeout(250);
    const now = await where();
    if (now === before) return;
    before = now;
  }
}

/** The clip in page coordinates, so a panel below the fold is cut from the full page —
 * widened to every mark, which may sit just outside the panel. */
export async function clipBox(page: Page, clip: Clip, marks: Box | null) {
  return page.evaluate(({ from, to, maxHeight, pad = 8, marks }) => {
    const box = (selector: string) => {
      const element = document.querySelector(selector);
      if (!element) throw new Error(`no element ${selector}`);
      const r = element.getBoundingClientRect();
      return { left: r.left + scrollX, top: r.top + scrollY, right: r.right + scrollX, bottom: r.bottom + scrollY };
    };
    const a = box(from);
    const b = to ? box(to) : a;
    const pageWidth = document.documentElement.scrollWidth;
    let left = Math.max(0, Math.min(a.left, b.left) - pad);
    let top = Math.max(0, Math.min(a.top, b.top) - pad);
    let right = Math.min(pageWidth, Math.max(a.right, b.right) + pad);
    let bottom = Math.max(a.bottom, b.bottom) + pad;
    if (maxHeight) bottom = Math.min(bottom, top + maxHeight);
    if (marks) {
      left = Math.max(0, Math.min(left, marks.left));
      top = Math.max(0, Math.min(top, marks.top));
      right = Math.min(pageWidth, Math.max(right, marks.right));
      bottom = Math.max(bottom, marks.bottom);
    }
    return { x: left, y: top, width: right - left, height: bottom - top };
  }, { ...clip, marks });
}
