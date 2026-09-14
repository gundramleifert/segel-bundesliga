import {
  type ColumnDef,
  type RowData,
  type SortingState,
  useTable,
} from "@tanstack/react-table";
import { useTranslation } from "react-i18next";

import type { ListParams } from "../lib/listParams";
import { TABLE_FEATURES } from "../lib/table";
import { formatSort, parseSort } from "../lib/listParams";
import { Empty, TableFrame } from "./Blocks";
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
 *     const query = useListSailors({ ...list.request, sort: list.sort ?? undefined },
 *       { query: { placeholderData: keepPreviousData } });
 *
 *     <DataTable columns={columns} page={query.data} params={list}
 *                testId="admin-sailors" empty={t("sailors.emptyText")} />
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

  if (page && !page.items.length) {
    return <Empty testId={`${testId}-empty`}>{empty}</Empty>;
  }

  return (
    <>
      <TableFrame testId={`${testId}-frame`}>
        <table
          data-testid={`${testId}-table`}
          className="data-table w-full border-collapse text-left text-sm"
        >
          <thead>
            {table.getHeaderGroups().map((group) => (
              <tr key={group.id} className="border-b border-slate-200 bg-slate-50">
                {group.headers.map((header) => {
                  const column = header.column;
                  const sorted = column.getIsSorted();
                  return (
                    <th
                      key={header.id}
                      scope="col"
                      // Only a column that is actually sorted claims a direction; "none"
                      // on every other header is noise in a screen reader.
                      aria-sort={
                        sorted ? (sorted === "desc" ? "descending" : "ascending") : undefined
                      }
                      className="font-medium text-slate-600"
                    >
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
                          <span aria-hidden="true" className="text-xs text-slate-400">
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
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row, index) => (
              <tr
                key={row.id}
                data-testid={`${testId}-row-${
                  rowTestId ? rowTestId(row.original, index) : index
                }`}
                className="border-b border-slate-100 last:border-0"
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
      <Pager page={page} onPage={params.setPage} current={params.page} testId={testId} />
    </>
  );
}

/** Stable empty rows, so a pending page does not hand the table a new array each render. */
const EMPTY: never[] = [];
