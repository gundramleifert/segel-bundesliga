import type { ReactNode } from "react";

/** The two layout primitives this site is built out of.
 *
 * Both exist for the same reason: the class strings they replace were each written out
 * more than twenty times, and one of them encodes a lesson that is invisible in the
 * string itself (see `Stack`). A pattern that has to be remembered will eventually be
 * copied wrong; a component cannot be.
 */

const GAP = {
  2: "gap-2",
  3: "gap-3",
  4: "gap-4",
  5: "gap-5",
  6: "gap-6",
  8: "gap-8",
} as const;

type Gap = keyof typeof GAP;

/** Things stacked down the page, each free to be narrower than its own content.
 *
 * `grid-cols-[minmax(0,1fr)]`, never a bare `grid` or a `flex-col`. A grid's `auto`
 * column is sized by its items' **min-content** width and its items stretch to the
 * column, so one wide table anywhere inside widens the stack — and everything else in it
 * — past the viewport. Mobile Chromium answers that by zooming the whole page out: 412 px
 * of viewport rendered as 754, every tap landing on the wrong element. That was Story
 * A-10, and it took an afternoon to find because nothing looks broken, it just looks
 * small (`docs/gotchas/grid-auto-columns-can-zoom-the-whole-page-out.md`).
 *
 * Allowing the column to be narrower than its content keeps the overflow inside whichever
 * box actually overflows, where an `overflow-x-auto` can deal with it.
 */
export function Stack({
  gap = 4,
  className = "",
  children,
  testId,
}: {
  gap?: Gap;
  className?: string;
  children: ReactNode;
  testId?: string;
}) {
  return (
    <div
      data-testid={testId}
      className={`grid grid-cols-[minmax(0,1fr)] ${GAP[gap]} ${className}`}
    >
      {children}
    </div>
  );
}

/** A list of cards: one column on a phone, two from `sm`, optionally three from `lg`.
 *
 * The breakpoints are the decision, and it belongs in one place — nine lists had it
 * written out, and they had already drifted into two different gaps and two different
 * column counts for lists that look identical to a reader.
 *
 * **Every track is `minmax(0, 1fr)`**, for the same reason as `Stack`: a bare `1fr` track
 * — and the single implicit column a plain `grid` gets on a phone — is floored at its
 * items' min-content width, so one card with a long title widens the whole list past the
 * viewport and the browser zooms the page out (Story A-10). Those nine hand-written
 * copies all said `grid gap-4 sm:grid-cols-2`, and all nine were one long event title
 * away from this. It only ever showed up once the test database had accumulated names
 * long enough to trip it.
 */
export function CardGrid({
  columns = 2,
  gap = 4,
  className = "",
  children,
  testId,
  as: Element = "ul",
}: {
  columns?: 2 | 3;
  gap?: Gap;
  className?: string;
  children: ReactNode;
  testId?: string;
  /** `ul` by default — a list of cards is a list. `div` where the children are not items. */
  as?: "ul" | "div";
}) {
  return (
    <Element
      data-testid={testId}
      className={`grid grid-cols-[minmax(0,1fr)] ${GAP[gap]} sm:grid-cols-[repeat(2,minmax(0,1fr))] ${
        columns === 3 ? "lg:grid-cols-[repeat(3,minmax(0,1fr))]" : ""
      } ${className}`}
    >
      {children}
    </Element>
  );
}
