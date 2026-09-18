# Live and Tracking

Part of the [user stories](README.md); the format, the status marks and the
identifier rule are explained there.

The plan behind these four stories — make or buy against SAP Sailing Analytics, the
module layout, the phases and their proofs — is `docs/PLAN_LIVE_IMPLEMENTATION.md`. The
result in one line: results and positions are ours to build (a day's work each on top of
B-5); the analytics that rank boats on the water are a small port of one-design ideas, not a
self-hosted SAP instance; SAP is used **once, offline, as an oracle** to check our
detectors against theirs on a recorded dataset. Decision numbers below refer to §3 of the
plan.

Data comes in three stages, and every story is built against the first: **emulated**
tracks posted through the real ingest endpoint (the emulator knows its own ground truth —
when it rounds, when it finishes — so it is the contract test for every detector), then
SAP's recorded Mövenstein dataset, then our own phones on our own boats.

## In the order of the plan's phases (A, B, D, C)

### L-1 ◐ See the boats move
As a **spectator** I want to **see the boats of the running race move on a map**,
so that I **follow the race from the shore, the club house or the sofa**.

Acceptance criteria:
- `/events/:id/live` shows a map with one marker per boat of the event, in the boat's colour
  and carrying the team's name that the pairing list puts on it for the running race, a
  short trail behind each, and a follow mode that keeps the fleet in view.
- **External or internal live view, per event.** `Event.live_url` empty means the internal
  map is the live view. Set — a SAP Sailing race board, a club's own page — every live link
  of the event (matchday page, `/events/:id/live`) leads there, in a new tab, and the map
  page shows the link instead of an empty map: two live pictures of one race is one too
  many. The organizer sets or clears it in the event editor; only `http(s)://` addresses
  are accepted. The API keeps its own live picture and stream either way, so switching
  back costs nothing.
- Markers move as fixes arrive, over B-5's stream, inline (`positions` frame) — the one
  payload that does not go through a refetch.
- **The tracker belongs to the boat, not the team** (decision 5). One phone per boat of the
  event, `Event.boat_count` of them; who sails boat 3 in race 17 is what `RaceEntry` already
  says. This is the largest simplification against SAP's competitor↔device mapping, and it is
  available only because the pairing list is ours.
- **The committee boat is a tracker too** (decision 6): its phone position *is* the boat end
  of the start and finish lines. Nobody types coordinates on the water.
- Ingest (`POST /api/track/fixes`) takes a device token issued from the race-control screen
  and a batch of fixes; a fix is `(tracker, t, lat, lon, sog, cog)`, unique per tracker and
  time, so a retried batch is idempotent. A wrong or expired token is refused.
- A spectator gets positions for a published event only; a draft event **and a published
  event in a draft series** answer 404 — the public router's predicate, reused (B-5).
- **Where fixes live is decided in this story, not deferred.** The free test instance bakes
  its SQLite file into the image and resets on every sleep and redeploy, so fixes written
  there are gone before a replay (L-3) is watched; SQLite's default journal mode takes an
  exclusive lock per ingest commit and would block the committee's result PUT. So: WAL and a
  busy timeout in `app/db.py`; for a deployment meant to keep a matchday, a persistent disk
  or Postgres plus an export of the day (`GET /api/races/{id}/track`), so a day never lives
  only in a container's filesystem. On the test instance fixes are **ephemeral by design**
  and the page says so.

What's done: `Tracker`/`Fix`, `POST /api/track/fixes` (token-gated, idempotent), WAL and a
busy timeout in `app/db.py`, `positions` frames inline on the stream, `GET
/api/events/{id}/live` (published only), the map page `/events/:id/live` (MapLibre on
OpenStreetMap, one rotated marker per boat with a minute of trail, follow mode). Still
open: the export of a day, the committee boat's tracker moving the line on the map.

Tests: `api/tests/stories/test_live_tracking.py::TestTrackersAndIngest`,
`api/tests/stories/test_live_tracking.py::TestTheLivePicture`,
`e2e/live-map.spec.ts::L-1/L-2: as a spectator I watch a simulated race on the map`

### L-2 ◐ Course, mark passings and a live ranking on the water
As a **spectator** I want to **see which leg each boat is on and who is ahead**, and as
**race committee** I want to **lay the course on the map with a few taps**,
so that **the live page tells a story rather than showing six dots**.

Acceptance criteria:
- **One course family first: windward/leeward with a leeward gate** (decision 7). Waypoints
  in order: `START` (line between committee boat and pin, **pin to port of the committee
  boat**), `WINDWARD` (one mark, rounded to port), then per further lap `GATE` (two marks,
  either one) and `WINDWARD` again, then `FINISH` (line between committee boat and pin,
  pin **left or right** — one flag). **The gate is rounded between laps, never on the way
  to the finish**: the league's course is start – W – G – W – finish (`laps = 2`, the
  default), and after the last windward mark the boats run straight down to the line; the
  second gate is not a mark of the course. Parameters: `laps`, finish upwind or downwind. Nothing else is modelled until real data
  asks for it. **The finish pin sits on the other side of the committee boat by default**
  (`finish_pin_side = "right"`, looking upwind): that is how most days are run, the finish
  line separate from the start line. `"left"` puts it through the start line — the
  combined mode — and the lay-course controls offer both.
- The race committee lays the course on the map: the committee boat follows its tracker
  (L-1), the pin and the marks are set by holding a phone next to them or by tapping the
  map. A re-lay creates a new course; races already started keep the one they were started
  with (WL-3 stamps it).
- The live page shows, per boat, the current leg, the gap to the boat ahead, and a rank;
  after a race the detected finish order prefills the race-control pad (WL-3) as a
  suggestion the committee confirms with one tap — the committee's word stays the result.
- **Geometry lives in a local tangent plane** (decision 8): one projection turns lat/lon
  into metres around the course centre and everything downstream is flat 2-D.
- **Distance to go is the projection onto the course axis** (decision 9): for a boat at `p`
  heading for waypoint `w` along unit vector `a`, `to_go = (w − p) · a`. Two boats on
  opposite tacks at the same height rank equal — the "distance to windward" a commentator
  means — and on a W/L course the axis from gate centre to windward mark *is* the wind axis,
  so no wind estimate is needed.
- **Ranking by time to go from a polar** (decision 10): remaining distance per leg divided
  by the polar's best VMG at the wind speed, summed. An upwind and a downwind boat become
  comparable in one number. Ranking depends on the polar's *shape*, not its speeds: scaling
  the polar by 1.2 must change no rank (unit test). The first polar is the ORC J/70 data in
  `api/app/tracking/polars/j70.csv`, in SAP's CSV shape so one loader reads their 49er and
  505 files too; the optimum angles and their speeds come from the `beat …`/`jibe …` rows —
  they must, because the beat angles lie below the table's first column.
- **Interfaces only where a second implementation is already known** (decision 11): a
  `Projection`, a `LegDistance` (axis projection, straight line; later wind- or
  polar-based), a `PassingDetector` (sequential course order; later the SAP candidate-graph
  port), a `Ranker` (time to go; leg then distance), a `WindSource` (course axis; manual;
  later estimated from tracks) and a `FixSource` (emulated, recorded, live). Pure functions
  over immutable inputs, no session, no ORM, so every one of them runs on a recorded track
  without a server. `RaceAnalysis` plus `default_pipeline()` is the one place concrete
  classes are named. Ingest, the hub and the map get **no** interface: one implementation
  each.
- **Mark passings need no candidate graph on this course family.** A line or gate is
  passed when the track segment crosses it in the leg's direction; the windward mark when
  the distance has a local minimum below about three boat lengths *and* the bearing from
  mark to boat sweeps through a port rounding's arc. A passing counts only if it is the
  **next expected waypoint** — the course order does the disambiguation SAP's Dijkstra does
  for arbitrary courses. If real data breaks this, the port of SAP's `CandidateFinder` /
  `CandidateChooser` (about a thousand lines of Python) is the fallback, not the start.
- **Derived, never stored** (decision 12): leg per boat, passing times, distance and time
  to go, rank. The same rule as points.
- **Contract test for every implementation:** against the emulator's ground truth, passings
  within ±3 s and a rank order that does not change when the boats' start order is permuted.
  A new implementation is admitted when it passes the same suite; `compare.py` runs several
  against one recorded track so an algorithm change is decided on data, not argued.
- **The tuned constants are settings**, not literals: `app/tracking/settings.py`
  (`SBL_TRACKING_*`) holds the mark radius, the line and gate margins, the default course
  sizes, the default wind and the emulator's noise — every one will be re-tuned on the
  first real tracks, and the same field list is what a committee's screen would edit once
  they move to the UI.
- **The map draws the class at its true size and the zone around the marks.** The live
  picture carries `boat_length_m` (7 m, the J/70's 6.93 called seven), `boat_beam_m` and
  `zone_radius_m` (three hull lengths, RRS 18); the map draws each hull as a polygon of
  that size, bow on its course over ground, from the zoom where a hull is about ten pixels
  long — below that an arrow marker carries the boat — and a dashed circle of the zone's
  radius around every mark boats round or finish at. Not around the start line's ends:
  rule 18 does not apply at a starting mark, and the committee boat gets a zone only when
  it is also the finish line's end. The numbers come from the server's settings, so the map
  hard-codes no class; the "no course yet" and "no boat yet" notices sit on the map, not in
  the side panel.
- **What a tactician draws** (`app/tracking/tactics.py`, derived, never stored): **laylines**
  from the windward mark down at the polar's best upwind angle either side of the wind,
  and from each gate mark up at its best downwind angle — the wind being the course axis
  until a wind source exists — and the **leader's line** through the leading boat square
  to its leg's axis, everything behind it being behind in distance to windward. Nothing
  joins the gate marks and no leg line is drawn. The panel shows the leg as **`2/4`**
  (the leg being sailed of the legs between the waypoints — start – W – G – W – finish is
  four; a finished boat reads just `finished`, no time), and one **to go / gap** column: the leader's metres to its next mark, every other
  boat as `+XX m` behind the leader in axis metres (`to_leader_m`, from
  `ranking.metres_to_go`, whole legs counting more than any distance within one). The
  race line names the wind direction.
- **Positions are estimated between fixes, the way SAP Sailing Analytics does it.** A
  marker that jumps to every fix is a slide show; the map draws each boat on every
  animation frame at *now − 1.5 s* on the server's clock, interpolated between the fixes it
  has (position linearly, heading along the shorter arc), and dead-reckons along course
  and speed for at most three seconds when the stream is late — then the boat stops rather
  than sailing off on a guess. The leader's line is shifted with its boat so it never runs
  ahead of it.

What's done: the whole analysis (`app/tracking/`: geometry, polar loader, W/L course,
sequential detector with the fix's own course over ground for direction, axis distance,
time-to-go ranking, `default_pipeline`), `Course`/`Mark` with `Race.course_id` stamped at
the start, the default course laid around the venue (`POST …/course/default`, also from
the map page), the live rank, leg and distance to go in the picture and the panel, the
detected finish order, hulls at true size and the three-length zones on the map, laylines
and the leader's line, the gap column, smooth positions between fixes. Still open: laying the course mark by mark on the map, the detected
order prefilling the race-control pad, `compare.py`, the SAP oracle.

Tests: `api/tests/unit/test_tracking_geo.py`, `api/tests/unit/test_polar.py`,
`api/tests/unit/test_tracking_contract.py`, `api/tests/unit/test_tactics.py`,
`api/tests/stories/test_live_tracking.py::TestLayingTheCourse`,
`api/tests/stories/test_live_tracking.py::TestTheLivePicture::test_the_picture_carries_hull_size_and_zone`,
`api/tests/stories/test_live_tracking.py::TestAWholeRaceSimulated`

### L-4 ◐ The phone on the boat is the tracker
As the **crew of boat 3** I want to **open one page on the phone in the cockpit and forget
about it**,
so that **the boat is on the map all day without any app to install**.

Acceptance criteria:
- `/track/:token` — the token is issued per boat from the race-control screen and shown as
  a QR code; the page requests a wake lock, watches the position, buffers fixes and posts a
  batch every ~5 s to the ingest endpoint (L-1), retrying while there is no coverage.
- It shows the boat's colour and name, the last fix's age, and the buffer size, so a crew
  can tell at a glance it is working.
- **The one open question is answered on the water, not on paper:** whether a browser page
  keeps delivering positions with a locked screen in a pocket. One morning with two phones
  decides whether a web page suffices or the boats need a native shell; L-2's shape may
  change with that result, which is why this story comes before L-3.
- The emulator is a client of the same ingest path (decision 13): it exercises the path
  real phones use, tacks with the polar's angles and speeds, picks a gate side at random,
  adds GPS noise, sails on past the finish as a real boat does, and is deterministic by
  seed. `POST /api/dev/emulate` (development only) runs it against a live event: it lays
  the default course if none is laid, issues trackers, starts the current race, streams
  the fixes, enters the finish order as the result and finishes the race — the whole race
  on the map, which was the goal set on 2026-09-15.

What's done: the emulator and the emulation job. Still open: the phone page itself and the
on-water morning that decides whether a web page suffices.

Tests: `api/tests/unit/test_tracking_contract.py`,
`api/tests/stories/test_live_tracking.py::TestAWholeRaceSimulated`

### L-3 ○ Replay a race
As a **spectator** I want to **scrub through a race that is over**,
so that I **can see how the leader got there**.

Acceptance criteria:
- A slider over the stored fixes of a race; the same map, markers and side panel as L-1 and
  L-2, fed from `GET /api/races/{id}/track` instead of the stream. Nothing new on the
  server.
- Scrubbing to a passing time puts the boat at the mark (e2e).
- On the test instance the replay says the day's fixes are ephemeral (L-1).

Tests: none yet
