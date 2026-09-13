import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useListClubs } from "../api/generated/sbl";
import type { Club } from "../api/types";
import { useAsync } from "../api/useApi";
import { Empty, PageHeader } from "../components/Blocks";
import { Async } from "../components/Async";
import { CardGrid } from "../components/Layouts";
import { LinkCard } from "../components/LinkCard";

/** B-4: As a visitor, I want to find the participating clubs. */
export function Clubs() {
  const { t } = useTranslation("clubs");
  const clubs = useAsync(useListClubs());
  const [filter, setFilter] = useState("");

  return (
    <Async state={clubs} testId="clubs" loadingText={t("loading")} empty={t("empty")}>
      {(data) => <ClubList data={data} filter={filter} setFilter={setFilter} />}
    </Async>
  );
}

function ClubList({
  data,
  filter,
  setFilter,
}: {
  data: Club[];
  filter: string;
  setFilter: (value: string) => void;
}) {
  const { t } = useTranslation("clubs");
  const term = filter.trim().toLowerCase();
  const matches = (club: Club) =>
    !term ||
    club.name.toLowerCase().includes(term) ||
    club.short_name.toLowerCase().includes(term) ||
    (club.city ?? "").toLowerCase().includes(term);

  const filtered = data.filter(matches);

  return (
    <>
      <PageHeader
        title={t("title")}
        testId="clubs-header"
      />

      <input
        type="search"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        placeholder={t("searchPlaceholder")}
        aria-label={t("searchPlaceholder")}
        data-testid="clubs-search-input"
        className="mb-4 w-full max-w-sm rounded border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-200"
      />

      {!filtered.length && <Empty testId="clubs-no-matches">{t("noMatches")}</Empty>}

      <CardGrid columns={3} testId="clubs-list">
        {filtered.map((club) => (
          <li key={club.id}>
            <LinkCard
              to={`/clubs/${club.id}`}
              testId={`club-card-${club.id}`}
              title={club.name}
              description={club.city}
              lead={
                club.logo_url ? (
                  <img
                    src={club.logo_url}
                    alt=""
                    className="size-10 shrink-0 rounded-lg bg-white object-contain p-1 ring-1 ring-slate-200"
                  />
                ) : (
                  // No crest uploaded: the abbreviation, rather than a grey placeholder
                  // that says nothing (Story V-3).
                  <span
                    aria-hidden
                    className="grid size-10 shrink-0 place-items-center rounded-lg bg-brand-600 text-xs font-bold text-white"
                  >
                    {club.short_name.slice(0, 4)}
                  </span>
                )
              }
            />
          </li>
        ))}
      </CardGrid>
    </>
  );
}
