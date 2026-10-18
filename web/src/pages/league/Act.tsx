import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { Link, Navigate, useParams, useSearchParams } from "react-router-dom";

import { getGetEventQueryKey, useGetEvent, useListLeagues } from "../../api/generated/sbl";
import type { EventSummary, League } from "../../api/types";
import { useAccount, useAsync } from "../../api/useApi";
import { useLive } from "../../api/useLive";
import { Async } from "../../components/Async";
import { ErrorMessage, LiveBadge, Loading, StatusBadge } from "../../components/Blocks";
import { Card, Columns, Panel, PillSwitch, TextCard, tone } from "../../components/site/Cards";
import { BARS, Block, DepthPage, Expand, PageLoading, SubBar } from "../../components/site/Frame";
import { DSBL_PHOTOS, leaguePhoto, useActNotices } from "../../content";
import { eventDates, locationText } from "../../lib/format";
import { actSlug, currentAct, hasResults, href, lastSailed, stateOf, type Act } from "../../lib/site";
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
  const [params, setParams] = useSearchParams();
  // A tab click scrolls the page so the matchday row sits right under the top bar and the
  // tab starts below it. A page opened by its URL keeps its picture in view.
  const anchor = useRef<HTMLDivElement>(null);
  const clicked = useRef(false);
  useEffect(() => {
    if (!clicked.current || !anchor.current) return;
    clicked.current = false;
    window.scrollTo({ top: anchor.current.getBoundingClientRect().top + window.scrollY - BARS.offset });
  }, [tabParam]);

  const canEnterResults = hasRole("admin", "race_officer");
  const tabs = TABS.filter((tb) => tb !== "entry" || canEnterResults);
  const fallback: Tab = hasResults(act) ? "results" : "notice-board";
  const tab: Tab = (tabs as readonly string[]).includes(tabParam ?? "") ? (tabParam as Tab) : fallback;
  const event = act.events.find((e) => String(e.id) === params.get("division")) ?? act.events[0];
  const kicker = [league?.short_name, actDates(act), act.first.venue?.water ?? act.first.venue?.name].filter(Boolean).join(" · ");

  // The matchday's tabs are its sub-menu: where you are on the left (the league, its
  // season, this act), the tabs beside it — the league's pages are a step up.
  const subnav = (
    <SubBar
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
      {/* Where a tab click scrolls to: the tab's top, just under the rows. */}
      <div ref={anchor} aria-hidden />
      {/* At least a screen tall, so a short tab can still be scrolled up to the rows;
          `panel-scroll`: a results table wider than a phone scrolls here, not the page
          (Story A-10). */}
      <div className="panel-scroll min-h-[calc(100dvh-7.5rem)]" data-testid={`site-act-${tab}`} data-flow>
        <TextCard className="mb-6 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
          <span data-testid="site-act-meta">
            {[locationText(act.first), act.first.host_club ? t("hostedBy", { host: act.first.host_club.name }) : null].filter(Boolean).join(" · ")}
          </span>
          <StateBadge state={act.state} />
        </TextCard>
        {act.events.length > 1 && tab !== "notice-board" && tab !== "media" && (
          <PillSwitch
            label={t("act.division")}
            className="mb-6"
            testId="site-division-switch"
            value={String(event.id)}
            options={act.events.map((e) => ({ value: String(e.id), label: divisionName(e), testId: `site-division-${e.id}` }))}
            onChange={(id) => {
              const next = new URLSearchParams(params);
              next.set("division", id);
              setParams(next, { replace: true });
            }}
          />
        )}

        {tab === "notice-board" && <NoticeBoard events={act.events} />}
        {/* The tables on a panel, which turns their light colours into the glass's. */}
        {tab === "results" && <Panel><Results key={event.id} event={event} /></Panel>}
        {tab === "pairing" && <Panel><PairingList key={event.id} eventId={event.id} /></Panel>}
        {tab === "crews" && <Panel><Crew key={event.id} eventId={event.id} /></Panel>}
        {tab === "live" && <LiveTab event={event} />}
        {tab === "media" && <MediaContent league={league?.slug ?? ""} limit={3} />}
        {tab === "entry" && <Panel><Entry key={event.id} event={event} /></Panel>}
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
        <Columns split="twoToOne">
          <Block title={t("noticeBoard.announcements")}>
            <Card className="px-4">
            {notices.map((n, i) => (
              <Expand
                key={n.title}
                open={i === 0}
                summary={
                  <span className="flex items-baseline gap-4">
                    <span className={`w-20 shrink-0 text-sm ${tone.faint}`}>{n.time}</span>
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
            </Card>
          </Block>
          <Block title={t("noticeBoard.documents")}>
            <Card className="p-4">
              <DocList docs={documents} />
            </Card>
          </Block>
        </Columns>
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
  const button = "mt-5 inline-block rounded-full bg-white px-5 py-2.5 text-sm font-semibold text-slate-950";
  return (
    <Card className="p-8 text-center" testId="site-live">
      <p className={`text-lg font-semibold ${tone.text}`}>{title}</p>
      <p className={`mt-1 ${tone.muted}`}>{t("live.text")}</p>
      <p className="mt-3"><StatusBadge status={event.status} /></p>
      {event.live_url ? (
        <a href={event.live_url} target="_blank" rel="noopener noreferrer" data-testid="matchday-live-external-link" className={button}>
          {t("live.external")}
        </a>
      ) : (
        <Link to={`/events/${event.id}/live`} data-testid="matchday-live-map-link" className={button}>
          {t("live.open")}
        </Link>
      )}
    </Card>
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
  if (detail.loading) return <PageLoading><Loading testId="matchday-loading" /></PageLoading>;
  if (detail.error) return <PageLoading><ErrorMessage text={detail.error} testId="matchday-error" /></PageLoading>;
  if (!detail.data) return null;

  const event = detail.data.event;
  const wanted = tab ?? OLD_VIEWS[params.get("view") ?? ""];
  const leagueId = event.series?.league_id;
  // Waits for the leagues only while they are on their way: if that request fails, the
  // event's own page is the honest answer, not a spinner that never ends.
  if (leagueId != null && leagues.isPending) return <PageLoading><Loading testId="matchday-loading" /></PageLoading>;
  const league = leagues.data?.find((l) => l.id === leagueId);
  if (league && event.series?.year) {
    const to = href.act(league.slug, event.series.year, actSlug(event), wanted);
    return <Navigate to={`${to}?division=${event.id}`} replace />;
  }
  const act: Act = { slug: `event-${event.id}`, matchday: event.matchday ?? null, events: [event], first: event, state: stateOf([event]) };
  return <MatchdayView league={null} act={act} tab={wanted} tabHref={(tb) => href.event(event.id, tb)} />;
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
