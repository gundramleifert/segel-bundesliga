import { Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { LegacyRedirect } from "./components/LegacyRedirect";
import { Help } from "./pages/Help";
import { Account } from "./pages/Account";
import { Sailor } from "./pages/Sailor";
import { Matchday } from "./pages/Matchday";
import { SeriesOverview } from "./pages/SeriesOverview";
import { Start } from "./pages/Start";
import { Standings } from "./pages/Standings";
import { Events } from "./pages/Events";
import { Admin } from "./pages/Admin";
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
        <Route path="clubs" element={<Clubs />} />
        <Route path="clubs/:id" element={<Club />} />
        <Route path="sailors/:id" element={<Sailor />} />
        <Route path="account" element={<Account />} />
        <Route path="admin" element={<Admin />} />
        <Route path="help" element={<Help />} />
        {/* Legacy German paths from before the English rewrite, plus the former
            "standings" paths from when the site presented a single league — kept as
            redirects so nothing bookmarked from an earlier build breaks outright. */}
        <Route path="standings" element={<Navigate to="/series" replace />} />
        <Route path="standings/:id" element={<LegacyRedirect to="/series/:id" />} />
        <Route path="tabelle" element={<Navigate to="/series" replace />} />
        <Route path="tabelle/:id" element={<LegacyRedirect to="/series/:id" />} />
        <Route path="termine" element={<Navigate to="/events" replace />} />
        <Route path="spieltage/:id" element={<LegacyRedirect to="/events/:id" />} />
        <Route path="vereine" element={<Navigate to="/clubs" replace />} />
        <Route path="vereine/:id" element={<LegacyRedirect to="/clubs/:id" />} />
        <Route path="segler/:id" element={<LegacyRedirect to="/sailors/:id" />} />
        <Route path="konto" element={<Navigate to="/account" replace />} />
        <Route path="verwaltung" element={<Navigate to="/admin" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
