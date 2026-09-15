import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

/** Two-pane transfer list: left what is available, right what is chosen.
 *
 * Clicking an entry moves it across; there is no separate add/remove button, the click
 * target already says what it does. The left pane carries a filter, useful once there are
 * more than a handful of entries to scan. Written for the clubs of an event
 * (`ClubSelector`) and generalised when the lineup needed the same movement with one
 * more thing on the right — a role per person (`LineupPanel`, Story V-2).
 *
 * The caller owns the selection and its order: `selected` is rendered as given, so a
 * caller can keep the helm first. Something a chosen row needs besides its label — a
 * role select — goes in `selectedExtra`; it is rendered *beside* the move-back button,
 * not inside it, so a click on the select does not unselect the person.
 */
export function TransferList<T extends { id: number }>({
  available,
  selected,
  label,
  secondary,
  matches,
  onSelect,
  onDeselect,
  selectedExtra,
  testId,
  id,
}: {
  available: T[];
  selected: T[];
  /** The main text of a row. */
  label: (item: T) => ReactNode;
  /** A muted addition to the right of the label — a short name, a role in the squad. */
  secondary?: (item: T) => ReactNode;
  /** Whether an available row matches the filter text (already lower-cased). */
  matches: (item: T, term: string) => boolean;
  onSelect: (item: T) => void;
  onDeselect: (item: T) => void;
  selectedExtra?: (item: T) => ReactNode;
  testId: string;
  id?: string;
}) {
  const { t } = useTranslation();
  const [filter, setFilter] = useState("");
  const term = filter.trim().toLowerCase();
  const shown = available.filter((item) => !term || matches(item, term));

  return (
    <div id={id} data-testid={testId} className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-2">
      <div className="rounded-md border border-slate-200">
        <div className="border-b border-slate-200 p-2">
          <input
            type="search"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder={t("common:transferList.filterPlaceholder")}
            aria-label={t("common:transferList.filterPlaceholder")}
            data-testid={`${testId}-filter-input`}
            className="w-full rounded border border-slate-300 px-2 py-1 text-sm outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-200"
          />
        </div>
        <p className="px-2 pt-2 text-xs font-medium uppercase tracking-wide text-slate-500">
          {t("common:transferList.available", { count: shown.length })}
        </p>
        <ul data-testid={`${testId}-available-list`} className="max-h-64 overflow-y-auto p-1">
          {shown.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                onClick={() => onSelect(item)}
                data-testid={`${testId}-available-${item.id}`}
                className="flex w-full items-center gap-2 rounded px-2 py-1 text-left text-sm hover:bg-slate-50"
              >
                <span aria-hidden className="text-slate-400">
                  +
                </span>
                <span className="min-w-0 flex-1 truncate">{label(item)}</span>
                {secondary && <span className="shrink-0 text-xs text-slate-400">{secondary(item)}</span>}
              </button>
            </li>
          ))}
          {!shown.length && (
            <li data-testid={`${testId}-available-empty`} className="px-2 py-3 text-center text-sm text-slate-400">
              {t("common:transferList.noneAvailable")}
            </li>
          )}
        </ul>
      </div>

      <div className="rounded-md border border-slate-200">
        <p className="border-b border-slate-200 px-2 py-2 text-xs font-medium uppercase tracking-wide text-slate-500">
          {t("common:transferList.selected", { count: selected.length })}
        </p>
        <ul data-testid={`${testId}-selected-list`} className="max-h-64 overflow-y-auto p-1">
          {selected.map((item) => (
            <li
              key={item.id}
              data-testid={`${testId}-selected-${item.id}`}
              className="flex items-center gap-2 rounded px-2 py-1 text-sm hover:bg-slate-50"
            >
              <span className="min-w-0 flex-1 truncate">{label(item)}</span>
              {selectedExtra ? (
                selectedExtra(item)
              ) : (
                secondary && <span className="shrink-0 text-xs text-slate-400">{secondary(item)}</span>
              )}
              <button
                type="button"
                onClick={() => onDeselect(item)}
                aria-label={t("common:transferList.remove")}
                data-testid={`${testId}-deselect-${item.id}`}
                className="shrink-0 rounded px-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                <span aria-hidden>×</span>
              </button>
            </li>
          ))}
          {!selected.length && (
            <li data-testid={`${testId}-selected-empty`} className="px-2 py-3 text-center text-sm text-slate-400">
              {t("common:transferList.noneSelected")}
            </li>
          )}
        </ul>
      </div>
    </div>
  );
}
