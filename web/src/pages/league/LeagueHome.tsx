import { useQueries } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { getGetSeriesTableQueryOptions, useGetSeriesTable } from "../../api/generated/sbl";
import type { Series } from "../../api/types";
import { ChapterScroller, type ChapterSpec } from "../../components/site/Chapters";
import {
  DSBL_PHOTOS,
  OWN_PHOTOS,
  leaguePhoto,
  useLeagueAbout,
  useLocalized,
  useNews,
  useVideos,
} from "../../content";
import { formatDate, locationText } from "../../lib/format";
import { href } from "../../lib/site";
import { LeagueGate, actDates, useActTitle, type LeagueYear } from "./shared";

/** `/:league` — the league's page in chapters, each a preview ending in its own page
 *  (Story B-14). */
export function LeagueHome() {
  return <LeagueGate>{(data) => <Chapters key={data.league.slug} {...data} />}</LeagueGate>;
}

function Chapters({ league, season, acts, year }: LeagueYear) {
  const { t } = useTranslation("site");
  const localized = useLocalized();
  const actTitle = useActTitle();
  const about = useLeagueAbout(league.slug).data;
  const news = (useNews(league.slug).data ?? []).slice(0, 3);
  const videos = useVideos(league.slug).data ?? [];
  const clubs = useClubsOf(season.series);
  const live = acts.find((a) => a.state === "live") ?? null;
  const earlier = season.years.filter((y) => y !== year);
  const several = season.series.length > 1;
  const l = league.slug;

  const chip = "rounded-full border border-white/40 px-4 py-2 hover:bg-white/10";
  // Each chapter is titled with its name — the word on its dot (Story B-14).
  const chapters: ChapterSpec[] = [
    {
      id: "standings",
      label: t("chapters.standings"),
      title: t("chapters.standings"),
      photo: leaguePhoto(l),
      more: { to: href.standings(l), label: t("standings.more") },
      body: season.series.length ? (
        <div className={`grid max-w-4xl grid-cols-[minmax(0,1fr)] gap-4 ${several ? "md:grid-cols-2" : ""}`}>
          {season.series.map((s) => (
            <div key={s.id}>
              {several && <p className="mb-2 text-sm font-semibold text-white/80">{s.name}</p>}
              <TopFive series={s} />
            </div>
          ))}
        </div>
      ) : (
        <p className="text-white/70">{t("standings.noSeries")}</p>
      ),
    },
    // Only while a matchday is live: between matchdays the season's page has the calendar.
    ...(live && year
      ? [
          {
            id: "results",
            label: t("chapters.results"),
            title: t("chapters.results"),
            photo: DSBL_PHOTOS.podium,
            more: { to: href.act(l, year, live.slug, "results"), label: t("now.resultsOf", { act: actTitle(live) }) },
            body: (
              <>
                <p className="max-w-xl text-lg text-white/80">
                  {[
                    actTitle(live),
                    actDates(live),
                    locationText(live.first),
                    live.first.host_club ? t("hostedBy", { host: live.first.host_club.name }) : null,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
                <div className="mt-5 flex flex-wrap gap-2 text-sm">
                  <Link to={href.act(l, year, live.slug, "live")} className={chip}>{t("tabs.live")}</Link>
                  <Link to={href.act(l, year, live.slug, "notice-board")} className={chip}>{t("tabs.notice-board")}</Link>
                </div>
              </>
            ),
          } satisfies ChapterSpec,
        ]
      : []),
    {
      id: "news",
      label: t("chapters.news"),
      title: t("chapters.news"),
      photo: DSBL_PHOTOS.swimmer,
      more: { to: href.news(l), label: t("news.more") },
      body: (
        <ul className="max-w-2xl space-y-4">
          {news.map((n) => (
            <li key={n.slug}>
              <Link to={href.article(l, n.slug)} className="block border-l-2 border-white/50 pl-4 hover:border-white">
                <p className="text-xs uppercase tracking-widest text-white/60">{formatDate(n.date)}</p>
                <p className="text-xl font-semibold">{n.title}</p>
              </Link>
            </li>
          ))}
        </ul>
      ),
    },
    {
      id: "media",
      label: t("chapters.media"),
      title: t("chapters.media"),
      photo: DSBL_PHOTOS.camera,
      more: { to: href.media(l), label: t("media.more") },
      body: <p className="max-w-xl text-lg text-white/80">{t("media.preview", { count: videos.length })}</p>,
    },
    {
      id: "about",
      label: t("chapters.about"),
      title: t("chapters.about"),
      photo: OWN_PHOTOS.title,
      more: { to: href.about(l), label: t("about.more") },
      body: (
        <div className="max-w-3xl">
          <p className="text-lg text-white/80">{about ? localized(about.intro) : league.name}</p>
          {clubs.length > 0 && (
            <ul className="mt-5 flex flex-wrap gap-2" data-testid="site-about-clubs">
              {clubs.slice(0, 36).map((c) => (
                <li key={c.id} className="rounded-full bg-white/10 px-3 py-1 text-sm backdrop-blur">
                  {c.short_name}
                </li>
              ))}
            </ul>
          )}
          <div className="mt-5 flex flex-wrap gap-2 text-sm">
            <Link to={href.clubs(l)} className={chip}>{t("clubs.more")}</Link>
            <Link to={href.press(l)} className={chip}>{t("press.more")}</Link>
          </div>
        </div>
      ),
    },
    // The earlier years, each leading to its standings; none yet, no chapter.
    ...(earlier.length
      ? [
          {
            id: "archive",
            label: t("chapters.archive"),
            title: t("chapters.archive"),
            photo: DSBL_PHOTOS.aerial,
            body: (
              <ul className="flex max-w-3xl flex-wrap gap-2" data-testid="site-archive-years">
                {earlier.map((y) => (
                  <li key={y}>
                    <Link to={href.standings(l, y)} className={`block ${chip} text-lg font-semibold`}>
                      {y}
                    </Link>
                  </li>
                ))}
              </ul>
            ),
          } satisfies ChapterSpec,
        ]
      : []),
  ];
  return <ChapterScroller chapters={chapters} league={league} />;
}

/** The first five of a division, on the picture. */
function TopFive({ series }: { series: Series }) {
  const { t } = useTranslation("site");
  const table = useGetSeriesTable(series.id).data;
  const rows = (table?.rows ?? []).filter((r) => (r.events_sailed ?? 0) > 0).slice(0, 5);
  if (!table) return <div className="h-48 animate-pulse rounded-2xl bg-white/10" />;
  if (!rows.length) return <p className="text-white/70">{t("standings.notYet")}</p>;
  return (
    <ol className="divide-y divide-white/10 rounded-2xl bg-white/10 px-4 backdrop-blur" data-testid={`site-top-five-${series.slug}`}>
      {rows.map((row) => (
        <li key={row.team.id} className="flex items-center gap-3 py-2">
          <span className="w-6 text-white/50">{row.rank}</span>
          <span className="flex-1 font-semibold">{row.team.club.short_name}</span>
          <span className="tabular-nums">{row.points}</span>
        </li>
      ))}
    </ol>
  );
}

/** Every club entered in the year's series, once — the clubs chapter's names. */
export function useClubsOf(series: Series[]) {
  const tables = useQueries({ queries: series.map((s) => getGetSeriesTableQueryOptions(s.id)) });
  const seen = new Map<number, { id: number; short_name: string; name: string }>();
  for (const table of tables) for (const row of table.data?.rows ?? []) seen.set(row.team.club.id, row.team.club);
  return [...seen.values()];
}
