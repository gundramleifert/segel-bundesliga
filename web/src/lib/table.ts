import { rowSortingFeature, tableFeatures } from "@tanstack/react-table";

/** The table features this site uses, and no others — Story A-13.
 *
 * TanStack Table v9 registers features explicitly rather than shipping them all, and only
 * sorting is needed here: filtering and paging happen on the server and arrive as data, so
 * there is no `rowPaginationFeature` — the page control is ours (`components/Pager`),
 * driven by the URL, and registering the feature would only add a second, client-side idea
 * of which page this is.
 *
 * It lives in its own module because every screen's column helper is typed by it
 * (`createColumnHelper<typeof TABLE_FEATURES, Row>()`), and because a module that exports
 * both a component and a constant loses React's fast refresh.
 */
export const TABLE_FEATURES = tableFeatures({ rowSortingFeature });
