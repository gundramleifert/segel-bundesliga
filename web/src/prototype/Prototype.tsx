import { Navigate, Route, Routes } from "react-router-dom";

import {
  ActPage,
  AssociationAboutPage,
  LeagueAboutPage,
  ArticlePage,
  AssociationHome,
  ClubsPage,
  LeagueHome,
  LiveRedirect,
  MediaPage,
  NewsPage,
  NoticeBoardPage,
  PressPage,
  ResultsRedirect,
  SeasonPage,
  StandingsPage,
  WithDev,
} from "./Pages";

/** The clickable prototype of option E (issue #14, concept in `docs/site-structure.md`):
 *  the URL scheme under `/prototype`, mock content, and a development switch for the
 *  variants still open. Outside the site's Layout; throwaway. */
export function Prototype() {
  return (
    <Routes>
      <Route index element={<AssociationHome />} />
      <Route path="about" element={<WithDev><AssociationAboutPage /></WithDev>} />
      <Route path=":league" element={<LeagueHome />} />
      <Route path=":league/about" element={<WithDev><LeagueAboutPage /></WithDev>} />
      <Route path=":league/standings" element={<WithDev><StandingsPage /></WithDev>} />
      <Route path=":league/season" element={<WithDev><SeasonPage /></WithDev>} />
      <Route path=":league/notice-board" element={<WithDev><NoticeBoardPage /></WithDev>} />
      <Route path=":league/clubs" element={<WithDev><ClubsPage /></WithDev>} />
      <Route path=":league/news" element={<WithDev><NewsPage /></WithDev>} />
      <Route path=":league/news/:slug" element={<WithDev><ArticlePage /></WithDev>} />
      <Route path=":league/media" element={<WithDev><MediaPage /></WithDev>} />
      <Route path=":league/press" element={<WithDev><PressPage /></WithDev>} />
      <Route path=":league/live" element={<LiveRedirect />} />
      <Route path=":league/results" element={<ResultsRedirect />} />
      <Route path=":league/:year/:act" element={<WithDev><ActPage /></WithDev>} />
      <Route path=":league/:year/:act/:tab" element={<WithDev><ActPage /></WithDev>} />
      <Route path="*" element={<Navigate to="/prototype" replace />} />
    </Routes>
  );
}
