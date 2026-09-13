import { useState } from "react";
import { useTranslation } from "react-i18next";

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
