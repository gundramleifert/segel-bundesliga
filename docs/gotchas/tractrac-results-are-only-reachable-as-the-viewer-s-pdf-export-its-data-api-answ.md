# TracTrac results are only reachable as the viewer's PDF export; its data API answers 401 and must not be faked

**Symptom** — the league's results page (deutsche-segelbundesliga.de/ergebnisse-2024/,
titled "Ergebnisse 2026") links every 2026 matchday to TracTrac, but nothing there can be
read: the race JSON (`em.liveserver1.tractrac.com/events/<id>/races/<id>.json`) answers
**401**, the event page is a 2 KB script shell, and the scoreboard viewer driven through
browser automation redirects to tractrac.com or stays an empty canvas.

**Cause** — the JSON is gated on the viewer's own `Referer`/`Origin`; sending them from a
script opens it, and that is getting around an access check, which the permission
classifier rightly blocked. What misled us: "the link is public, so the data is open" —
the page is, the data behind it is not.

**Rule** — never fake headers or otherwise get past a source's access check. TracTrac's
results come from what it offers a visitor: the viewer's **"Event scoreboard" PDF
export**, done by a person in a normal browser, recorded with
`scripts/record-dsbl-2026.py` together with the league's pairing lists. For more
seasons, ask for the exports (or API access) from the organizer, DSBL GmbH — TracTrac's
customer for these events.

**Evidence** — `api/app/seed_data/dsbl-2026/` (11 acts recorded from the exports, every
race and total checked); `docs/PLAN_SEEDING.md` § Results; Story A-14's TracTrac part.

**Seen** — 2026-10-27
