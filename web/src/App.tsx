import { Navigate, Route, Routes } from "react-router-dom";

import { Layout, SiteShell } from "./components/Layout";
import { LegacyRedirect } from "./components/LegacyRedirect";
import { Help } from "./pages/Help";
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
import { WireframeIndex, WireframeOption } from "./wireframes/Wireframes";
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

export default function App() {
  return (
    <Routes>
      {/* Issue #13: five homepage options to compare, each with its own header — so
          outside the site's Layout. Throwaway until one is chosen. */}
      <Route path="wireframes" element={<WireframeIndex />} />
      <Route path="wireframes/:option" element={<WireframeOption />} />
      <Route path="wireframes/:option/:league" element={<WireframeOption />} />
      {/* Issue #14: option E as a clickable prototype — the chosen structure, mock data. */}
      <Route path="prototype/*" element={<Prototype />} />
      <Route element={<SiteShell />}>
      {/* The site's structure (issue #14, docs/site-structure.md, Stories B-13–B-16): the
          association's home, each league's chapter page and the depth pages behind it.
          They draw their own frame. A league's path is one free segment, so the static
          routes below (`/me`, `/admin`, …) win over it by react-router's ranking. */}
      <Route index element={<AssociationHome />} />
      <Route path="about" element={<AssociationAboutPage />} />
      <Route path=":league" element={<LeagueHome />} />
      <Route path=":league/about" element={<LeagueAboutPage />} />
      <Route path=":league/standings" element={<StandingsPage />} />
      <Route path=":league/:year/standings" element={<StandingsPage />} />
      <Route path=":league/season" element={<SeasonPage />} />
      <Route path=":league/:year/season" element={<SeasonPage />} />
      <Route path=":league/notice-board" element={<NoticeBoardPage />} />
      <Route path=":league/clubs" element={<ClubsPage />} />
      <Route path=":league/news" element={<NewsPage />} />
      <Route path=":league/news/:slug" element={<ArticlePage />} />
      <Route path=":league/media" element={<MediaPage />} />
      <Route path=":league/press" element={<PressPage />} />
      <Route path=":league/live" element={<LiveRedirect />} />
      <Route path=":league/results" element={<ResultsRedirect />} />
      <Route path=":league/:year/:act" element={<ActPage />} />
      <Route path=":league/:year/:act/:tab" element={<ActPage />} />
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
        <Route path="help" element={<Help />} />
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
