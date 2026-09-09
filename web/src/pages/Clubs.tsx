import { Card } from "@heroui/react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { api, type Club } from "../api/client";
import { useApi } from "../api/useApi";
import { ErrorMessage, Loading, Empty, PageHeader } from "../components/Blocks";

/** B-4: As a visitor, I want to find the participating clubs. */
export function Clubs() {
  const { t } = useTranslation("clubs");
  const { data, error, loading } = useApi(["clubs"], (signal) => api.clubs(signal));
  const [filter, setFilter] = useState("");

  if (loading) return <Loading text={t("loading")} testId="clubs-loading" />;
  if (error) return <ErrorMessage text={error} testId="clubs-error" />;
  if (!data?.length) return <Empty testId="clubs-empty">{t("empty")}</Empty>;

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
        subtitle={t("subtitle", { count: data.length })}
        testId="clubs-header"
      />

      <input
        type="search"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        placeholder={t("searchPlaceholder")}
        aria-label={t("searchPlaceholder")}
        data-testid="clubs-search-input"
        className="mb-4 w-full max-w-sm rounded border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-marke-500 focus:ring-1 focus:ring-marke-200"
      />

      {!filtered.length && <Empty testId="clubs-no-matches">{t("noMatches")}</Empty>}

      <ul data-testid="clubs-list" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map((club) => (
          <li key={club.id}>
            <Link
              to={`/clubs/${club.id}`}
              data-testid={`club-card-${club.id}`}
              className="group block h-full"
            >
              <Card className="h-full transition-shadow group-hover:shadow-md">
                <Card.Header>
                  <div className="flex items-center gap-3">
                    {club.logo_url ? (
                      <img
                        src={club.logo_url}
                        alt=""
                        className="size-10 shrink-0 rounded-lg bg-white object-contain p-1 ring-1 ring-slate-200"
                      />
                    ) : (
                      <span
                        aria-hidden
                        className="grid size-10 shrink-0 place-items-center rounded-lg bg-marke-600 text-xs font-bold text-white"
                      >
                        {club.short_name.slice(0, 4)}
                      </span>
                    )}
                    <div className="min-w-0">
                      <Card.Title className="truncate text-base">{club.name}</Card.Title>
                      <Card.Description>{club.city}</Card.Description>
                    </div>
                  </div>
                </Card.Header>
              </Card>
            </Link>
          </li>
        ))}
      </ul>
    </>
  );
}
