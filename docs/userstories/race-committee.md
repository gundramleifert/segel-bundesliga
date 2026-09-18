# Race Committee

Part of the [user stories](README.md); the format, the status marks and the
identifier rule are explained there.

The race committee runs the races of one matchday from the water and enters their
results. Everything derived from a result — points, standings, the freeze of an
event — follows from the raw entry, so correcting is as ordinary as entering.

## On the water

### WL-1 ○ Run races
As **race committee** I want to **have a simple app with which I run the races**,
so that I **work quickly and accurately on the water**.

The screen itself — which race is next, who is on which boat, start, recall, finish, the
progress through the day — is Story **WL-3**. What stays here is the part WL-3 deliberately
leaves open:

Acceptance criteria:
- It works **without network**: every tap is stored locally and reconciled when the
  connection returns, with the same "later entry wins, the overridden state is logged"
  rule as WL-2. WL-3's `localStorage` mirror of the finish order is *not* this: it survives a
  reload, not a morning without coverage.
- Usable with wet hands on a rocking boat: large areas, no fiddling (WL-3 states the sizes).

Tests: none yet

### WL-3 ◐ Start, recall and finish races from one screen
As **race committee** I want **one full-screen page that shows the current race and lets me
start it, recall it, abandon it or record its finish with a few large taps**,
so that **on the water I handle one race at a time and never hunt through three tables**.

Today `RaceStatus.RUNNING` and `Race.started_at` exist and are **never set**: a race goes
from `scheduled` straight to `finished` when a result is saved, and nothing in the system
knows a race is *underway*. B-5's "which race is running" and everything in L-1…L-3 read
`started_at`/`finished_at`, so this story comes first. Plan: `docs/PLAN_LIVE_IMPLEMENTATION.md`
§7 (decision 14).

Acceptance criteria:
- **A page, not a Matchday tab:** `/events/:id/race-control`, gated to `admin` and
  `race_officer`, linked from the manage screen and the results tab. The results tab stays
  the *correction* screen — a protest heard weeks later belongs there, not here.
- **One race on screen, the current one:** the first race that is neither `finished` nor
  `abandoned` — the rule the results tab already uses to find the open race. Header names
  the race and its flight, a progress bar shows races done over the event's total. Arrows
  reach the previous race (to correct) and the next (to preview), nothing further.
- **Everything is sized by the event** — `Event.boat_count` chips, `ceil(team_count /
  boat_count)` races per flight, `flight_count` flights. A guest club's four-boat event works
  exactly like a league day; no "six" and no "48" in the code.
- **Scheduled:** the event's boats in their colours, each with the team the pairing list puts
  on it. Buttons **Start** (the gun went now) and **Start sequence** (5-4-1-0 minutes per
  RRS 26, fires Start at 0), and **AP** (see *Signals*).
- **Running:** elapsed clock; one chip per boat as a finish pad — tap in finish order, tap
  again to undo; codes (OCS, DNF, DSQ, RDG …) one tap below. Buttons **X** (individual
  recall), **General recall** (First Substitute, back to `scheduled`), **Abandon → resail**
  (N, the same reset), **Abandon → no resail** (`abandoned`, scores nothing), **Shorten**
  (S), **Finish** — enabled once every boat has a position or a code.
- **Signals are what the committee actually does on the water, so the screen speaks in
  flags.** Two kinds, deliberately kept apart:
  - **Transitions** are signals that change the race's status and are the endpoints above:
    First Substitute is the recall, N is the abandonment (with or without resail), the gun
    is the start. Nothing new.
  - **Displayed signals** stay hoisted for a while and mean something to the boats and to
    the spectators (B-5's running-race view shows them): **AP** (postponed — cancels a
    running start sequence, the race stays `scheduled`; hauling it down means the warning
    signal follows one minute later, which the screen counts), **X** (individual recall,
    with the boats over the line), **S** (shortened course, the finish is at the next mark).
    The one currently displayed is stored on the race (`Race.signal`, nullable) and cleared
    when hauled down — a flag on the mast is state, its hoist is an audit row like every
    other action here. `POST …/races/{race_id}/signal` with `{signal: "AP" | "X" | "S" |
    null}`; AP is allowed only while `scheduled`, X and S only while `running`.
  - **The preparatory flag decides the penalty.** The start sequence asks for it once —
    **P** (default), **I**, **Z**, **U**, **black** — and stores it (`Race.preparatory`).
    Tapping a boat under **X** gives it the code that flag prescribes: `OCS` under P and I
    (the boat may return and start correctly, and the committee then clears the code with
    one tap), `ZFP` under Z, `UFD` under U, `BFD` under black — codes that stay. `UFD` and
    `BFD` are not in `ResultCode` today and are added here, scored like `OCS` (RRS A5.2:
    starters + 1, discardable unless the sailing instructions say otherwise). An OCS mark
    is nothing but a result code recorded early, so the finish pad already knows how to
    show, change and clear it; no second per-boat state is invented.
  - **AP over A**, **N over A** (no more racing today) and **AP over H**, **N over H** (back
    to the harbour) are not race signals but the day's: they map to VA-10's finish or to
    plain postponement, and the screen offers them where the event's own transitions are.
- **Finished:** the result, read-only, then the next race slides in; **Correct** leads to
  that row in the results tab.
- **Races run strictly one at a time.** Starting a race while another is `running` is
  refused with `race-already-running`; recalling or abandoning a race that is not running
  with `race-not-running`; anything while the event is not `live` with `event-not-live`.
  The event's own gate is reused: a `planned` event shows one button, **Start matchday**
  (the existing `POST …/start`, VA-8 readiness applies); `final` or `cancelled` shows the
  state and a link to VA-10's reopen. The page invents no state of its own.
- **One service owns the transitions.** `app/services/race_state.py` implements start,
  recall, abandon (both kinds) and finish — and the result PUT goes through it too. Until
  now `put_race_result` set `finished` with no check at all, and neither the standings
  service nor the scoring reads `Race.status`: a race is scored the moment its entries carry
  codes, whatever its status says. Left as is, this state machine would be advisory — race
  18 finished from the results tab while race 17 runs, an abandoned race still scoring. So:
  the PUT refuses to finish a race while another one is running, and refuses an `abandoned`
  race; **recall and abandon clear the race's entries** (code, position, redress) before
  recomputing, which is what makes "scores nothing" true; a `finished` race stays editable
  forever, which is the protest case.
- **A recalled first race leaves the event frozen.** The configuration freeze (VA-8) counts
  races no longer `scheduled` and recorded codes — both of which a general recall of race 1
  undoes, un-freezing the event with the fleet on the water. Every transition writes an
  `AuditLog` row anyway; the freeze predicate counts those too, so a race that has started
  *once* keeps the event frozen.
- **Start** sets `started_at` and stamps the race with the event's active course if one is
  laid (L-2); **Finish** sets `finished_at`; recall clears `started_at`. Every transition is
  idempotent (a second tap in a rocking boat is not an error) and publishes on the live
  stream (B-5).
- **Wet hands:** chips at least 64 px, no dropdowns on the main path. The finish order is
  mirrored to `localStorage` per race so a reload or a dropped connection does not lose the
  taps — not WL-1's offline sync, but it removes the likeliest way to lose a race.
- The tap-to-finish chips leave `RaceResultRow` for a shared `FinishOrderPad` component, so
  the results tab and this page cannot drift apart.

Endpoints: `POST /api/admin/events/{event_id}/races/{race_id}/start`, `…/recall`,
`…/abandon?resail=`, `…/signal`; finish is the existing `PUT …/result`.

What's done: the state machine (`app/services/race_state.py`) with the guarded PUT, the
cleared entries, the audit-row freeze, `started_at`/`finished_at`, `Race.signal` and
`Race.preparatory`, `UFD`/`BFD`; the page `/events/:id/race-control` with the start
sequence, the signals, the two-tap abandon, the finish pad kept on the device until
"Finish", and the codes below it; `FinishOrderPad`/`useFinishOrder` shared with the results
tab. Still open: `Race.course_id` (there is no `Course` table until L-2), the detected
finish order as a suggestion (L-2), and the day's signals AP/N over A or H, which map to
VA-10 and are reached from the manage screen for now.

Tests: `api/tests/stories/test_race_control.py`,
`api/tests/unit/test_scoring.py::test_non_finishers_score_starters_plus_one`,
`e2e/race-control.spec.ts::WL-3: as race committee I run one race at a time`

## Results

### WL-2 ◐ Enter and edit results easily
As **race committee** I want to **enter and correct results easily**,
so that **a mis-entry is not a disaster**.

Acceptance criteria:
- Finish line is recorded by tapping in order, not by typing position numbers.
- Penalty codes (DNF, DSQ, OCS, ZFP, RDG …) are readily accessible.
- Every entry can be undone and changed later.
- **A boat with no result yet is a normal state, not an error.** A race begins with six of
  them and is entered one boat at a time, so "no result recorded" has to be something the
  screen can *send*, not merely something it starts out with. `code: null` for a boat
  clears that boat's result — code, position and redress alike — and undoing a tap uses
  exactly that. Without it, the screen had to report a boat whose position had not been
  typed yet as `FINISHED` with no position, which the endpoint correctly refused: a red
  "Enter a finish position for boat 4" appeared under the race on the way to every
  hand-entered result and cleared itself a keystroke later. The refusal itself stays — it
  still catches a *code* that needs a position arriving without one.
- A correction overrides import from foreign systems, never the other way.
- With simultaneous changes on two devices, the later entry wins; the overridden status is
  not lost but logged and displayed.

Open: full offline capture is Story WL-1 (offline sync) territory and stays open here. The
overridden state on a stale-`version` submission is written to `AuditLog`
(`app/services/standings.py`) but not yet surfaced anywhere in the UI — displaying that history
remains open.
What's done: `PUT /api/admin/events/{event_id}/races/{race_id}/result` records
`code`/`finish_position`/`redress_points` per boat (`admin`, `race_officer`), rejects an
invalid ranking (two boats claiming the same place), and recomputes points/standings
immediately, so a protest decision is a one-row correction, never a data migration. With a
stale `version`, the later submission still wins (a rocking boat is no place for a hard
conflict error), but the state it replaces is written to `AuditLog` first, not silently
dropped. `web/src/pages/Matchday.tsx`'s results-entry tab (`RaceResultRow`) now makes the
finish line the primary, fast path: tapping a boat's colored chip in finish order assigns it
`FINISHED` + the next unused position (a normal 6-boat race is 6 taps), the chip shows the
assigned rank as a badge, tapping again undoes just that boat, and a "reset race" action clears
all taps at once. The existing per-boat code `<select>` and manual position/redress `<input>`s
stay available underneath for the exceptions (DNF, DSQ, OCS, RDG, …) and always reflect the same
component state as the tap flow, so the two can never drift apart. Every result code now carries
a tooltip spelling out its exact point consequence (from `api/app/scoring/low_point.py`), and
picking `RDG` prefills the redress points with a suggested RRS A10 average of the team's other
scored races in the event — clearly labelled as a suggestion, never enforced. Duplicate finish
positions from the manual inputs (tap-assignment cannot produce one by construction) are flagged
in the UI and block Save immediately, ahead of the existing
`/errors/race-result-duplicate-position` server-side check.

Tests: `api/tests/stories/test_result_entry.py::TestEnteringResults`
