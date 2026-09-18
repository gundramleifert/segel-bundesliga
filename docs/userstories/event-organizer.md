# Event Organizer

Part of the [user stories](README.md); the format, the status marks and the
identifier rule are explained there.

The organizer owns one event from its first draft to its closing: configuration,
participants and their waivers, the draw, the day itself and the declaration that racing
is over. The stories stand in that order; the last one walks the whole way in one test.

## Setting the event up

### VA-6 ● Create event with its configuration
As an **event organizer** I want to **create an event with name, date, and configuration**,
so that **everything else follows from it**.

Acceptance criteria:
- Only **name and date** are required. Everything else has sensible defaults.
- The configuration consists of **number of teams, number of boats, and number of flights**. From
  it the number of races per flight is calculated — no constants in code. Teams and boats
  are picked as one of the catalog's combinations, the flights then from 1 up to that
  combination's stored length ([VA-7](#va-7--take-finished-pairing-list-from-catalog)).
- **Boats** can be specified with **color and name**; on the water they are referred to by name,
  not number. Without specification, `boat_count` boats are created in league colors; with
  specification, their count determines `boat_count`.
- Boats belong to the **event**, not the draw: a new pairing list changes the assignment,
  not the boats at the dock.
- Each boat row defaults to a color from the league colors, in order (`WHITE` beyond that, or
  once a custom field is left empty — "no color" is not a choice), and a name of
  **"Boat 1".."Boat N"** by position — a clearer starting point than an empty required field,
  freely renamed afterwards. **Three controls, always shown together**: a plain named select, a
  native color picker, and a free-text field — the color itself is only actually visible in the
  picker. Choosing a named color in the select copies it into the picker/text; editing either
  the picker or the text switches the select to "Custom", so a hand-picked color is never left
  sitting silently under a named option it no longer matches.
- In addition to administration, editorial, and race committee, also the **leadership of the
  host club** can create — not for a foreign host.
- **How the pairing list prints** is part of the setup too, and the panel offers it next to
  the draw: font size, landscape, per-team pages (`print_settings`). Empty means the sheet
  is printed the way its configuration implies — see [B-3](visitor.md#b-3--view-pairing-list), which
  owns the reasoning.
- **Creating is three steps on one screen, in the order the work happens:** 1. general
  data — name, dates, series, host, size and boats; 2. the clubs that enter; 3. the
  pairing list. One form asking for all of it at once was too fat to read, and it hid the
  fact that the clubs and the draw are decisions of their own. **The event exists after
  step 1** and can be published right there — the calendar entry often precedes the field
  — so steps 2 and 3 can each be skipped and finished later in the manage panel, which
  offers the same clubs and the same draw. The last screen says whether the event is
  ready 🚀 or what is still missing, offers publication, and — once published with a
  list — opens the pairing list and its PDF. The wizard never blocks on what a later step
  needs: a title alone still saves.
  **The wizard is a page of its own**, `/admin/events/new`, reached from the "＋" top-right
  of the events list — the tab is the list, and creating anything (a club, a series, a
  sailor, an event) is the same shape: the plus in the same corner, a page per entry, and
  "Back to the list" when it is done.

Endpoints: `POST /api/admin/events`

Tests: `api/tests/stories/test_create_event.py::TestCreateEvent`,
`e2e/lifecycle.spec.ts::VA-6: creating an event in three steps`

### A-2 ● Create matchday
As an **event organizer** I want to **create a matchday with name, date, and host**,
so that **the date is set before details are finalized**.

Acceptance criteria:
- Access is available to **administration, editorial, and race committee** — all three
  contribute an event.
- Name, date, league, and season are sufficient. The **host** is selected from created clubs
  (A-1).
- Without an end date, the matchday is single-day; an end before the start is rejected.
- The **venue remains open** and can be added later — it often is not yet determined when
  creating. The interface names the host instead of leaving a gap.
- An **own logo** is possible; without one, the host's crest applies.
- The matchday number increments if not specified; a taken number is rejected.
- Club accounts may not create matchdays.

Endpoints: `POST /api/admin/events`, `PATCH /api/admin/events/{slug}`

Tests: `api/tests/stories/test_master_data.py::TestCreatingAMatchday`

Open: The interface for this is still missing — only via API so far.

### VA-8 ● Save a draft, publish it, start it
As an **event organizer** I want to **save an event that isn't finished yet, publish it when
it is worth showing, and start it when it is valid**, so that I **can work in the order the
season actually happens — and so that nothing moves under a race that is already sailing**.

Acceptance criteria:
- **Saving never depends on validity.** Title alone is enough; no date, no host, no boats, the
  wrong number of clubs — all savable. That is the normal early state, not an error.
- **Publication is a separate flag, not a status.** `Event.published` and `Series.published`
  decide *who can see it*; `Event.status` (`planned` → `live` → `final`, or `cancelled`)
  says where it stands sportingly. The two are orthogonal: a published event can be
  `planned`, and a started one can stay unpublished.
- **Publishing locks nothing.** A published event stays fully editable, and it does not have
  to be complete — the calendar entry is often what makes people ask about the missing
  pieces. Unpublishing takes it back to a draft; results and pairing list are untouched.
- **A draft does not exist publicly.** Every public endpoint (series list and standings
  table, event list and detail, pairing list, club and sailor pages, the club list and the
  event-logo fallback) shows published data only, and answers **404** rather than 403 — a
  draft's existence is itself not public. A published event of an *unpublished* series stays
  hidden, or one matchday would give the draft series away. `/api/admin/…` shows everything.
- **Validity is computed, never stored**, and it answers with a **list of reasons**, not a
  flag: the organizer has to be told what is missing. Each reason is a stable code plus the
  numbers involved (`registered`/`configured`, `teams`/`boats`/`flights`/`available`, …),
  translated by the client — never an English sentence from the server. The rules:
  registered teams ≠ `team_count`, boats set up ≠ `boat_count`, no catalog entry for
  `team_count`/`boat_count`/`flight_count`, and no date.
- **Validity gates the draw and the start**, and reports the same reasons in the same shape.
  A single cause keeps its own code and status, so `pairing-team-count-mismatch` (409) and
  `pairing-catalog-missing` (404) read exactly as before; several causes arrive together as
  `event-not-ready` (409) carrying `reasons`. The catalog reason is exempt where it makes no
  sense: the optimizer job, an imported draw, and the start of an event whose list already
  exists.
- **Starting is a decision, not a date passing.** `POST …/start` requires readiness and a
  pairing list (`event-without-pairing-list`) and moves the event to `live`. A matchday
  postponed by fog must not start itself. Calling it twice is not an error.
- **After the first race, the configuration freezes.** The trigger is precise and does not
  depend on `status`: any race of the event that has left `scheduled` (running, finished,
  abandoned) **or** any result recorded. Frozen are the dimensions (`team_count`,
  `boat_count`, `flight_count`), the series and matchday, the entered clubs, the boats and
  the pairing list — `event-configuration-frozen` (409), carrying `races_started` and
  `results_recorded`. A redraw *before* the first start still works, which is the point of
  drawing twice while the fleet is at the dock.
- **Results are never frozen.** Entering, correcting and re-correcting results is the whole
  purpose of the race-committee screens, and a protest decision must stay possible months
  later (see [WL-2](race-committee.md#wl-2--enter-and-edit-results-easily) and "Points are derived, not
  entered" in `docs/concepts.md`). Title, dates, venue, host, logo, status and publication
  also stay editable while racing: a typo has to be fixable on a race day too.

- **Drafts are listed where they are finished.** `GET /api/admin/events` lists every event,
  drafts included, ordered dateless-first then newest-first. The public `GET /api/events`
  shows published events only — the right list for a calendar and exactly the wrong one for
  the screen that publishes, where it would hide the single event being worked on.

Endpoints: `GET /api/admin/events`, `GET /api/admin/events/{id}/readiness`,
`POST /api/admin/events/{id}/publish`, `POST /api/admin/events/{id}/unpublish`,
`POST /api/admin/events/{id}/start`, `POST /api/admin/series/{id}/publish`,
`POST /api/admin/series/{id}/unpublish`; `published` also on `POST /api/admin/events`,
`PATCH /api/admin/events/{id}`, `POST /api/admin/series`, `PATCH /api/admin/series/{id}`.
Computed in `api/app/services/event_readiness.py`. The admin screen is
`web/src/pages/AdminEvents.tsx` — a three-step creation whose first step gates almost
nothing (VA-6), and a manage panel per event carrying the readiness reasons, the date, the
entered clubs, the draw, publication and the start.

Tests: `api/tests/stories/test_event_lifecycle.py::TestSavingAnIncompleteEvent`,
`::TestPublication`, `::TestStarting`, `::TestFreezeAfterTheFirstRace`,
`api/tests/stories/test_complete_lifecycle.py::TestTheAdminEventList`

## Participants and their waivers

### VA-1 ○ Import registrations and sailors from manage2sail
As an **event organizer** I want to **import registrations — clubs, teams and their
sailors — from manage2sail**, so that I **don't have to type them in**.

Acceptance criteria:
- **manage2sail is optional.** Nothing on this site requires it: clubs, sailors, squads
  and lineups are created here directly (V-*, S-*), and an event with no M2S counterpart is
  the normal case for a club's own regatta. The import is a per-event action the organizer
  triggers, never a dependency.
- Import via M2S access **and** alternatively via file upload (the CSV/XML export M2S
  offers), so a missing token does not block.
- Assignment to existing clubs, teams **and sailors** via `ExternalId` (source
  `MANAGE2SAIL`), never by name comparison. A sailor unknown here is created without a
  login and linked; a known one is updated; name spelling differences never create a
  duplicate.
- **Sync, not just import:** the run is repeatable — a second run with unchanged data
  changes nothing — and a later run picks up crew changes M2S recorded since. Data the
  club entered here (waivers, profile settings, `ClubMember` consent) is never overwritten
  by a sync; only what M2S is the source of (registration, crew list) moves.
- After the run, it is clear what was created, changed, skipped, and what could not be
  assigned.

Open question: Scope and access of the M2S export — to be asked at the league office
(see `docs/findings.md`, section 4).

Tests: none yet

### VA-2 ○ Self check-in with liability waiver
As an **event organizer** I want **teams to check themselves in at the event and confirm
the liability waiver**, so that I **have little work on event day**.

Acceptance criteria:
- **Check-in happens in advance, not on event day.** The link/QR opens a set number of days
  before the event (reuse the deadline pattern from V-2) and closes at event start. On event
  day the organizer only reads the status list — nothing legal is signed on the dock.
- A team checks in by itself (QR code or link), without any involvement from the organizer.
- During check-in, the crew is confirmed or corrected.
- The liability waiver is displayed in full text and must be actively confirmed.
- The confirmation is **documented proof**: who (authenticated account, not a typed-in name),
  when, which version of the text. The text version is tracked — a text changed later must
  not retroactively alter an old confirmation.
- The organizer sees at a glance which teams have checked in and which are missing.

Overlaps with story S-1: If the liability waiver is already available for the season, only
attendance needs to be confirmed at check-in. Check-in thus becomes much shorter.

Note: This is the legally most sensitive part of the project. Legal landscape and the two
constraints that actually bind (insurer's required form, guardian consent for minors) are
written up in `docs/findings.md` section 6. Before building, the league and its insurer must
confirm whether an authenticated online confirmation is accepted for adults; if not, everyone
takes the scan-upload path from S-1.

Tests: none yet

### VA-5 ◐ Confirm liability waivers
As a **race organizer** I want to **only check off submitted liability waivers**,
so that I **don't have to collect anything on event day**.

Acceptance criteria:
- List of all people in the participating squads with their status: cleared, missing,
  outdated version, or (for a minor) waiting on the guardian's signature. **Built** —
  `GET /api/admin/events/{event_id}/waivers` (see [S-3](sailor.md#s-3--confirm-a-waiver-version-for-a-series-or-event)),
  shown on the event's admin panel with a link to a minor's uploaded scan (S-1).
- Who is not cleared cannot be registered for a matchday — the lock applies in Story V-2,
  not on the water. **Not yet wired** into the V-2 lineup check.
- Every confirmation is logged: who, when. **Built** — the confirmation row records it.

Access: the event's host-club leadership, plus `admin`, `editor`, `race_officer`. No fifth
role was added — the on-site organizer is a `race_officer` or the host `club_manager`.

Tests: `api/tests/stories/test_waiver.py::TestMinors` (check-in list),
`e2e/waiver.spec.ts` (the organizer's panel)

## The draw

### VA-7 ● Take finished pairing list from catalog
As an **event organizer** I want to **have the draw immediately**, so that I **don't wait
ten minutes for an optimization run**.

Acceptance criteria:
- A pairing list depends only on **teams, boats, and flights**. For the usual configurations,
  it lies **pre-calculated** in the catalog.
- **Exactly one file per teams-and-boats combination** is stored — the `out.yml` of the
  Java tool, computed for the **longest day** that combination is sailed on (18 teams on 6
  boats: 16 flights). It carries all information; the configuration is read from its
  content, not from the filename. An official draw can be deposited unchanged.
- **A shorter day takes the first flights of the stored list.** The organizer picks the
  teams-and-boats combination and then any number of flights from 1 up to the stored
  length; the draw cuts the list after that flight. Every flight of a stored list has every
  team exactly once, so a prefix is a valid draw. What it is *not* is re-optimized: the
  boat distribution was balanced over the whole list, and a prefix is as balanced as its
  first flights happen to be. Asking for more flights than the file holds is refused with
  the sizes that exist.
- A **seed value** shuffles the starting positions. That takes milliseconds.
- **Shuffling does not change quality**: boat distribution, encounters, and boat changes depend
  on the structure of the list, not on which name is at which starting position.
- The same seed produces the **same** draw — recoverable in case of dispute.
- If no entry fits the configuration, the response says which ones are available; the way via
  the calculation job ([VA-3](#va-3--calculate-and-publish-pairing-list-in-the-interface))
  remains.
- **The draw is the third step of creating an event** ([VA-6](#va-6--create-event-with-its-configuration)):
  the seed is prefilled (`1240`, reproducible) and one press draws. It used to fire
  automatically right after creation, which for a new event without clubs always failed and
  reported that failure as the first thing the organizer saw; now the step is refused
  visibly, names the readiness reasons, and can be skipped — the manage panel offers the
  same draw later. The event exists either way.

Endpoints: `GET /api/admin/pairing/catalog`,
`POST /api/admin/events/{id}/pairing/from-catalog`

Extend catalog: `uv run python -m app.pairing.catalog --teams 18 --boats 6 --flights 16`

Tests: `api/tests/unit/test_pairing_catalog.py`,
`api/tests/stories/test_create_event.py::TestPairingFromCatalog`

### VA-3 ○ Calculate and publish pairing list in the interface
As an **event organizer** I want to **calculate and publish the pairing list via the
interface**, so that I **don't have to operate command-line tools**.

Acceptance criteria:
- Team count, boat count, and flight count are set in the interface; calculation runs on the
  server, not in the browser.
- Calculation takes noticeably longer than a click — it needs a progress indicator and the
  ability to leave the page in between.
- **Before publishing, quality is displayed**: boat distribution per team, encounter frequency,
  boat changes between flights. The organizer decides rather than blindly trusting the result.
- The draw is **reproducible**: same input and same seed produce the same list. A draw must
  be provable in case of dispute.
- Generate multiple suggestions side by side and select the best.
- Publishing makes the list publicly visible (Story B-3) and can be undone as long as no
  races have been sailed.
- An already sailed race must not be overwritten by recalculation.
- Output as printable PDF that can be distributed to teams — done, as the download on the
  public pairing list ([B-3](visitor.md#b-3--view-pairing-list)); the organizer needs no separate one.

**Open decision:** This story elevates the generator from fallback to main function. Three
approaches are available — enhance the Python generator, call the existing Java tool from
the backend, or extend the Java tool with an interface. See `docs/findings.md`, section 2.

Implemented in the backend is the chain: start job, query progress, read quality report,
publish — `POST /api/admin/events/{slug}/pairing/jobs`, `GET /api/admin/jobs/{id}`,
`POST /api/admin/events/{slug}/pairing/publish`. Calculation is done with the Java tool.
The interface is missing.

Tests: `api/tests/unit/test_pairing_generator_jar.py`, `api/tests/unit/test_pairing_generator.py`

## The matchday and after it

### VA-4 ○ Participants write posts on the homepage
As an **event organizer** I want to **enable participants to easily publish posts on the
homepage**, so that **the page lives without me writing everything myself**.

Acceptance criteria:
- A participant writes a post with text and images, without needing to know editorial tools.
- The post appears under the name of the club or person, not anonymously.
- Images are resized on upload; mobile format works.
- A draft can be saved and continued later.

**Decided (29.08.2026): Club account with editorial approval.**

- **One account per club**, not per sailor — 18 accounts instead of hundreds, and far fewer
  personal data under GDPR.
- A post arrives as a **draft** and is approved by editorial. An official league page is liable
  for what appears on it; unmoderated publishing would be a risk without benefit.
- **Image rights:** Photos of people need their consent, foreign photos need a license. Both
  must be confirmed on upload.
- There needs to be a way to quickly take down an approved post.

Tests: none yet

### VA-10 ● Close an event, or call it off

As an **event organizer** I want to **declare that racing is over, or that it never
happened**, so that **the calendar, the series table and everyone reading them stop treating
a finished day as if it were still running**.

`EventStatus` has carried `final` and `cancelled` from the beginning, and
`app/services/standings.py` already scores `live` and `final` alike — but nothing ever set
either. The only transition that existed was `start` (`planned` → `live`), so every event
that had ever begun stayed "live" forever, including seasons that ended months ago.

Acceptance criteria:
- **Finishing** (`POST …/finish`) moves a **live** event to `final`. It is a declaration by
  the people on site, never a consequence of a date passing or of all races being sailed —
  a matchday that loses its last three flights to dying wind is still over when the race
  committee says it is.
- **Finishing does not require complete results**, and deliberately so: requiring all 48
  races would disable the button exactly on the days it is needed. A day where *nothing*
  was sailed is a cancellation, not a finish.
- **Finishing freezes nothing.** The configuration was already frozen by the first race
  (VA-8), and results stay editable forever — a protest heard weeks later is the entire
  point of the race-committee screens, and it must still land on a `final` event.
- **Cancelling** (`POST …/cancel`) is available from `planned` **and** from `live`: a day
  can be called off before anyone leaves the dock, or abandoned halfway through. It
  **deletes nothing** — pairing list and any results recorded stay exactly as they are, so
  a cancellation that turns out to be premature costs no data.
- **A cancelled event scores nothing, and costs nobody anything.** It drops out of
  `scored_events`, so the "who misses an event gets participants + 1" rule does **not**
  fire for it — being at a regatta that was called off must never be worse than staying
  home.
- **Both are reversible** (`POST …/reopen`), because both are human judgements made in a
  hurry: `final` → `live`, `cancelled` → `planned`. Nothing else about the event changes.
- Every transition is **idempotent** — finishing a `final` event answers 200, the same way
  starting a `live` one already does. A second tap on a button in a rocking boat is not an
  error.
- Refusals are typed and say which state the event is actually in: finishing something that
  never started is `event-not-started`, and reopening something that was never closed is
  `event-not-closed`.
- **Publication stays orthogonal.** Finishing does not publish, cancelling does not
  withdraw — `published` remains the only thing that decides who can see the event
  (VA-8).
- Permissions are the same as for starting: `admin`, `editor`, `race_officer`.

In the interface, the three transitions live in their own block at the bottom of the manage
panel — after publication and the start, because that is the order an organizer does them
in. The block shows **only the transitions that apply right now**: an open event offers
Finish and Call off, a closed one offers a single Reopen and nothing else. That is
deliberate — a permanently visible, permanently disabled "Reopen" on every planned event
would be four-fifths noise on a screen that has to work at 412 px (Story A-10).

Neither closing asks for confirmation. Both are one tap to undo and neither deletes
anything, so a confirmation dialog would buy nothing and cost a tap on a boat.

Tests: `api/tests/stories/test_event_closing.py`,
`e2e/lifecycle.spec.ts::VA-10: closing an event, and taking it back`

## The whole way

### VA-9 ● Run one event from end to end

As the **association** I want **one test that walks the whole way — clubs, series, event,
boats, clubs entered, draw, start, all races sailed, standings, freeze, protest** — so that
**the steps are proven to fit together in the order they actually happen**.

Acceptance criteria:
- Every individual step is already covered by its own story test. What this adds is the
  **sequence**: each step's output really is the next step's input, through the HTTP API
  only, with nothing reached around into the database.
- It runs the catalog's **smallest** configuration (12 clubs, 6 boats, 8 flights = 16
  races), not the league's 48 — small enough to sail to the end in a test, large enough to
  be a real pairing list rather than a hand-made fixture.
- Deliberately **one long test**, not several: a step that only makes sense after the
  previous one has happened cannot be a test that runs on its own.
- It asserts the things that are wrong only *in sequence*: that a draw refuses while the
  clubs are still being added, that an event saves with no date because the date is agreed
  later, that a series' registrations gate who may enter its events, that the whole fleet's
  points add up to what 16 races hand out, and that a protest decision still lands after
  the configuration has frozen.
- **The drawn list ends up on paper.** Once the event is published, the PDF endpoint
  answers the sheet ([B-3](visitor.md#b-3--view-pairing-list)) — a real PDF where the
  server can print, and a clear "cannot print here" where it cannot, so the test never
  skips silently. The browser walk ends the same way: the wizard's last screen offers the
  download and the file arrives.

Tests: `api/tests/stories/test_complete_lifecycle.py::TestTheCompleteLifecycle`,
`e2e/lifecycle.spec.ts::VA-8/VA-9: from a draft to a running event`
