import { useEffect, useRef, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, Navigate, NavLink, useParams, useSearchParams } from "react-router-dom";

import { getGetEventQueryKey, useGetEvent, useListLeagues } from "../../api/generated/sbl";
import type { EventSummary, League } from "../../api/types";
import { useAccount, useAsync } from "../../api/useApi";
import { useLive } from "../../api/useLive";
import { Async } from "../../components/Async";
import { ErrorMessage, LiveBadge, Loading, StatusBadge } from "../../components/Blocks";
import { Block, DepthPage, Expand, SubBar, TopBar, useSecondRow } from "../../components/site/Frame";
import { useSiteVersion } from "../../components/site/settings";
import { DSBL_PHOTOS, leaguePhoto, useActNotices } from "../../content";
import { eventDates, locationText } from "../../lib/format";
import { currentAct, hasResults, href, lastSailed, type Act } from "../../lib/site";
import { Crew, DailyStandings, PairingList, ResultsEntry } from "../Matchday";
import { DocList, MediaContent } from "./Depth";
import { ExampleNote, LeagueGate, StateBadge, actDates, divisionName, useActTitle } from "./shared";

// The matchday page (Story B-15): one act, its tabs in the URL, a division switch inside
// the tab when the act sails several. An event in no league has the same page at
// `/events/:id`.

const TABS = ["notice-board", "results", "pairing", "crews", "live", "media", "entry"] as const;
type Tab = (typeof TABS)[number];

/** `/:league/:year/:act/:tab?` */
export function ActPage() {
  const { act: slug, tab } = useParams();
  return (
    <LeagueGate>
      {({ league, acts, year }) => {
        const act = acts.find((a) => a.slug === slug);
        if (!act || !year) return <Navigate to={href.season(league.slug)} replace />;
        return (
          <MatchdayView
            league={league}
            act={act}
            tab={tab}
            tabHref={(t) => href.act(league.slug, year, act.slug, t)}
          />
        );
      }}
    </LeagueGate>
  );
}

/** What a matchday page shows, wherever it hangs. */
function MatchdayView({
  league,
  act,
  tab: tabParam,
  tabHref,
}: {
  league: League | null;
  act: Act;
  tab: string | undefined;
  tabHref: (tab: Tab) => string;
}) {
  const { t } = useTranslation("site");
  const actTitle = useActTitle();
  const { hasRole } = useAccount();
  const second = useSecondRow();
  const classic = useSiteVersion() === "classic";
  const [params, setParams] = useSearchParams();
  // A tab click scrolls the page so the matchday row sits right under the top bar and the
  // tab starts below it. A page opened by its URL keeps its picture in view.
  const anchor = useRef<HTMLDivElement>(null);
  const clicked = useRef(false);
  useEffect(() => {
    if (!clicked.current || !anchor.current) return;
    clicked.current = false;
    window.scrollTo({ top: anchor.current.getBoundingClientRect().top + window.scrollY - second.offset });
  }, [tabParam, second.offset]);

  const canEnterResults = hasRole("admin", "race_officer");
  const tabs = TABS.filter((tb) => tb !== "entry" || canEnterResults);
  const fallback: Tab = hasResults(act) ? "results" : "notice-board";
  const tab: Tab = (tabs as readonly string[]).includes(tabParam ?? "") ? (tabParam as Tab) : fallback;
  const event = act.events.find((e) => String(e.id) === params.get("division")) ?? act.events[0];
  const kicker = [league?.short_name, actDates(act), act.first.venue?.water ?? act.first.venue?.name].filter(Boolean).join(" · ");

  // With a sub-menu, the matchday's tabs are it: where you are on the left (the league,
  // its season, this act), the tabs beside it — the league's pages are a step up.
  const subnav = classic ? undefined : (
    <SubBar
      overlay
      label={t("act.tabs")}
      testId="site-act-bar"
      crumbs={[
        ...(league
          ? [
              { label: league.short_name, to: href.league(league.slug) },
              { label: t("pages.season"), to: href.season(league.slug) },
            ]
          : []),
        { label: actTitle(act) },
      ]}
      items={tabs.map((tb) => ({
        key: tb,
        to: { pathname: tabHref(tb), search: params.toString() },
        label: t(`tabs.${tb}`),
        current: tb === tab,
        testId: `site-act-tab-${tb}`,
        state: { keepScroll: true },
        onClick: () => {
          clicked.current = true;
        },
      }))}
    />
  );

  return (
    <DepthPage
      league={league}
      title={actTitle(act)}
      kicker={kicker}
      photo={hasResults(act) ? DSBL_PHOTOS.podium : league ? leaguePhoto(league.slug) : DSBL_PHOTOS.race}
      subnav={subnav}
    >
      {/* Which matchday this is and what it has, in one row that stays under the top bar
          — the second and last row of navigation (Story B-13). */}
      <div ref={anchor} aria-hidden />
      {classic && <nav
        aria-label={t("act.tabs")}
        data-testid="site-act-bar"
        className={`scrollbar-none sticky z-10 -mx-4 mb-8 overflow-x-auto border-b border-slate-200 bg-white/95 px-4 backdrop-blur ${second.top}`}
      >
        <ul className="flex items-center gap-1">
          <li className="mr-2 shrink-0 border-r border-slate-200 py-2 pr-4">
            <p className="text-sm font-semibold text-slate-900">{actTitle(act)}</p>
            <p className="text-xs text-slate-500">{actDates(act)}</p>
          </li>
          {tabs.map((tb) => (
            <li key={tb} className="shrink-0">
              <NavLink
                to={{ pathname: tabHref(tb), search: params.toString() }}
                // This page scrolls itself on a tab click (above); the site's reset to the
                // top on a new page must not undo that.
                state={{ keepScroll: true }}
                onClick={() => {
                  clicked.current = true;
                }}
                data-testid={`site-act-tab-${tb}`}
                aria-current={tb === tab ? "page" : undefined}
                className={`-mb-px block whitespace-nowrap border-b-2 px-3 py-4 text-sm font-medium ${
                  tb === tab ? "border-slate-900 text-slate-900" : "border-transparent text-slate-500 hover:text-slate-900"
                }`}
              >
                {t(`tabs.${tb}`)}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>}

      {/* At least a screen tall, so a short tab can still be scrolled up to the row. */}
      {/* `panel-scroll`: a results table wider than a phone scrolls here, not the page
          (Story A-10). */}
      <div className="panel-scroll min-h-[calc(100dvh-7.5rem)]" data-testid={`site-act-${tab}`}>
        <div className="mb-6 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-slate-600">
          <span data-testid="site-act-meta">
            {[locationText(act.first), act.first.host_club ? t("hostedBy", { host: act.first.host_club.name }) : null].filter(Boolean).join(" · ")}
          </span>
          <StateBadge state={act.state} />
        </div>
        {act.events.length > 1 && tab !== "notice-board" && tab !== "media" && (
          <div role="radiogroup" aria-label={t("act.division")} className="mb-6 inline-flex rounded-full bg-slate-100 p-1" data-testid="site-division-switch">
            {act.events.map((e) => (
              <button
                key={e.id}
                type="button"
                role="radio"
                aria-checked={e.id === event.id}
                data-testid={`site-division-${e.id}`}
                onClick={() => {
                  const next = new URLSearchParams(params);
                  next.set("division", String(e.id));
                  setParams(next, { replace: true });
                }}
                className={`rounded-full px-4 py-1.5 text-sm font-medium ${e.id === event.id ? "bg-white text-slate-900 shadow" : "text-slate-600 hover:text-slate-900"}`}
              >
                {divisionName(e)}
              </button>
            ))}
          </div>
        )}

        {tab === "notice-board" && <NoticeBoard events={act.events} />}
        {tab === "results" && <Results key={event.id} event={event} />}
        {tab === "pairing" && <PairingList key={event.id} eventId={event.id} />}
        {tab === "crews" && <Crew key={event.id} eventId={event.id} />}
        {tab === "live" && <LiveTab event={event} />}
        {tab === "media" && <MediaContent league={league?.slug ?? ""} limit={3} />}
        {tab === "entry" && <Entry key={event.id} event={event} />}
      </div>
    </DepthPage>
  );
}

function NoticeBoard({ events }: { events: EventSummary[] }) {
  const { t } = useTranslation("site");
  const board = useActNotices(events.map((e) => e.id));
  return (
    <Async state={board} testId="site-act-notices">
      {({ notices, documents, example }) => (
        <>
        {example && <ExampleNote />}
        <div className="grid grid-cols-[minmax(0,1fr)] gap-10 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
          <Block title={t("noticeBoard.announcements")}>
            {notices.map((n, i) => (
              <Expand
                key={n.title}
                open={i === 0}
                summary={
                  <span className="flex items-baseline gap-4">
                    <span className="w-20 shrink-0 text-sm text-slate-500">{n.time}</span>
                    <span
                      className={`shrink-0 rounded-full px-2 text-xs font-semibold ${
                        n.from === "jury" ? "bg-amber-50 text-amber-800" : n.from === "organizer" ? "bg-slate-100 text-slate-600" : "bg-brand-50 text-brand-700"
                      }`}
                    >
                      {t(`noticeBoard.from.${n.from}`)}
                    </span>
                    <span className="font-medium">{n.title}</span>
                  </span>
                }
              >
                {n.body}
              </Expand>
            ))}
          </Block>
          <Block title={t("noticeBoard.documents")}>
            <DocList docs={documents} />
          </Block>
        </div>
        </>
      )}
    </Async>
  );
}

/** The division's ranking of the act, live while racing (Story B-5). */
function Results({ event }: { event: EventSummary }) {
  const { t } = useTranslation("matchday");
  const detail = useAsync(useGetEvent(event.id));
  const live = useEventLive(event);
  return (
    <Async state={detail} testId="matchday" loadingText={t("loading")}>
      {(data) => (
        <>
          <p className="mb-4 flex flex-wrap items-center gap-3 text-sm text-slate-500">
            <span data-testid="matchday-races-count">{t("racesCount", { scored: data.races_scored, total: data.races_total })}</span>
            {/* The status from the event's own query, which the stream refreshes — the
                act's list from the league's year is a snapshot of when the page opened. */}
            {data.event.status === "live" && <LiveBadge state={live} testId="matchday-live-badge" />}
          </p>
          <DailyStandings standings={data.standings} event={data.event} />
        </>
      )}
    </Async>
  );
}

/** The race committee's correction screen (Story WL-2). */
function Entry({ event }: { event: EventSummary }) {
  const detail = useAsync(useGetEvent(event.id));
  useEventLive(event);
  return (
    <Async state={detail} testId="matchday">
      {(data) => <ResultsEntry eventId={event.id} standings={data.standings} />}
    </Async>
  );
}

/** Hear about results and transitions while the page is open — published events only, a
 *  draft has no stream. The prefixes end in a slash: "/api/events/1" would also match 12.
 *  The league's year is refetched too: the act's state, its badge and the Now chapter
 *  are derived from the events' states in it. */
function useEventLive(event: EventSummary) {
  return useLive(event.published ? `event:${event.id}` : null, [
    getGetEventQueryKey(event.id),
    `/api/events/${event.id}/`,
    `/api/admin/events/${event.id}/`,
    "/api/leagues/",
  ]);
}

/** The live map while racing, a replay afterwards — or the live view the event names. */
function LiveTab({ event }: { event: EventSummary }) {
  const { t } = useTranslation("site");
  const title = event.status === "live" ? t("live.now") : event.status === "final" ? t("live.replay") : t("live.from", { dates: eventDates(event) });
  return (
    <div className="rounded-2xl border border-slate-200 p-8 text-center" data-testid="site-live">
      <p className="text-lg font-semibold">{title}</p>
      <p className="mt-1 text-slate-600">{t("live.text")}</p>
      <p className="mt-3"><StatusBadge status={event.status} /></p>
      {event.live_url ? (
        <a href={event.live_url} target="_blank" rel="noopener noreferrer" data-testid="matchday-live-external-link" className="mt-5 inline-block rounded-full bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white">
          {t("live.external")}
        </a>
      ) : (
        <Link to={`/events/${event.id}/live`} data-testid="matchday-live-map-link" className="mt-5 inline-block rounded-full bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white">
          {t("live.open")}
        </Link>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- an event's own page

/** The old tab names (`?view=`) of the former matchday page, by their new ones. */
const OLD_VIEWS: Record<string, Tab> = { standings: "results", pairing: "pairing", crew: "crews", results: "entry" };

/** `/events/:id/:tab?` — an event in a league goes to its act's page (Story B-16); one in
 *  no league, a club's own regatta, keeps this address and the same page (Story B-15). */
export function EventPage() {
  const { id = "" } = useParams();
  const { tab } = useParams();
  const [params] = useSearchParams();
  const leagues = useListLeagues();
  const detail = useAsync(useGetEvent(Number(id)));
  if (detail.loading) return <Bare><Loading testId="matchday-loading" /></Bare>;
  if (detail.error) return <Bare><ErrorMessage text={detail.error} testId="matchday-error" /></Bare>;
  if (!detail.data) return null;

  const event = detail.data.event;
  const wanted = tab ?? OLD_VIEWS[params.get("view") ?? ""];
  const leagueId = event.series?.league_id;
  // Waits for the leagues only while they are on their way: if that request fails, the
  // event's own page is the honest answer, not a spinner that never ends.
  if (leagueId != null && leagues.isPending) return <Bare><Loading testId="matchday-loading" /></Bare>;
  const league = leagues.data?.find((l) => l.id === leagueId);
  if (league && event.series?.year) {
    // The same slug `actsOf` gives the act, so an event with no matchday — a cup's one
    // weekend — has one page, not two.
    const slug = event.matchday != null ? `act-${event.matchday}` : `event-${event.id}`;
    const to = href.act(league.slug, event.series.year, slug, wanted);
    return <Navigate to={`${to}?division=${event.id}`} replace />;
  }
  const act: Act = { slug: `event-${event.id}`, matchday: event.matchday ?? null, events: [event], first: event, state: stateOfEvent(event) };
  return <MatchdayView league={null} act={act} tab={wanted} tabHref={(tb) => href.event(event.id, tb)} />;
}

function stateOfEvent(event: EventSummary): Act["state"] {
  if (event.status === "live") return "live";
  if (event.status === "final") return "done";
  if (event.status === "cancelled") return "cancelled";
  return "planned";
}

function Bare({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-dvh bg-white">
      <TopBar />
      <main id="content" className="mx-auto max-w-6xl px-4">{children}</main>
    </div>
  );
}

// ---------------------------------------------------------------- short paths

/** `/:league/live` — the running act's live tab, else the next one's (Story B-16). */
export function LiveRedirect() {
  return (
    <LeagueGate>
      {({ league, acts, year }) => {
        const act = currentAct(acts);
        return <Navigate to={act && year ? href.act(league.slug, year, act.slug, "live") : href.season(league.slug)} replace />;
      }}
    </LeagueGate>
  );
}

/** `/:league/results` — the last act with results, else the standings. */
export function ResultsRedirect() {
  return (
    <LeagueGate>
      {({ league, acts, year }) => {
        const last = lastSailed(acts) ?? acts.find((a) => a.state === "live");
        return <Navigate to={last && year ? href.act(league.slug, year, last.slug, "results") : href.standings(league.slug)} replace />;
      }}
    </LeagueGate>
  );
}
