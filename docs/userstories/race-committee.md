# Race Committee

Part of the [user stories](README.md); the format, the status marks and the
identifier rule are explained there.

The race committee runs the races of one matchday from the water and enters their
results. Everything derived from a result — points, standings, the freeze of an
event — follows from the raw entry, so correcting is as ordinary as entering.

## Before the season: the jury

The league's protest committees and umpires are not the clubs' to find: the association
keeps a **pool of judges** and a **jury organizer** who staffs every event from it
(decided 2026-11-03). The organizer asks the pool which events each can do, the judges
answer, and whom the organizer approves is the event's jury — the `jury` tuple the site
already knows (Z-2), with everything that comes with it: the event in their space (Z-10),
the notice board (VA-11) and an expense claim on it, settled by the host club's
treasurer (F-2, F-3).

### JU-1 ● The jury organizer keeps the pool of judges
As the **jury organizer** I want to **say who is a judge**, so that **I know whom I can
ask for an event, and only they are asked**.

Acceptance criteria:
- **Jury organizer** is a relation on the site, `jury_organizer` (Z-2): given by the
  site's `admin` like every site relation, and the admin is one too. It opens the league
  office's **Jury** section (`/office/jury`, A-11) and nothing else of the office.
- **Being a judge is a tuple too** — `user:judge:site`, written by the jury organizer
  (`POST /api/jury/judges`, any account the organizer finds, `GET /api/jury/candidates`)
  and deleted by them (`DELETE /api/jury/judges/{user_id}`). Being a judge grants nothing
  on any event; it only means the jury organizer may ask and write to that person.
- Removing a judge from the pool withdraws their open requests (those not approved). An
  event they were approved for keeps them as its jury: taking someone off an event is
  its own step (JU-5).
- The judge has no league office: *Me › Jury* is theirs (JU-2, JU-4).
- Anyone else is refused (403) — a series' or an event's `jury` is no jury organizer.

Endpoints: `GET/POST /api/jury/judges`, `DELETE /api/jury/judges/{user_id}`,
`GET /api/jury/candidates`

Tests: `api/tests/stories/test_jury.py::TestThePool`,
`web/tests/test_workspace.ts`,
`e2e/jury.spec.ts::JU-1/JU-2/JU-3/JU-4/JU-5: the jury organizer staffs an event from the pool of judges`

### JU-2 ● A judge says which licences they hold
As a **judge** I want to **say which licences I hold**, so that **the jury organizer
asks me for what I can do**.

Acceptance criteria:
- Three licences, after the DSV's licence rules for race officials: **umpire**,
  **national judge** and **regional judge** (`JudgeLicence`). Any number, none included.
- **The judge's own word** (decided 2026-11-03): nobody checks a licence and nobody but
  the judge sets it — trust, as on the water. *Me › Jury* shows the three to tick
  (`PUT /api/me/jury/licences`).
- Only a judge has the section and may save; anyone else is refused (`not-a-judge`).
- The jury organizer sees each judge's licences in the pool and filters by one (JU-3).

Endpoints: `GET /api/me/jury`, `PUT /api/me/jury/licences`

Tests: `api/tests/stories/test_jury.py::TestLicences`,
`e2e/jury.spec.ts::JU-1/JU-2/JU-3/JU-4/JU-5: the jury organizer staffs an event from the pool of judges`

### JU-3 ● The jury organizer asks judges for events, many at once
As the **jury organizer** I want to **ask judges whether they can do an event — several
events and several judges in one go —** and **find the judges I still need to ask**, so
that **every event is staffed without a mail per person and event**.

Acceptance criteria:
- **The pool is the site's one table** (A-13): name, address, licences — searched,
  sorted and paged on the server. Each **event I pick** becomes a column of its own
  showing each judge's state there — *invited*, *available*, *declined*, *approved* or
  nothing — and **its header filters by it, including or excluding**: *approved*, *not
  approved*, *available*, *invited*, *declined*, *asked*, *not asked*
  (`event=<id>:<state>`, `!` excluding; several events combine). So "available for
  Kiel, not yet approved anywhere else that weekend" or "not asked for Hamburg" is one
  filter each. The events offered are those not over (`GET /api/jury/events`), drafts
  included — a season is staffed before it is published.
- **Asking is one step for many** (`POST /api/jury/invitations`): the events picked ×
  the judges ticked, with an optional note. A pair already asked is left as it is; an
  event already over is refused (`jury-event-closed`), and so is anyone not in the pool
  (`not-a-judge`). **Each judge gets one mail** naming every event newly asked, the note,
  and the link to *Me › Jury*.
- **Writing to judges** without asking for anything (`POST /api/jury/messages`): a
  subject and a text to the judges ticked, one mail each — the pool is whom the organizer
  may write to, nobody else.

Endpoints: `GET /api/jury/judges`, `GET /api/jury/events`, `POST /api/jury/invitations`,
`POST /api/jury/messages`

Tests: `api/tests/stories/test_jury.py::TestAsking`,
`e2e/jury.spec.ts::JU-1/JU-2/JU-3/JU-4/JU-5: the jury organizer staffs an event from the pool of judges`

### JU-4 ● A judge answers: I can, or I cannot
As a **judge** I want to **answer each request — I can do this event, or I cannot —**
so that **the jury organizer knows whom to approve**.

Acceptance criteria:
- *Me › Jury* lists my requests, the next event first, each with its dates and state.
  An unanswered one is a to-do on *Me* (`jury_invited`, Z-8).
- Answering *available* is my application for the event; *declined* says I cannot. I may
  change my answer until I am approved (`PUT /api/me/jury/requests/{event_id}`); after
  that it is the jury organizer's to take me off (`jury-already-approved`).
- Only my own request, and only one that exists: an event nobody asked me for answers
  404.

Endpoints: `GET /api/me/jury`, `PUT /api/me/jury/requests/{event_id}`

Tests: `api/tests/stories/test_jury.py::TestAnswering`,
`e2e/jury.spec.ts::JU-1/JU-2/JU-3/JU-4/JU-5: the jury organizer staffs an event from the pool of judges`

### JU-5 ● The jury organizer approves or assigns — and the judge is the event's jury
As the **jury organizer** I want to **approve a judge who is available, or put a judge
on an event myself**, so that **the event has its jury, and the judge can work and claim
costs on it**.

Acceptance criteria:
- **Approving is assigning** (`PUT /api/jury/events/{event_id}/judges/{user_id}`): from
  any state, or with no request at all — a judge I agreed with on the phone needs no
  invitation first. Only a judge from the pool.
- **The approved judge is the event's jury at once**: the `jury` tuple on the event,
  written directly (Z-2) — so the event appears in their space, they publish on its
  notice board, and they may file an expense claim on it, which **its host club's
  treasurer** decides and pays (F-2, F-3). Someone who already held it keeps the one row.
  The judge gets a mail saying so.
- **Taking a judge off** (`DELETE …/judges/{user_id}`) deletes that tuple and leaves the
  judge's answer as it was. A claim already filed stays the treasurer's to decide.
- An event over is refused (`jury-event-closed`).

Endpoints: `PUT /api/jury/events/{event_id}/judges/{user_id}`,
`DELETE /api/jury/events/{event_id}/judges/{user_id}`

Tests: `api/tests/stories/test_jury.py::TestApproving`,
`e2e/jury.spec.ts::JU-1/JU-2/JU-3/JU-4/JU-5: the jury organizer staffs an event from the pool of judges`

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
- **A page, not a Matchday tab:** `/events/:id/race-control`, gated to the race committee
  *of that event* (see below), linked from the manage screen, the event's *Race day ›
  Race control* section in My space (Z-10, #32) and the results tab. The results tab stays
  the *correction* screen — a protest heard weeks later belongs there, not here.
- **One race on screen, the current one:** the race on the water, else the first race that
  is neither `finished` nor `abandoned` — decided by the server, which owns the transitions
  (`services/race_state.py::current_sequence`), and sent as `current_sequence` with the
  races (`GET /api/admin/events/{id}/races`); the results tab marks the same race. `null`
  once every race is done. Header names
  the race and its flight, a progress bar shows races done over the event's total. Arrows
  reach the previous race (to correct) and the next (to preview), nothing further.
- **Everything is sized by the event** — `Event.boat_count` chips, `ceil(team_count /
  boat_count)` races per flight, `flight_count` flights. A guest club's four-boat event works
  exactly like a league day; no "six" and no "48" in the code.
- **Scheduled:** the event's boats in their colours, each with the team the pairing list puts
  on it. Buttons **Start** (the gun went now), **Start sequence** — **in 10 s**, or **at
  the next full minute** at least 10 s away (tapped at 14:04:52 → 14:06:00), so the signals
  fall on the clock — and **AP** (see *Signals*).
- **The sequence is a state machine** (`web/src/lib/startSequence.ts`): idle → armed
  (its one piece of state is when the first signal is) → the start. Starting again while
  armed is the **restart**, **Abort** goes back to idle. Which flag is up, the next signal
  and the gun are derived from the clock. The armed sequence and its preparatory flag are mirrored per race
  on the device, because the card remounts on every change of the race and a phone
  reloads; a sequence whose start has passed is dropped, never fired late.
- **The screen says what to do next**, biggest: "P UP + one short sound" and the countdown
  to it; below, which flags are up and the start time.
- **The start sequence is the league's 3-2-1-0**, not RRS 26's 5-4-1-0: at 3 minutes the
  **club flag** goes up (one sound), at 2 the **preparatory flag** (one sound), at 1 the
  preparatory flag comes down (one long sound), at 0 the club flag comes down (one sound)
  and that is the start, which the screen records by itself. The screen shows which flag
  is up and counts down to the next signal.
- **AP is part of the same machine.** With no sequence running, AP goes up at the tap
  (two sounds). During a sequence it goes up 10 s after the tap, at the latest 3 s before
  the start, and not at all in the last 8 s (5 s to get the flag ready, plus 3); the
  sequence runs on until AP is up. While AP is up, the two sequence buttons are the way
  down — **AP down in 10 s** or **at the next full minute** — and AP comes down then,
  counted in like any signal (one sound), with the club flag a minute later. The screen
  hauls AP down and records the start by itself when the clock reaches them.
- **A general recall works the same way.** It puts the race back to `scheduled` with the
  **First Substitute** up (two long sounds). The screen shows it, and the sequence buttons
  become **1st Substitute down in 10 s** / **at the next full minute**: it comes down then,
  counted in, one sound, and the club flag goes up a minute later. The First Substitute is
  not a race signal on the server — the recall itself is the transition — so it lives in
  the sequence state, mirrored with it.
- **The phone sounds the signals** — before each, a ping at ten seconds to go (at the tap
  itself when the signal is ten seconds away or less, as after "in 10 s") and low beeps at
  three, two and one; then the signal's own tone, an octave higher, short or long
  as the rules count it (AP up and a recall are two, a second apart). Booked on the audio
  clock, not the page's timers, so the countdown on the screen turns with the beep. A cue
  for whoever works the real horn, not a replacement for it. Any tap on the screen
  switches the sound on (a browser plays nothing without one); a sequence restored after a
  reload shows "tap to turn the sound on" until then. A speaker button mutes it, the choice
  stays on the device, and "Test sound" plays a shortened count-in to check the volume.
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
- **The committee's tools appear on the events I run, and only there.** The race-control
  page, the results tab and the live view's course controls are offered by what the server
  answers for *this* event — `GET /api/events/{id}/access` (`record_results`, `control`,
  `manage`), computed with the permission model — never by a summary role. A race officer
  appointed for one event used to see the controls on every event (and get a 403 on
  saving), while one appointed through the event's series or host club never saw them.
  A guest gets all `false`; the answer is a separate request so the public event detail
  stays the same for everyone and can be cached as such.
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
`api/tests/stories/test_event_access.py`,
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
dropped. The results-entry tab (`RaceResultRow` in `web/src/pages/league/act/Results.tsx`) now makes the
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

Tests: `api/tests/stories/test_result_entry.py::TestEnteringResults`,
`api/tests/unit/test_results.py`

### WL-4 ◐ Penalty points for a team on a matchday
As **race committee** I want to **give a team penalty points for the matchday as a
whole**, so that **a penalty that belongs to no single race — a late crew list, a missed
briefing, damage to a boat — still counts**.

SAP Sailing calls these **carried points**: points a team starts the matchday with, before
its first race. The DSBL used them in 2023 (3 points each for four teams in Berlin).

Acceptance criteria:
- **Once per matchday, on the team's entry in the event** — not per race, and not in the
  series: a team's penalty in Berlin is no penalty in Kiel.
- **Added once, never discarded:** the team's total and net for the matchday each grow by
  exactly that amount, whatever discards apply to its races. It is raw data like a
  finish position — the points stay derived (`compute_event`), and the series table
  follows from the matchday's.
- A reason can be noted with it. Setting it again replaces it; removing it is setting it
  to nothing. Every change is written to `AuditLog`.
- Who may: whoever may enter results for the event (`race_officer` on it, its series, its
  host club or the site). A closed (`final`) event still takes it, like a protest
  decision — closing freezes nothing.
- The matchday table shows the penalty next to the team, so a total that is not the sum
  of its races explains itself.
- The SAP import (Story A-14) brings it in from `carriedPoints`; a penalty set here wins
  over the import.

Endpoint: `PUT /api/admin/events/{event_id}/teams/{team_id}/penalty`. Entered in
`web/src/pages/league/act/Results.tsx`, the results tab (*Penalty points for the matchday*, below the
races); the standings show "incl. 3 penalty" with the reason as its tooltip.

Open: no browser test covers the entry form yet.

Tests: `api/tests/stories/test_result_entry.py::TestMatchdayPenalty`,
`api/tests/unit/test_scoring.py::test_a_matchday_penalty_counts_once_and_is_never_discarded`

### WL-5 ◐ The race committee scores in SAP Sailing, the site follows
As **race committee** of an event scored on SAP Sailing (VA-14) I want to **enter results,
penalties and protest decisions in SAP Sailing alone**, so that **there is one source of
results on the day, and the site, its tables and its live pages follow by themselves**.

Acceptance criteria:
- **While the event is live, the site asks SAP every 10–30 s** for the leaderboard and
  takes what changed: finish position, code (DNF, OCS, …), redress, and the team's
  carried points (WL-4) — **raw data only**. The points are derived here as for every
  event (`compute_event`), and SAP's net points are compared with ours; a difference is
  reported to the event's race officers and the league office, never silently taken.
- **Every open page follows** through the live stream (B-5), published after the commit.
- **SAP is the source for this event**: entering or changing a result here is refused
  (`event-scored-on-sap`), the result screens say where results are entered and link to
  the leaderboard. A protest decision weeks later is made in SAP too, and the site takes
  it on its next ask — for a `final` event a race officer asks for it once.
- **SAP unreachable:** the site keeps the last results it took and says since when
  ("results as of 14:32") — never an empty table, never stale data passed off as current.
- One asker per event on the server, never one per visitor against SAP.
- The event's status still changes only through its transitions (VA-8, VA-10) — closing
  the day is a declaration here, whatever SAP shows.

What is built: `POST /api/events/{id}/sap/results` (the event's race officers and
organizers) takes the results now; while the event is live the server does it every
`SBL_SAP_POLL_SECONDS` (`app/services/sap_scoring.py`), and every open page follows. A
sent event's results land on the teams, boats and races of our draw through the links the
send stored, and on an event scored on SAP a result changed there replaces ours. Result
entry, the matchday penalty, the race start, recall, abandon, race signals and the start
sequence answer
`event-scored-on-sap` (409, with the leaderboard); results are entered in SAP's Race
Manager app, and the site's race-control screen and result entry are not offered there
(VA-14). *Set up › Scoring* fetches the results on request and links SAP's leaderboard.
Still open: "results as of" on the pages.

Tests: `api/tests/stories/test_sap_send.py::TestBothDirections`,
`api/tests/stories/test_sap_send.py::TestTheLivePoll`,
`api/tests/stories/test_journey_sap_scored.py::TestAMatchdayScoredOnSap`,
`api/tests/stories/test_scoring_backend.py::TestTheEventChoosesItsScoring`,
`e2e/sap-scoring.spec.ts`
