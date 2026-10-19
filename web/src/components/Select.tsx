import type { SelectHTMLAttributes } from "react";

/** The one dropdown: a native `<select>` with its colours and size decided here.
 *
 *  **Colours are always set, never inherited.** A native select paints its own field and
 *  its own option list, but takes its *text* colour from the page. On paper that is dark
 *  text on a white field; on the official pages' glass (`.on-glass`, `site/Cards.tsx`
 *  `Panel`) the text turns white while the browser still draws a white field and a white
 *  list — white on white (the pairing list's "all clubs" picker, 2026-10-18). So the field
 *  names `bg-white text-slate-900` itself: on paper that is what it says, and `.on-glass`
 *  maps exactly those classes to glass, and gives the open list a dark scheme of its own
 *  (`index.css`, `.on-glass select`). One rule for every dropdown on both surfaces,
 *  instead of a fix per page.
 *
 *  **Size says where it stands**, not how big it looks:
 *  - `field` — a labelled form control, the column's full width (`Field`);
 *  - `inline` — beside a button or a heading in a toolbar, as wide as its longest option;
 *  - `row` — inside a list row, next to a name (`RoleSelect`);
 *  - `touch` — on the water: a thumb-sized target (`RaceControl`).
 *
 *  `className` is for **layout only** — `flex-1`, a fixed width. A colour or a padding
 *  there loses or wins by its place in Tailwind's stylesheet, not in this list
 *  (docs/gotchas, "Appending a Tailwind class…"), so those are props here. */
export type SelectSize = "field" | "inline" | "row" | "touch";

/** `paper` — a field: a white box with a border, on paper and (mapped) on glass.
 *  `bar` — an entry of the top row: no box, the row's own text, its pill shape and hover,
 *  a chevron of its own; on a picture (`dark`) its open list is dark. */
export type SelectTone = "paper" | "bar";

const BASE =
  "rounded-md border bg-white text-slate-900 outline-none " +
  "focus:border-brand-500 focus:ring-2 focus:ring-brand-200 disabled:opacity-60";

const SIZES: Record<SelectSize, string> = {
  field: "w-full px-3 py-2 text-sm",
  inline: "w-auto max-w-full px-2 py-1 text-sm",
  row: "shrink-0 px-1.5 py-0.5 text-xs",
  touch: "min-h-11 px-2",
};

export function Select({
  size = "field",
  tone = "paper",
  dark = false,
  invalid = false,
  testId,
  className = "",
  ...rest
}: {
  size?: SelectSize;
  tone?: SelectTone;
  /** On a dark surface outside `.on-glass` — the top row over a picture: the open list
   *  gets the dark scheme, or its white text would sit on the browser's white. */
  dark?: boolean;
  /** Marks the field wrong — the red border, and `aria-invalid` for a screen reader. */
  invalid?: boolean;
  testId?: string;
  className?: string;
} & Omit<SelectHTMLAttributes<HTMLSelectElement>, "className" | "size">) {
  if (tone === "bar") {
    return (
      <span className={`relative inline-flex shrink-0 items-center ${className}`}>
        <select
          {...rest}
          data-testid={testId}
          className={`cursor-pointer appearance-none rounded-full bg-transparent py-1.5 pl-2.5 pr-6 text-[13px] font-medium text-inherit outline-none transition focus-visible:ring-2 focus-visible:ring-current sm:pl-3 sm:pr-7 sm:text-sm ${
            dark ? "on-dark hover:text-white" : "hover:text-slate-950"
          }`}
        />
        <svg
          aria-hidden
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          className="pointer-events-none absolute right-1.5 size-3.5 sm:right-2"
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </span>
    );
  }
  const border = invalid ? "border-red-500 ring-2 ring-red-200" : "border-slate-300";
  return (
    <select
      {...rest}
      aria-invalid={invalid || undefined}
      data-testid={testId}
      className={`${BASE} ${border} ${SIZES[size]} ${className}`}
    />
  );
}
