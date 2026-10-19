import { keepPreviousData } from "@tanstack/react-query";
import { createColumnHelper } from "@tanstack/react-table";
import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { useListAllPosts } from "../../../api/generated/sbl";
import type { PostAdmin, PostPage } from "../../../api/types";
import { useAsync } from "../../../api/useApi";
import { AddButton } from "../../../components/AddButton";
import { Badge, ErrorMessage, Loading } from "../../../components/Blocks";
import { DataTable } from "../../../components/DataTable";
import { PublicationBadge } from "../events/PublicationBadge";
import { Field, Section } from "../../../components/Form";
import { INPUT_CLASS } from "../../../lib/admin";
import { formatDate } from "../../../lib/format";
import { useListParams, type ListParams } from "../../../lib/listParams";
import { TABLE_FEATURES } from "../../../lib/table";

/** Story R-1: editorial's posts — news and press releases, drafts among them — newest
 *  first, each leading to the page it is written on. */
export function PostsAdmin() {
  const { t } = useTranslation("admin");
  const list = useListParams();
  const results = useAsync(
    useListAllPosts(
      { ...list.request, q: list.q || undefined, sort: list.sort ?? undefined },
      { query: { placeholderData: keepPreviousData } },
    ),
  );

  return (
    <Section
      title={t("posts.title")}
      testId="admin-posts-section"
      action={<AddButton label={t("posts.newButton")} to="/admin/news/new" testId="admin-posts-new-button" />}
    >
      <Field label={t("posts.searchLabel")}>
        <input
          className={INPUT_CLASS}
          value={list.q}
          onChange={(e) => list.setQuery(e.target.value)}
          placeholder={t("posts.searchPlaceholder")}
          data-testid="admin-posts-search-input"
        />
      </Field>
      {results.loading && <Loading testId="admin-posts-loading" />}
      {results.error && <ErrorMessage text={results.error} testId="admin-posts-error" />}
      {results.data && <PostTable page={results.data} params={list} />}
    </Section>
  );
}

const column = createColumnHelper<typeof TABLE_FEATURES, PostAdmin>();

function PostTable({ page, params }: { page: PostPage; params: ListParams }) {
  const { t } = useTranslation("admin");
  const columns = useMemo(
    () =>
      column.columns([
        column.accessor("published_on", {
          header: t("posts.dateHeader"),
          // Sortable where the server sorts (`POST_SORT`, app/routers/posts.py).
          enableSorting: true,
          cell: ({ row }) => <span className="whitespace-nowrap text-slate-500">{formatDate(row.original.published_on)}</span>,
        }),
        column.accessor("title", {
          header: t("posts.titleHeader"),
          enableSorting: true,
          cell: ({ row }) => (
            <Link
              to={`/admin/news/${row.original.id}`}
              className="font-medium underline-offset-2 hover:underline"
              data-testid={`admin-posts-link-${row.original.id}`}
            >
              {row.original.title}
            </Link>
          ),
        }),
        column.accessor("kind", {
          header: t("posts.kindHeader"),
          enableSorting: false,
          cell: ({ row }) => t(`posts.kind.${row.original.kind}`),
        }),
        column.accessor("league", {
          header: t("posts.leagueHeader"),
          enableSorting: false,
          cell: ({ row }) => <span className="text-slate-500">{row.original.league ?? t("posts.association")}</span>,
        }),
        column.accessor("published", {
          header: t("posts.stateHeader"),
          enableSorting: false,
          cell: ({ row }) => (
            <span className="flex flex-wrap gap-1">
              <PublicationBadge published={row.original.published} testId={`admin-posts-state-${row.original.id}`} />
              {row.original.example && <Badge>{t("posts.exampleBadge")}</Badge>}
            </span>
          ),
        }),
      ]),
    [t],
  );
  return (
    <DataTable
      columns={columns}
      page={page}
      params={params}
      testId="admin-posts"
      empty={t("posts.emptyText")}
      rowTestId={(post) => post.id}
    />
  );
}
