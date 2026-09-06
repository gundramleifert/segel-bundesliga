import { Card } from "@heroui/react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import { useApi } from "../api/useApi";
import { Fehler, Laden, Leer, Seitenkopf } from "../components/Bausteine";

/** B-4: As a visitor, I want to find the participating clubs. */
export function Clubs() {
  const { t } = useTranslation("clubs");
  const { data, error, loading } = useApi(["clubs"], (signal) => api.clubs(signal));

  if (loading) return <Laden text={t("loading")} />;
  if (error) return <Fehler text={error} />;
  if (!data?.length) return <Leer>{t("empty")}</Leer>;

  return (
    <>
      <Seitenkopf titel={t("title")} unterzeile={t("subtitle", { count: data.length })} />

      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {data.map((verein) => (
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
