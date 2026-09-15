import { Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { LegacyRedirect } from "./components/LegacyRedirect";
import { Help } from "./pages/Help";
import { Account } from "./pages/Account";
import { LegalNotice } from "./pages/LegalNotice";
import { Privacy } from "./pages/Privacy";
import { Sailor } from "./pages/Sailor";
import { Live } from "./pages/Live";
import { LiveNow } from "./pages/LiveNow";
import { Matchday } from "./pages/Matchday";
import { RaceControl } from "./pages/RaceControl";
import { SeriesOverview } from "./pages/SeriesOverview";
import { Start } from "./pages/Start";
import { Standings } from "./pages/Standings";
import { Events } from "./pages/Events";
import { Admin } from "./pages/Admin";
import { MyClub } from "./pages/MyClub";
import { Club } from "./pages/Club";
import { Clubs } from "./pages/Clubs";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Start />} />
        {/* Several series run at once, so the way in is the overview; a single series'
            table hangs below it. There is deliberately no bare "standings" page — it could
            only ever have shown one arbitrary series of several. */}
        <Route path="series" element={<SeriesOverview />} />
        <Route path="series/:id" element={<Standings />} />
        <Route path="events" element={<Events />} />
        <Route path="events/:id" element={<Matchday />} />
        {/* Story WL-3: the race committee's screen on the water — a page, not a tab. */}
        <Route path="events/:id/race-control" element={<RaceControl />} />
        {/* Stories L-1, L-2: the boats on the map. */}
        <Route path="events/:id/live" element={<Live />} />
        {/* Story B-5: the running event, else the next date. */}
        <Route path="live" element={<LiveNow />} />
        <Route path="clubs" element={<Clubs />} />
        <Route path="clubs/:id" element={<Club />} />
        <Route path="sailors/:id" element={<Sailor />} />
        <Route path="account" element={<Account />} />
        {/* Story V-12: the club manager's own screen. Deliberately not under /admin — the
            whole point is that it needs no admin role. */}
        <Route path="club" element={<MyClub />} />
        <Route path="admin" element={<Admin />} />
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
        <Route path="standings" element={<Navigate to="/series" replace />} />
        <Route path="standings/:id" element={<LegacyRedirect to="/series/:id" />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
