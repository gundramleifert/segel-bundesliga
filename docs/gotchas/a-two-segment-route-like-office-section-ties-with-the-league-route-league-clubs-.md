# A two-segment route like office/:section ties with the league route :league/clubs — spell out every static path that shares a word with a league page

**Symptom** — `/office/clubs`, `/office/news` and `/office/media` landed on the
association's home page, while `/office/events` and `/office/sailors` worked; the
redirect `/admin/clubs/new` → `/office/clubs/new` silently did nothing.

**Cause** — react-router ranks a route by its segments: static scores more than dynamic,
a splat less. `office/:section` (static + dynamic) and the league page `:league/clubs`
(dynamic + static) score the **same**, and a tie goes to the route listed first — the
league routes are (`LEAGUE_ROUTES` in `App.tsx`). So "office" was read as an unknown
league, which redirects home. Only the words a league page also has (`clubs`, `news`,
`media`, …) collided, which made it look like a bug in those sections. Likewise the splat
`admin/*` ranks below `:league/:year/:act`, so `/admin/clubs/new` was an act. What misled:
the routes looked right in isolation, and the specs passed for the sections that happen
not to share a word with a league page.

**Rule** — a top-level static path whose second segment is dynamic, or a splat, is in
competition with the league's one-free-segment routes. Spell out each concrete path
(`office/clubs`, `admin/:area/new`) so it is static where the league's is dynamic; keep
the dynamic form only as a fallback.

**Evidence** — `web/src/App.tsx` (`OFFICE_SECTIONS.map(...)`, `admin/:area/new`);
`e2e/lifecycle.spec.ts` "A-11/Z-10: the league office, a section per area" failed on
`workspace-content-office-clubs` and on the `/office/clubs/new` URL before, passes after.

**Seen** — 2026-10-25
