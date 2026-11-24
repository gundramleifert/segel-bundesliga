import { keepPreviousData } from "@tanstack/react-query";
import { createColumnHelper } from "@tanstack/react-table";
import { Button } from "@heroui/react";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { useListFeedback, useMarkFeedback } from "../../api/generated/sbl";
import { FeedbackCategory } from "../../api/generated/model/feedbackCategory";
import type { FeedbackOut } from "../../api/generated/model/feedbackOut";
import { useAsync, useInvalidate } from "../../api/useApi";
import { ErrorMessage, Loading } from "../../components/Blocks";
import { DataTable } from "../../components/DataTable";
import { Field, Section } from "../../components/Form";
import { Select } from "../../components/Select";
import { INPUT_CLASS, errorText } from "../../lib/admin";
import { formatDateTime } from "../../lib/format";
import { useListParams, type ListParams } from "../../lib/listParams";
import { TABLE_FEATURES } from "../../lib/table";

/** Story A-15: what people sent with *Feedback* (S-9), newest first — the site's
 *  `feedback_receiver`s and its admin. Kind and handled are filtered on the server
 *  (`FeedbackFilter`), never here. */
export function FeedbackAdmin() {
  const { t } = useTranslation("admin");
  const list = useListParams();
  const category = list.filter("category");
  const state = list.filter("handled");
  const rows = useAsync(
    useListFeedback(
      {
        ...list.request,
        q: list.q || undefined,
        sort: list.sort ?? undefined,
        category: (category || undefined) as FeedbackCategory | undefined,
        handled: state === "" ? undefined : state === "true",
      },
      { query: { placeholderData: keepPreviousData } },
    ),
  );

  return (
    <Section title={t("feedback.title")} testId="admin-feedback-section">
      <div className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-3">
        <Field label={t("feedback.searchLabel")}>
          <input
            className={INPUT_CLASS}
            value={list.q}
            onChange={(e) => list.setQuery(e.target.value)}
            placeholder={t("feedback.searchPlaceholder")}
            data-testid="admin-feedback-search-input"
          />
        </Field>
        <Field label={t("feedback.categoryLabel")}>
          <Select
            value={category}
            onChange={(e) => list.setFilter("category", e.target.value)}
            testId="admin-feedback-category-filter"
          >
            <option value="">{t("feedback.allCategories")}</option>
            {Object.values(FeedbackCategory).map((value) => (
              <option key={value} value={value}>
                {t(`feedback.categories.${value}`, { ns: "common" })}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t("feedback.stateLabel")}>
          <Select
            value={state}
            onChange={(e) => list.setFilter("handled", e.target.value)}
            testId="admin-feedback-state-filter"
          >
            <option value="">{t("feedback.stateAll")}</option>
            <option value="false">{t("feedback.stateOpen")}</option>
            <option value="true">{t("feedback.stateHandled")}</option>
          </Select>
        </Field>
      </div>

      {rows.loading && <Loading text={t("feedback.loadingText")} testId="admin-feedback-loading" />}
      {rows.error && <ErrorMessage text={rows.error} testId="admin-feedback-error" />}
      {rows.data && <FeedbackTable page={rows.data} params={list} />}
    </Section>
  );
}

const column = createColumnHelper<typeof TABLE_FEATURES, FeedbackOut>();

function FeedbackTable({
  page,
  params,
}: {
  page: { items: FeedbackOut[]; total: number; limit: number; offset: number };
  params: ListParams;
}) {
  const { t } = useTranslation("admin");
  const columns = useMemo(
    () =>
      column.columns([
        column.accessor("created_at", {
          header: t("feedback.whenHeader"),
          // Sortable where the server can sort (`FeedbackFilter`).
          enableSorting: true,
          cell: ({ row }) => (
            <span className="whitespace-nowrap tabular-nums">{formatDateTime(row.original.created_at)}</span>
          ),
        }),
        column.accessor("category", {
          header: t("feedback.kindHeader"),
          enableSorting: true,
          cell: ({ row }) => t(`feedback.categories.${row.original.category}`, { ns: "common" }),
        }),
        column.display({
          id: "message",
          header: t("feedback.messageHeader"),
          cell: ({ row }) => (
            <div className="flex min-w-48 max-w-prose flex-col gap-1">
              <p className="whitespace-pre-wrap break-words text-foreground">{row.original.message}</p>
              <Link
                to={row.original.path}
                className="break-all text-xs text-link underline underline-offset-2"
                data-testid={`admin-feedback-path-${row.original.id}`}
              >
                {row.original.path}
              </Link>
            </div>
          ),
        }),
        column.display({
          id: "from",
          header: t("feedback.fromHeader"),
          cell: ({ row }) => (
            <div className="flex flex-col">
              <span className="font-medium text-foreground">{row.original.name}</span>
              <a href={`mailto:${row.original.email}`} className="text-xs text-muted underline-offset-2 hover:underline">
                {row.original.email}
              </a>
            </div>
          ),
        }),
        column.display({
          id: "context",
          header: t("feedback.contextHeader"),
          cell: ({ row }) => <Context row={row.original} />,
        }),
        column.display({
          id: "handled",
          header: t("feedback.handledHeader"),
          cell: ({ row }) => <HandledCell row={row.original} />,
        }),
      ]),
    [t],
  );

  return (
    <DataTable
      columns={columns}
      page={page}
      params={params}
      testId="admin-feedback"
      empty={t("feedback.emptyText")}
      rowTestId={(row) => row.id}
    />
  );
}

/** Language, release, window, browser — what the page knew when it was sent. */
function Context({ row }: { row: FeedbackOut }) {
  const { t } = useTranslation("admin");
  const entries: [string, string][] = [
    [t("feedback.language"), row.locale],
    [t("feedback.release"), row.app_version],
    [
      t("feedback.window"),
      row.viewport_width != null && row.viewport_height != null ? `${row.viewport_width}×${row.viewport_height}` : "",
    ],
    [t("feedback.browser"), row.user_agent],
  ];
  return (
    <dl className="grid min-w-48 grid-cols-[auto_minmax(0,1fr)] gap-x-2 text-xs" data-testid={`admin-feedback-context-${row.id}`}>
      {entries
        .filter(([, value]) => value)
        .map(([label, value]) => (
          <div key={label} className="contents">
            <dt className="text-muted">{label}</dt>
            <dd className="break-words text-foreground">{value}</dd>
          </div>
        ))}
    </dl>
  );
}

function HandledCell({ row }: { row: FeedbackOut }) {
  const { t } = useTranslation("admin");
  const invalidate = useInvalidate();
  const mark = useMarkFeedback({ mutation: { onSuccess: () => invalidate("/api/admin/feedback") } });
  return (
    <div className="flex flex-col items-start gap-1">
      <span className={row.handled ? "text-success" : "text-warning"} data-testid={`admin-feedback-state-${row.id}`}>
        {row.handled ? t("feedback.handled") : t("feedback.open")}
      </span>
      <Button
        size="sm"
        variant="secondary"
        isDisabled={mark.isPending}
        onPress={() => mark.mutate({ feedbackId: row.id, data: { handled: !row.handled } })}
        data-testid={`admin-feedback-toggle-${row.id}`}
      >
        {row.handled ? t("feedback.markOpen") : t("feedback.markHandled")}
      </Button>
      {mark.error && <span className="text-xs text-danger">{errorText(mark.error)}</span>}
    </div>
  );
}
