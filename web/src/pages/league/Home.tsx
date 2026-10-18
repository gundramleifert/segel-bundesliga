import { useQueries } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { getGetLeagueSeasonQueryOptions } from "../../api/generated/sbl";
import { ChapterScroller, type ChapterSpec } from "../../components/site/Chapters";
import { Card, CardRow, Columns, MediaCard, TextCard, useTone } from "../../components/site/Cards";
import { Block, DepthPage, useLeagues } from "../../components/site/Frame";
import { Img } from "../../components/site/Media";
import { BOARD, MEMBER_LEAGUES, OWN_PHOTOS, leagueAbout, useAssociation, useLocalized, useNews, type Article } from "../../content";
import { actsOf, currentAct, href } from "../../lib/site";
import { NewsTiles, useClubsOf } from "./LeagueHome";
import { StateBadge, actDates, useActTitle } from "./shared";

/** `/` — the association's home, a chapter page too: the competitions and what each is
 *  sailing, news, the service for clubs, the association (Story B-14). */
export function AssociationHome() {
  const { t } = useTranslation("site");
  const localized = useLocalized();
  const actTitle = useActTitle();
  const leagues = useLeagues();
  const association = useAssociation().data;
  const news = useNews().data ?? [];
  const articleHref = (n: Article) => href.article(n.league ?? MEMBER_LEAGUES[0], n.slug);
  const seasons = useQueries({ queries: leagues.map((l) => getGetLeagueSeasonQueryOptions(l.slug)) });

  const chapters: ChapterSpec[] = [
    {
      id: "now",
      label: t("chapters.now"),
      // The page's one h1 names the page; every other chapter is titled with its name.
      title: "Deutsche Segel-Liga e.V.",
      // The competitions in one chapter: what each is sailing now and what each is, on
      // one card — once a list here and the same four leagues as cards in a second one.
      body: (
        <CardRow columns={4} testId="site-home-now">
          {leagues.map((l, i) => {
            const season = seasons[i]?.data;
            const act = season ? currentAct(actsOf(season)) : null;
            const about = leagueAbout(l.slug);
            return (
              <li key={l.slug}>
                <Card to={href.league(l.slug)} className="flex h-full flex-col p-5">
                  <p className="text-2xl font-semibold">{l.short_name}</p>
                  {act ? (
                    <p className="mt-2 flex flex-wrap items-center gap-2 text-sm">
                      <span className="font-medium">{actTitle(act)}</span>
                      <StateBadge state={act.state} dark />
                      <span className="w-full text-white/60">{actDates(act)}</span>
                    </p>
                  ) : null}
                  <p className="mt-3 text-sm text-white/80">{l.tagline}</p>
                  {about && <p className="mt-2 line-clamp-3 text-sm leading-relaxed text-white/60">{localized(about.intro)}</p>}
                </Card>
              </li>
            );
          })}
        </CardRow>
      ),
      extra: (
        <CardRow testId="site-home-figures">
          {(["competitions", "clubs", "since"] as const).map((k) => (
            <li key={k}>
              <Card className="h-full p-4">
                <p className="text-3xl font-semibold tabular-nums">{t(`home.figures.${k}.value`, { count: leagues.length })}</p>
                <p className="mt-1 text-xs uppercase tracking-widest text-white/60">{t(`home.figures.${k}.label`)}</p>
              </Card>
            </li>
          ))}
        </CardRow>
      ),
    },
    {
      id: "news",
      label: t("chapters.news"),
      title: t("chapters.news"),
      body: <NewsTiles items={news.slice(0, 3)} rest={news.slice(3, 6)} link={articleHref} />,
    },
    {
      id: "clubs",
      label: t("chapters.forClubs"),
      title: t("chapters.forClubs"),
      body: <TextCard className="text-lg">{association ? localized(association.service) : null}</TextCard>,
      extra: (
        <CardRow testId="site-home-services">
          {(["pairing", "results", "live", "waivers", "expenses", "own"] as const).map((k) => (
            <li key={k}>
              <Card className="h-full p-4">
                <p className="font-semibold">{t(`home.services.${k}.title`)}</p>
                <p className="mt-1 text-sm leading-relaxed text-white/70">{t(`home.services.${k}.text`)}</p>
              </Card>
            </li>
          ))}
        </CardRow>
      ),
    },
    {
      id: "about",
      label: t("chapters.about"),
      title: t("chapters.about"),
      more: { to: href.about(), label: t("home.aboutMore") },
      // The text and the board each a card, side by side on a wide screen.
      body: (
        <Columns>
          {association && (
            <TextCard>
              <p className="text-lg text-white">{t("home.founded", { date: localized(association.founded) })}</p>
              <p className="mt-3 leading-relaxed">{localized(association.history)}</p>
              <p className="mt-3 text-sm text-white/60">{localized(association.record)}</p>
            </TextCard>
          )}
          <Card className="p-4 sm:p-5">
            <ul className="space-y-3">
              {BOARD.map((b) => (
                <li key={b.name} className="flex items-center gap-3">
                  <span className="size-12 shrink-0 overflow-hidden rounded-full bg-white/10">
                    <Img photo={b.photo} />
                  </span>
                  <span className="text-sm">
                    <b className="block">{b.name}</b>
                    <span className="text-white/60">{localized(b.role)}</span>
                  </span>
                </li>
              ))}
            </ul>
          </Card>
        </Columns>
      ),
    },
  ];
  return <ChapterScroller chapters={chapters} photo={OWN_PHOTOS.title} />;
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
          <TextCard className="mb-10">
            <p className="text-lg leading-relaxed">{localized(association.history)}</p>
            <p className={`mt-3 ${tone.faint}`}>{localized(association.record)}</p>
          </TextCard>
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
