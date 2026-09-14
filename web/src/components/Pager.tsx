import { Button } from "@heroui/react";
import { useTranslation } from "react-i18next";

/** One page of a long list, and the way to the next one — Story A-13.
 *
 * The backend answers every list that grows with the database as
 * `{ items, total, limit, offset }` (`api/app/pagination.py`). This renders the second
 * half of that envelope: where the reader is, and how to move. It is deliberately the only
 * place that turns three numbers into the sentence "26–50 of 180", because four screens
 * had started to need it and each would have counted the last row slightly differently.
 *
 * It renders **nothing** when everything fits on one page — a pager under a list of twelve
 * clubs is noise that says only "there is no more".
 *
 * The page someone is on lives in the URL, not in this component — see `lib/listParams`,
 * which owns `?page=`, `?sort=` and `?q=` together because they interact. Paging with
 * TanStack Query: the offset is part of the query key (a different page is a different
 * query, not a stale version of the same one), so the hook needs
 * `placeholderData: keepPreviousData` — without it `data` empties on every step and the
 * list is replaced by a spinner between pages.
 *
 *     const list = useListParams();
 *     const query = useListEvents({ ...list.request },
 *       { query: { placeholderData: keepPreviousData } });
 *     ...
 *     <Pager page={query.data} current={list.page} onPage={list.setPage} testId="events" />
 */
export function Pager({
  page,
  current,
  onPage,
  testId,
}: {
  page: { total: number; limit: number; offset: number } | null | undefined;
  /** The page someone is on, 1-based — it lives in the URL (`lib/listParams`). */
  current: number;
  onPage: (page: number) => void;
  testId: string;
}) {
  const { t } = useTranslation();
  if (!page || page.total <= page.limit) return null;

  const { total, limit, offset } = page;
  const first = offset + 1;
  // The last row of *this* page, which is not `offset + limit` on the final page.
  const last = Math.min(offset + limit, total);
  const pages = Math.ceil(total / limit);

  return (
    <div
      data-testid={`${testId}-pager`}
      className="mt-4 flex flex-wrap items-center justify-between gap-3"
    >
      <p className="text-sm text-slate-600" data-testid={`${testId}-pager-range`}>
        {t("pager.range", { first, last, total })}
      </p>
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          variant="ghost"
          isDisabled={current <= 1}
          onPress={() => onPage(current - 1)}
          data-testid={`${testId}-pager-previous`}
        >
          {t("pager.previous")}
        </Button>
        <span className="text-sm text-slate-600" data-testid={`${testId}-pager-page`}>
          {t("pager.page", { page: current, pages })}
        </span>
        <Button
          size="sm"
          variant="ghost"
          isDisabled={current >= pages}
          onPress={() => onPage(current + 1)}
          data-testid={`${testId}-pager-next`}
        >
          {t("pager.next")}
        </Button>
      </div>
    </div>
  );
}

/** Rows per page on the screens that page.
 *
 * The same number the backend defaults to (`app/pagination.py::DEFAULT_LIMIT`), named here
 * so that asking for a page and asking for the whole list (`WHOLE_LIST` in `api/useApi`)
 * read as two different decisions rather than two magic numbers.
 */
export const PAGE_SIZE = 25;
