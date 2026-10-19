import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, Navigate, useParams } from "react-router-dom";

import { useGetSeriesTable } from "../../api/generated/sbl";
import type { LeagueSeason, Series } from "../../api/types";
import { useAsync } from "../../api/useApi";
import { Async } from "../../components/Async";
import { StandingsTable } from "../../components/StandingsTable";
import { Card, CardRow, Columns, MediaCard, Panel, TextCard, tone } from "../../components/site/Cards";
import { Block, DepthPage, Expand, PageLoading } from "../../components/site/Frame";
import { ErrorMessage, Loading } from "../../components/Blocks";
import { YouTubePlayer } from "../../components/site/Media";
import {
  DSBL_PHOTOS,
  OWN_PHOTOS,
  PRESS_CONTACT,
  leaguePhoto,
  tableMarks,
  useArticle,
  useGallery,
  useLeagueAbout,
  useLocalized,
  useNews,
  usePress,
  useSeasonDocuments,
  useVideos,
  type ArticleSummary,
  type DocGroup,
  type TableMarks,
} from "../../content";
import { formatDate, locationText } from "../../lib/format";
import { currentAct, href } from "../../lib/site";
import { RichText } from "../../components/RichText";
import { ExampleNote, LeagueGate, StateBadge, actDates, divisionName, useActTitle, type LeagueYear } from "./shared";

// The depth pages behind a league's chapters (Story B-14), each a `DepthPage`.

const kickerOf = ({ league, year }: LeagueYear) => (year ? `${league.short_name} · ${year}` : league.short_name);

// ---------------------------------------------------------------- standings

/** `/:league/standings` and `/:league/:year/standings` — every division's full table. */
export function StandingsPage() {
  const { t } = useTranslation("site");
  return (
    <LeagueGate>
      {(data) => {
        const { league, season, year } = data;
        return (
          <DepthPage league={league} title={t("pages.standings")} kicker={kickerOf(data)} photo={DSBL_PHOTOS.podium}>
            {season.series.length ? (
              // One division under the other: with a column per act, two tables side by
              // side left each too narrow to read.
              <>
                {season.series.map((s) => (
                  <Block key={s.id} title={s.name} testId={`site-standings-${s.slug}`}>
                    <Panel>
                      <DivisionTable series={s} marks={tableMarks(league.slug, s.level)} league={league.slug} year={year} />
                    </Panel>
                  </Block>
                ))}
              </>
            ) : (
              <TextCard>{t("standings.noSeries")}</TextCard>
            )}
            {season.years.length > 1 && (
              <Block title={t("standings.archive")}>
                <ul className="flex flex-wrap gap-2 text-sm">
                  {season.years.map((y) => (
                    <li key={y}>
                      <Link
                        to={href.standings(league.slug, y)}
                        className={`block ${y === year ? tone.chipOn : tone.chip}`}
                      >
                        {y}
                      </Link>
                    </li>
                  ))}
                </ul>
              </Block>
            )}
          </DepthPage>
        );
      }}
    </LeagueGate>
  );
}

function DivisionTable({ series, marks, league, year }: { series: Series; marks: TableMarks; league: string; year: number | null }) {
  const { t } = useTranslation("site");
  const table = useAsync(useGetSeriesTable(series.id));
  return (
    <Async state={table} testId={`site-table-${series.slug}`}>
      {(data) =>
        data.rows.every((r) => (r.events_sailed ?? 0) === 0) ? (
          <p className="text-slate-500">{t("standings.notYet")}</p>
        ) : (
          // A table wider than a phone scrolls here, not the page (Story A-10).
          <div className="panel-scroll">
            <StandingsTable
              data={data}
              marks={marks}
              testId="site-standings"
              actHref={(event) =>
                year && event.matchday != null ? href.act(league, year, `act-${event.matchday}`, "results") : href.event(event.id)
              }
            />
          </div>
        )
      }
    </Async>
  );
}

// ---------------------------------------------------------------- season

/** `/:league/season` — every act of the year, expanding to its details and its tabs. */
export function SeasonPage() {
  const { t } = useTranslation("site");
  const actTitle = useActTitle();
  return (
    <LeagueGate>
      {(data) => {
        const { league, acts, year } = data;
        return (
          <DepthPage league={league} title={t("pages.season")} kicker={kickerOf(data)} photo={DSBL_PHOTOS.aerial}>
            <Block title={t("season.matchdays")}>
              {!acts.length && <TextCard>{t("season.empty")}</TextCard>}
              {acts.length > 0 && <Card className="px-4">
              {acts.map((act) => (
                <Expand
                  key={act.slug}
                  testId="site-season-act"
                  open={act.state === "next" || act.state === "live"}
                  summary={
                    <span className="flex items-center gap-4">
                      <span className={`w-32 shrink-0 text-sm ${tone.faint}`}>{actDates(act)}</span>
                      <span className="min-w-0 flex-1 truncate font-medium">{actTitle(act)}</span>
                      <StateBadge state={act.state} />
                    </span>
                  }
                >
                  <p>
                    {[
                      locationText(act.first),
                      act.first.host_club ? t("hostedBy", { host: act.first.host_club.name }) : null,
                      act.events.map(divisionName).join(" · "),
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                  {year && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {(["notice-board", "results", "pairing", "crews", "live"] as const).map((tab) => (
                        <Link
                          key={tab}
                          to={href.act(league.slug, year, act.slug, tab)}
                          className={tone.chip}
                        >
                          {t(`tabs.${tab}`)}
                        </Link>
                      ))}
                    </div>
                  )}
                </Expand>
              ))}
              </Card>}
            </Block>
            <Block title={t("noticeBoard.season")} more={{ to: href.noticeBoard(league.slug), label: t("noticeBoard.all") }}>
              <TextCard>{t("noticeBoard.seasonPreview")}</TextCard>
            </Block>
          </DepthPage>
        );
      }}
    </LeagueGate>
  );
}

// ---------------------------------------------------------------- notice board

/** `/:league/notice-board` — the season's documents; the act's own notices are on its page. */
export function NoticeBoardPage() {
  const { t } = useTranslation("site");
  const localized = useLocalized();
  const actTitle = useActTitle();
  return (
    <LeagueGate>
      {(data) => {
        const { league, acts, year } = data;
        const act = currentAct(acts);
        return (
          <DepthPage league={league} title={t("noticeBoard.season")} kicker={kickerOf(data)} photo={OWN_PHOTOS.title}>
            <TextCard className="mb-8">
              {t("noticeBoard.intro")}{" "}
              {act && year && (
                <Link to={href.act(league.slug, year, act.slug, "notice-board")} className={tone.link}>
                  {t("noticeBoard.ofAct", { act: actTitle(act) })} →
                </Link>
              )}
            </TextCard>
            <SeasonDocuments league={league.slug} render={(group) => (
              <Card key={localized(group.title)} className="mb-4 px-4">
                <Expand open summary={<span className="font-semibold">{localized(group.title)}</span>}>
                  <DocList docs={group.docs} />
                </Expand>
              </Card>
            )} />
          </DepthPage>
        );
      }}
    </LeagueGate>
  );
}

function SeasonDocuments({ league, render }: { league: string; render: (group: DocGroup) => ReactNode }) {
  const documents = useSeasonDocuments(league);
  return (
    <Async state={documents} testId="site-season-documents">
      {({ groups, example }) => (
        <>
          {example && <ExampleNote />}
          {groups.map(render)}
        </>
      )}
    </Async>
  );
}

export function DocList({ docs }: { docs: string[] }) {
  return (
    <ul className="space-y-1.5">
      {docs.map((doc) => (
        <li key={doc} className="flex items-center gap-3">
          <span className={`grid size-8 shrink-0 place-items-center rounded-md text-[10px] font-bold bg-white/15 text-white/80`}>PDF</span>
          {/* No download mark until there is a file to download. */}
          <span className={`flex-1 ${tone.text}`}>{doc}</span>
        </li>
      ))}
    </ul>
  );
}

// ---------------------------------------------------------------- clubs

/** `/:league/clubs` — the clubs of each division, each leading to its own page. */
export function ClubsPage() {
  const { t } = useTranslation("site");
  return (
    <LeagueGate>
      {(data) => (
        <DepthPage league={data.league} title={t("pages.clubs")} kicker={kickerOf(data)} photo={DSBL_PHOTOS.race}>
          {!data.season.series.length && <TextCard>{t("clubs.none")}</TextCard>}
          {data.season.series.map((s) => (
            <Block key={s.id} title={s.name}>
              <DivisionClubs series={s} />
            </Block>
          ))}
        </DepthPage>
      )}
    </LeagueGate>
  );
}

function DivisionClubs({ series }: { series: LeagueSeason["series"][number] }) {
  const { t } = useTranslation("site");
  const clubs = series.clubs ?? [];
  if (!clubs.length) return <TextCard>{t("clubs.none")}</TextCard>;
  return (
    <CardRow columns={6} testId={`site-clubs-${series.slug}`}>
      {clubs.map((club) => (
        <li key={club.id}>
          <Card to={href.club(club.id)} className="flex h-full flex-col items-center gap-2 p-4 text-center">
            <span className={`grid size-12 place-items-center rounded-full text-sm font-bold bg-white/15 text-white`}>{club.short_name}</span>
            <span className={`line-clamp-2 text-xs ${tone.muted}`}>{club.name}</span>
          </Card>
        </li>
      ))}
    </CardRow>
  );
}

// ---------------------------------------------------------------- news

export function NewsPage() {
  const { t } = useTranslation("site");
  return (
    <LeagueGate>
      {({ league }) => (
        <DepthPage league={league} title={t("pages.news")} kicker={league.short_name} photo={DSBL_PHOTOS.swimmer}>
          <NewsGrid league={league.slug} />
        </DepthPage>
      )}
    </LeagueGate>
  );
}

function NewsGrid({ league }: { league: string }) {
  const news = useNews(league);
  return (
    <Async state={news} testId="site-news">
      {(items) => <NewsCards league={league} items={items} />}
    </Async>
  );
}

/** Articles as cards: picture, date, title, teaser — each leading to its own page. */
function NewsCards({ league, items }: { league: string; items: ArticleSummary[] }) {
  return (
    <CardRow>
      {items.map((n) => (
        <li key={n.slug}>
          <MediaCard
            to={href.article(league, n.slug)}
            image={n.photo}
            kicker={formatDate(n.date)}
            title={n.title}
            text={n.teaser}
            testId={`site-news-${n.slug}`}
          />
        </li>
      ))}
    </CardRow>
  );
}

/** `/:league/news/:slug` — one article: the lead, the text, a quote, who wrote it, and
 *  the league's next articles. */
export function ArticlePage() {
  const { t } = useTranslation("site");
  const { slug, league: leagueSlug = "" } = useParams();
  const { data: article, loading, error, notFound } = useArticle(slug);
  const more = (useNews(leagueSlug).data ?? []).filter((n) => n.slug !== slug).slice(0, 3);
  return (
    <LeagueGate>
      {({ league }) =>
        // An unknown or withdrawn article leads back to the league's news; a failure says so.
        notFound ? (
          <Navigate to={href.news(league.slug)} replace />
        ) : loading ? (
          <PageLoading><Loading testId="site-article-loading" /></PageLoading>
        ) : error || !article ? (
          <PageLoading><ErrorMessage text={error ?? ""} testId="site-article-error" /></PageLoading>
        ) : (
          <DepthPage league={league} title={article.title} kicker={`${t("pages.news")} · ${formatDate(article.date)}`} photo={article.photo}>
            {article.example && <ExampleNote text={t("news.example")} />}
            {/* Text to read closely: one column of a reading width, centred on its glass. */}
            <Panel className="mb-12 sm:p-10">
            <article className="mx-auto max-w-2xl" data-testid="site-article">
              <p className="text-xl font-medium leading-relaxed text-slate-900" data-testid="site-article-lead">{article.teaser}</p>
              {article.author && (
                <p className="mt-3 text-sm text-slate-500" data-testid="site-article-byline">
                  {t("news.byline", { author: article.author, date: formatDate(article.date) })}
                </p>
              )}
              <RichText html={article.body} className="mt-8 text-lg leading-relaxed text-slate-700" testId="site-article-body" />
              {article.quote && (
                <blockquote className="my-10 border-l-4 border-brand-600 pl-6">
                  <p className="text-2xl font-semibold leading-snug tracking-tight text-slate-900">“{article.quote.text}”</p>
                  <footer className="mt-2 text-sm text-slate-500">— {article.quote.by}</footer>
                </blockquote>
              )}
            </article>
            <p className="mx-auto mt-10 max-w-2xl">
              <Link to={href.news(league.slug)} className="font-medium text-brand-700 hover:underline" data-testid="site-article-back">
                ← {t("news.more")}
              </Link>
            </p>
            </Panel>
            {more.length > 0 && (
              <Block title={t("news.related")} more={{ to: href.news(league.slug), label: t("news.more") }} testId="site-article-related">
                <NewsCards league={league.slug} items={more} />
              </Block>
            )}
          </DepthPage>
        )
      }
    </LeagueGate>
  );
}

// ---------------------------------------------------------------- media

export function MediaPage() {
  const { t } = useTranslation("site");
  return (
    <LeagueGate>
      {({ league }) => (
        <DepthPage league={league} title={t("media.page")} kicker={league.short_name} photo={DSBL_PHOTOS.camera}>
          <MediaContent league={league.slug} />
        </DepthPage>
      )}
    </LeagueGate>
  );
}

export function MediaContent({ league, limit }: { league: string; limit?: number }) {
  const { t } = useTranslation("site");
  const videos = useVideos(league);
  const gallery = useGallery(league);
  return (
    <>
      <Block title={t("media.videos")}>
        <Async state={videos} testId="site-videos" empty={t("media.none")}>
          {(items) => (
            <CardRow>
              {items.slice(0, limit).map((v) => (
                <li key={v.id}>
                  <YouTubePlayer id={v.id} title={v.title} />
                </li>
              ))}
            </CardRow>
          )}
        </Async>
      </Block>
      <Block title={t("media.photos")}>
        <Async state={gallery} testId="site-gallery" empty={t("media.none")}>
          {(photos) => (
            <>
              <CardRow>
                {photos.slice(0, limit ? limit + 1 : undefined).map((p) => (
                  <li key={p.src}>
                    <MediaCard image={p} aspect="aspect-[3/2]" text={p.alt} />
                  </li>
                ))}
              </CardRow>
              <TextCard className="mt-4 text-xs">{t("media.credits")}</TextCard>
            </>
          )}
        </Async>
      </Block>
    </>
  );
}

// ---------------------------------------------------------------- press

export function PressPage() {
  const { t } = useTranslation("site");
  return (
    <LeagueGate>
      {({ league }) => (
        <DepthPage league={league} title={t("press.page")} kicker={league.short_name} photo={DSBL_PHOTOS.studio}>
          <Columns split="twoToOne">
            <Block title={t("press.releases")}>
              <Card className="px-4">
                <Releases league={league.slug} />
              </Card>
            </Block>
            <div>
              {(["kit", "photos", "accreditation"] as const).map((key) => (
                <Card key={key} className="mb-3 p-4">
                  <p className={`font-semibold ${tone.text}`}>{t(`press.${key}`)}</p>
                  <p className={`text-sm ${tone.muted}`}>{t(`press.${key}Text`)}</p>
                </Card>
              ))}
              <Card className="mb-3 p-4">
                <p className={`font-semibold ${tone.text}`}>{t("press.contact")}</p>
                <p className={`text-sm ${tone.muted}`}>{PRESS_CONTACT}</p>
              </Card>
            </div>
          </Columns>
        </DepthPage>
      )}
    </LeagueGate>
  );
}

function Releases({ league }: { league: string }) {
  const press = usePress(league);
  return (
    <Async state={press} testId="site-press">
      {(items) => items.map((p, i) => <Release key={p.slug} release={p} first={i === 0} />)}
    </Async>
  );
}

/** One release: its date and title, and its text read once it is opened — the list does
 *  not carry the text (Story R-1). The newest is open from the start. */
function Release({ release, first }: { release: ArticleSummary; first: boolean }) {
  const [opened, setOpened] = useState(first);
  return (
    <Expand
      open={first}
      onToggle={(open) => open && setOpened(true)}
      testId={`site-press-release-${release.slug}`}
      summary={
        <span className="flex items-baseline gap-4">
          <span className={`w-28 shrink-0 text-sm ${tone.faint}`}>{formatDate(release.date)}</span>
          <span className="font-medium">{release.title}</span>
        </span>
      }
    >
      {opened && <ReleaseText slug={release.slug} />}
    </Expand>
  );
}

function ReleaseText({ slug }: { slug: string }) {
  const article = useArticle(slug);
  return (
    <Async state={article} testId={`site-press-text-${slug}`}>
      {(a) => <RichText html={a.body} testId={`site-press-text-${slug}`} />}
    </Async>
  );
}

// ---------------------------------------------------------------- about

/** `/:league/about` — what the league is and what is at stake. */
export function LeagueAboutPage() {
  const { t } = useTranslation("site");
  const localized = useLocalized();
  const { league: slug = "" } = useParams();
  const about = useLeagueAbout(slug).data;
  return (
    <LeagueGate>
      {({ league }) => (
        <DepthPage league={league} title={t("about.title", { league: league.short_name })} kicker={league.name} photo={about?.photo ?? leaguePhoto(slug)}>
          {about ? (
            <>
              <TextCard className="mb-10 text-lg leading-relaxed">{localized(about.intro)}</TextCard>
              <Block title={t("about.stake")}>
                <CardRow>
                  {about.facts.map((f) => (
                    <li key={f.en}>
                      <Card className={`h-full p-4 text-sm leading-relaxed ${tone.muted}`}>{localized(f)}</Card>
                    </li>
                  ))}
                </CardRow>
              </Block>
            </>
          ) : (
            <TextCard className="text-lg leading-relaxed">{league.tagline ?? league.name}</TextCard>
          )}
        </DepthPage>
      )}
    </LeagueGate>
  );
}

