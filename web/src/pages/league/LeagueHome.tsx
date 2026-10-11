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
  usePress,
  useVideos,
} from "../../content";
import { formatDate, locationText } from "../../lib/format";
import { currentAct, hasResults, href, lastSailed, type Act } from "../../lib/site";
import { LeagueGate, StateBadge, actDates, divisionName, useActTitle, type LeagueYear } from "./shared";

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
  const press = (usePress(league.slug).data ?? []).slice(0, 3);
  const videos = useVideos(league.slug).data ?? [];
  const clubs = useClubsOf(season.series);
  const act = currentAct(acts);
  const last = lastSailed(acts);
  const several = season.series.length > 1;
  const l = league.slug;

  const chip = "rounded-full border border-white/40 px-4 py-2 hover:bg-white/10";
  const chapters: ChapterSpec[] = [
    {
      id: "now",
      label: t("chapters.now"),
      title: !act
        ? t("now.nothingYet", { league: league.short_name })
        : act.state === "done"
          ? t("now.seasonComplete")
          : t("now.title", { act: actTitle(act), dates: actDates(act) }),
      photo: leaguePhoto(l),
      more: act && year ? { to: href.act(l, year, act.slug), label: t("now.matchdayPage") } : undefined,
      body: act ? (
        <>
          <p className="max-w-xl text-lg text-white/80">
            {[
              locationText(act.first),
              act.first.host_club ? t("hostedBy", { host: act.first.host_club.name }) : null,
              act.events.map(divisionName).join(" · "),
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
          <div className="mt-5 flex flex-wrap gap-2 text-sm">
            {year && <Link to={href.act(l, year, act.slug, "live")} className={chip}>{t("tabs.live")}</Link>}
            {year && <Link to={href.act(l, year, act.slug, "notice-board")} className={chip}>{t("tabs.notice-board")}</Link>}
            {last && <Link to={href.results(l)} className={chip}>{t("now.resultsOf", { act: actTitle(last) })}</Link>}
          </div>
        </>
      ) : (
        <p className="max-w-xl text-lg text-white/80">{league.tagline}</p>
      ),
    },
    {
      id: "standings",
      label: t("chapters.standings"),
      title: t("standings.title"),
      photo: DSBL_PHOTOS.podium,
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
    {
      id: "season",
      label: t("chapters.season"),
      title: t("season.title", { count: acts.length }),
      photo: DSBL_PHOTOS.aerial,
      more: { to: href.season(l), label: t("season.more") },
      body: acts.length ? (
        <div className="max-w-2xl rounded-2xl bg-white/10 px-4 backdrop-blur">
          {acts.map((a) => (
            <ActLine key={a.slug} league={l} year={year} act={a} title={actTitle(a)} />
          ))}
        </div>
      ) : (
        <p className="text-white/70">{t("season.empty")}</p>
      ),
    },
    {
      id: "clubs",
      label: t("chapters.clubs"),
      title: clubs.length ? t("clubs.title", { count: clubs.length }) : t("clubs.titleNone"),
      photo: DSBL_PHOTOS.race,
      more: { to: href.clubs(l), label: t("clubs.more") },
      body: clubs.length ? (
        <ul className="flex max-w-3xl flex-wrap gap-2">
          {clubs.slice(0, 36).map((c) => (
            <li key={c.id} className="rounded-full bg-white/10 px-3 py-1 text-sm backdrop-blur">
              {c.short_name}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-white/70">{t("clubs.none")}</p>
      ),
    },
    {
      id: "news",
      label: t("chapters.news"),
      title: t("news.title"),
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
      title: t("media.title"),
      photo: DSBL_PHOTOS.camera,
      more: { to: href.media(l), label: t("media.more") },
      body: <p className="max-w-xl text-lg text-white/80">{t("media.preview", { count: videos.length })}</p>,
    },
    {
      id: "press",
      label: t("chapters.press"),
      title: t("press.title"),
      photo: DSBL_PHOTOS.studio,
      more: { to: href.press(l), label: t("press.more") },
      body: (
        <ul className="max-w-2xl space-y-2">
          {press.map((p) => (
            <li key={p.title} className="flex items-baseline gap-3">
              <span className="w-28 shrink-0 text-sm text-white/60">{formatDate(p.date)}</span>
              <span className="font-medium">{p.title}</span>
            </li>
          ))}
        </ul>
      ),
    },
    {
      id: "about",
      label: t("chapters.about"),
      title: t("about.title", { league: league.short_name }),
      photo: OWN_PHOTOS.title,
      more: { to: href.about(l), label: t("about.more") },
      body: <p className="max-w-2xl text-lg text-white/80">{about ? localized(about.intro) : league.name}</p>,
    },
  ];
  return <ChapterScroller chapters={chapters} league={league} />;
}

function ActLine({ league, year, act, title }: { league: string; year: number | null; act: Act; title: string }) {
  const body = (
    <>
      <span className="w-32 shrink-0 text-sm text-white/70">{actDates(act)}</span>
      <span className="min-w-0 flex-1 truncate font-medium">{title}</span>
      <StateBadge state={act.state} dark />
    </>
  );
  const row = "flex items-center gap-4 border-b border-white/15 py-2.5 transition last:border-0";
  return year ? (
    <Link to={href.act(league, year, act.slug, hasResults(act) ? "results" : undefined)} className={`${row} hover:bg-white/5`}>
      {body}
    </Link>
  ) : (
    <div className={row}>{body}</div>
  );
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
