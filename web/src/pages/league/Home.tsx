import { useQueries } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { getGetLeagueSeasonQueryOptions, useGetLeagueSeason } from "../../api/generated/sbl";
import { ChapterScroller, type ChapterSpec } from "../../components/site/Chapters";
import { Block, DepthPage, useLeagues } from "../../components/site/Frame";
import { Img } from "../../components/site/Media";
import { BOARD, DSBL_PHOTOS, MEMBER_LEAGUE, OWN_PHOTOS, useAssociation, useLocalized, useNews } from "../../content";
import { formatDate } from "../../lib/format";
import { actsOf, currentAct, href } from "../../lib/site";
import { useClubsOf } from "./LeagueHome";
import { StateBadge, actDates, useActTitle } from "./shared";

/** `/` — the association's home, a chapter page too: every league's current act, the
 *  leagues, news, the service for clubs, the association (Story B-14). */
export function AssociationHome() {
  const { t } = useTranslation("site");
  const localized = useLocalized();
  const actTitle = useActTitle();
  const leagues = useLeagues();
  const association = useAssociation().data;
  const news = (useNews().data ?? []).slice(0, 3);
  const seasons = useQueries({ queries: leagues.map((l) => getGetLeagueSeasonQueryOptions(l.slug)) });
  const leagueOf = new Map(leagues.map((l) => [l.slug, l.short_name]));

  const chapters: ChapterSpec[] = [
    {
      id: "now",
      label: t("chapters.now"),
      title: t("home.title"),
      photo: OWN_PHOTOS.title,
      body: (
        <div className="max-w-2xl rounded-2xl bg-white/10 px-4 backdrop-blur" data-testid="site-home-now">
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
        </div>
      ),
    },
    {
      id: "leagues",
      label: t("chapters.leagues"),
      title: t("home.leagues"),
      photo: DSBL_PHOTOS.race,
      body: (
        <ul className="grid max-w-4xl grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-3">
          {leagues.map((l) => (
            <li key={l.slug}>
              <Link to={href.league(l.slug)} className="block h-full rounded-2xl bg-white/10 p-5 backdrop-blur transition hover:bg-white/20">
                <p className="text-2xl font-semibold">{l.short_name}</p>
                <p className="mt-1 text-sm text-white/75">{l.tagline}</p>
              </Link>
            </li>
          ))}
        </ul>
      ),
    },
    {
      id: "news",
      label: t("chapters.news"),
      title: t("home.news"),
      photo: DSBL_PHOTOS.swimmer,
      body: (
        <ul className="max-w-2xl space-y-3">
          {news.map((n) => {
            const league = n.league ?? MEMBER_LEAGUE;
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
      title: t("home.forClubs"),
      photo: DSBL_PHOTOS.podium,
      body: <p className="max-w-xl text-lg text-white/80">{association ? localized(association.service) : null}</p>,
    },
    {
      id: "about",
      label: t("chapters.about"),
      title: "Deutsche Segel-Liga e.V.",
      photo: DSBL_PHOTOS.studio,
      more: { to: href.about(), label: t("home.aboutMore") },
      body: (
        <div className="max-w-2xl">
          {association && <p className="text-lg text-white/80">{t("home.founded", { date: localized(association.founded) })}</p>}
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
  const members = useGetLeagueSeason(MEMBER_LEAGUE).data;
  const clubs = useClubsOf(members?.series ?? []);
  return (
    <DepthPage league={null} title="Deutsche Segel-Liga e.V." kicker={t("home.aboutKicker")} photo={OWN_PHOTOS.title}>
      {association && (
        <>
          <p className="max-w-3xl text-lg leading-relaxed text-slate-700">{localized(association.history)}</p>
          <p className="mt-3 max-w-3xl text-slate-600">{localized(association.record)}</p>
        </>
      )}
      <Block title={t("home.board")}>
        <ul className="grid grid-cols-[minmax(0,1fr)] gap-6 sm:grid-cols-3">
          {BOARD.map((b) => (
            <li key={b.name}>
              <div className="aspect-[2/3] overflow-hidden rounded-xl bg-slate-100">
                <Img photo={b.photo} />
              </div>
              <p className="mt-3 font-semibold">{b.name}</p>
              <p className="text-sm text-slate-500">{localized(b.role)}</p>
            </li>
          ))}
        </ul>
      </Block>
      {clubs.length > 0 && (
        <Block title={t("home.members", { count: clubs.length })}>
          <ul className="grid grid-cols-[minmax(0,1fr)] gap-x-8 gap-y-1 text-sm text-slate-700 md:grid-cols-2">
            {clubs.map((c) => (
              <li key={c.id}>
                <Link to={href.club(c.id)} className="hover:underline">
                  <b className="inline-block w-24">{c.short_name}</b>
                  {c.name}
                </Link>
              </li>
            ))}
          </ul>
        </Block>
      )}
    </DepthPage>
  );
}
