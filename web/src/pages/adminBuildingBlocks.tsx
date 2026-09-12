import { Card } from "@heroui/react";
import {
  cloneElement,
  isValidElement,
  useId,
  useState,
  type ReactElement,
  type ReactNode,
} from "react";
import { useTranslation } from "react-i18next";

import { ErrorMessage } from "../components/Blocks";
import { slugify } from "../lib/testids";

/** Small pieces shared by every admin form.
 *
 * Deliberately plain form elements instead of HeroUI inputs: the forms here are a tool,
 * not a showcase page, and a plain <input> behaves more predictably in a form than a
 * component with its own state management.
 */

export function Section({
  title,
  hint,
  children,
  testId,
}: {
  title: string;
  hint?: ReactNode;
  children: ReactNode;
  testId?: string;
}) {
  const resolvedTestId = testId ?? `admin-section-${slugify(title)}`;
  return (
    <section data-testid={resolvedTestId}>
      <h2 className="mb-1 text-lg font-semibold">{title}</h2>
      {hint && <p className="mb-3 text-sm text-slate-600">{hint}</p>}
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

/** Two-pane transfer list for choosing which clubs participate.
 *
 * Left: not (yet) selected, with a filter — useful once there are more than a handful of
 * clubs to scan. Right: selected. Clicking an entry moves it across; there's no separate
 * "add"/"remove" button, the click target already says what it does.
 */
export function ClubSelector({
  clubs,
  selectedIds,
  toggle,
  id,
  testId,
}: {
  clubs: { id: number; name: string; short_name: string }[];
  selectedIds: Set<number>;
  toggle: (id: number) => void;
  id?: string;
  testId?: string;
}) {
  const { t } = useTranslation();
  const [filter, setFilter] = useState("");
  const resolvedTestId = testId ?? "clubs-transfer-list";

  const term = filter.trim().toLowerCase();
  const matches = (club: { name: string; short_name: string }) =>
    !term ||
    club.name.toLowerCase().includes(term) ||
    club.short_name.toLowerCase().includes(term);

  const available = clubs.filter((v) => !selectedIds.has(v.id) && matches(v));
  const selected = clubs.filter((v) => selectedIds.has(v.id));

  return (
    <div
      id={id}
      data-testid={resolvedTestId}
      className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-2"
    >
      <div className="rounded-md border border-slate-200">
        <div className="border-b border-slate-200 p-2">
          <input
            type="search"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder={t("common:transferList.filterPlaceholder")}
            aria-label={t("common:transferList.filterPlaceholder")}
            data-testid={`${resolvedTestId}-filter-input`}
            className="w-full rounded border border-slate-300 px-2 py-1 text-sm outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-200"
          />
        </div>
        <p className="px-2 pt-2 text-xs font-medium uppercase tracking-wide text-slate-500">
          {t("common:transferList.available", { count: available.length })}
        </p>
        <ul data-testid={`${resolvedTestId}-available-list`} className="max-h-56 overflow-y-auto p-1">
          {available.map((club) => (
            <li key={club.id}>
              <button
                type="button"
                onClick={() => toggle(club.id)}
                data-testid={`${resolvedTestId}-available-${club.id}`}
                className="flex w-full items-center gap-2 rounded px-2 py-1 text-left text-sm hover:bg-slate-50"
              >
                <span aria-hidden className="text-slate-400">
                  +
                </span>
                <span className="flex-1 truncate">{club.name}</span>
                <span className="text-slate-400">{club.short_name}</span>
              </button>
            </li>
          ))}
          {!available.length && (
            <li
              data-testid={`${resolvedTestId}-available-empty`}
              className="px-2 py-3 text-center text-sm text-slate-400"
            >
              {t("common:transferList.noneAvailable")}
            </li>
          )}
        </ul>
      </div>

      <div className="rounded-md border border-slate-200">
        <p className="border-b border-slate-200 px-2 py-2 text-xs font-medium uppercase tracking-wide text-slate-500">
          {t("common:transferList.selected", { count: selected.length })}
        </p>
        <ul data-testid={`${resolvedTestId}-selected-list`} className="max-h-56 overflow-y-auto p-1">
          {selected.map((club) => (
            <li key={club.id}>
              <button
                type="button"
                onClick={() => toggle(club.id)}
                data-testid={`${resolvedTestId}-selected-${club.id}`}
                className="flex w-full items-center gap-2 rounded px-2 py-1 text-left text-sm hover:bg-slate-50"
              >
                <span className="flex-1 truncate">{club.name}</span>
                <span className="text-slate-400">{club.short_name}</span>
                <span aria-hidden className="text-slate-400">
                  ×
                </span>
              </button>
            </li>
          ))}
          {!selected.length && (
            <li
              data-testid={`${resolvedTestId}-selected-empty`}
              className="px-2 py-3 text-center text-sm text-slate-400"
            >
              {t("common:transferList.noneSelected")}
            </li>
          )}
        </ul>
      </div>
    </div>
  );
}
