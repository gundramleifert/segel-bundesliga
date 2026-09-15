# Live data on the site — implementation plan

Status: **phases 0–2 built** (stories, SSE transport, race control — 2026-09-15); the map,
the emulator and the analytics are next, as one goal (§9). Written 2026-09-14 from a review of the code, of
`reference/sailing-analytics`, and of the decisions taken in discussion. Everything marked
*verified* was read in the code or measured; everything marked *assumption* has to be
confirmed by the step named next to it.

Stories come first (`CLAUDE.md`, "How to update the docs"): this file is the plan the
stories are written *from*. Once a story exists, that story is the truth and this file only
says why the order is what it is.

---

## 1. Where we stand (verified 2026-09-14)

| Piece | State |
|---|---|
| Result entry | ✅ `PUT /api/admin/events/{id}/races/{race_id}/result` → `recompute_event` (`app/routers/admin.py`) |
| Daily standings | ✅ `GET /api/events/{id}` recomputes on every read |
| Season standings incl. the running day | ✅ `SCORED_STATES` already contains `LIVE` |
| Pairing list with per-race status | ✅ `PairingRow.status` |
| Background work in-process | ✅ `app/jobs.py` — the pattern to copy, cost already stated there |
| **Any push mechanism** | ❌ none: no SSE, no WebSocket, no `refetchInterval` anywhere in `api/` or `web/` |
| **"Which race is running"** | ❌ `RaceStatus.RUNNING` and `Race.started_at` exist and **nothing sets them** — result entry jumps `scheduled → finished` |
| GPS, courses, marks, map | ❌ nothing; `Venue.lat/lon` exist (nullable); no map library in `web/package.json` |

So of Story B-5's three views, two (live daily and live season standings) are transport
work — the numbers are already right the moment someone reloads. The third ("which race is
running") is a one-endpoint gap in race control, not a live-data gap.

Deployment shape that matters (`render.yaml`, `api/Dockerfile`): one uvicorn process; the
site is a **static site with a `/api/*` rewrite** to the API service; free instances sleep
after 15 min idle.

---

## 2. Make or buy — SAP Sailing Analytics

"Live data" is three layers with three different answers.

| Layer | What it is | Decision |
|---|---|---|
| **1. Live results & standings** | race finished → tables update everywhere | **Make.** The truth is `RaceEntry`; SAP would only ever hold a copy of our own numbers. |
| **2. Positions on a map** | where are the six boats, replay afterwards | **Make, small.** Our ingest, our store, our map. Forward to SAP *if configured*, like `renderer_available()` — an optional sink, never a dependency. |
| **3. Race analytics** | legs, live rank, mark roundings, wind, VMG | **Port the one-design subset; do not self-host.** Details in §2.2. |

### 2.1 Facts about the SAP system (verified)

- **License:** Apache 2.0. Upstream is Eclipse Azimuth; `SAP/sailing-analytics` is the
  branded downstream with the same history. The **ATTRIBUTION/BRANDING** clause is in the
  *API documentation* of both — it governs use of their API, not a port of their code. A
  port carries an Apache NOTICE line and nothing else.
- **Maintained, by one person.** Last push 2026-09-14, ~25 commits in the preceding week,
  nearly all by a single maintainer; two others appear once each. Not abandoned — bus
  factor 1. That is a risk for *self-hosting* (2 GB Java/GWT/OSGi/MongoDB), not for a port.
- **Self-hosting cost:** Java app + MongoDB + RabbitMQ; SAP's own sizing for exactly our
  case ("national sailing league, six boats, 18 competitors, one live leaderboard") is
  **8 GB RAM, 4–8 CPUs**. The race viewer needs a **Google Maps API key** (an OSM viewer is
  listed as a wanted contribution). Results go in only as XRR/CSV document import.
- **Their `simulator` module is not a GPS emitter.** It is a routing/strategy simulator
  (49er polars on a wind grid, "Omniscient / Opportunistic / 1-Turner" paths) behind a GWT
  UI. Not reusable for us.
- **They ship one real recorded dataset:** `java/com.sap.sailing.domain.test/resources/`
  `MoevensteinCompetitorPositions.json.gz` + `MoevensteinMarkPositions.json.gz`
  (Travemünde). Real tracks with real mark positions, Apache 2.0 — our second data stage.
- **They ship polar files** in their CSV shape (`PolarDiagram49*.csv`, `PolarDiagram505STG.csv`)
  — test fixtures for our polar loader. **No J/70 polar.**
- `java/com.sap.sailing.manage2sail/` contains a working **manage2sail results parser** —
  a reference for Story VA-1 later.

### 2.2 The port, sized (sizes from the GitHub API, classes read raw)

| Package | Size | What it does | Port? |
|---|---|---|---|
| `tracking/impl` + interfaces | 1.5 MB, ~165 files (`TrackedRaceImpl` alone 246 KB) | tracked race/leg/competitor model, caches, listeners, sensors, replication | **No** — framework; we have our own model |
| `markpassingcalculation/impl` | 310 KB, 13 files | `CandidateFinderImpl` (~2,000 lines): candidates from distance minima + cross-track-error line crossings, probabilistic scoring. `CandidateChooserImpl` (~1,200 lines): DAG over candidates, Dijkstra for the most probable sequence. **No wind dependency; pure geometry + timing.** | **Later, as fallback** (§5) |
| `maneuverdetection/impl` | 229 KB | tack/gybe detection from course curves | only if we want estimated wind |
| wind estimation | ~650 lines + 12 KB | kinematic, from maneuvers, 1 s cache | later or never — the RC can type the wind in |
| `ranking` | 110 KB | ORC/time-on-time handicaps; `OneDesignRankingMetric` 10 KB | the 10 KB |

≈ 50k lines of Java in total; **~12k are relevant to a one-design league and compress to
~3–4k lines of Python.** Writing that is days with an agent. What the agent does not
shorten: knowing the result is *right*. Mark-passing detection carries half a dozen tuned
constants (`STRICTNESS_OF_DISTANCE_BASED_PROBABILITY = 10`,
`PENALTY_FOR_WRONG_DIRECTION = 0.7`, …) validated on thousands of races; we get four
matchdays a year. Hence **§2.3**.

### 2.3 SAP as an oracle, never a runtime

Run SAP's `docker compose up` **once, locally**, feed it recorded tracks, read its mark
passings and legs back through the v1 API, and assert our implementation matches. This is
the pattern `api/tests/unit/test_pairing_generator_jar.py` already uses against the Java
pairing tool. Recorded outputs go to `api/tests/fixtures/` (rule: external systems are never
called live in tests).

---

## 3. Architecture decisions

Numbered so stories can cite them.

1. **SSE, not WebSocket.** Traffic is one-directional; the only client→server message would
   be "subscribe to event 12", and that is a URL. `EventSource` reconnects by itself with
   `Last-Event-ID`, rides the existing CORS/proxy path as plain HTTP, and needs no bearer
   token — which matters, because `EventSource` *cannot* set headers, and live spectator
   data is public anyway (Story B-6). **B-5's "WebSocket with SSE as fallback" and the
   original plan's Phase 5 are corrected by this.** Fallback is *polling* (`refetchInterval`
   ≈ 20 s) after repeated connect failures.
2. **The stream carries a version token, not the payload — except positions.**
   `event: change · data: {"topic":"event:12","version":37}` → the browser invalidates the
   TanStack key and refetches through the generated client. Shipping standings down the
   socket would be a second serialization of the same table that can disagree with the
   first, bypassing every error/i18n/cache path the pages have. Positions are the one
   exception: six boats at 1 Hz is exactly where a refetch per tick would be absurd, so a
   `positions` frame carries them inline.
3. **Publish after commit, never inside the transaction.** A subscriber that refetches while
   the writer's transaction is open reads the *old* standings and stops updating until the
   next race. (This is the single trap in the whole feature; it will become a gotcha if
   anyone forgets it.)
4. **Fan-out in-process**, `api/app/live.py`, a `Hub` of `topic → set[asyncio.Queue]`, with
   the same stated cost as `app/jobs.py`: one uvicorn process. When there are two workers,
   that file is where Redis pub/sub or Postgres `LISTEN/NOTIFY` goes. Bounded queues,
   drop-oldest, heartbeat comment every ~15 s (proxies kill idle streams).
5. **The tracker belongs to the boat, not the team.** One phone per boat of the event
   (`Event.boat_count` of them); who sails boat 3 in race 17 is what `RaceEntry` already says. This is the biggest
   simplification versus SAP's competitor↔device mapping, and it is only available
   because the pairing list is ours.
6. **The committee boat is a tracker too.** Its phone position *is* the boat end of the
   start and finish lines. The pin and marks are pinged once by a phone held next to them,
   or tapped on the map. Nobody types coordinates on the water.
7. **One course family first: windward/leeward with a leeward gate.** Waypoints in order:
   `START` (line: committee boat + pin, **pin to port of the committee boat**), `WINDWARD`
   (single mark, port rounding), `GATE` (two marks, either), repeated per lap, `FINISH`
   (line: committee boat + pin, pin **left or right** — one flag). Parameters: `laps`,
   finish upwind or downwind. Nothing else is modelled until real data asks for it.
8. **Geometry in a local tangent plane.** One `Projection` turns lat/lon into metres around
   the course centre; everything downstream is flat 2-D. Exact to centimetres at 2 km;
   haversine everywhere would be the mistake.
9. **Distance to go by axis projection.** For a boat at `p` on a leg toward waypoint `w`
   along the course axis unit vector `a`: `to_go = (w − p) · a`. Upwind, a boat on port and
   one on starboard at the same height rank equal — exactly the "distance to windward" a
   commentator means. On a W/L course the axis (gate centre → windward mark) *is* the wind
   axis, so this needs **no wind estimate**. Straight-line distance stays as its own
   implementation (better on the last hundred metres to a mark).
10. **Ranking by time to go, from a polar.** `time_to_go = Σ to_go_leg / vmg_optimal(tws)`
    over the remaining legs makes an upwind boat and a downwind boat comparable in one
    number. Ranking depends on the polar's *shape*, not its absolute speeds — scaling the
    polar by 1.2 must not change any rank (unit test).
11. **Interfaces only where a second implementation is already known** (§5). Pure
    functions over immutable inputs, no session, no ORM — swappable *and* runnable on a
    recorded track without a server. No interface for ingest, the hub or the map: one
    implementation each, and an abstraction with one implementation is what "keep it small"
    is about.
12. **Derived, never stored:** leg per boat, passing times, distance and time to go, rank.
    Same rule as points.
13. **The emulator is a client of the real ingest endpoint.** It exercises the path real
    phones will use, and it knows its own ground truth (it decides when it rounds), which
    makes it the contract test for every detector and distance implementation.
14. **Race control is a page, not a Matchday tab.** On the water it has to be full-screen,
    one race at a time, big targets; it must not share a screen with three tables. The
    results tab stays the *correction* screen (a protest weeks later).

---

## 4. Data model (additions only)

| Table | Fields | Note |
|---|---|---|
| `Race` | + `finished_at`, + `course_id` (nullable), + `signal` (nullable: `AP`, `X`, `S`), + `preparatory` (`P` default, `I`, `Z`, `U`, `BLACK`) | `started_at` exists and is never set — WL-3 sets both. `course_id` is stamped at **start** with the event's active course, which is what "old races keep theirs" means in the model. `signal` is the flag currently displayed, cleared when hauled down; `preparatory` decides which code an OCS tap produces (`OCS`/`ZFP`/`UFD`/`BFD`) |
| `Course` | `event_id`, `laps`, `finish_upwind`, `finish_pin_side`, `created_at` | one active per event (the newest); a re-lay creates a new row, races already started keep their `course_id` |
| `Mark` | `course_id`, `role` (`committee_boat`, `start_pin`, `windward`, `gate_left`, `gate_right`, `finish_pin`), `lat`, `lon`, `set_at` | the committee boat's position is also updated from its tracker |
| `Tracker` | `event_id`, `boat_id` **or** `mark_role`, `device_token`, `active_from`, `active_to` | device→boat mapping; token issued from the RC screen |
| `Fix` | `tracker_id`, `t`, `lat`, `lon`, `sog`, `cog` | ~170k rows per matchday; unique `(tracker_id, t)` makes ingest idempotent |

**Where fixes live is a decision phase A has to take, not defer.** The test deployment
bakes its SQLite file into the image and **resets it on every sleep and redeploy**
(`render.yaml`, `docs/deploy.md`) — fixes written there are gone before the replay is
watched. And SQLite's default `journal_mode=DELETE` takes an exclusive lock per ingest
commit, which would block the RC's result PUT and every spectator GET. So, in phase A:
`PRAGMA journal_mode=WAL` + `busy_timeout` in `app/db.py` for development; for any
deployment that is meant to keep a matchday, either a persistent disk or Postgres, and an
export-after-the-day (`GET /api/races/{id}/track` → file) so a day is never only in a
container filesystem. On the free test instance fixes are **ephemeral by design**, and the
page says so. Retention beyond that is a later decision. Postgres-specific types stay out
(`CLAUDE.md`). One initial migration, regenerated, as always.

---

## 5. Modules and interfaces

```
api/app/live.py               SSE hub; the one topic is event:{id} — live is an event, a series only has one that is
api/app/tracking/
  ingest.py                   POST /api/track/fixes — device token, batch, idempotent
  geo.py                      Projection: LocalTangentPlane; segment crossing, side of line
  course.py                   Course + Marks → list[Waypoint] for the W/L family
  passings.py                 PassingDetector implementations
  distance.py                 LegDistance implementations
  ranking.py                  Ranker implementations
  wind.py                     WindSource implementations
  polar.py                    Polar: SAP CSV loader, interpolation, fit from tracks
  analysis.py                 RaceAnalysis(projection, distance, detector, ranker, wind)
                              + default_pipeline() — the ONE place concrete classes are named
  emulate.py                  python -m app.tracking.emulate --event 12 --race 5 --speed 10
  compare.py                  python -m app.tracking.compare --track f.json --distance axis,straight
web/src/api/useLive.ts        useLive(topic, keys) → "live" | "reconnecting" | "off"
web/src/pages/RaceControl.tsx /events/:id/race-control          (WL-3)
web/src/pages/Live.tsx        /events/:id/live — MapLibre GL, OSM tiles   (L-1…L-3)
web/src/pages/Track.tsx       /track/:token — the phone page             (L-4)
web/src/components/FinishOrderPad.tsx   extracted from RaceResultRow, used by both screens
```

The `Protocol`s, with the implementations known today (default first):

```python
class Projection(Protocol):
    def to_xy(self, lat: float, lon: float) -> XY: ...
    def to_geo(self, xy: XY) -> tuple[float, float]: ...
# LocalTangentPlane(origin)

class LegDistance(Protocol):
    def to_go(self, boat: XY, leg: Leg) -> float: ...
# AxisProjectionDistance · StraightLineDistance · later WindProjectionDistance(wind), PolarVmgDistance(polar)

class PassingDetector(Protocol):
    def update(self, track: Track, course: Course, so_far: list[Passing]) -> list[Passing]: ...
# SequentialCourseDetector · later CandidateGraphDetector (the SAP port) · SapOracleDetector (tests only)

class Ranker(Protocol):
    def rank(self, boats: list[BoatState]) -> list[Ranked]: ...
# ByTimeToGo(polar) · ByLegThenDistance

class WindSource(Protocol):
    def wind_at(self, t: datetime) -> Wind | None: ...
# CourseAxisWind (from the marks) · ManualWind (RC types it) · later TrackEstimatedWind

class FixSource(Protocol):
    def fixes(self) -> AsyncIterator[Fix]: ...
# EmulatedRace(seed, polar, wind) · RecordedTrack(path) · IngestQueue (the live one)

@dataclass(frozen=True)
class Polar:
    def speed(self, tws: float, twa: float) -> float: ...
    def best_upwind(self, tws: float) -> tuple[float, float]: ...    # (twa, vmg)
    def best_downwind(self, tws: float) -> tuple[float, float]: ...
```

**Mark passings for the W/L family** (`SequentialCourseDetector`) need no candidate graph:

- Start / finish / gate: the track segment crosses the line (side-of-line sign flips) and
  the heading component along the course axis is positive in the leg's direction.
- Windward mark: a local minimum of distance below ~3 boat lengths *and* the bearing from
  mark to boat sweeps through the arc a port rounding produces.
- A passing counts only if it is the **next expected waypoint** — the course order does the
  disambiguation SAP's Dijkstra does for arbitrary courses. If real data breaks this, the
  port of `CandidateFinder`/`Chooser` (~1,000 lines of Python) is the fallback, not the
  start.

**Contract test for every implementation:** run against `EmulatedRace` ground truth —
passings within ±3 s, rank order stable under permutation of the boats' start order. A new
implementation is admitted when it passes the same suite; `compare.py` runs several against
one recorded track so an algorithm change is *decided on data*, not argued.

### Polar

- Loader reads SAP's CSV shape (`wind speed` header row, `beat angles`/`beat sog`,
  `jibe angles`/`jibe sog`, SOG rows per TWA). Their 49er and 505 files become fixtures in
  `api/tests/fixtures/polars/`.
- **J/70 polar: `api/tests/fixtures/polars/j70.csv`** — ORC rated velocities (4–24 kt TWS,
  52°–150° TWA, beat/run VMG and angles), provided 2026-09-14, written in the SAP CSV shape.
  The `beat sog` / `jibe sog` rows are **derived** (`vmg / cos(angle)`) and say so in the
  file; the ORC rows are verbatim; row names follow SAP's spelling (`jibe angles`,
  `jibe sog`) so one loader reads both. Loader rule: the optimal angles **and their
  speeds** come from the `beat …`/`jibe …` rows — they *must*, because every beat angle
  (37.6°–45.8°) lies below the table's first TWA column (52°) and the 10/12 kt gybe angles
  (151.6°) lie above its last (150°); the TWA table serves every other angle. Known
  wrinkle: at 24 kt the rated run VMG (12.43) matches the 150° row, not the stated gybe
  angle (145.6°) — ORC rounds its optimum rows independently of the table; the derived SOG
  is consistent with the VMG, which is what `ByTimeToGo` uses, so the wrinkle is cosmetic
  there and a unit test pins it. Second source later: `fit_polar` from our own tracks
  plus a wind (manual or estimated) after the first matchdays — the league's *own* boats,
  sails and crews, which no certificate gives.
- Uses: emulator tacking angles and speeds (`best_upwind(tws)` instead of hard-coded
  45°/150°), `ByTimeToGo`, "% of polar" per boat for spectators, and later
  `TrackEstimatedWind` (observed SOG + heading against the polar constrains TWA).

---

## 6. Live transport

- `GET /api/live?topic=event:12` (public router; **404 for a draft** — and "draft" is the
  public router's own predicate `_only_public_events` (`Event.published` **and** the series
  not a draft), reused, never restated per endpoint). **Live is an event**: `event:{id}` is
  the only topic — a series is never live, it has an event that is, and the series table
  page listens on that event (or the next planned one, so it hears the start) and
  refetches its own table. Frames: `change {topic, version}`, `positions {race, t,
  boats:[…]}`, heartbeat comment every 15 s, `retry:` set.
- Publishers: `put_race_result` (after commit), **all six** event transitions in
  `routers/events.py` (`publish`/`unpublish` included — they change who may see the event,
  which is a change a live page must hear), WL-3's race transitions, the pairing draw;
  positions from ingest.
- `useLive(topic, keys)`: `EventSource` → `invalidate(...keys)` on `change` — spread, because
  `useInvalidate()` is variadic and an array passed as one target matches no query and
  invalidates nothing, silently (its own doc comment warns about that); exposes
  `"live" | "reconnecting" | "off"`; after N failed connects switches the given queries to
  `refetchInterval: 20_000`. The last table stays on screen while reconnecting — B-5's
  "never present stale data as current" is a badge, not an empty page; TanStack keeps `data`.
- **Verify before trusting it in production:** the static site's `/api/*` rewrite may
  *buffer* a streaming response and SSE would then never deliver. Cheap answers in order:
  test it; if buffered, point the stream at the API origin directly (no token needed, CORS
  suffices); the polling fallback covers it regardless. An open stream also keeps a free
  instance awake (good for testing, costs instance hours).
- `GET /api/live/now` → the running event, else the next one, so `/live` redirects instead
  of showing an empty table (B-5's fourth criterion).

---

## 7. WL-3 — Race control page

**Route:** `/events/:id/race-control`, gated to `admin` / `race_officer`
(`useAccount().hasRole`, as the results tab). Linked from the manage screen and the results
tab.

**One race on screen — the current one:** the first race that is neither `finished` nor
`abandoned`, the rule `ResultsEntry.stillOpen` already encodes. Header `Race 17 · Flight 6
of {flight_count}`, progress bar `done / (flight_count × races_per_flight)` (WL-1:
"progress is visible at any time"). Arrows reach the previous (correct) and the next
(preview) race, nothing further. Everything sized by the event: `Event.boat_count` boats,
`ceil(team_count / boat_count)` races per flight — a guest club's four-boat event must
work here exactly like a league day (`CLAUDE.md`: the Event defines the configuration).

| Status | On screen | Buttons |
|---|---|---|
| `scheduled` | the event's boats in their colours, each with the team the pairing puts on it; **AP** badge while postponed | **Start** (gun went now) · **Start sequence** (asks for the preparatory flag P/I/Z/U/black, 5-4-1-0 per RRS 26, fires Start at 0) · **AP** (postpone; cancels the sequence, hauling down starts a one-minute count to the warning signal) |
| `running` | elapsed clock; one chip per boat as a finish pad — tap in finish order, tap again to undo; codes (OCS, DNF, DSQ, RDG…) one tap below; **X**/**S** badge while displayed | **X** (individual recall: tap the boats over the line → the code the preparatory flag prescribes, `OCS` clearable under P/I) · **General recall** (First Substitute → `scheduled`, `started_at` cleared, audit row) · **Abandon → resail** (N, same reset) · **Abandon → no resail** (`abandoned`, unscored) · **Shorten** (S) · **Finish** — enabled once every boat has a position or a code |

Signals are two kinds (Story WL-3): **transitions** (gun, First Substitute, N) are the
endpoints below; **displayed signals** (AP, X, S) are state on the race — `Race.signal`,
one at a time, `POST …/races/{race_id}/signal {signal | null}`, AP only while `scheduled`,
X and S only while `running` — plus an audit row per hoist. AP/N over A or H are the day's
signals and map to VA-10, not to race state.
| `finished` | the result, read-only, two seconds, then the next race slides in | **Correct** → that row in the results tab |

- **One race-state service, `app/services/race_state.py`, owns all five transitions** —
  start, recall, abandon (both kinds), finish — and the result PUT calls it too. Today
  `put_race_result` sets `FINISHED` with **no status check**, and neither
  `services/standings.py` nor `scoring/low_point.py` ever reads `Race.status`: a race is
  scored the moment its entries carry codes, whatever its status says. Left as is, WL-3's
  state machine would be advisory: race 18 could be finished from the results tab while
  race 17 is `running` (with `started_at = NULL`), and an abandoned race would keep
  scoring. So: (a) the PUT refuses to finish a race while another is `running`
  (`race-already-running`) and a race that is `abandoned`; (b) **recall and abandon clear
  the race's entries** (code, position, redress) *before* recomputing — that is what makes
  "unscored" true, not the status; (c) the correction path stays: a `finished` race may be
  edited at any time, which is the protest case.
- **Finish** is that service's fifth transition, reached through the existing `PUT …/result`
  (which already recomputes) plus `finished_at`. Scoring does not move; the truth stays
  `RaceEntry`.
- **The freeze needs a monotonic signal.** `configuration_frozen`
  (`services/event_readiness.py`) counts `Race.status != scheduled` and recorded codes —
  both of which a general recall of the first race undoes, un-freezing the event with the
  fleet on the water. Every transition writes an `AuditLog` row anyway; the freeze predicate
  counts those too, and a recalled race stays a race that *has started once*.
- **Event gate, reused:** event `planned` → one button, **Start matchday**, calling the
  existing `POST /start` (VA-8 readiness applies). `final`/`cancelled` → the state and a link
  to VA-10's reopen. The page invents no state of its own.
- **Endpoints** (all publish to `race:{id}` and `event:{id}`):
  `POST …/races/{race_id}/start` (`scheduled → running`, `started_at`),
  `POST …/recall` (`running → scheduled`, audit row),
  `POST …/abandon?resail=` (`running → scheduled | abandoned`),
  `POST …/signal` (`{signal: "AP" | "X" | "S" | null}`, sets `Race.signal`).
  Problems: `race-already-running` (races run strictly one at a time), `race-not-running`,
  `race-not-scheduled` (AP on a running race), `event-not-live`.
- **Wet hands:** chips ≥ 64 px, no dropdowns on the main path. Finish order mirrored to
  `localStorage` per race id so a reload or a dropped connection does not lose the taps —
  *not* WL-1's offline sync (still open), but it removes the likeliest way to lose a race.
- **Shared component:** the tap-to-finish chips in `RaceResultRow` move to
  `components/FinishOrderPad.tsx`, used by both screens.
- **Tracking joins later (phase B):** the running view gains the map thumbnail and the
  *detected* finish order as a suggestion the RC confirms with one tap.

---

## 8. Data stages for tracking

1. **Emulated** — `EmulatedRace(seed, polar, wind)`: J/70 polar (placeholder until the ORC
   data arrives), tacks on laylines with a random offset, random gate choice, ±5 m GPS
   noise, deterministic by seed. Posts through the real ingest endpoint (§3.13).
2. **Recorded, foreign** — the Mövenstein dataset from SAP (§2.1): real tracks, real mark
   positions; loader `RecordedTrack`.
3. **Recorded, ours** — the first matchday with phones on the boats. From here on the
   fixtures, the fitted polar and the tuned constants are the league's own.

---

## 9. Phases, in order

Each phase ends green in `scripts/check.sh` and is pushed on its own.

**The goal set on 2026-09-15, after phases 0–2: simulate a whole race on a real map.** A
short W/L course laid on the map, the start, the boats running the course with position
*and heading* and speed, the marks, a live result while they sail, the finish detected,
and the next race up — all driven by the emulator, all on a real map. That is phases A
and B below pulled into one target and demonstrated end to end before any phone goes on
a boat; D (real phones) and C (replay) follow it. Phase 2 is what its "start" and "next
race" steps stand on.

| # | Phase | Delivers | Proof |
|---|---|---|---|
| 0 | **Stories** | B-5 rewritten (§3.1–3.4); **WL-3** race control; **L-1** see boats live; **L-2** course, passings, live rank; **L-3** replay; **L-4** phone tracker. `docs/findings.md` §3 gets the make/buy result; `CLAUDE.md` gets the domain rules that outlive the stories | `check-docs.py` |
| 1 | **Transport** | `live.py`, `GET /api/live`, publishers in result entry and event transitions, `useLive`, badge + polling fallback on Matchday and Standings | Hub unit test (two subscribers, slow one dropped); story test streaming over the ASGI transport; **e2e: one context enters a result, a second context's standings change without a reload** — this is also B-5's proof |
| 2 | **WL-3 race control** | §7 in full: `race_state.py`, the guarded PUT, entries cleared on recall/abandon, the monotonic freeze, `started_at`/`finished_at`; `FinishOrderPad` extracted | story tests for start/recall/abandon incl. refusals; **an abandoned race scores nothing; a recalled first race leaves the event frozen**; e2e start → tap every boat → finish → next race is current |
| A | **See boats move** | **storage decision (§4)** + WAL pragma; `Fix`/`Tracker`, ingest, `positions` frames, emulator, `/events/:id/live` with one coloured marker per boat, 60 s trails, follow mode | ingest idempotency and token refusal; spectator gets positions for a published event, 404 for a draft *and* for a published event in a draft series; e2e with the emulator running: the markers move |
| B | **Course and live standings on the water** | `Course`/`Mark`, RC lays the course on the map (committee boat follows its tracker), `passings`, `distance`, `ranking`, `polar`, side panel (leg, gaps, rank), detected finish order prefills WL-3's pad | contract suite against emulator ground truth; polar scale-invariance; property test: permuting start order changes no passing |
| D | **Real phones** | `/track/:token`: wake lock, `watchPosition`, buffer, batch every 5 s, retry. **The one-morning on-water test** with two phones and locked screens | the test itself — its result decides whether a web page suffices or the boats need a native shell |
| C | **Replay** | slider over stored fixes, same components fed from `GET /api/races/{id}/track`; nothing new on the server | e2e: scrub to a passing time, the boat is at the mark |
| E | **Oracle** (optional, before trusting B on real data) | SAP compose once locally, Mövenstein through both, `SapOracleDetector` recorded to fixtures | agreement within tolerance, or a documented reason |

**D before C** because D's result can change B's shape and C is pure UI. **Phase 2 before
A** because every later live feature reads `started_at`/`finished_at`, and it gives B-5 its
"which race is running" data source; it is a day's work.

Later, separate: SAP as an optional *sink* for positions (`gps_fixes`, our backend as the
gatekeeper — the endpoint has no auth of its own); manage2sail import (VA-1) with SAP's
parser as reference; wind estimation.

---

## 10. Risks, open items, and who resolves them

| Item | Status | Resolution |
|---|---|---|
| Static-site rewrite buffers SSE | *assumption* | test in phase 1; fallback described in §6 |
| Phone background GPS with a locked screen | *unknown, biggest one* | phase D's on-water morning |
| J/70 polar | ✅ ORC data in `api/tests/fixtures/polars/j70.csv` | `fit_polar` from own tracks later, for the league's real boats |
| SAP branding clause on a self-hosted instance | verified present in both repos' API docs | irrelevant to a port; only matters if SAP ever becomes a runtime source |
| SAP bus factor 1 | verified | reason not to self-host; no effect on the port or the oracle |
| Fixes on the test deployment vanish on sleep/redeploy; SQLite exclusive locks on ingest | verified (`render.yaml`, `app/db.py` has no pragmas) | phase A storage decision, §4 |
| Race status is advisory today (no guard in the PUT, never read by scoring); recall un-freezes the event | verified (`admin.py`, `standings.py`, `event_readiness.py`) | WL-3's `race_state.py`, §7 |
| `compute_event` runs on every GET | verified | fine for a league day's size; measure before caching |
| Single uvicorn process | verified | `live.py` states the cost like `jobs.py`; LISTEN/NOTIFY when it changes |

---

## 11. Documentation that changes with this plan

- `docs/userstories.md`: B-5 rewritten; WL-3, L-1…L-4 added; WL-1 loses "start a race" to
  WL-3 and keeps offline sync.
- `CLAUDE.md`, Domain decisions: SSE with version tokens and the after-commit rule; tracker
  belongs to the boat; committee boat is a tracker; W/L course family; derived-never-stored
  for legs and ranks; SAP as oracle only.
- `docs/findings.md` §3: the make/buy result, the sizing, the Mövenstein and polar fixtures,
  the manage2sail parser pointer.
- `~/.claude/plans/iterative-jingling-willow.md` Phase 5: superseded by this file.
- `docs/gotchas/`: written when — not if — the after-commit rule or the SSE buffering bites.
