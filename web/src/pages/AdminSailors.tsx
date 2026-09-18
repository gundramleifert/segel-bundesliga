import { keepPreviousData } from "@tanstack/react-query";
import { createColumnHelper } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import {
  useListAllSeries,
  useListSailors,
} from "../api/generated/sbl";
import type { SailorAdmin, SeriesAdmin } from "../api/types";
import { WHOLE_LIST, useAsync, useAsyncRows } from "../api/useApi";
import { DataTable } from "../components/DataTable";
import { TABLE_FEATURES } from "../lib/table";
import { useListParams, type ListParams } from "../lib/listParams";
import { ErrorMessage, Loading, Empty } from "../components/Blocks";
import { SquadPanel } from "../components/SquadPanel";
import { INPUT_CLASS } from "../lib/admin";
import { Section, Field } from "../components/Form";
import { AddButton } from "../components/AddButton";

/** Stories V-4 and V-1: Create sailors and register a squad for a series.
 *
 * Two levels that must not be confused: The **person** exists independently of
 * any competition. The **squad** is their registration for a series—from that, a lineup
 * is drawn for each matchday.
 */
export function SailorsAdmin() {
  return (
    <>
      <Sailors />
      <Squad />
    </>
  );
}

// ------------------------------------------------------------------------ Person

function Sailors() {
  const { t } = useTranslation("admin");

  // Every registered sailor has a row here — a couple of hundred, so paged, sorted and
  // searched on the server, with all three in the URL (Story A-13).
  const list = useListParams();
  const results = useAsync(
    useListSailors(
      { ...list.request, q: list.q || undefined, sort: list.sort ?? undefined },
      { query: { placeholderData: keepPreviousData } },
    ),
  );

  return (
    <Section
      title={t("sailors.title")}
      testId="admin-sailors-section"
      action={<AddButton label={t("sailors.newButton")} to="/admin/sailors/new" testId="admin-sailors-new-button" />}
    >
      <Field label={t("sailors.searchLabel")} hint={t("sailors.searchHint")}>
        <input
          className={INPUT_CLASS}
          value={list.q}
          onChange={(e) => list.setQuery(e.target.value)}
          placeholder={t("sailors.searchPlaceholder")}
          data-testid="admin-sailors-search-input"
        />
      </Field>

      {results.loading && <Loading text={t("sailors.loadingText")} testId="admin-sailors-loading" />}
      {results.error && <ErrorMessage text={results.error} testId="admin-sailors-error" />}
      {results.data && <SailorList page={results.data} params={list} />}
    </Section>
  );
}

const sailorColumn = createColumnHelper<typeof TABLE_FEATURES, SailorAdmin>();

function SailorList({ page, params }: { page: SailorPage; params: ListParams }) {
  const { t } = useTranslation("admin");
  // Memoised, as the library asks: a fresh column array every render rebuilds the table.
  // The headers are translated, so `t` is what it depends on.
  const columns = useMemo(
    () =>
      sailorColumn.columns([
        sailorColumn.accessor("last_name", {
          header: t("sailors.nameHeader"),
          // Sortable exactly where the server can sort (`SAILOR_SORT` in
          // `app/routers/sailors.py`) — a header that promises more would 422.
          enableSorting: true,
          cell: ({ row }) => (
            <Link
              to={`/sailors/${row.original.id}`}
              data-testid={`admin-sailors-link-${row.original.id}`}
              className="font-medium underline-offset-2 hover:underline"
            >
              {row.original.first_name} {row.original.last_name}
            </Link>
          ),
        }),
        sailorColumn.accessor("email", {
          header: t("sailors.emailHeader"),
          enableSorting: true,
          cell: ({ row }) => (
            <span className="text-slate-500">{row.original.email ?? "—"}</span>
          ),
        }),
        sailorColumn.accessor("squads", {
          header: t("sailors.squadsHeader"),
          enableSorting: false,
          cell: ({ row }) => (
            <span className="text-slate-400">
              {/* i18next's own plural forms (`_one` / `_other`), so the count reaches the
                  singular too — a hand-rolled pair showed "{{count}} registration" once. */}
              {t("sailors.registrationsLabel", { count: row.original.squads ?? 0 })}
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
      testId="admin-sailors"
      empty={t("sailors.emptyText")}
      rowTestId={(sailor) => sailor.id}
    />
  );
}

type SailorPage = { items: SailorAdmin[]; total: number; limit: number; offset: number };

// ------------------------------------------------------------------------- Squad

function Squad() {
  const { t } = useTranslation("admin");
  // A selector, so the whole list rather than a page.
  const seriesList = useAsyncRows(useListAllSeries({ limit: WHOLE_LIST }));
  const [seriesId, setSeriesId] = useState<number | null>(null);

  const series = seriesList.data?.find((s) => s.id === seriesId) ?? null;

  return (
    <Section
      title={t("squad.title")}
      testId="admin-squad-section"
    >
      {seriesList.loading && <Loading text={t("squad.seriesLoadingText")} testId="admin-squad-series-loading" />}
      {seriesList.error && <ErrorMessage text={seriesList.error} testId="admin-squad-series-error" />}

      {seriesList.data && (
        <Field label={t("squad.seriesLabel")}>
          <select
            className={INPUT_CLASS}
            value={seriesId ?? ""}
            onChange={(e) => setSeriesId(e.target.value ? Number(e.target.value) : null)}
            data-testid="admin-squad-series-select"
          >
            <option value="">{t("squad.seriesNone")}</option>
            {seriesList.data.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </Field>
      )}

      {series && <SeriesSquad series={series} />}
    </Section>
  );
}

function SeriesSquad({ series }: { series: SeriesAdmin }) {
  const { t } = useTranslation("admin");
  const [teamId, setzeTeamId] = useState<number | null>(null);
  const clubs = series.clubs ?? [];
  const selectedClub = clubs.find((v) => v.team_id === teamId) ?? null;

  if (!clubs.length) {
    return <Empty testId="admin-squad-club-empty">{t("squad.clubEmptyText")}</Empty>;
  }

  return (
    <>
      <Field label={t("squad.clubLabel")}>
        <select
          className={INPUT_CLASS}
          value={teamId ?? ""}
          onChange={(e) => setzeTeamId(e.target.value ? Number(e.target.value) : null)}
          data-testid="admin-squad-club-select"
        >
          <option value="">{t("squad.clubNone")}</option>
          {clubs.map((clubName) => (
            <option key={clubName.team_id} value={clubName.team_id}>
              {clubName.name}
            </option>
          ))}
        </select>
      </Field>

      {selectedClub && <SquadPanel teamId={selectedClub.team_id} title={selectedClub.name} />}
    </>
  );
}
