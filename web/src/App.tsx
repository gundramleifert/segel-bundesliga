import type { ReactElement } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { Layout, SiteShell } from "./components/Layout";
import { LegacyRedirect, PrefixRedirect } from "./components/LegacyRedirect";
import { HelpLanding, HelpPageView } from "./pages/Help";
import { Account } from "./pages/Account";
import { LegalNotice } from "./pages/LegalNotice";
import { Privacy } from "./pages/Privacy";
import { Sailor } from "./pages/Sailor";
import { Live } from "./pages/Live";
import { LiveNow } from "./pages/LiveNow";
import { RaceControl } from "./pages/RaceControl";
import { Events } from "./pages/Events";
import { Admin } from "./pages/Admin";
import { AdminClubNew } from "./pages/AdminClubNew";
import { AdminEventNew } from "./pages/AdminEventNew";
import { AdminSailorNew } from "./pages/AdminSailorNew";
import { AdminSeriesNew } from "./pages/AdminSeriesNew";
import { Club } from "./pages/Club";
import { Clubs } from "./pages/Clubs";
import { ClubPage, EventPage as MyEventPage, ProfilePage, SeriesPage as MySeriesPage } from "./pages/me/Contexts";
import { ClubRedirect, MeIndex } from "./pages/me/Redirects";
import { Prototype } from "./prototype/Prototype";
import { ActPage, EventPage, LiveRedirect, ResultsRedirect } from "./pages/league/Act";
import {
  ArticlePage,
  ClubsPage,
  LeagueAboutPage,
  MediaPage,
  NewsPage,
  NoticeBoardPage,
  PressPage,
  SeasonPage,
  StandingsPage,
} from "./pages/league/Depth";
import { AssociationAboutPage, AssociationHome } from "./pages/league/Home";
import { LeagueHome } from "./pages/league/LeagueHome";
import { SeriesPage } from "./pages/league/SeriesPage";

/** Every page of a league, by its path under `/:league` — one list, so the old DSBL
 *  addresses below cannot miss a page the league has. */
const LEAGUE_ROUTES: [sub: string, page: ReactElement][] = [
  ["", <LeagueHome />],
  ["about", <LeagueAboutPage />],
  ["standings", <StandingsPage />],
  [":year/standings", <StandingsPage />],
  ["season", <SeasonPage />],
  [":year/season", <SeasonPage />],
  ["notice-board", <NoticeBoardPage />],
  ["clubs", <ClubsPage />],
  ["news", <NewsPage />],
  ["news/:slug", <ArticlePage />],
  ["media", <MediaPage />],
  ["press", <PressPage />],
  ["live", <LiveRedirect />],
  ["results", <ResultsRedirect />],
  [":year/:act", <ActPage />],
  [":year/:act/:tab", <ActPage />],
];

export default function App() {
  return (
    <Routes>
      {/* Issue #13: five homepage options to compare, each with its own header — so
          outside the site's Layout. Throwaway until one is chosen. */}
      {/* Issue #14: option E as a clickable prototype — the chosen structure, mock data. */}
      <Route path="prototype/*" element={<Prototype />} />
      <Route element={<SiteShell />}>
      {/* The site's structure (issue #14, docs/site-structure.md, Stories B-13–B-16): the
          association's home, each league's chapter page and the depth pages behind it.
          They draw their own frame. A league's path is one free segment, so the static
          routes below (`/me`, `/admin`, …) win over it by react-router's ranking. */}
      <Route index element={<AssociationHome />} />
      {/* The DSBL was one league until 2026-10-16; its 1. Liga is its heir (Story B-16).
          Every path a league has, spelled out under `dsbl/`: a splat `dsbl/*` ranks below
          `:league/standings` (a static segment and a dynamic one beat a static one and a
          splat), so `/dsbl/standings` was the league "dsbl" — unknown, hence home. */}
      {LEAGUE_ROUTES.map(([sub]) => (
        <Route key={`dsbl/${sub}`} path={sub ? `dsbl/${sub}` : "dsbl"} element={<PrefixRedirect from="dsbl" to="1-liga" />} />
      ))}
      <Route path="about" element={<AssociationAboutPage />} />
      {LEAGUE_ROUTES.map(([sub, page]) => (
        <Route key={`:league/${sub}`} path={sub ? `:league/${sub}` : ":league"} element={page} />
      ))}
      {/* An event in no league keeps its page; one in a league goes to its act (B-15, B-16). */}
      <Route path="events/:id" element={<EventPage />} />
      <Route path="events/:id/:tab" element={<EventPage />} />
      <Route element={<Layout />}>
        {/* A series in a league goes to its league's standings; one in no league keeps
            its own table (Story B-16). The overview of every series is the leagues now. */}
        <Route path="series" element={<Navigate to="/" replace />} />
        <Route path="series/:id" element={<SeriesPage />} />
        <Route path="events" element={<Events />} />
        {/* Story WL-3: the race committee's screen on the water — a page, not a tab. */}
        <Route path="events/:id/race-control" element={<RaceControl />} />
        {/* Stories L-1, L-2: the boats on the map. */}
        <Route path="events/:id/live" element={<Live />} />
        {/* Story B-5: the running event, else the next date. */}
        <Route path="live" element={<LiveNow />} />
        <Route path="clubs" element={<Clubs />} />
        <Route path="clubs/:id" element={<Club />} />
        <Route path="sailors/:id" element={<Sailor />} />
        {/* Signed out: the sign-in page. Signed in, it forwards to /me/profile. */}
        <Route path="account" element={<Account />} />
        {/* Stories Z-8, S-7: my space — everything I am part of, and my page in each. */}
        <Route path="me" element={<MeIndex />} />
        <Route path="me/profile" element={<ProfilePage />} />
        <Route path="me/club/:id" element={<ClubPage />} />
        <Route path="me/series/:id" element={<MySeriesPage />} />
        <Route path="me/event/:id" element={<MyEventPage />} />
        {/* The screens my space replaced, kept as redirects (Story S-7). */}
        <Route path="club" element={<ClubRedirect />} />
        <Route path="reimbursements" element={<Navigate to="/me" replace />} />
        <Route path="admin" element={<Admin />} />
        {/* Creating is a page of its own per area, reached from the "＋" on its tab. */}
        <Route path="admin/clubs/new" element={<AdminClubNew />} />
        <Route path="admin/series/new" element={<AdminSeriesNew />} />
        <Route path="admin/events/new" element={<AdminEventNew />} />
        <Route path="admin/sailors/new" element={<AdminSailorNew />} />
        {/* Story B-18: the handbook, pages from web/src/handbook/. */}
        <Route path="help" element={<HelpLanding />} />
        <Route path="help/:page" element={<HelpPageView />} />
        <Route path="legal-notice" element={<LegalNotice />} />
        <Route path="privacy" element={<Privacy />} />
        {/* The former "standings" paths, from when the site presented a single league
            rather than several series — kept as redirects because they were the real URLs
            of a deployed build.

            Every route on this site is English. The German paths of the pre-rename build
            (`/tabelle`, `/termine`, `/spieltage`, `/vereine`, `/segler`, `/konto`,
            `/verwaltung`) and the German legal aliases (`/impressum`, `/datenschutz`) are
            deliberately gone: German is a language this site is *translated into*, never a
            second set of identifiers. The catch-all below answers anyone who still tries
            one. */}
        <Route path="standings" element={<Navigate to="/" replace />} />
        <Route path="standings/:id" element={<LegacyRedirect to="/series/:id" />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
      </Route>
    </Routes>
  );
}
