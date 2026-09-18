# User Stories

Here we collect what the system should be able to do — from the perspective of those who use it. Each story gets an identifier (`B-1`, `WL-3`, …); tests carry the same identifier in their docstring. This makes it possible to look in both directions: What is already covered by this story? And which story does this test belong to?

**One file per person, from the one who sets the site up to the one who only reads it.**
Inside a file the stories stand in the order of the work — master data before the season,
the season before the matchday, the matchday before its aftermath — under one `##` heading
per phase.

| File | Who |
|---|---|
| [administration.md](administration.md) | Administration: clubs, series, accounts and roles, the admin screens |
| [race-committee.md](race-committee.md) | Race committee: running races, entering results |
| [event-organizer.md](event-organizer.md) | Event organizer: one event from draft to closing |
| [club-manager.md](club-manager.md) | Club manager: members, competitions, squad and lineup, the club page |
| [sailor.md](sailor.md) | Sailor: account, club, waiver, profile |
| [visitor.md](visitor.md) | Visitor and fans: everything that is public |
| [live.md](live.md) | Live and tracking — spectator, race committee and the phone on the boat share these; the plan is `docs/PLAN_LIVE_IMPLEMENTATION.md` |

**Identifiers are permanent, files are not.** The letter records where a story was
first told (`B` Visitor/Fan · `WL` Race Committee · `VA` Event Organizer · `V` Club Manager
· `S` Sailor · `Z` Access · `A` Administration · `L` Live and tracking · `R` Editorial) and
never changes, because tests carry it. A story sits in the file of the person who tells
it, so `A-5` is read in `visitor.md` and `Z-2` in `administration.md`. `scripts/check-docs.py`
reads the whole folder: every `Tests:` reference must resolve, every story a test names
must exist, and every link between the files must land on a heading.

**Status:** ○ open · ◐ partial · ● implemented and tested

Format:

```
### B-1 ● View league standings
As a **fan** I want to **see the current league standings**,
so that I **know where my team stands**.

Acceptance criteria:
- All 18 teams, places 1–18, fewer points rank higher.
- For each matchday, the position achieved there is visible.
- A not yet sailed matchday does not count.

Tests: `api/tests/stories/test_visitor.py::TestSeriesTable`
```

---

## Still to Write

Sensible next areas:

- **A-…** Administration: set up seasons and leagues, maintain venues.
- **File storage — decided for S-1, S-2 and V-3.** Three stories need
  uploads: the scan of the consent (S-1), member photo (S-2), and club crest (V-3). S-2
  and V-3 use a local directory (`api/uploads/sailors/{id}.jpg`,
  `api/uploads/clubs/{id}.png`; deterministic path, no database column, access control per
  request in `app/routers/sailors.py` and `app/routers/clubs.py`) — see their sections
  above for the reasoning, including why a crest keeps its alpha channel where a photo does
  not. S-1 uses the same local directory (`api/uploads/waivers/`) but a **random file
  name** known only to the confirmation row, one serving endpoint that checks access and
  logs every retrieval, and type/size limits (PDF, JPEG, PNG; 10 MB). **Access control
  differs per story** — a crest and most photos are public, the scan from S-1 on no
  account — which is why the three never share a static path. Still open: virus scanning
  and the retention job, and S3-compatible storage once the site leaves one machine.
- **Deadlines:** deliberately left out for now. Series and event each have a **time range**
  (`starts_on`, `ends_on`); a deadline concept is derived from this if it becomes clear what
  is needed.
- **R-…** Editorial: publish post, create gallery.
