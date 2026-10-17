import { useQueries } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { getGetSeriesTableQueryOptions, useGetEvent, useGetSeriesTable } from "../../api/generated/sbl";
import type { Series } from "../../api/types";
import { ChapterScroller, type ChapterSpec } from "../../components/site/Chapters";
import { useSiteVersion } from "../../components/site/settings";
import {
  DSBL_PHOTOS,
  OWN_PHOTOS,
  leaguePhoto,
  useLeagueAbout,
  useLocalized,
  useNews,
  useVideos,
  type Article,
  type Video,
} from "../../content";
import { formatDate, locationText } from "../../lib/format";
import { href, type Act } from "../../lib/site";
import { LeagueGate, StateBadge, actDates, useActTitle, type LeagueYear } from "./shared";

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
  const full = useSiteVersion() === "submenu";
  const allNews = useNews(league.slug).data ?? [];
  const news = allNews.slice(0, 3);
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
      page: "standings",
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
      extra: acts.length > 0 && <SeasonStrip league={l} acts={acts} year={year} />,
    },
    // Only while a matchday is live: between matchdays the season's page has the calendar.
    ...(live && year
      ? [
          {
            id: "results",
            page: "season",
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
            extra: <LiveProgress eventId={live.first.id} />,
          } satisfies ChapterSpec,
        ]
      : []),
    {
      id: "news",
      page: "news",
      label: t("chapters.news"),
      title: t("chapters.news"),
      photo: DSBL_PHOTOS.swimmer,
      more: { to: href.news(l), label: t("news.more") },
      body: full ? (
        <NewsTiles items={allNews.slice(0, 3)} rest={allNews.slice(3, 6)} link={(n) => href.article(l, n.slug)} />
      ) : (
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
      page: "media",
      label: t("chapters.media"),
      title: t("chapters.media"),
      photo: DSBL_PHOTOS.camera,
      more: { to: href.media(l), label: t("media.more") },
      body: <p className="max-w-xl text-lg text-white/80">{t("media.preview", { count: videos.length })}</p>,
      extra: <VideoTiles league={l} videos={videos} />,
    },
    {
      id: "about",
      page: "about",
      label: t("chapters.about"),
      title: t("chapters.about"),
      photo: OWN_PHOTOS.title,
      more: { to: href.about(l), label: t("about.more") },
      body: (
        <div className="max-w-3xl">
          <p className="text-lg text-white/80">{about ? localized(about.intro) : league.name}</p>
          {full && about && about.facts.length > 0 && (
            <ul className="mt-6 grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-3" data-testid="site-about-facts">
              {about.facts.map((f) => (
                <li key={f.en} className="rounded-2xl bg-white/10 p-4 text-sm leading-relaxed text-white/85 backdrop-blur">
                  {localized(f)}
                </li>
              ))}
            </ul>
          )}
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
            page: "standings",
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

/** The year's matchdays in a row, each with its state — the season at a glance, on the
 *  standings chapter (the layout with a sub-menu). */
function SeasonStrip({ league, acts, year }: { league: string; acts: Act[]; year: number | null }) {
  const { t } = useTranslation("site");
  const actTitle = useActTitle();
  return (
    <div data-testid="site-season-strip">
      <p className="mb-3 text-sm font-semibold uppercase tracking-widest text-white/60">{t("season.calendar", { year: year ?? "" })}</p>
      <ol className="grid grid-cols-[minmax(0,1fr)] gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {acts.map((a) => {
          const inner = (
            <>
              <span className="min-w-0 flex-1">
                <span className="block truncate font-semibold">{actTitle(a)}</span>
                <span className="block text-xs text-white/60">{actDates(a)}</span>
              </span>
              <StateBadge state={a.state} dark />
            </>
          );
          const box = "flex items-center gap-3 rounded-xl bg-white/10 px-4 py-2.5 backdrop-blur";
          return (
            <li key={a.slug}>
              {year ? (
                <Link to={href.act(league, year, a.slug)} className={`${box} transition hover:bg-white/20`}>{inner}</Link>
              ) : (
                <div className={box}>{inner}</div>
              )}
            </li>
          );
        })}
      </ol>
      <Link to={href.season(league)} className="mt-3 inline-block text-sm font-medium text-white/80 hover:text-white hover:underline">
        {t("season.more")} →
      </Link>
    </div>
  );
}

/** How far the running act has come — races sailed of races planned. */
function LiveProgress({ eventId }: { eventId: number }) {
  const { t } = useTranslation("site");
  const data = useGetEvent(eventId).data;
  if (!data || !data.races_total) return null;
  const share = Math.round((100 * data.races_scored) / data.races_total);
  return (
    <div className="max-w-md" data-testid="site-live-progress">
      <p className="mb-2 text-sm text-white/80">{t("live.progress", { scored: data.races_scored, total: data.races_total })}</p>
      <div className="h-2 overflow-hidden rounded-full bg-white/15">
        <div className="h-full rounded-full bg-white" style={{ width: `${share}%` }} />
      </div>
    </div>
  );
}

/** The newest articles as cards over the picture, the next few as headlines. */
export function NewsTiles({ items, rest = [], link }: { items: Article[]; rest?: Article[]; link: (n: Article) => string }) {
  return (
    <div data-testid="site-news-tiles">
      <ul className="grid grid-cols-[minmax(0,1fr)] gap-4 sm:grid-cols-3">
        {items.map((n) => (
          <li key={n.slug}>
            <Link to={link(n)} className="group block h-full overflow-hidden rounded-2xl bg-white/10 backdrop-blur transition hover:bg-white/20">
              <div className="aspect-[16/9] overflow-hidden">
                <img src={n.photo.src} alt={n.photo.alt} loading="lazy" className="block h-full w-full object-cover transition group-hover:scale-105" />
              </div>
              <div className="p-4">
                <p className="text-xs uppercase tracking-widest text-white/60">{formatDate(n.date)}</p>
                <p className="mt-1 font-semibold leading-snug">{n.title}</p>
                <p className="mt-1 line-clamp-2 text-sm text-white/70">{n.teaser}</p>
              </div>
            </Link>
          </li>
        ))}
      </ul>
      {rest.length > 0 && (
        <ul className="mt-5 grid grid-cols-[minmax(0,1fr)] gap-x-6 gap-y-2 sm:grid-cols-3">
          {rest.map((n) => (
            <li key={n.slug}>
              <Link to={link(n)} className="block border-l-2 border-white/40 pl-3 text-sm hover:border-white">
                <span className="block text-xs text-white/50">{formatDate(n.date)}</span>
                <span className="font-medium">{n.title}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** The league's videos as stills, each leading to the media page. */
function VideoTiles({ league, videos }: { league: string; videos: Video[] }) {
  return (
    <ul className="grid grid-cols-[minmax(0,1fr)] gap-4 sm:grid-cols-3" data-testid="site-video-tiles">
      {videos.map((v) => (
        <li key={v.id}>
          <Link to={href.media(league)} className="group block overflow-hidden rounded-2xl bg-white/10 backdrop-blur transition hover:bg-white/20">
            <div className="relative aspect-video overflow-hidden bg-slate-900">
              <img src={`https://i.ytimg.com/vi/${v.id}/hqdefault.jpg`} alt="" loading="lazy" className="block h-full w-full object-cover opacity-90 transition group-hover:scale-105" />
              <span aria-hidden className="absolute inset-0 m-auto flex size-12 items-center justify-center rounded-full bg-white/90 pl-1 text-slate-950">▶</span>
            </div>
            <p className="p-3 text-sm font-medium">{v.title}</p>
          </Link>
        </li>
      ))}
    </ul>
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
