import type { ComponentProps } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import ReactMarkdown from "react-markdown";

import { api } from "../api/client";
import { useApi } from "../api/useApi";
import {
  Fehler,
  Laden,
  Leer,
  Seitenkopf,
  SpieltagKarte,
  TabellenRahmen,
} from "../components/Bausteine";
import { punkte } from "../lib/format";

/** Minimal Tailwind styling for the series' Markdown description — this project has no
 *  typography plugin, so headings, emphasis and paragraphs are styled element by element
 *  rather than through a `prose` class. */
const MARKDOWN_COMPONENTS = {
  h1: (props: ComponentProps<"h2">) => (
    <h2 className="mb-2 text-lg font-semibold text-slate-900" {...props} />
  ),
  h2: (props: ComponentProps<"h3">) => (
    <h3 className="mb-2 text-base font-semibold text-slate-900" {...props} />
  ),
  h3: (props: ComponentProps<"h4">) => (
    <h4 className="mb-2 text-sm font-semibold text-slate-900" {...props} />
  ),
  p: (props: ComponentProps<"p">) => (
    <p className="mb-2 text-sm text-slate-600 last:mb-0" {...props} />
  ),
  ul: (props: ComponentProps<"ul">) => (
    <ul className="mb-2 list-disc pl-5 text-sm text-slate-600 last:mb-0" {...props} />
  ),
  ol: (props: ComponentProps<"ol">) => (
    <ol className="mb-2 list-decimal pl-5 text-sm text-slate-600 last:mb-0" {...props} />
  ),
  a: (props: ComponentProps<"a">) => (
    <a className="underline underline-offset-2 hover:text-marke-700" {...props} />
  ),
};

/** B-1: As a fan, I want to see where my team stands in the series.
 *
 * With an id in the URL, the named series; without one, the first of the current year —
 * there are several at once (first, second, juniors, SCL).
 */
export function Standings() {
  const { t } = useTranslation("standings");
  const { id } = useParams();
  const serieId = id ? Number(id) : null;
  const { data, error, loading } = useApi(["series-table", serieId], (signal) =>
    serieId ? api.table(serieId, signal) : api.firstSeries(signal),
  );

  if (loading) return <Laden text={t("loading.text")} />;
  if (error) return <Fehler text={error} />;
  if (!data) return null;

  return (
    <>
      <Seitenkopf
        titel={data.series.name}
        unterzeile={t("subtitle", {
          teamCount: data.rows.length,
          actCount: data.events.length
        })}
      />

      {/* The series' events, front and center — same card as the home page and the
          events list, so a matchday looks the same everywhere it appears. */}
      <section className="mb-8">
        <h2 className="mb-3 text-lg font-semibold">{t("eventsSection.heading")}</h2>
        {data.events.length ? (
          <ul className="grid gap-4 sm:grid-cols-2">
            {data.events.map((event) => (
              <li key={event.id}>
                <SpieltagKarte event={event} />
              </li>
            ))}
          </ul>
        ) : (
          <Leer>{t("eventsSection.empty")}</Leer>
        )}
      </section>

      {/* Free-text, Markdown, written by the admin — nothing shown when absent. */}
      {data.series.description && (
        <div className="mb-6">
          <ReactMarkdown components={MARKDOWN_COMPONENTS}>
            {data.series.description}
          </ReactMarkdown>
        </div>
      )}

      {/* A series without a sailed event has no table — saying so plainly is clearer
          than showing an empty grid. */}
      {!data.rows.length ? (
        <Leer>
          {data.events.length
            ? t("empty.noRaces")
            : t("empty.noEvents")}
        </Leer>
      ) : (
      <>
      <TabellenRahmen>
        <table className="w-full min-w-[36rem] border-collapse text-sm">
          <caption className="sr-only">
            {t("caption", { seriesName: data.series.name })}
          </caption>
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-left">
              <th scope="col" className="w-14 px-4 py-3 font-medium text-slate-600">
                {t("table.rank")}
              </th>
              <th scope="col" className="px-4 py-3 font-medium text-slate-600">
                {t("table.club")}
              </th>
              <th scope="col" className="w-24 px-4 py-3 text-right font-medium text-slate-600">
                {t("table.points")}
              </th>
              {data.events.map((spieltag) => (
                <th
                  key={spieltag.id}
                  scope="col"
                  className="w-20 px-3 py-3 text-center font-medium text-slate-600"
                  title={spieltag.title}
                >
                  {t("table.act", { matchday: spieltag.matchday })}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((zeile) => (
              <tr
                key={zeile.team.id}
                className="border-b border-slate-100 last:border-0 hover:bg-slate-50"
              >
                <td className="px-4 py-3 font-semibold tabular-nums text-slate-900">
                  {zeile.rank}
                </td>
                <td className="px-4 py-3">
                  <Link
                    to={`/clubs/${zeile.team.club.id}`}
                    className="font-medium text-slate-900 underline-offset-2 hover:underline"
                  >
                    {zeile.team.club.name}
                  </Link>
                  <span className="ml-2 text-slate-500">{zeile.team.club.short_name}</span>
                </td>
                <td className="px-4 py-3 text-right font-semibold tabular-nums">
                  {punkte(zeile.points)}
                </td>
                {data.events.map((spieltag) => (
                  <td
                    key={spieltag.id}
                    className="px-3 py-3 text-center tabular-nums text-slate-500"
                  >
                    <span
                      className={
                        zeile.missed_matchdays?.includes(spieltag.matchday ?? 0)
                          ? "italic text-slate-400"
                          : ""
                      }
                      title={
                        zeile.missed_matchdays?.includes(spieltag.matchday ?? 0)
                          ? t("table.notSailed")
                          : undefined
                      }
                    >
                      {zeile.ranks_by_matchday[String(spieltag.matchday)] ?? "–"}
                    </span>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </TabellenRahmen>
      {/* The scoring rule itself is short and unconditional — it stays here as a
          permanent legend, independent of whatever the series' own description says. */}
      <p className="mt-3 text-sm text-slate-500">{t("scoringNote")}</p>
      </>
      )}
    </>
  );
}
