import { Card } from "@heroui/react";
import {
  cloneElement,
  isValidElement,
  useId,
  type ReactElement,
  type ReactNode,
} from "react";

import { ErrorMessage } from "./Blocks";
import { slugify } from "../lib/testids";

/** The form primitives every screen here is built from.
 *
 * Deliberately plain form elements instead of HeroUI inputs: the forms here are a tool,
 * not a showcase page, and a plain <input> behaves more predictably in a form than a
 * component with its own state management.
 *
 * These lived under `pages/adminBuildingBlocks.tsx` until `SquadPanel` — a component —
 * needed `Field`, and a component importing from `pages/` is backwards. They were never
 * admin-specific anyway: a labelled control and a save result are the same thing
 * wherever they appear.
 */

export function Section({
  title,
  children,
  testId,
}: {
  title: string;
  children: ReactNode;
  testId?: string;
}) {
  const resolvedTestId = testId ?? `admin-section-${slugify(title)}`;
  return (
    <section data-testid={resolvedTestId}>
      <h2 className="mb-3 text-lg font-semibold">{title}</h2>
      <Card>
        {/* The explicit `minmax(0,1fr)` column matters on a narrow screen: a grid's `auto`
            column is sized by its items' min-content width, so one wide table or form row
            inside a section widens the section — and, through the page's own grid, every
            other section with it. The browser answers that by zooming the whole page out,
            which is how the admin screens ended up unreadable and untappable on a phone
            (Story A-10). Allowing the column to be narrower than its content keeps the
            overflow inside the box that actually overflows. */}
        <Card.Content className="grid grid-cols-[minmax(0,1fr)] gap-4 py-4">{children}</Card.Content>
      </Card>
    </section>
  );
}

export function Field({
  label,
  hint,
  children,
  testId,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
  testId?: string;
}) {
  // The label is associated via htmlFor, not by wrapping the control. Wrapping a
  // <input type="date"> (or any input with a native popup) in a <label> makes every
  // click on the field bubble back to the label and re-toggle the picker — it opens
  // and instantly closes, so a date can never be picked and the form stays un-submittable.
  const id = useId();
  const control = isValidElement(children)
    ? cloneElement(children as ReactElement<{ id?: string }>, { id })
    : children;

  return (
    <div data-testid={testId ?? `field-${slugify(label)}`} className="text-sm">
      <label htmlFor={id} className="font-medium text-slate-700">
        {label}
      </label>
      {hint && <span className="ml-2 text-slate-500">{hint}</span>}
      <div className="mt-1">{control}</div>
    </div>
  );
}

export function Message({
  success,
  error,
  testId,
}: {
  success?: string | null;
  error?: string | null;
  testId?: string;
}) {
  if (error) return <ErrorMessage text={error} testId={testId ? `${testId}-error` : undefined} />;
  if (success) {
    return (
      <p
        role="status"
        data-testid={testId ? `${testId}-success` : "success-message"}
        className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-800"
      >
        {success}
      </p>
    );
  }
  return null;
}
