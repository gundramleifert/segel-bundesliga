import { useEffect, useRef, type ReactNode } from "react";
import { Link, Navigate, NavLink, useParams } from "react-router-dom";

import { ChapterDots, Img } from "../wireframes/kit";
import type { Photo, Row } from "../wireframes/data";
import { formatDate } from "../wireframes/nav";
import {
  ASSOCIATION,
  BOARD,
  BOAT_COLORS,
  DSL_PHOTOS,
  CREW_NAMES,
  DSBL_PHOTOS,
  EVENT_DOCUMENTS,
  LEAGUES,
  NEWS,
  NOTICES,
  PRESS,
  SEASON_DOCUMENTS,
  VIDEOS,
  YEAR,
  currentAct,
  flightRaces,
  lastSailed,
  newsOf,
  type Act,
  type ProtoLeague,
} from "./data";
import { Block, Chapter, DepthPage, DevSwitch, Expand, Footer, TopBar, YouTubePlayer } from "./parts";
import { href, useActiveChapter, useChapterMode, useDetailMode, useLeague } from "./state";

// ---------------------------------------------------------------- the chapter pages

type ChapterSpec = {
  id: string;
  label: string;
  title: string;
  photo: Photo;
  more?: { to: string; label: string };
  body: ReactNode;
};

/** The face of a league (or of the association): full-screen chapters over pictures,
 *  dots on the right, each chapter a preview that ends in its own page (option E). */
function ChapterScroller({ chapters, active }: { chapters: ChapterSpec[]; active?: string }) {
  const mode = useChapterMode();
  const current = useActiveChapter(chapters[0].id, `${chapters.map((c) => c.id).join()}|${mode}`);
  return (
    // Its own scroller, fixed over the screen, so the document behind has nothing to
    // scroll and the snapping (when on) is this box's alone.
    <div className={`scrollbar-none fixed inset-0 overflow-y-auto bg-slate-950 ${mode === "snap" ? "snap-y snap-mandatory" : ""}`}>
      <TopBar overlay active={active} />
      <ChapterDots chapters={chapters.map((c) => [c.id, c.label] as const)} active={current} />
      {chapters.map((c, i) => (
        <Chapter key={c.id} id={c.id} n={i + 1} of={chapters.length} photo={c.photo} title={c.title} more={c.more} playing={current === c.id} video={i}>
          {c.body}
        </Chapter>
      ))}
      <div className="snap-start"><Footer /></div>
      <DevSwitch />
    </div>
  );
}

function ActLine({ league, act }: { league: ProtoLeague; act: Act }) {
  return (
    <Link
      to={href.act(league.slug, YEAR, act.slug)}
      className="flex items-center gap-4 border-b border-white/15 py-2.5 transition last:border-0 hover:bg-white/5"
    >
      <span className="w-28 shrink-0 text-sm text-white/70">{act.dates}</span>
      <span className="min-w-0 flex-1 truncate font-medium">{act.title} · {act.venue}</span>
      <StateBadge state={act.state} dark />
    </Link>
  );
}

function StateBadge({ state, dark = false }: { state: Act["state"]; dark?: boolean }) {
  const label = { done: "Results", live: "Live", next: "Next", planned: "Planned" }[state];
  const tone =
    state === "live"
      ? "bg-red-600 text-white"
      : state === "next"
        ? dark ? "bg-white text-slate-950" : "bg-brand-600 text-white"
        : dark ? "bg-white/10 text-white/80" : "bg-slate-100 text-slate-600";
  return <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold ${tone}`}>{label}</span>;
}

function MiniTable({ rows, limit = 5 }: { rows: Row[]; limit?: number }) {
  if (!rows.length) return <p className="text-white/70">No races sailed yet — entries open until 31 January.</p>;
  return (
    <ol className="divide-y divide-white/10 rounded-2xl bg-white/10 px-4 backdrop-blur">
      {rows.slice(0, limit).map((row) => (
        <li key={row.short} className="flex items-center gap-3 py-2">
          <span className="w-6 text-white/50">{row.rank}</span>
          <span className="flex-1 font-semibold">{row.short}</span>
          <span className="tabular-nums">{row.points}</span>
        </li>
      ))}
    </ol>
  );
}

export function LeagueHome() {
  const league = useLeague();
  if (!league) return <Navigate to={href.home()} replace />;
  const act = currentAct(league);
  const last = lastSailed(league);
  const clubs = league.divisions.flatMap((d) => d.rows.map((r) => r.short));
  const news = newsOf(league).slice(0, 3);
  const several = league.divisions.length > 1;

  const chapters: ChapterSpec[] = [
    {
      id: "now",
      label: "Now",
      title: act.state === "done" ? "Season complete." : `${act.title} in ${act.venue}, ${act.dates}.`,
      photo: league.photo,
      more: { to: href.act(league.slug, YEAR, act.slug), label: "Matchday page" },
      body: (
        <>
          <p className="max-w-xl text-lg text-white/80">{act.water} · hosted by {act.host} · {act.divisions.join(" and ")}</p>
          <div className="mt-5 flex flex-wrap gap-2 text-sm">
            <Link to={href.live(league.slug)} className="rounded-full border border-white/40 px-4 py-2 hover:bg-white/10">Live map</Link>
            <Link to={href.act(league.slug, YEAR, act.slug, "notice-board")} className="rounded-full border border-white/40 px-4 py-2 hover:bg-white/10">Notice board</Link>
            {last && <Link to={href.results(league.slug)} className="rounded-full border border-white/40 px-4 py-2 hover:bg-white/10">Results {last.title}</Link>}
          </div>
        </>
      ),
    },
    {
      id: "standings",
      label: "Standings",
      title: "Where everyone stands.",
      photo: DSBL_PHOTOS.podium,
      more: { to: href.standings(league.slug), label: "Full standings" },
      body: (
        <div className={`grid max-w-4xl grid-cols-[minmax(0,1fr)] gap-4 ${several ? "md:grid-cols-2" : ""}`}>
          {league.divisions.map((d) => (
            <div key={d.slug}>
              {several && <p className="mb-2 text-sm font-semibold text-white/80">{d.name}</p>}
              <MiniTable rows={d.rows} />
            </div>
          ))}
        </div>
      ),
    },
    {
      id: "season",
      label: "Season",
      title: `${league.acts.length} ${league.acts.length === 1 ? "weekend" : "weekends"}, one season.`,
      photo: DSBL_PHOTOS.aerial,
      more: { to: href.season(league.slug), label: "Season & notice board" },
      body: (
        <div className="max-w-2xl rounded-2xl bg-white/10 px-4 backdrop-blur">
          {league.acts.map((a) => <ActLine key={a.slug} league={league} act={a} />)}
        </div>
      ),
    },
    {
      id: "clubs",
      label: "Clubs",
      title: `${clubs.length || "Every"} clubs.`,
      photo: DSBL_PHOTOS.race,
      more: { to: href.clubs(league.slug), label: "All clubs" },
      body: (
        <ul className="flex max-w-3xl flex-wrap gap-2">
          {(clubs.length ? clubs : ["Entries open"]).slice(0, 24).map((c, i) => (
            <li key={`${c}-${i}`} className="rounded-full bg-white/10 px-3 py-1 text-sm backdrop-blur">{c}</li>
          ))}
        </ul>
      ),
    },
    {
      id: "news",
      label: "News",
      title: "From the water.",
      photo: DSBL_PHOTOS.swimmer,
      more: { to: href.news(league.slug), label: "All news" },
      body: (
        <ul className="max-w-2xl space-y-4">
          {news.map((n) => (
            <li key={n.slug}>
              <Link to={href.article(league.slug, n.slug)} className="block border-l-2 border-white/50 pl-4 hover:border-white">
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
      label: "Media",
      title: "Watch it again.",
      photo: DSBL_PHOTOS.camera,
      more: { to: href.media(league.slug), label: "Photos & videos" },
      body: <p className="max-w-xl text-lg text-white/80">{VIDEOS.length} videos and galleries from every matchday.</p>,
    },
    {
      id: "press",
      label: "Press",
      title: "For the press.",
      photo: DSBL_PHOTOS.studio,
      more: { to: href.press(league.slug), label: "Press centre" },
      body: (
        <ul className="max-w-2xl space-y-2">
          {PRESS.slice(0, 3).map((p) => (
            <li key={p.title} className="flex items-baseline gap-3">
              <span className="w-24 shrink-0 text-sm text-white/60">{formatDate(p.date)}</span>
              <span className="font-medium">{p.title}</span>
            </li>
          ))}
        </ul>
      ),
    },
    {
      id: "about",
      label: "About",
      title: `About the ${league.short}.`,
      photo: DSL_PHOTOS.title,
      more: { to: href.about(league.slug), label: "How it works" },
      body: <p className="max-w-2xl text-lg text-white/80">{league.about.intro}</p>,
    },
  ];
  return <ChapterScroller key={league.slug} chapters={chapters} active={league.slug} />;
}

export function AssociationHome() {
  const chapters: ChapterSpec[] = [
    {
      id: "now",
      label: "Now",
      title: "Three competitions, one association.",
      photo: DSL_PHOTOS.title,
      body: (
        <div className="max-w-2xl rounded-2xl bg-white/10 px-4 backdrop-blur">
          {LEAGUES.map((l) => {
            const act = currentAct(l);
            return (
              <Link key={l.slug} to={href.league(l.slug)} className="flex items-center gap-4 border-b border-white/15 py-3 last:border-0 hover:bg-white/5">
                <span className="w-32 shrink-0 font-semibold">{l.short}</span>
                <span className="min-w-0 flex-1 truncate text-white/80">{act.title} · {act.venue} · {act.dates}</span>
                <StateBadge state={act.state} dark />
              </Link>
            );
          })}
        </div>
      ),
    },
    {
      id: "leagues",
      label: "Leagues",
      title: "Pick your league.",
      photo: DSBL_PHOTOS.race,
      body: (
        <ul className="grid max-w-4xl grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-3">
          {LEAGUES.map((l) => (
            <li key={l.slug}>
              <Link to={href.league(l.slug)} className="block h-full rounded-2xl bg-white/10 p-5 backdrop-blur transition hover:bg-white/20">
                <p className="text-2xl font-semibold">{l.short}</p>
                <p className="mt-1 text-sm text-white/75">{l.tagline}</p>
              </Link>
            </li>
          ))}
        </ul>
      ),
    },
    {
      id: "news",
      label: "News",
      title: "News from all leagues.",
      photo: DSBL_PHOTOS.swimmer,
      more: { to: href.news("dsbl"), label: "All news" },
      body: (
        <ul className="max-w-2xl space-y-3">
          {NEWS.slice(0, 3).map((n) => (
            <li key={n.slug} className="border-l-2 border-white/50 pl-4">
              <p className="text-xs uppercase tracking-widest text-white/60">{n.league} · {formatDate(n.date)}</p>
              <p className="text-xl font-semibold">{n.title}</p>
            </li>
          ))}
        </ul>
      ),
    },
    {
      id: "clubs",
      label: "For clubs",
      title: "Run your own regatta here.",
      photo: DSBL_PHOTOS.podium,
      body: <p className="max-w-xl text-lg text-white/80">Pairing lists, results, live tracking, waivers and expense claims — the association's service for every member club.</p>,
    },
    {
      id: "about",
      label: "About",
      title: "Deutsche Segel-Liga e.V.",
      photo: DSBL_PHOTOS.studio,
      more: { to: href.about(), label: "About the association" },
      body: (
        <div className="max-w-2xl">
          <p className="text-lg text-white/80">Founded {ASSOCIATION.founded}. {ASSOCIATION.clubs} member clubs, {ASSOCIATION.competitions} competitions.</p>
          <ul className="mt-5 flex flex-wrap gap-4">
            {BOARD.map((b) => (
              <li key={b.name} className="flex items-center gap-3">
                <span className="size-12 overflow-hidden rounded-full bg-white/10"><Img photo={b.photo} className="h-full w-full object-cover" /></span>
                <span className="text-sm"><b className="block">{b.name}</b><span className="text-white/60">{b.role}</span></span>
              </li>
            ))}
          </ul>
        </div>
      ),
    },
  ];
  return <ChapterScroller chapters={chapters} />;
}

// ---------------------------------------------------------------- the depth pages

/** Points per act for a row — invented but stable, so a row always expands the same way. */
const perAct = (row: Row, acts: Act[]) =>
  acts.filter((a) => a.state === "done").map((a, i) => ({ act: a.title, points: ((row.rank * 3 + i * 5) % 9) + 1 }));

export function StandingsPage() {
  const league = useLeague();
  if (!league) return <Navigate to={href.home()} replace />;
  return (
    <DepthPage league={league} title="Standings" kicker={`${league.short} · ${YEAR}`} photo={DSBL_PHOTOS.podium}>
      <div className={`grid grid-cols-[minmax(0,1fr)] gap-10 ${league.divisions.length > 1 ? "lg:grid-cols-2" : ""}`}>
        {league.divisions.map((d, di) => (
          <Block key={d.slug} title={d.name}>
            {!d.rows.length ? (
              <p className="text-slate-500">No races sailed yet.</p>
            ) : (
              <div>
                {d.rows.map((row) => {
                  // deutsche-segelliga.de/wettbewerbe: four down, four up, 13–18 of the 2. Liga requalify.
                  const promoted = di === 1 && row.rank <= 4;
                  const relegated = di === 0 && league.divisions.length > 1 && row.rank > d.rows.length - 4;
                  const requalify = di === 1 && row.rank >= 13;
                  return (
                    <Expand
                      key={row.short}
                      summary={
                        <span className="flex items-center gap-3">
                          <span className="w-6 text-slate-400">{row.rank}</span>
                          <span className="flex-1 font-medium">
                            {row.short} <span className="hidden font-normal text-slate-500 sm:inline">{row.club}</span>
                          </span>
                          {promoted && <span className="rounded-full bg-emerald-50 px-2 text-xs text-emerald-700">promotion</span>}
                          {relegated && <span className="rounded-full bg-red-50 px-2 text-xs text-red-700">relegation</span>}
                          {requalify && <span className="rounded-full bg-amber-50 px-2 text-xs text-amber-800">requalification</span>}
                          <span className="w-10 text-right tabular-nums">{row.points}</span>
                        </span>
                      }
                    >
                      <div className="flex flex-wrap gap-2">
                        {perAct(row, league.acts).map((p) => (
                          <span key={p.act} className="rounded-lg bg-slate-50 px-3 py-1.5">
                            {p.act}: <b className="tabular-nums">{p.points}</b>
                          </span>
                        ))}
                      </div>
                    </Expand>
                  );
                })}
              </div>
            )}
          </Block>
        ))}
      </div>
      <Block title="Archive">
        <ul className="flex gap-2 text-sm">
          {[2025, 2024, 2023].map((y) => (
            <li key={y} className="rounded-full border border-slate-200 px-4 py-1.5 text-slate-500">{y}</li>
          ))}
        </ul>
      </Block>
    </DepthPage>
  );
}

export function SeasonPage() {
  const league = useLeague();
  if (!league) return <Navigate to={href.home()} replace />;
  return (
    <DepthPage league={league} title="Season & matchdays" kicker={`${league.short} · ${YEAR}`} photo={DSBL_PHOTOS.aerial}>
      <Block title="Matchdays" more={{ to: "#", label: "Add to calendar" }}>
        {league.acts.map((act) => (
          <Expand
            key={act.slug}
            open={act.state === "next" || act.state === "live"}
            summary={
              <span className="flex items-center gap-4">
                <span className="w-28 shrink-0 text-sm text-slate-500">{act.dates}</span>
                <span className="min-w-0 flex-1 truncate font-medium">{act.title} · {act.venue}</span>
                <StateBadge state={act.state} />
              </span>
            }
          >
            <p>{act.water} · hosted by {act.host} · {act.divisions.join(" and ")}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {(["notice-board", "results", "live"] as const).map((tab) => (
                <Link key={tab} to={href.act(league.slug, YEAR, act.slug, tab)} className="rounded-full border border-slate-200 px-3 py-1 text-slate-700 hover:border-slate-400">
                  {TAB_LABELS[tab]}
                </Link>
              ))}
            </div>
          </Expand>
        ))}
      </Block>
      <Block title="Season notice board" more={{ to: href.noticeBoard(league.slug), label: "All documents" }}>
        <p className="text-slate-600">League regulations, the season's notice of race, charter terms and entry deadlines.</p>
      </Block>
    </DepthPage>
  );
}

export function NoticeBoardPage() {
  const league = useLeague();
  if (!league) return <Navigate to={href.home()} replace />;
  const act = currentAct(league);
  return (
    <DepthPage league={league} title="Season notice board" kicker={`${league.short} · ${YEAR}`} photo={DSBL_PHOTOS.studio}>
      <p className="mb-8 max-w-2xl text-slate-600">
        Documents for the whole season. A matchday's own notices — amendments, jury decisions, the protest list — are on its page:{" "}
        <Link to={href.act(league.slug, YEAR, act.slug, "notice-board")} className="font-medium text-brand-700 hover:underline">
          notice board of {act.title} →
        </Link>
      </p>
      {SEASON_DOCUMENTS.map((group) => (
        <Expand key={group.title} open summary={<span className="font-semibold">{group.title}</span>}>
          <DocList docs={group.docs} />
        </Expand>
      ))}
    </DepthPage>
  );
}

function DocList({ docs }: { docs: string[] }) {
  return (
    <ul className="space-y-1.5">
      {docs.map((doc) => (
        <li key={doc} className="flex items-center gap-3">
          <span className="grid size-8 shrink-0 place-items-center rounded-md bg-slate-100 text-[10px] font-bold text-slate-500">PDF</span>
          <span className="flex-1 text-slate-800">{doc}</span>
          <span className="text-brand-700">↓</span>
        </li>
      ))}
    </ul>
  );
}

export function ClubsPage() {
  const league = useLeague();
  if (!league) return <Navigate to={href.home()} replace />;
  return (
    <DepthPage league={league} title="Clubs" kicker={`${league.short} · ${YEAR}`} photo={DSBL_PHOTOS.race}>
      {league.divisions.map((d) => (
        <Block key={d.slug} title={d.name}>
          {d.rows.length ? (
            <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
              {d.rows.map((row) => (
                <li key={row.short} className="flex flex-col items-center gap-2 rounded-xl border border-slate-200 p-4 text-center">
                  <span className="grid size-12 place-items-center rounded-full bg-slate-100 text-sm font-bold text-slate-600">{row.short}</span>
                  <span className="line-clamp-2 text-xs text-slate-600">{row.club}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-slate-500">Entries open until 31 January.</p>
          )}
        </Block>
      ))}
    </DepthPage>
  );
}

export function NewsPage() {
  const league = useLeague();
  if (!league) return <Navigate to={href.home()} replace />;
  return (
    <DepthPage league={league} title="News" kicker={league.short} photo={DSBL_PHOTOS.swimmer}>
      <ul className="grid grid-cols-[minmax(0,1fr)] gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {newsOf(league).map((n) => (
          <li key={n.slug}>
            <Link to={href.article(league.slug, n.slug)} className="group block">
              <div className="aspect-[3/2] overflow-hidden rounded-xl bg-slate-100"><Img photo={n.photo} className="transition group-hover:scale-105" /></div>
              <p className="mt-3 text-xs font-semibold uppercase tracking-widest text-brand-600">{formatDate(n.date)}</p>
              <p className="mt-1 text-lg font-semibold leading-snug group-hover:underline">{n.title}</p>
              <p className="mt-1 text-sm text-slate-600">{n.teaser}</p>
            </Link>
          </li>
        ))}
      </ul>
    </DepthPage>
  );
}

export function ArticlePage() {
  const league = useLeague();
  const { slug } = useParams();
  const article = NEWS.find((n) => n.slug === slug);
  if (!league || !article) return <Navigate to={league ? href.news(league.slug) : href.home()} replace />;
  return (
    <DepthPage league={league} title={article.title} kicker={`News · ${formatDate(article.date)}`} photo={article.photo}>
      <article className="max-w-2xl space-y-4 text-lg leading-relaxed text-slate-700">
        {article.body.map((p) => <p key={p}>{p}</p>)}
      </article>
      <p className="mt-10"><Link to={href.news(league.slug)} className="font-medium text-brand-700 hover:underline">← All news</Link></p>
    </DepthPage>
  );
}

const GALLERY = Object.values(DSBL_PHOTOS);

export function MediaPage() {
  const league = useLeague();
  if (!league) return <Navigate to={href.home()} replace />;
  return (
    <DepthPage league={league} title="Photos & videos" kicker={league.short} photo={DSBL_PHOTOS.camera}>
      <Block title="Videos" more={{ to: "#", label: "YouTube channel" }}>
        <div className="grid grid-cols-[minmax(0,1fr)] gap-6 md:grid-cols-3">
          {VIDEOS.map((v, i) => <YouTubePlayer key={v.id} video={i} />)}
        </div>
      </Block>
      <Block title="Photos">
        <ul className="grid grid-cols-2 gap-2 md:grid-cols-3">
          {GALLERY.map((p) => (
            <li key={p.src} className="aspect-[3/2] overflow-hidden rounded-lg bg-slate-100" title={`© ${p.credit}`}>
              <Img photo={p} />
            </li>
          ))}
        </ul>
        <p className="mt-3 text-xs text-slate-500">© Deutsche Segel-Bundesliga; aerial photo © Adam Burdylo.</p>
      </Block>
    </DepthPage>
  );
}

export function PressPage() {
  const league = useLeague();
  if (!league) return <Navigate to={href.home()} replace />;
  return (
    <DepthPage league={league} title="Press centre" kicker={league.short} photo={DSBL_PHOTOS.studio}>
      <div className="grid grid-cols-[minmax(0,1fr)] gap-10 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Block title="Press releases">
          {PRESS.map((p, i) => (
            <Expand key={p.title} open={i === 0} summary={
              <span className="flex items-baseline gap-4">
                <span className="w-24 shrink-0 text-sm text-slate-500">{formatDate(p.date)}</span>
                <span className="font-medium">{p.title}</span>
              </span>
            }>
              <p>{p.body}</p>
              <p className="mt-2 font-medium text-brand-700">Download PDF ↓</p>
            </Expand>
          ))}
        </Block>
        <div>
          {[
            ["Press kit", "Logos, fact sheet, the season's dates"],
            ["Print photos", "High resolution, free for editorial use"],
            ["Accreditation", "On the water or ashore, per matchday"],
            ["Contact", "presse@segelliga.example.com"],
          ].map(([t, d]) => (
            <div key={t} className="mb-3 rounded-xl border border-slate-200 p-4">
              <p className="font-semibold">{t}</p>
              <p className="text-sm text-slate-600">{d}</p>
            </div>
          ))}
        </div>
      </div>
    </DepthPage>
  );
}

// ---------------------------------------------------------------- the matchday page

const TABS = ["notice-board", "results", "pairing", "crews", "live", "media"] as const;
type Tab = (typeof TABS)[number];
const TAB_LABELS: Record<Tab, string> = {
  "notice-board": "Notice board",
  results: "Results",
  pairing: "Pairing list",
  crews: "Crews",
  live: "Live",
  media: "Media",
};

export function ActPage() {
  const league = useLeague();
  const detail = useDetailMode();
  // A tab click scrolls the page so that the matchday row sits right under the top bar and
  // the tab's content starts below it. A page opened by its URL keeps its picture in view.
  const anchor = useRef<HTMLDivElement>(null);
  const clicked = useRef(false);
  const { act: actSlug, tab: tabParam } = useParams();
  useEffect(() => {
    if (!clicked.current || !anchor.current) return;
    clicked.current = false;
    // The anchor is not sticky, so it marks where the row sits in the page; the row itself
    // would report where it is stuck. 56 px is the top bar, 113 px bar plus B's pills.
    const offset = detail === "sheet" ? 113 : 56;
    window.scrollTo({ top: anchor.current.getBoundingClientRect().top + window.scrollY - offset });
  }, [tabParam, detail]);
  const act = league?.acts.find((a) => a.slug === actSlug);
  if (!league || !act) return <Navigate to={league ? href.season(league.slug) : href.home()} replace />;
  const fallback: Tab = act.state === "done" ? "results" : "notice-board";
  const tab: Tab = (TABS as readonly string[]).includes(tabParam ?? "") ? (tabParam as Tab) : fallback;
  const clubs = league.divisions.find((d) => act.divisions.includes(d.short))?.rows.map((r) => r.short) ?? [];

  return (
    <DepthPage league={league} title={`${act.title} · ${act.venue}`} kicker={`${league.short} · ${act.dates} ${YEAR} · ${act.water}`} photo={act.state === "done" ? DSBL_PHOTOS.podium : DSBL_PHOTOS.race}>
      {/* Which matchday this is and what it has, in one row that stays under the top bar
          while the page scrolls — the second and last row of navigation. In layout B the
          sheet's own row of pills already sits under the bar, so this one sits under that. */}
      <div ref={anchor} aria-hidden />
      <nav
        aria-label="Matchday"
        data-testid="proto-act-bar"
        className={`scrollbar-none sticky z-10 -mx-4 mb-8 overflow-x-auto border-b border-slate-200 bg-white/95 px-4 backdrop-blur ${detail === "sheet" ? "top-[113px]" : "top-14"}`}
      >
        <ul className="flex items-center gap-1">
          <li className="mr-2 shrink-0 border-r border-slate-200 py-2 pr-4">
            <p className="text-sm font-semibold text-slate-900">{act.title} · {act.venue}</p>
            <p className="text-xs text-slate-500">{act.dates}</p>
          </li>
          {TABS.map((t) => (
            <li key={t} className="shrink-0">
              <NavLink
                to={href.act(league.slug, YEAR, act.slug, t)}
                onClick={() => {
                  clicked.current = true;
                }}
                className={`-mb-px block whitespace-nowrap border-b-2 px-3 py-4 text-sm font-medium ${t === tab ? "border-slate-900 text-slate-900" : "border-transparent text-slate-500 hover:text-slate-900"}`}
              >
                {TAB_LABELS[t]}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      {/* At least a screen tall, so a short tab can still be scrolled up to the row. */}
      <div className="min-h-[calc(100dvh-7.5rem)]">

      {tab === "notice-board" && (
        <div className="grid grid-cols-[minmax(0,1fr)] gap-10 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
          <Block title="Announcements">
            {NOTICES.slice().reverse().map((n, i) => (
              <Expand key={n.title} open={i === 0} summary={
                <span className="flex items-baseline gap-4">
                  <span className="w-20 shrink-0 text-sm text-slate-500">{n.time}</span>
                  <span className={`shrink-0 rounded-full px-2 text-xs font-semibold ${n.from === "Jury" ? "bg-amber-50 text-amber-800" : n.from === "Organizer" ? "bg-slate-100 text-slate-600" : "bg-brand-50 text-brand-700"}`}>{n.from}</span>
                  <span className="font-medium">{n.title}</span>
                </span>
              }>
                {n.body}
              </Expand>
            ))}
          </Block>
          <Block title="Documents"><DocList docs={EVENT_DOCUMENTS} /></Block>
        </div>
      )}

      {tab === "results" && (
        act.state !== "done" ? (
          <p className="text-slate-500">No races sailed yet — the first warning signal is on the notice board.</p>
        ) : (
          <div className="grid grid-cols-[minmax(0,1fr)] gap-10 lg:grid-cols-2">
            <Block title="Ranking of the act">
              <ol>
                {clubs.slice(0, 18).map((c, i) => (
                  <li key={c} className="flex items-center gap-3 border-b border-slate-100 py-2 last:border-0">
                    <span className="w-6 text-slate-400">{i + 1}</span>
                    <span className="flex-1 font-medium">{c}</span>
                    <span className="tabular-nums text-slate-600">{i + 1}</span>
                  </li>
                ))}
              </ol>
            </Block>
            <Block title="Race by race">
              {[1, 2, 3, 4].map((flight) => (
                <Expand key={flight} open={flight === 1} summary={<span className="font-medium">Flight {flight} · races {(flight - 1) * 3 + 1}–{flight * 3}</span>}>
                  {flightRaces(clubs, flight).map((race) => (
                    <div key={race.number} className="mb-2 flex items-center gap-3">
                      <span className="w-14 shrink-0 text-slate-500">Race {race.number}</span>
                      <ol className="flex flex-wrap gap-1.5">
                        {race.order.map((team, place) => (
                          <li key={team} className="inline-flex items-center gap-1.5 rounded-md bg-slate-50 px-2 py-0.5 text-slate-800">
                            <b className="text-xs text-slate-400">{place + 1}</b>
                            <span className="size-2 rounded-full" style={{ background: BOAT_COLORS[(place + flight) % 6][1] }} />
                            {team}
                          </li>
                        ))}
                      </ol>
                    </div>
                  ))}
                </Expand>
              ))}
            </Block>
          </div>
        )
      )}

      {tab === "pairing" && (
        <Block title="Pairing list" more={{ to: "#", label: "Download PDF" }}>
          <div className="scrollbar-none overflow-x-auto">
            <table className="min-w-[40rem] text-sm">
              <thead>
                <tr className="text-left text-slate-500">
                  <th className="py-2 pr-4 font-medium">Race</th>
                  {BOAT_COLORS.map(([name, color]) => (
                    <th key={name} className="px-2 py-2 font-medium">
                      <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full ring-1 ring-slate-300" style={{ background: color }} />{name}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[1, 2, 3].flatMap((flight) => flightRaces(clubs, flight)).map((race) => (
                  <tr key={race.number} className="border-t border-slate-100">
                    <td className="py-1.5 pr-4 text-slate-500">{race.number}</td>
                    {race.order.map((team) => <td key={team} className="px-2 py-1.5 font-medium">{team}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Block>
      )}

      {tab === "crews" && (
        <Block title="Who sails for each club">
          {clubs.map((c, i) => (
            <Expand key={c} summary={<span className="font-medium">{c}</span>}>
              {CREW_NAMES.slice(i % 2, (i % 2) + 4).join(" · ")}
            </Expand>
          ))}
        </Block>
      )}

      {tab === "live" && (
        <div className="rounded-2xl border border-slate-200 p-8 text-center">
          <p className="text-lg font-semibold">{act.state === "done" ? "Tracking replay" : `Live from ${act.dates}`}</p>
          <p className="mt-1 text-slate-600">Every boat on the map, the ranking of the race and the wind — from the sailors' phones.</p>
          <Link to="/live" className="mt-5 inline-block rounded-full bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white">Open the live map</Link>
        </div>
      )}

      {tab === "media" && (
        <div className="grid grid-cols-[minmax(0,1fr)] gap-6 md:grid-cols-2">
          <YouTubePlayer video={0} />
          <ul className="grid grid-cols-2 gap-2">
            {GALLERY.slice(0, 4).map((p) => (
              <li key={p.src} className="aspect-[3/2] overflow-hidden rounded-lg bg-slate-100"><Img photo={p} /></li>
            ))}
          </ul>
        </div>
      )}
      </div>
    </DepthPage>
  );
}

// ---------------------------------------------------------------- short paths

/** `/:league/live` — the running act, else the next one (issue #14). */
export function LiveRedirect() {
  const league = useLeague();
  if (!league) return <Navigate to={href.home()} replace />;
  return <Navigate to={href.act(league.slug, YEAR, currentAct(league).slug, "live")} replace />;
}

/** `/:league/results` — the last act with results. */
export function ResultsRedirect() {
  const league = useLeague();
  if (!league) return <Navigate to={href.home()} replace />;
  const last = lastSailed(league);
  return <Navigate to={last ? href.act(league.slug, YEAR, last.slug, "results") : href.standings(league.slug)} replace />;
}

/** Every depth page carries the development switch too. */
export function WithDev({ children }: { children: ReactNode }) {
  return (
    <>
      {children}
      <DevSwitch />
    </>
  );
}

// ---------------------------------------------------------------- about

/** How a league works — the text of deutsche-segelliga.de/wettbewerbe, condensed. */
export function LeagueAboutPage() {
  const league = useLeague();
  if (!league) return <Navigate to={href.home()} replace />;
  return (
    <DepthPage league={league} title={`About the ${league.short}`} kicker={league.name} photo={DSL_PHOTOS.title}>
      <p className="max-w-3xl text-lg leading-relaxed text-slate-700">{league.about.intro}</p>
      <Block title="What is at stake">
        <ul className="max-w-3xl space-y-2 text-slate-700">
          {league.about.facts.map((f) => <li key={f} className="flex gap-3"><span className="text-brand-600">—</span>{f}</li>)}
        </ul>
      </Block>
      <Block title="The boat">
        <p className="max-w-3xl text-slate-700">J/70 one-designs provided by the league and rotated between the teams after every race — so that only the sailing decides.</p>
      </Block>
    </DepthPage>
  );
}

/** The association: history, board, member clubs. */
export function AssociationAboutPage() {
  return (
    <DepthPage league={null} title="Deutsche Segel-Liga e.V." kicker="About the association" photo={DSL_PHOTOS.title}>
      <p className="max-w-3xl text-lg leading-relaxed text-slate-700">{ASSOCIATION.history}</p>
      <p className="mt-3 max-w-3xl text-slate-600">{ASSOCIATION.record}</p>
      <Block title="Board">
        <ul className="grid grid-cols-[minmax(0,1fr)] gap-6 sm:grid-cols-3">
          {BOARD.map((b) => (
            <li key={b.name}>
              <div className="aspect-[2/3] overflow-hidden rounded-xl bg-slate-100"><Img photo={b.photo} /></div>
              <p className="mt-3 font-semibold">{b.name}</p>
              <p className="text-sm text-slate-500">{b.role}</p>
            </li>
          ))}
        </ul>
      </Block>
      <Block title="Member clubs 2026 — the 36 clubs of the 1. and 2. Liga">
        <div className="grid grid-cols-[minmax(0,1fr)] gap-8 md:grid-cols-2">
          {LEAGUES[0].divisions.map((d) => (
            <div key={d.slug}>
              <p className="mb-2 font-semibold">{d.name}</p>
              <ul className="space-y-1 text-sm text-slate-700">
                {d.rows.map((r) => <li key={r.short}><b className="inline-block w-20">{r.short}</b>{r.club}</li>)}
              </ul>
            </div>
          ))}
        </div>
      </Block>
    </DepthPage>
  );
}
