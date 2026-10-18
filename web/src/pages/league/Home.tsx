import { useQueries } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { getGetLeagueSeasonQueryOptions } from "../../api/generated/sbl";
import { ChapterScroller, type ChapterSpec } from "../../components/site/Chapters";
import { Card, CardRow, MediaCard, useTone } from "../../components/site/Cards";
import { Block, DepthPage, useLeagues } from "../../components/site/Frame";
import { Img } from "../../components/site/Media";
import { useSiteVersion } from "../../components/site/settings";
import { BOARD, DSBL_PHOTOS, MEMBER_LEAGUES, OWN_PHOTOS, leagueAbout, useAssociation, useLocalized, useNews, type Article } from "../../content";
import { formatDate } from "../../lib/format";
import { actsOf, currentAct, href } from "../../lib/site";
import { NewsTiles, useClubsOf } from "./LeagueHome";
import { StateBadge, actDates, useActTitle } from "./shared";

/** `/` — the association's home, a chapter page too: every league's current act, the
 *  leagues, news, the service for clubs, the association (Story B-14). */
export function AssociationHome() {
  const { t } = useTranslation("site");
  const localized = useLocalized();
  const actTitle = useActTitle();
  const leagues = useLeagues();
  const association = useAssociation().data;
  const full = useSiteVersion() === "submenu";
  const allNews = useNews().data ?? [];
  const news = allNews.slice(0, 3);
  const articleHref = (n: Article) => href.article(n.league ?? MEMBER_LEAGUES[0], n.slug);
  const seasons = useQueries({ queries: leagues.map((l) => getGetLeagueSeasonQueryOptions(l.slug)) });
  const leagueOf = new Map(leagues.map((l) => [l.slug, l.short_name]));

  const chapters: ChapterSpec[] = [
    {
      id: "now",
      label: t("chapters.now"),
      // The page's one h1 names the page; every other chapter is titled with its name.
      title: "Deutsche Segel-Liga e.V.",
      photo: OWN_PHOTOS.title,
      body: (
        <Card className="max-w-2xl px-4" testId="site-home-now">
          {leagues.map((l, i) => {
            const season = seasons[i]?.data;
            const act = season ? currentAct(actsOf(season)) : null;
            return (
              <Link key={l.slug} to={href.league(l.slug)} className="flex items-center gap-4 border-b border-white/15 py-3 last:border-0 hover:bg-white/5">
                <span className="w-32 shrink-0 font-semibold">{l.short_name}</span>
                <span className="min-w-0 flex-1 truncate text-white/80">
                  {act ? `${actTitle(act)} · ${actDates(act)}` : (l.tagline ?? "")}
                </span>
                {act && <StateBadge state={act.state} dark />}
              </Link>
            );
          })}
        </Card>
      ),
      extra: full && (
        <ul className="grid max-w-2xl grid-cols-3 gap-3" data-testid="site-home-figures">
          {(["competitions", "clubs", "since"] as const).map((k) => (
            <li key={k}>
              <Card className="h-full p-4">
              <p className="text-3xl font-semibold tabular-nums">{t(`home.figures.${k}.value`, { count: leagues.length })}</p>
              <p className="mt-1 text-xs uppercase tracking-widest text-white/60">{t(`home.figures.${k}.label`)}</p>
              </Card>
            </li>
          ))}
        </ul>
      ),
    },
    {
      id: "leagues",
      label: t("chapters.leagues"),
      title: t("chapters.leagues"),
      photo: DSBL_PHOTOS.race,
      body: (
        <ul className="grid max-w-4xl grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {leagues.map((l) => (
            <li key={l.slug}>
              <Card to={href.league(l.slug)} className="h-full p-5">
                <p className="text-2xl font-semibold">{l.short_name}</p>
                <p className="mt-1 text-sm text-white/75">{l.tagline}</p>
                {full && leagueAbout(l.slug) && (
                  <p className="mt-3 line-clamp-4 text-sm leading-relaxed text-white/60">{localized(leagueAbout(l.slug)!.intro)}</p>
                )}
              </Card>
            </li>
          ))}
        </ul>
      ),
    },
    {
      id: "news",
      label: t("chapters.news"),
      title: t("chapters.news"),
      photo: DSBL_PHOTOS.swimmer,
      body: full ? (
        <NewsTiles items={allNews.slice(0, 3)} rest={allNews.slice(3, 6)} link={articleHref} />
      ) : (
        <ul className="max-w-2xl space-y-3">
          {news.map((n) => {
            const league = n.league ?? MEMBER_LEAGUES[0];
            return (
              <li key={n.slug}>
                <Link to={href.article(league, n.slug)} className="block border-l-2 border-white/50 pl-4 hover:border-white">
                  <p className="text-xs uppercase tracking-widest text-white/60">
                    {(n.league ? leagueOf.get(n.league) : t("home.association")) ?? n.league} · {formatDate(n.date)}
                  </p>
                  <p className="text-xl font-semibold">{n.title}</p>
                </Link>
              </li>
            );
          })}
        </ul>
      ),
    },
    {
      id: "clubs",
      label: t("chapters.forClubs"),
      title: t("chapters.forClubs"),
      photo: DSBL_PHOTOS.podium,
      body: <p className="max-w-xl text-lg text-white/80">{association ? localized(association.service) : null}</p>,
      extra: full && (
        <ul className="grid max-w-4xl grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-2 lg:grid-cols-3" data-testid="site-home-services">
          {(["pairing", "results", "live", "waivers", "expenses", "own"] as const).map((k) => (
            <li key={k}>
              <Card className="h-full p-4">
                <p className="font-semibold">{t(`home.services.${k}.title`)}</p>
                <p className="mt-1 text-sm leading-relaxed text-white/70">{t(`home.services.${k}.text`)}</p>
              </Card>
            </li>
          ))}
        </ul>
      ),
    },
    {
      id: "about",
      label: t("chapters.about"),
      title: t("chapters.about"),
      photo: DSBL_PHOTOS.studio,
      more: { to: href.about(), label: t("home.aboutMore") },
      body: (
        <div className="max-w-2xl">
          {association && <p className="text-lg text-white/80">{t("home.founded", { date: localized(association.founded) })}</p>}
          {full && association && (
            <>
              <p className="mt-4 leading-relaxed text-white/75">{localized(association.history)}</p>
              <p className="mt-2 text-sm text-white/60">{localized(association.record)}</p>
            </>
          )}
          <ul className="mt-5 flex flex-wrap gap-4">
            {BOARD.map((b) => (
              <li key={b.name} className="flex items-center gap-3">
                <span className="size-12 overflow-hidden rounded-full bg-white/10">
                  <Img photo={b.photo} />
                </span>
                <span className="text-sm">
                  <b className="block">{b.name}</b>
                  <span className="text-white/60">{localized(b.role)}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      ),
    },
  ];
  return <ChapterScroller chapters={chapters} />;
}

/** `/about` — the association: history, board, member clubs. */
export function AssociationAboutPage() {
  const { t } = useTranslation("site");
  const localized = useLocalized();
  const association = useAssociation().data;
  const members = useQueries({ queries: MEMBER_LEAGUES.map((l) => getGetLeagueSeasonQueryOptions(l)) });
  const clubs = useClubsOf(members.flatMap((m) => m.data?.series ?? []));
  const tone = useTone();
  return (
    <DepthPage league={null} title="Deutsche Segel-Liga e.V." kicker={t("home.aboutKicker")} photo={OWN_PHOTOS.title}>
      {association && (
        <>
          <p className={`max-w-3xl text-lg leading-relaxed ${tone.muted}`}>{localized(association.history)}</p>
          <p className={`mb-10 mt-3 max-w-3xl ${tone.faint}`}>{localized(association.record)}</p>
        </>
      )}
      <Block title={t("home.board")}>
        <CardRow>
          {BOARD.map((b) => (
            <li key={b.name}>
              <MediaCard image={b.photo} aspect="aspect-[4/5]" title={b.name} text={localized(b.role)} />
            </li>
          ))}
        </CardRow>
      </Block>
      {clubs.length > 0 && (
        <Block title={t("home.members", { count: clubs.length })}>
          <Card className="p-4">
            <ul className={`grid grid-cols-[minmax(0,1fr)] gap-x-8 gap-y-1 text-sm md:grid-cols-2 ${tone.muted}`}>
              {clubs.map((c) => (
                <li key={c.id}>
                  <Link to={href.club(c.id)} className={`hover:underline ${tone.dark ? "hover:text-white" : "hover:text-slate-900"}`}>
                    <b className={`inline-block w-24 ${tone.text}`}>{c.short_name}</b>
                    {c.name}
                  </Link>
                </li>
              ))}
            </ul>
          </Card>
        </Block>
      )}
    </DepthPage>
  );
}
