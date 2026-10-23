import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { useGetEvent, useGetSeriesTable } from "../../api/generated/sbl";
import type { Series } from "../../api/types";
import { Card, CardRow, Columns, MediaCard, TextCard, tone } from "../../components/site/Cards";
import { ChapterScroller, type ChapterSpec } from "../../components/site/Chapters";
import {
  useLeagueAbout,
  useLocalized,
  useNews,
  useVideos,
  type ArticleSummary,
  type Video,
} from "../../content";
import { formatDate, locationText, teamLabel } from "../../lib/format";
import { href, type Act } from "../../lib/site";
import { LeagueGate, StateBadge, actDates, useActName, useActTitle, type LeagueYear } from "./shared";

/** `/:league` — the league's page in chapters, each a preview ending in its own page
 *  (Story B-14). */
export function LeagueHome() {
  return <LeagueGate>{(data) => <Chapters key={data.league.slug} {...data} />}</LeagueGate>;
}

function Chapters({ league, season, acts, year }: LeagueYear) {
  const { t } = useTranslation("site");
  const localized = useLocalized();
  const actTitle = useActTitle();
  const actName = useActName();
  const about = useLeagueAbout(league.slug).data;
  const news = useNews(league.slug).data ?? [];
  const videos = useVideos(league.slug).data ?? [];
  const clubs = season.clubs ?? [];
  const live = acts.find((a) => a.state === "live") ?? null;
  const earlier = season.years.filter((y) => y !== year);
  const several = season.series.length > 1;
  const l = league.slug;

  const fives = season.series.map((s) => <TopFive key={s.id} series={s} label={several ? s.name : undefined} />);
  const table = !season.series.length ? (
    <TextCard>{t("standings.noSeries")}</TextCard>
  ) : several ? (
    <Columns>{fives}</Columns>
  ) : (
    fives[0]
  );
  // Each chapter is titled with its name — the word on its dot (Story B-14).
  const chapters: ChapterSpec[] = [
    // Only while a matchday is live, and then it opens the page — on a race day that is
    // what a fan comes for (Story B-14). Between matchdays the season's page has the calendar.
    ...(live && year
      ? [
          {
            id: "results",
            label: t("chapters.results"),
            // About one act, so its title names it: "Results Act 2" — and, opening the page,
            // that is the page's heading.
            title: t("now.resultsOf", { act: actName(live) }),
            more: { to: href.act(l, year, live.slug, "results"), label: t("now.resultsOf", { act: actTitle(live) }) },
            body: (
              <Card className="p-5" testId="site-live-act">
                <p className="text-lg text-muted">
                  {[
                    actTitle(live),
                    actDates(live),
                    locationText(live.first),
                    live.first.host_club ? t("hostedBy", { host: live.first.host_club.name }) : null,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
                <div className="my-5 flex flex-wrap gap-2 text-sm">
                  <Link to={href.act(l, year, live.slug, "live")} className="rounded-full bg-default px-4 py-2 hover:bg-default-hover">{t("tabs.live")}</Link>
                  <Link to={href.act(l, year, live.slug, "notice-board")} className="rounded-full bg-default px-4 py-2 hover:bg-default-hover">{t("tabs.notice-board")}</Link>
                </div>
                <LiveProgress eventId={live.first.id} />
              </Card>
            ),
          } satisfies ChapterSpec,
        ]
      : []),
    {
      id: "standings",
      label: t("chapters.standings"),
      title: t("chapters.standings"),
      more: { to: href.standings(l), label: t("standings.more") },
      // The table on the left, the year's matchdays beside it.
      body: acts.length ? (
        <Columns testId="site-standings-split">
          {table}
          <SeasonStrip league={l} acts={acts} year={year} />
        </Columns>
      ) : (
        table
      ),
    },
    {
      id: "news",
      label: t("chapters.news"),
      title: t("chapters.news"),
      more: { to: href.news(l), label: t("news.more") },
      body: <NewsTiles items={news.slice(0, 3)} rest={news.slice(3, 6)} link={(n) => href.article(l, n.slug)} />,
    },
    {
      id: "media",
      label: t("chapters.media"),
      title: t("chapters.media"),
      more: { to: href.media(l), label: t("media.more") },
      body: (
        <>
          <TextCard>{t("media.preview", { count: videos.length })}</TextCard>
          <VideoTiles league={l} videos={videos} />
        </>
      ),
    },
    {
      id: "about",
      label: t("chapters.about"),
      title: t("chapters.about"),
      more: { to: href.about(l), label: t("about.more") },
      body: (
        <>
          <TextCard className="text-lg leading-relaxed">{about ? localized(about.intro) : league.name}</TextCard>
          {about && about.facts.length > 0 && (
            <CardRow testId="site-about-facts">
              {about.facts.map((f) => (
                <li key={f.en}>
                  <Card className="h-full p-4 text-sm leading-relaxed text-muted">{localized(f)}</Card>
                </li>
              ))}
            </CardRow>
          )}
          {/* One card of names, not 36 pills of glass: each would blur the picture again. */}
          {clubs.length > 0 && (
            <Card className="p-4">
              <ul className="flex flex-wrap gap-2" data-testid="site-about-clubs">
                {clubs.slice(0, 36).map((c) => (
                  <li key={c.id} className="rounded-full bg-default px-3 py-1 text-sm">
                    {c.short_name}
                  </li>
                ))}
              </ul>
            </Card>
          )}
          <div className="flex flex-wrap gap-2 text-sm">
            <Link to={href.clubs(l)} className={tone.chip}>{t("clubs.more")}</Link>
            <Link to={href.press(l)} className={tone.chip}>{t("press.more")}</Link>
          </div>
        </>
      ),
    },
    // The earlier years, each leading to its standings; none yet, no chapter.
    ...(earlier.length
      ? [
          {
            id: "archive",
            label: t("chapters.archive"),
            title: t("chapters.archive"),
            body: (
              <ul className="flex flex-wrap gap-2" data-testid="site-archive-years">
                {earlier.map((y) => (
                  <li key={y}>
                    <Link to={href.standings(l, y)} className={`block ${tone.chip} text-lg font-semibold`}>
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

/** The year's matchdays, each with its state — the season at a glance, beside the table
 *  on the standings chapter. */
function SeasonStrip({ league, acts, year }: { league: string; acts: Act[]; year: number | null }) {
  const { t } = useTranslation("site");
  const actTitle = useActTitle();
  return (
    // One card, like the table beside it: its label and its link inside, no text bare.
    <Card className="px-4" testId="site-season-strip">
      <p className="flex items-baseline justify-between gap-3 border-b border-separator py-2.5 text-sm">
        <span className="font-semibold uppercase tracking-widest text-muted">{t("season.calendar", { year: year ?? "" })}</span>
        <Link to={href.season(league)} className="font-medium text-muted hover:text-foreground hover:underline">
          {t("season.more")} →
        </Link>
      </p>
      <ol className="divide-y divide-separator">
        {acts.map((a) => {
          const inner = (
            <>
              <span className="min-w-0 flex-1">
                <span className="block truncate font-semibold">{actTitle(a)}</span>
                <span className="block text-xs text-muted">{actDates(a)}</span>
              </span>
              <StateBadge state={a.state} />
            </>
          );
          return (
            <li key={a.slug}>
              {year ? (
                <Link to={href.act(league, year, a.slug)} className="flex items-center gap-3 py-2.5 hover:text-muted">
                  {inner}
                </Link>
              ) : (
                <div className="flex items-center gap-3 py-2.5">{inner}</div>
              )}
            </li>
          );
        })}
      </ol>
    </Card>
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
      <p className="mb-2 text-sm text-muted">{t("live.progress", { scored: data.races_scored, total: data.races_total })}</p>
      <div className="h-2 overflow-hidden rounded-full bg-default">
        <div className="h-full rounded-full bg-foreground" style={{ width: `${share}%` }} />
      </div>
    </div>
  );
}

/** The newest articles as cards over the picture, the next few as headlines. */
export function NewsTiles({ items, rest = [], link }: { items: ArticleSummary[]; rest?: ArticleSummary[]; link: (n: ArticleSummary) => string }) {
  return (
    <div data-testid="site-news-tiles">
      <CardRow>
        {items.map((n) => (
          <li key={n.slug}>
            <MediaCard to={link(n)} image={n.photo} kicker={formatDate(n.date)} title={n.title} text={n.teaser} />
          </li>
        ))}
      </CardRow>
      {rest.length > 0 && (
        <Card className="mt-4 p-4">
        <ul className="grid grid-cols-[minmax(0,1fr)] gap-x-6 gap-y-3 sm:grid-cols-3">
          {rest.map((n) => (
            <li key={n.slug}>
              <Link to={link(n)} className="block border-l-2 border-border pl-3 text-sm hover:border-foreground">
                <span className="block text-xs text-faint">{formatDate(n.date)}</span>
                <span className="font-medium">{n.title}</span>
              </Link>
            </li>
          ))}
        </ul>
        </Card>
      )}
    </div>
  );
}

/** The league's videos as stills, each leading to the media page. */
function VideoTiles({ league, videos }: { league: string; videos: Video[] }) {
  return (
    <CardRow testId="site-video-tiles">
      {videos.map((v) => (
        <li key={v.id}>
          <MediaCard to={href.media(league)} image={{ src: `https://i.ytimg.com/vi/${v.id}/hqdefault.jpg`, alt: "" }} title={v.title} play />
        </li>
      ))}
    </CardRow>
  );
}

/** The first five of a division, on the picture. */
function TopFive({ series, label }: { series: Series; label?: string }) {
  const { t } = useTranslation("site");
  const table = useGetSeriesTable(series.id).data;
  const rows = (table?.rows ?? []).filter((r) => (r.events_sailed ?? 0) > 0).slice(0, 5);
  if (!table) return <div className="h-48 animate-pulse rounded-2xl bg-default" />;
  // The same block when nothing is sailed yet — the division's place on the page, empty.
  if (!rows.length) {
    return (
      <TextCard testId={`site-top-five-${series.slug}`}>
        <span data-empty>{label ? `${label}: ` : ""}{t("standings.notYet")}</span>
      </TextCard>
    );
  }
  return (
    <Card className="px-4">
    {label && <p className="border-b border-separator py-2.5 text-sm font-semibold uppercase tracking-widest text-muted">{label}</p>}
    <ol className="divide-y divide-separator" data-testid={`site-top-five-${series.slug}`}>
      {rows.map((row) => (
        <li key={row.team.id} className="flex items-center gap-3 py-2">
          <span className="w-6 text-faint">{row.rank}</span>
          <span className="flex-1 font-semibold">{teamLabel(row.team)}</span>
          <span className="tabular-nums">{row.points}</span>
        </li>
      ))}
    </ol>
    </Card>
  );
}
