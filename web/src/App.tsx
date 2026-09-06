import { Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { LegacyRedirect } from "./components/LegacyRedirect";
import { Account } from "./pages/Konto";
import { Sailor } from "./pages/Segler";
import { Matchday } from "./pages/Spieltag";
import { Start } from "./pages/Start";
import { Standings } from "./pages/Tabelle";
import { Events } from "./pages/Termine";
import { Admin } from "./pages/Verwaltung";
import { Club } from "./pages/Verein";
import { Clubs } from "./pages/Vereine";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Start />} />
        <Route path="standings" element={<Standings />} />
        <Route path="standings/:id" element={<Standings />} />
        <Route path="events" element={<Events />} />
        <Route path="events/:id" element={<Matchday />} />
        <Route path="clubs" element={<Clubs />} />
        <Route path="clubs/:id" element={<Club />} />
        <Route path="sailors/:id" element={<Sailor />} />
        <Route path="account" element={<Account />} />
        <Route path="admin" element={<Admin />} />
        {/* Legacy German paths from before the English rewrite — kept as redirects so
            nothing bookmarked from the earlier build breaks outright. */}
        <Route path="tabelle" element={<Navigate to="/standings" replace />} />
        <Route path="tabelle/:id" element={<LegacyRedirect to="/standings/:id" />} />
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
