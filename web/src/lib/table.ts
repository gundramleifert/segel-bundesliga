import { metaHelper, rowSortingFeature, tableFeatures } from "@tanstack/react-table";

/** One filter a column offers in its header: a query parameter the **server** narrows by
 *  (Story A-13 — never the page in the browser), with the choices it takes. A boolean
 *  filter is a choice of `"true"` and `"false"`; "all" is the parameter left out.
 *
 *  The shape of Backbone's column filters (`meta.filterKind`, a popover in the header),
 *  not its mechanics: Backbone lists the distinct values of the rows it holds and filters
 *  them in the browser, which here would only ever see one page. */
export type ColumnFilter = {
  /** The list's query parameter — `role`, `no_birth_date`. */
  param: string;
  /** What the filter asks, heading its choices in the popover. */
  label: string;
  /** The choices besides "all", in the order shown. */
  options: readonly { value: string; label: string }[];
};

/** What a column may declare beyond TanStack's own (`meta` of a column definition). */
export type TableColumnMeta = {
  /** The filters in this column's header, each its own query parameter. */
  filters?: readonly ColumnFilter[];
};

/** The table features this site uses, and no others — Story A-13.
 *
 * TanStack Table v9 registers features explicitly rather than shipping them all, and only
 * sorting is needed here: filtering and paging happen on the server and arrive as data, so
 * there is no `rowPaginationFeature` — the page control is ours (`components/Pager`),
 * driven by the URL, and registering the feature would only add a second, client-side idea
 * of which page this is. The column filters are no feature either, for the same reason:
 * `columnMeta` only types what a column declares (`TableColumnMeta`), and `DataTable`
 * turns it into query parameters.
 *
 * It lives in its own module because every screen's column helper is typed by it
 * (`createColumnHelper<typeof TABLE_FEATURES, Row>()`), and because a module that exports
 * both a component and a constant loses React's fast refresh.
 */
export const TABLE_FEATURES = tableFeatures({
  rowSortingFeature,
  columnMeta: metaHelper<TableColumnMeta>(),
});
