# Research Findings

Sources and decision bases so they do not need to be reworked. 
As of 29.08.2026. Each entry names its source — assumptions are marked as such.

---

## 1. League Format

Documented via [Lindauer Segler-Club](https://www.lsc.de/info-4-wissenswertes-ueber-den-ablauf-eines-segelbundesliga-events/)
and [Deutsche Segel-Liga](https://deutsche-segelliga.de/wettbewerbe/1-liga/):

- 18 Teams, 6 identical J/70s, four-person crews, fleet racing.
- One **Flight** = 3 Races with 6 boats; each of the 18 Teams races once.
- Goal: **16 Flights = 48 Races** per Matchday, boat changes between Flights.
- The **Pairing list** (Team → Boat → Race) is drawn at the latest one week beforehand.

**OPEN — and not verifiable anywhere:** How the season standings emerge from the Matchdays. 
We currently calculate with *Sum of Matchday placements* (`app/services/standings.py`, marked 
there as ASSUMPTION).

The legacy project `reference/segel-bundesliga` provides **no answer** to this: it contains 
no scoring logic whatsoever, provably via full-text search across all sources — no points, 
no rankings, no penalty codes, no relegation/promotion. At its core it is a Pairing generator 
with a small CMS. The answer must come from the **League regulations or Racing rules** of 
the Deutsche Segel-Liga.

---

## 2. PairingList — the User's Existing Generator

Repo: `github.com/gundramleifert/PairingList` (Java, Maven), cloned as `reference/PairingList`.
Contains **41 event directories** with real pairings since 2023 (DSBL, SCL, JSCL, WSCL,
DSL Cup, US Sailing League).

**Decision (29.08.2026):** The JAR generates the Pairing lists, including for 
calculation from the UI (Story VA-3). A port to Python comes later.
Integrated via `api/app/pairing/generator.py`.

### Why Not Python — The Numbers

The actual cost driver of a Matchday is **boat logistics**, not combinatorics. If a Team 
stays on the **same boat slot** from the last Race of one Flight to the first of the next, 
it does not need to move. The Java tool optimizes for this; our Python generator does not yet:

| Pairing | Boat changes | Stays on board | Saved harbor shuttles | Boat span |
|---|---|---|---|---|
| Official, actually raced | **0** | 25 | 12 | 2 |
| JAR, short run 6.5 s | 3 | 21 | 8 | 4 |
| Python fallback | **27–28** | 1 | 0 | 1 |

The official list manages 16 Flights with **zero** boat changes. The Python fallback forces 
nearly every Team to switch after each Flight — with better boat distribution that is 
operationally worthless. Before porting, the Python optimizer must master this criterion.

Measured with `api/app/pairing/logistics.py`, a faithful port of
`CostCalculatorBoatSchedule.getInterFlightStat`. A test ensures our numbers match exactly 
those the Java tool itself outputs.

### Operating the JAR

- Build: `mvn -DskipTests package` in `reference/PairingList` (requires network for Maven Central).
- **The fat JAR has no `Main-Class` entry** — invoke via
  `java -cp <jar> gundramleifert.pairing_list.Optimizer`.
- `-dc display_cfg.yml` is **mandatory**, even if no PDF is wanted; otherwise it aborts.
- **Runtime:** With production configuration (20,000 iterations, 600/2000 individuals), one 
  Matchday with 16 Flights runs **well over 8 minutes**. This never belongs in an 
  HTTP request. Reduced settings deliver usable lists in ~7 seconds, but measurably worse.
- The tool reports per Flight `###### Flight N ######` and at the end 
  `saved Shuttles: in habour: … at sea: … - boat changes: …`. Both are captured: the 
  first for progress display, the second as a sanity check against our own numbers.
- Java 17 or newer required. If Java or the JAR is missing, the backend continues running — 
  just without the ability to compute new lists.

### Output Formats (verified against `events/2026_DSBL-1`)

`schedule_cfg.yml` — Input/Configuration:

```yaml
flights: 16
titles: ["Pairing List - 1. Segel-Bundesliga - MRSV/DTYC", ...]   # one per print variant
teams: ["BYC (BA)", "BYC (BE)", "BSC", ...]                        # 18 abbreviations
boats:
- color: BLACK
- color: GREEN
- color: DARKBLUE
- color: RED
- color: GRAY
- color: ORANGE
```

`pairing_list.yml` — the result:

```yaml
flights:
- races:
  - "2,0,15,12,1,13"    # 0-based indices into teams[]; Position = Boat 1..6
  - "7,10,16,14,11,3"
  - "17,4,5,8,6,9"
```

`pairing_list.csv` — same, 1-based, with trailing semicolon:

```
Race;Flight;Boat 1;Boat 2;Boat 3;Boat 4;Boat 5;Boat 6
1;1;3;1;16;13;2;14;
```

Verification row 1: yml `2,0,15,12,1,13` + 1 = csv `3,1,16,13,2,14`. ✓

`pairing_list_N_teams.yml` (N = 0..5) — one cyclically rotated team list per print variant;
`display_cfg.yml`, `opt_cfg.yml` — Display and optimization weights, respectively.

### Pitfalls in Existing Data (verified against Java source)

- **The YAML version is authoritative.** In events through 2023, the CSV column `Flight` 
  contains not the Flight number but the Race number **within** the Flight — grouping by it 
  yields wrong Flights.
- **Never use `pairing_list_N_teams.yml` to decode indices.** The list is rotated, and the 
  offset is not coupled to `schedule_cfg.yml` due to an array mutation in `Saver`. Always 
  use `schedule_cfg.teams`.
- **Incomplete fleets:** If the team count is not divisible by the boat count (Vilamoura 
  17/6, US-West 7/4), the tool internally pads to `ceil(teams/boats)·boats`. In the pairing, 
  indices at or above the real team count appear — they mean "boat stays empty". The importer 
  treats them as empty slots (`app/pairing/importer.py`).
- **Older formats:** `title:` as a string instead of `titles:` as a list (before 04/2024); 
  `boats` as a plain string list instead of `- color:` mappings (2023); `color` can be `null`.
- **Do not normalize:** Umlauts (`BYCÜ`) and parenthetical suffixes (`BYC (BA)` vs. `BYC (BE)`) 
  distinguish real clubs. Directory names `<YYYY[-MM-DD]>_<slug>` have unreliable dates.
- **Additional optimization goal we missed:** Besides encounter and boat distribution, the 
  Java tool also minimizes **boat changes and shuttle trips** between Flights (weights 
  `weightStayOnBoat`, `weightStayOnShuttle`, `weightChangeBetweenBoats`). A Team staying 
  on the same boat between two Flights does not need to return to shore. Our fallback 
  generator does not yet measure this.

### Data Model Consequences

- **Boats have colors**, not just numbers. Field `Boat.color` is added 
  (BLACK, GREEN, DARKBLUE, RED, GRAY, ORANGE).
- Team abbreviations contain umlauts and parentheses: `BYCÜ`, `SMCÜ`, `BYC (BA)`, `KYC (SH)`.
  Mapping to our Teams **never via name comparison**, always via `ExternalId`.

---

## 3. SAP Sailing Analytics — API

Source: sparse clone at `reference/sailing-analytics`, path
`java/com.sap.sailing.server.gateway/webservices/api/`. The user operates their own
**instance** (Docker Compose, port 8888).

### v2 — Exactly One Endpoint

`GET /sailingserver/api/v2/leaderboards/{name}`

| Parameter | Meaning |
|---|---|
| `secret` | **Mandatory**, assigned per regatta |
| `resultState` | `Live` or `Final` |
| `columnNames`, `raceDetails` | repeatable; `raceDetails=ALL` for everything |
| `time` / `timeasmillis` | State at a point in time (ISO 8601 or ms) |
| `maxCompetitorsCount` | Default 1000 |

### v1 — Significantly Richer, Including

**Read:** `regattas`, `regattas/{name}/races`, `.../entries`, `.../competitors`,
`.../races/{racename}/competitors/positions`, `.../competitors/live`, `.../wind`,
`.../markpassings`, `trackedRaces/*`.

### Handset Tracking: Confirmed Possible — Phase 5 Becomes Small

Confirmed via source code (`GPSFixesResource.java`, `LeaderboardsResource.postCheckin`). Two steps:

1. **Assign Device:** `POST /api/v1/leaderboards/{name}/device_mappings/start` with
   `{competitorId, deviceUuid, fromMillis, secret}`. The Competitor must be registered in 
   the regatta. End via `.../device_mappings/end` with `toMillis`.
2. **Send Positions:** `POST /api/v1/gps_fixes` with
   `{deviceUuid, fixes: [{timestamp, latitude, longitude, speed, course}]}`.
   `timestamp` in **Unix milliseconds**, `speed` in **m/s**, `course` as COG in degrees true.
   `speed` and `course` are **mandatory** in the deserializer. Recommended: gzip, batches of ~1000 Fixes.

The server maps Fixes to the correct Race based on device mappings valid at that time.
**This eliminates the need for our own position store and track evaluation.**

> **Security-relevant:** `gps_fixes` performs **no authentication** checking in the code. 
> Handsets must never send directly to SAP Sailing. Our backend is the gatekeeper:
> it authenticates the tracking session, verifies Team assignment, then forwards.

Before build: clarify with the operator whether the instance has these endpoints enabled,
rate limits, and what happens to Fixes without valid mapping.

### Writing Results: Document Import Only

`PUT /api/v1/leaderboard/{name}/results`, `Content-Type: application/octet-stream`, body is
a **result document** (ISAF XRR XML or CSV, selected via the mandatory parameter
`scoreCorrectionProvider`). Authentication via **Bearer token with `UPDATE` right**; the
regatta `secret` is not sufficient here. Matching is explicit via `sailId`+`competitorId` and
`raceNumber`+`raceColumnName`. Without `allowPartialImport`, incomplete matching results in
no import at all.

**Consequence:** There is no "Place X for Boat Y in Race Z" endpoint via JSON. The Race 
Officer therefore writes to **our** database — which remains authoritative — and we generate 
an XRR/CSV document for SAP Sailing as needed. This confirms the conflict rule "Race Officer 
wins against Import".

### v2 Leaderboard Response Structure

Derived from `LeaderboardsResourceV2.getLeaderboardJson`. Complete documentation in
`reference/sailing-analytics/CLAUDE.md`, section 4. Essentials:

- **Top level:** `name`, `boatClass`, `resultTimepoint` (ms), `resultState`, `columnNames[]`,
  `trackedRacesInfo[]`, `competitors[]`.
- **`competitors[]`** sorted by overall rank: `id` (UUID), `name`, `shortName`, `sailID`,
  `nationality`, `rank`, `overallRank`, `netPoints`, plus **`columns`** — an object with 
  RaceColumn name as key; per cell `totalPoints`, `netPoints`, `maxPointsReason`,
  `isDiscarded`, `rank`, `finished`.
- **Pitfall:** On empty leaderboard, the key is **`raceScores`** instead of `columns`.
  In v1 it is always `raceScores`. Parser must handle both.
- Stable IDs are present (Competitor UUID, Race UUID) — basis for `ExternalId`.

### Legal Requirements

The v2 documentation includes an **ATTRIBUTION/BRANDING** clause: anyone using the API must 
display SAP branding in every end-user interface based on this data. Additionally, position 
and weather data require special permissions. This affects the website directly and must be 
clarified before going live.

---

## 4. manage2sail

Scarcely documented publicly. What is confirmed: there is an **Access Token** for result 
and regatta structure import, and an Integration tab for export to external systems.

**Consequence:** The M2S adapter has a **CSV/XML upload as fallback from the start** so the 
business office is not blocked if the token path does not work out. Token and export scope 
must be requested from the business office.

---

## 5. Environment

- **No Docker, no Postgres** installed in this WSL2 environment. Development therefore runs
  on **SQLite** (`sqlite+aiosqlite:///./sbl.db`); the production target remains Postgres.
  Therefore the data model contains no PG-specific types (no JSONB, no ARRAY).
- Add Postgres: `sudo apt install -y postgresql`, then `sudo service postgresql start`
  (required after each restart in WSL without systemd).
- `uv` requires `UV_CACHE_DIR` in a scratch area — `~/.cache` is read-only in this session.
