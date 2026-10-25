import { keepPreviousData } from "@tanstack/react-query";
import { createColumnHelper } from "@tanstack/react-table";
import { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { useListAllPosts, useListLeagues } from "../../../api/generated/sbl";
import { PostKind, type PostAdminSummary, type PostPage } from "../../../api/types";
import { useAsync } from "../../../api/useApi";
import { AddButton } from "../../../components/AddButton";
import { Badge, ErrorMessage, Loading } from "../../../components/Blocks";
import { DataTable } from "../../../components/DataTable";
import { PublicationBadge } from "../events/PublicationBadge";
import { Field, Section } from "../../../components/Form";
import { Select } from "../../../components/Select";
import { INPUT_CLASS } from "../../../lib/admin";
import { formatDate } from "../../../lib/format";
import { useListParams, type ListParams } from "../../../lib/listParams";
import { TABLE_FEATURES } from "../../../lib/table";

/** Story R-1: editorial's posts — news and press releases, drafts among them — newest
 *  first, each leading to the page it is written on. */
export function PostsAdmin() {
  const { t } = useTranslation("admin");
  const list = useListParams();
  // The filters live in the address like the search, so a filtered list can be shared
  // and survives a reload; changing one goes back to the first page.
  const [params, setParams] = useSearchParams();
  const filter = (key: string) => params.get(key) ?? "";
  // From the address as it is now, not as this render saw it: two filters set one after
  // the other would otherwise each write over the other.
  const setFilter = (key: string, value: string) =>
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        if (value) next.set(key, value);
        else next.delete(key);
        next.delete("page");
        return next;
      },
      { replace: true },
    );
  const leagues = useAsync(useListLeagues());
  const state = filter("state");
  const results = useAsync(
    useListAllPosts(
      {
        ...list.request,
        q: list.q || undefined,
        sort: list.sort ?? undefined,
        kind: (filter("kind") || undefined) as PostKind | undefined,
        league: filter("league") || undefined,
        published: state ? state === "published" : undefined,
      },
      { query: { placeholderData: keepPreviousData } },
    ),
  );

  return (
    <Section
      title={t("posts.title")}
      testId="admin-posts-section"
      action={<AddButton label={t("posts.newButton")} to="/office/news/new" testId="admin-posts-new-button" />}
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
      <div className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-3">
        <Field label={t("posts.kindLabel")}>
          <Select value={filter("kind")} onChange={(e) => setFilter("kind", e.target.value)} testId="admin-posts-kind-filter">
            <option value="">{t("posts.filterAll")}</option>
            <option value={PostKind.news}>{t("posts.kind.news")}</option>
            <option value={PostKind.press}>{t("posts.kind.press")}</option>
          </Select>
        </Field>
        <Field label={t("posts.leagueHeader")}>
          <Select value={filter("league")} onChange={(e) => setFilter("league", e.target.value)} testId="admin-posts-league-filter">
            <option value="">{t("posts.filterAll")}</option>
            <option value="association">{t("posts.association")}</option>
            {(leagues.data ?? []).map((league) => (
              <option key={league.id} value={league.slug}>
                {league.short_name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t("posts.stateHeader")}>
          <Select value={state} onChange={(e) => setFilter("state", e.target.value)} testId="admin-posts-state-filter">
            <option value="">{t("posts.filterAll")}</option>
            <option value="draft">{t("posts.filterDrafts")}</option>
            <option value="published">{t("posts.filterPublished")}</option>
          </Select>
        </Field>
      </div>
      {results.loading && <Loading testId="admin-posts-loading" />}
      {results.error && <ErrorMessage text={results.error} testId="admin-posts-error" />}
      {results.data && <PostTable page={results.data} params={list} />}
    </Section>
  );
}

const column = createColumnHelper<typeof TABLE_FEATURES, PostAdminSummary>();

function PostTable({ page, params }: { page: PostPage; params: ListParams }) {
  const { t } = useTranslation("admin");
  const columns = useMemo(
    () =>
      column.columns([
        column.accessor("published_on", {
          header: t("posts.dateHeader"),
          // Sortable where the server sorts (`POST_SORT`, app/routers/posts.py).
          enableSorting: true,
          cell: ({ row }) => <span className="whitespace-nowrap text-muted">{formatDate(row.original.published_on)}</span>,
        }),
        column.accessor("title", {
          header: t("posts.titleHeader"),
          enableSorting: true,
          cell: ({ row }) => (
            <Link
              to={`/office/news/${row.original.id}`}
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
          cell: ({ row }) => <span className="text-muted">{row.original.league_name ?? t("posts.association")}</span>,
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
