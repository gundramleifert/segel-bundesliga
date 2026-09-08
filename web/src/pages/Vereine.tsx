import { Card } from "@heroui/react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { api, type Club } from "../api/client";
import { useApi } from "../api/useApi";
import { Fehler, Laden, Leer, Seitenkopf } from "../components/Bausteine";

/** B-4: As a visitor, I want to find the participating clubs. */
export function Clubs() {
  const { t } = useTranslation("clubs");
  const { data, error, loading } = useApi(["clubs"], (signal) => api.clubs(signal));
  const [filter, setFilter] = useState("");

  if (loading) return <Laden text={t("loading")} />;
  if (error) return <Fehler text={error} />;
  if (!data?.length) return <Leer>{t("empty")}</Leer>;

  const term = filter.trim().toLowerCase();
  const matches = (verein: Club) =>
    !term ||
    verein.name.toLowerCase().includes(term) ||
    verein.short_name.toLowerCase().includes(term) ||
    (verein.city ?? "").toLowerCase().includes(term);

  const gefiltert = data.filter(matches);

  return (
    <>
      <Seitenkopf titel={t("title")} unterzeile={t("subtitle", { count: data.length })} />

      <input
        type="search"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        placeholder={t("searchPlaceholder")}
        aria-label={t("searchPlaceholder")}
        className="mb-4 w-full max-w-sm rounded border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-marke-500 focus:ring-1 focus:ring-marke-200"
      />

      {!gefiltert.length && <Leer>{t("noMatches")}</Leer>}

      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {gefiltert.map((verein) => (
          <li key={verein.id}>
            <Link to={`/clubs/${verein.id}`} className="group block h-full">
              <Card className="h-full transition-shadow group-hover:shadow-md">
                <Card.Header>
                  <div className="flex items-center gap-3">
                    {verein.logo_url ? (
                      <img
                        src={verein.logo_url}
                        alt=""
                        className="size-10 shrink-0 rounded-lg bg-white object-contain p-1 ring-1 ring-slate-200"
                      />
                    ) : (
                      <span
                        aria-hidden
                        className="grid size-10 shrink-0 place-items-center rounded-lg bg-marke-600 text-xs font-bold text-white"
                      >
                        {verein.short_name.slice(0, 4)}
                      </span>
                    )}
                    <div className="min-w-0">
                      <Card.Title className="truncate text-base">{verein.name}</Card.Title>
                      <Card.Description>{verein.city}</Card.Description>
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
