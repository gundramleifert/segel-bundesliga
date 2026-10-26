import { Button, Popover } from "@heroui/react";
import {
  type ColumnDef,
  type RowData,
  type SortingState,
  useTable,
} from "@tanstack/react-table";
import { useTranslation } from "react-i18next";

import { INPUT_CLASS } from "../lib/admin";
import type { ListParams } from "../lib/listParams";
import { TABLE_FEATURES, type ColumnFilter, type TableColumnMeta } from "../lib/table";
import { formatSort, parseSort } from "../lib/listParams";
import { TableFrame } from "./Blocks";
import { Pager } from "./Pager";

/** The one table on this site — Story A-13.
 *
 * Every long list had grown its own arrangement: a `<ul>` of rows here, a table there, a
 * search box on two of them. This is the shape they share: a header row whose sortable
 * columns are buttons, a body, and the paging control underneath.
 *
 * **The server does the work.** Sorting, searching and paging happen in one indexed query
 * (`app/pagination.py`); the table is told so with `manualSorting`/`manualPagination` and
 * is handed exactly the rows to draw plus `rowCount` for the total. It owns the *state
 * model* — which column is sorted, and what the next click on a header means — and we sync
 * that to the URL through {@link ListParams}, so a sorted page can be linked and survives
 * a reload.
 *
 *     const list = useListParams();
 *     const query = useListPeople({ ...list.request, sort: list.sort ?? undefined },
 *       { query: { placeholderData: keepPreviousData } });
 *
 *     <DataTable columns={columns} page={query.data} params={list}
 *                testId="admin-people" empty={t("sailors.emptyText")} />
 *
 * **Filters live in the column they narrow** (the shape of Backbone's table): a column
 * declares them in `meta.filters` (`lib/table.ts`), and its header gets a filter button
 * beside the sort control, opening the choices. Each filter is a query parameter in the
 * URL, read by the server — so a filtered list can be linked like a sorted one. `search`
 * adds the one search box above the table, over the columns the server searches. A page
 * that a filter empties keeps its header — the filter that emptied it stays in reach.
 *
 * Headless means we own every element: the markup below is ours, carries the project's
 * `.data-table` surface, sits in a `TableFrame` so a wide table scrolls inside its panel
 * instead of widening the page (Story A-10), and says `aria-sort` on the column that is
 * sorted, because a sort nobody can hear is a sort half the readers do not have.
 */
export function DataTable<TData extends RowData>({
  columns,
  page,
  params,
  testId,
  empty,
  rowTestId,
  search,
}: {
  /** Built with `createColumnHelper<typeof TABLE_FEATURES, T>().columns([...])`. The
   *  value type is the library's own `any` — a column list is heterogeneous by nature. */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  columns: ColumnDef<typeof TABLE_FEATURES, TData, any>[];
  page: { items: TData[]; total: number; limit: number; offset: number } | null;
  params: ListParams;
  /** Names the table and everything in it: `${testId}-table`, `-row-*`, `-pager`. */
  testId: string;
  empty: string;
  /** A stable id per row, so a test can address one. Defaults to its position. */
  rowTestId?: (row: TData, index: number) => string | number;
  /** A search box above the table (`q`), with this placeholder; none without it. */
  search?: string;
}) {
  const { t } = useTranslation();
  const sorting = parseSort(params.sort);

  const table = useTable({
    features: TABLE_FEATURES,
    columns,
    data: page?.items ?? EMPTY,
    // "The server already sorted this." Without it the table would re-sort the rows it was
    // handed — which are one page of an already-sorted whole, so the result would be a page
    // sorted within itself and wrong across the list.
    manualSorting: true,
    state: { sorting },
    onSortingChange: (updater) => {
      const next = typeof updater === "function" ? updater(sorting) : updater;
      params.setSort(formatSort(next as SortingState));
    },
  });

  return (
    <>
      {search !== undefined && (
        <input
          className={`${INPUT_CLASS} mb-2 max-w-sm`}
          value={params.q}
          onChange={(e) => params.setQuery(e.target.value)}
          placeholder={search}
          aria-label={search}
          data-testid={`${testId}-search-input`}
        />
      )}
      {/* Its own sideways scroller: a table wider than a phone scrolls inside it, never the
          page (Story A-10) — the page that did slid a dialog half off the screen.
          `relative`, or an absolutely placed child (a header's `sr-only` label) escapes the
          scroller and widens the page anyway. */}
      <div className="panel-scroll relative">
        <TableFrame testId={`${testId}-frame`}>
          <table
            data-testid={`${testId}-table`}
            className="data-table w-full border-collapse text-left text-sm"
          >
            <thead>
              {table.getHeaderGroups().map((group) => (
                <tr key={group.id} className="border-b border-separator bg-surface-secondary">
                  {group.headers.map((header) => {
                    const column = header.column;
                    const sorted = column.getIsSorted();
                    const filters = (column.columnDef.meta as TableColumnMeta | undefined)?.filters;
                    return (
                      <th
                        key={header.id}
                        scope="col"
                        // Only a column that is actually sorted claims a direction; "none"
                        // on every other header is noise in a screen reader.
                        aria-sort={
                          sorted ? (sorted === "desc" ? "descending" : "ascending") : undefined
                        }
                        className="font-medium text-muted"
                      >
                        <span className="flex items-center gap-1">
                        {header.isPlaceholder ? null : column.getCanSort() ? (
                          <button
                            type="button"
                            onClick={column.getToggleSortingHandler()}
                            data-testid={`${testId}-sort-${column.id}`}
                            className="flex items-center gap-1 font-medium underline-offset-2 hover:underline"
                          >
                            <table.FlexRender header={header} />
                            {/* A glyph, not an icon font: it has to survive a print and a
                                copy-paste of the table. */}
                            <span aria-hidden="true" className="text-xs text-faint">
                              {sorted === "asc" ? "▲" : sorted === "desc" ? "▼" : "↕"}
                            </span>
                            <span className="sr-only">
                              {sorted === "asc"
                                ? t("table.sortedAscending")
                                : sorted === "desc"
                                  ? t("table.sortedDescending")
                                  : t("table.sortBy")}
                            </span>
                          </button>
                        ) : (
                          <table.FlexRender header={header} />
                        )}
                        {filters?.length ? (
                          <HeaderFilter filters={filters} params={params} testId={`${testId}-filter-${column.id}`} />
                        ) : null}
                        </span>
                      </th>
                    );
                  })}
                </tr>
              ))}
            </thead>
            <tbody>
              {page && !page.items.length && (
                <tr>
                  <td colSpan={table.getAllLeafColumns().length} className="text-muted" data-testid={`${testId}-empty`}>
                    {empty}
                  </td>
                </tr>
              )}
              {table.getRowModel().rows.map((row, index) => (
                <tr
                  key={row.id}
                  data-testid={`${testId}-row-${
                    rowTestId ? rowTestId(row.original, index) : index
                  }`}
                  className="border-b border-separator last:border-0"
                >
                  {row.getAllCells().map((cell) => (
                    <td key={cell.id}>
                      <table.FlexRender cell={cell} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </TableFrame>
      </div>
      <Pager page={page} onPage={params.setPage} current={params.page} testId={testId} />
    </>
  );
}

/** A column's filters, behind one button in its header: each filter's choices, "all"
 *  first, the chosen one marked. The button is marked while any of them is set. Choosing
 *  writes the query parameter (and goes back to page one, `ListParams.setFilter`). */
function HeaderFilter({ filters, params, testId }: { filters: readonly ColumnFilter[]; params: ListParams; testId: string }) {
  const { t } = useTranslation();
  const active = filters.some((f) => params.filter(f.param) !== "");
  return (
    <Popover>
      <Button
        isIconOnly
        size="sm"
        variant="ghost"
        aria-label={t("table.filter")}
        className={active ? "text-accent" : "text-faint"}
        data-active={active || undefined}
        data-testid={testId}
      >
        {/* A funnel, drawn: it has to read as "filter" without an icon font. */}
        <svg aria-hidden="true" viewBox="0 0 16 16" className="size-3.5" fill={active ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.5">
          <path d="M2 3h12l-4.5 5.5V13l-3 1.5V8.5z" strokeLinejoin="round" />
        </svg>
      </Button>
      <Popover.Content placement="bottom start">
        <Popover.Dialog className="flex max-w-xs flex-col gap-3 p-1" data-testid={`${testId}-popover`}>
          {filters.map((filter) => {
            const current = params.filter(filter.param);
            const choice = (value: string, label: string) => (
              <label key={value || "all"} className="flex items-center gap-2 text-sm text-foreground">
                <input
                  type="radio"
                  name={`${testId}-${filter.param}`}
                  checked={current === value}
                  onChange={() => params.setFilter(filter.param, value)}
                  data-testid={`${testId}-${filter.param}-${value || "all"}`}
                />
                {label}
              </label>
            );
            return (
              <fieldset key={filter.param} className="flex flex-col gap-1">
                <legend className="mb-1 text-xs font-medium text-muted">{filter.label}</legend>
                {choice("", t("table.filterAll"))}
                {filter.options.map((o) => choice(o.value, o.label))}
              </fieldset>
            );
          })}
        </Popover.Dialog>
      </Popover.Content>
    </Popover>
  );
}

/** Stable empty rows, so a pending page does not hand the table a new array each render. */
const EMPTY: never[] = [];
