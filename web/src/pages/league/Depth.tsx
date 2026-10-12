import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, Navigate, useParams } from "react-router-dom";

import { useGetSeriesTable } from "../../api/generated/sbl";
import type { Series } from "../../api/types";
import { useAsync } from "../../api/useApi";
import { Async } from "../../components/Async";
import { StandingsTable } from "../../components/StandingsTable";
import { Block, DepthPage, Expand } from "../../components/site/Frame";
import { Img, YouTubePlayer } from "../../components/site/Media";
import {
  DSBL_PHOTOS,
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
  type DocGroup,
  type TableMarks,
} from "../../content";
import { formatDate, locationText } from "../../lib/format";
import { currentAct, href } from "../../lib/site";
import { useClubsOf } from "./LeagueHome";
import { ExampleNote, LeagueGate, StateBadge, actDates, divisionName, useActTitle, type LeagueYear } from "./shared";

// The depth pages behind a league's chapters (Story B-14). Each is a `DepthPage`, framed
// by whichever variant the DEV switch picks; the content is the same in all three.

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
              <div>
                {season.series.map((s) => (
                  <Block key={s.id} title={s.name} testId={`site-standings-${s.slug}`}>
                    <DivisionTable series={s} marks={tableMarks(league.slug, s.level)} league={league.slug} year={year} />
                  </Block>
                ))}
              </div>
            ) : (
              <p className="text-slate-500">{t("standings.noSeries")}</p>
            )}
            {season.years.length > 1 && (
              <Block title={t("standings.archive")}>
                <ul className="flex flex-wrap gap-2 text-sm">
                  {season.years.map((y) => (
                    <li key={y}>
                      <Link
                        to={href.standings(league.slug, y)}
                        className={`block rounded-full border px-4 py-1.5 ${y === year ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200 text-slate-600 hover:border-slate-400"}`}
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
              {!acts.length && <p className="text-slate-500">{t("season.empty")}</p>}
              {acts.map((act) => (
                <Expand
                  key={act.slug}
                  testId="site-season-act"
                  open={act.state === "next" || act.state === "live"}
                  summary={
                    <span className="flex items-center gap-4">
                      <span className="w-32 shrink-0 text-sm text-slate-500">{actDates(act)}</span>
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
                          className="rounded-full border border-slate-200 px-3 py-1 text-slate-700 hover:border-slate-400"
                        >
                          {t(`tabs.${tab}`)}
                        </Link>
                      ))}
                    </div>
                  )}
                </Expand>
              ))}
            </Block>
            <Block title={t("noticeBoard.season")} more={{ to: href.noticeBoard(league.slug), label: t("noticeBoard.all") }}>
              <p className="text-slate-600">{t("noticeBoard.seasonPreview")}</p>
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
          <DepthPage league={league} title={t("noticeBoard.season")} kicker={kickerOf(data)} photo={DSBL_PHOTOS.studio}>
            <p className="mb-8 max-w-2xl text-slate-600">
              {t("noticeBoard.intro")}{" "}
              {act && year && (
                <Link to={href.act(league.slug, year, act.slug, "notice-board")} className="font-medium text-brand-700 hover:underline">
                  {t("noticeBoard.ofAct", { act: actTitle(act) })} →
                </Link>
              )}
            </p>
            <SeasonDocuments league={league.slug} render={(group) => (
              <Expand key={localized(group.title)} open summary={<span className="font-semibold">{localized(group.title)}</span>}>
                <DocList docs={group.docs} />
              </Expand>
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
          <span className="grid size-8 shrink-0 place-items-center rounded-md bg-slate-100 text-[10px] font-bold text-slate-500">PDF</span>
          {/* No download mark until there is a file to download. */}
          <span className="flex-1 text-slate-800">{doc}</span>
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
          {!data.season.series.length && <p className="text-slate-500">{t("clubs.none")}</p>}
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

function DivisionClubs({ series }: { series: Series }) {
  const { t } = useTranslation("site");
  const clubs = useClubsOf([series]);
  if (!clubs.length) return <p className="text-slate-500">{t("clubs.none")}</p>;
  return (
    <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6" data-testid={`site-clubs-${series.slug}`}>
      {clubs.map((club) => (
        <li key={club.id}>
          <Link to={href.club(club.id)} className="flex h-full flex-col items-center gap-2 rounded-xl border border-slate-200 p-4 text-center transition hover:border-slate-400">
            <span className="grid size-12 place-items-center rounded-full bg-slate-100 text-sm font-bold text-slate-600">{club.short_name}</span>
            <span className="line-clamp-2 text-xs text-slate-600">{club.name}</span>
          </Link>
        </li>
      ))}
    </ul>
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
      {(items) => (
        <ul className="grid grid-cols-[minmax(0,1fr)] gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((n) => (
            <li key={n.slug}>
              <Link to={href.article(league, n.slug)} className="group block">
                <div className="aspect-[3/2] overflow-hidden rounded-xl bg-slate-100">
                  <Img photo={n.photo} className="transition group-hover:scale-105" />
                </div>
                <p className="mt-3 text-xs font-semibold uppercase tracking-widest text-brand-600">{formatDate(n.date)}</p>
                <p className="mt-1 text-lg font-semibold leading-snug group-hover:underline">{n.title}</p>
                <p className="mt-1 text-sm text-slate-600">{n.teaser}</p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Async>
  );
}

export function ArticlePage() {
  const { t } = useTranslation("site");
  const { slug } = useParams();
  const article = useArticle(slug).data;
  return (
    <LeagueGate>
      {({ league }) =>
        !article ? (
          <Navigate to={href.news(league.slug)} replace />
        ) : (
          <DepthPage league={league} title={article.title} kicker={`${t("pages.news")} · ${formatDate(article.date)}`} photo={article.photo}>
            <article className="max-w-2xl space-y-4 text-lg leading-relaxed text-slate-700">
              {article.body.map((p) => (
                <p key={p}>{p}</p>
              ))}
            </article>
            <p className="mt-10">
              <Link to={href.news(league.slug)} className="font-medium text-brand-700 hover:underline">
                ← {t("news.more")}
              </Link>
            </p>
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
            <div className="grid grid-cols-[minmax(0,1fr)] gap-6 md:grid-cols-3">
              {items.slice(0, limit).map((v) => (
                <YouTubePlayer key={v.id} id={v.id} title={v.title} />
              ))}
            </div>
          )}
        </Async>
      </Block>
      <Block title={t("media.photos")}>
        <Async state={gallery} testId="site-gallery" empty={t("media.none")}>
          {(photos) => (
            <>
              <ul className="grid grid-cols-2 gap-2 md:grid-cols-3">
                {photos.slice(0, limit ? limit + 1 : undefined).map((p) => (
                  <li key={p.src} className="aspect-[3/2] overflow-hidden rounded-lg bg-slate-100">
                    <Img photo={p} />
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-xs text-slate-500">{t("media.credits")}</p>
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
          <div className="grid grid-cols-[minmax(0,1fr)] gap-10 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
            <Block title={t("press.releases")}>
              <Releases league={league.slug} />
            </Block>
            <div>
              {(["kit", "photos", "accreditation"] as const).map((key) => (
                <div key={key} className="mb-3 rounded-xl border border-slate-200 p-4">
                  <p className="font-semibold">{t(`press.${key}`)}</p>
                  <p className="text-sm text-slate-600">{t(`press.${key}Text`)}</p>
                </div>
              ))}
              <div className="mb-3 rounded-xl border border-slate-200 p-4">
                <p className="font-semibold">{t("press.contact")}</p>
                <p className="text-sm text-slate-600">{PRESS_CONTACT}</p>
              </div>
            </div>
          </div>
        </DepthPage>
      )}
    </LeagueGate>
  );
}

function Releases({ league }: { league: string }) {
  const press = usePress(league);
  return (
    <Async state={press} testId="site-press">
      {(items) =>
        items.map((p, i) => (
          <Expand
            key={p.title}
            open={i === 0}
            summary={
              <span className="flex items-baseline gap-4">
                <span className="w-28 shrink-0 text-sm text-slate-500">{formatDate(p.date)}</span>
                <span className="font-medium">{p.title}</span>
              </span>
            }
          >
            <p>{p.body}</p>
          </Expand>
        ))
      }
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
              <p className="max-w-3xl text-lg leading-relaxed text-slate-700">{localized(about.intro)}</p>
              <Block title={t("about.stake")}>
                <ul className="max-w-3xl space-y-2 text-slate-700">
                  {about.facts.map((f) => (
                    <li key={f.en} className="flex gap-3">
                      <span aria-hidden className="text-brand-600">—</span>
                      {localized(f)}
                    </li>
                  ))}
                </ul>
              </Block>
            </>
          ) : (
            <p className="max-w-3xl text-lg leading-relaxed text-slate-700">{league.tagline ?? league.name}</p>
          )}
        </DepthPage>
      )}
    </LeagueGate>
  );
}

