# Domain decisions — the full text

Moved out of `CLAUDE.md` on 2026-11-12 (review 8.1), word for word: `CLAUDE.md` keeps one line per decision and points here for the reasons. Where a decision has a check, the check is the rule; this is why it is so.

### Domain decisions

These points were deliberately decided this way; bypassing them costs a lot later:

- **Points are computed, never stored** (decided 2026-11-12, review 2.1). The raw data in
  `RaceEntry` (`code`, `finish_position`, `redress_points`) is all there is;
  `app/services/standings.py::compute_event`/`compute_series` score it on every read. A
  protest decision changes one row, and the next read says so — no recompute to forget.
  `tests/architecture/test_rules.py` refuses a stored copy. A tie nothing breaks is shared
  (1, 1, 3); the series breaks ties by the acts in sailing order.
- **Series instead of League + Season.** A `Series` is a set of events scored together —
  "1st Segel-Bundesliga 2026". `Series.year` is what finds the current year and a
  league's years; the name carries the year only for display.
  Terms: see `docs/concepts.md`.
- **`Team` is the enrollment** — to a Series, to an Event, or to both.
  `event_id` empty means **registration for the Series** (Squad and public visibility depend on
  this), `event_id` set means **participation in an Event** (Pairing list, results and lineup
  depend on this). Who participates in an Event must also be registered for that Series; the
  row carries both IDs then. Both cannot be null. This also means: a club can participate in
  multiple Series, and enrollment in "DSBL 2026" does not apply in 2027.
- **A club enters one team per event — or as many as the event's `teams_per_club`
  allows** (Story VA-13, decided 2026-10-23; the Junioren-Liga has `KiYC 1` and `KiYC 2`).
  `Team.number` tells a club's teams in one event apart and names them (`KYC (SH) 2`); the
  club stays registered **once** for the series, and every team it enters is lined up
  from that one squad — a sailor may sail for team 1 at one act and team 2 at the next,
  never for two teams in one act. In the series table each team is its own row.
- **The pairing list belongs to the Event, as do the teams in it.** Draw and scoring work on
  this Event's participants, not all Series registrations. When creating an Event, Series
  registrations are pre-selected by default.
- **A club appears publicly only when enrolled.** `GET /api/clubs` filters by year;
  a newly created club is visible only in `/api/admin/clubs`.
- **Participation is public, affiliation is not.** Whoever is registered for a Series or
  entered into an Event is named publicly — the pairing list, the results and the standings
  carry that name anyway, so hiding it on the club page would be theatre. Plain club
  **membership** (an active `ClubMembership`) is different: it is shown only to that club's own
  members and organizers and to the site's `admin` (`GET /api/clubs/{id}/members`, Story
  V-10). Never widen
  the roster to guests, and never gate a squad or a lineup behind a login.
  A person may additionally switch off their own **profile page** (`Person.profile_public`, `Person` after #40,
  Story S-4) — that hides the collection (photo, club and matchday history, the page
  itself), while the **name** stays on every competition record, as plain text instead of a
  link. So: a name in a result is never hidden, and a profile page is never forced.
- **A tie is broken by places sailed: more firsts, then more seconds, …, finally the last
  race** (decided 2026-10-27, `app/scoring/low_point.py::_tiebreak_key`). Only a finish
  is a place — a redress, a penalty or a did-not-finish counts towards the points, never
  as a place. That is how the league's scoring (TracTrac) ranks; comparing scores (RRS
  A8.1 read literally) would count a redress 3.0 as a third place and ranked one tie of
  2026 the other way.
- **Who misses an Event gets that Event's participant count + 1 points.** Not showing up must
  never be better than showing up and finishing last
  (`app/services/standings.py::compute_series`).
- **The current year is the newest one not in the future** — not simply the highest ID. Otherwise
  creating "DSBL 2027" would immediately switch the public page to a year where no one is registered
  yet (`app/services/series.py`).
- **A League is what links the years: `/1-liga` is the league, its series are its years**
  (issue #14, Story B-14, `docs/site-structure.md`). The 1. and 2. Liga are **two
  leagues** (decided 2026-10-16 — each is a top-level entry of the site, like
  deutsche-segelbundesliga.de's), though they sail the same weekends; `Series.level` still
  says which division a series is. An **act** is the events of a league's year sharing a
  matchday number — one page, `/:league/:year/act-:n`. `Series.league_id` is optional:
  a series or event in no league keeps its own page at `/series/:id` / `/events/:id`.
  The current year is asked **per league**. News, press, pictures and documents come from
  the API; only the videos and the association's own texts are static content behind
  hooks (`web/src/content/`). **Nothing invented is static content**: an example belongs
  to a test's practice season (`app/practice.py`), and a notice board shows what Manage2Sail published
  (Story A-14).
- **An Event can belong to a Series, but need not.** `series_id` and `matchday`
  are optional. The normal case is an Event within a Series; a cup or training weekend stands
  alone, appears in the calendar, and scores in no Series ranking. The **Event number belongs to
  the Event**, not the Series.
- **Host club and Venue are different.** `Event.host_club_id` is the club running the Event,
  `Event.venue_id` the sailing area — and the latter is **optional** because it is often not
  set when the Event is created. `Event.logo_url` defaults to the host's emblem.
- **The Event defines the configuration.** `Event.team_count`, `boat_count` and `flight_count`
  determine everything else: `races_per_flight = ceil(team_count / boat_count)`. No magic constants
  in code.
- **Scoring rules belong to the Series** (`Series.scoring` as JSON), not in code.
  Women's and youth leagues score differently, and rules change between years.
- **External systems are matched via `ExternalId`, never by name comparison.** Club
  and team names are spelled differently in SAP Sailing, manage2sail, and here
  (`BYC (BA)`, `BYCÜ`, `KYC (SH)`). The one bridge on a first import is the club
  **code** (`app/imports/`, Story A-14) — and at Manage2Sail a code is *not* unique
  (`KYC` is Kiel and Konstanz), so there a club's key is code plus M2S's club name, and a
  shared code is never matched.
- **Boats have colors** (BLACK, GREEN, DARKBLUE, RED, GRAY, ORANGE) **and belong to the Event**,
  not the draw: the organizer assigns color and name when creating the Event; a new pairing list
  only swaps the assignment.
- **One Flight = 3 races**, each with all 18 teams, each on a different one of 6 boats.
  16 flights = 48 races per matchday.
- **Pairing lists are generated by the Java tool — in its own repository, never here**
  (decided 2026-11-11: this project runs no Java). Its `pairing_list.yml` goes into the
  catalog with `app.pairing.catalog` (below). A generator written here would have to beat
  its boat changes between flights — 0 where a simple one makes ~27 (`docs/findings.md` § 2).
- **The site never computes a pairing list; it takes the catalog's** (decided 2026-11-07,
  Story VA-3 dropped with its compute job): an optimization run takes minutes and is done
  once, offline, per configuration.
- **The catalog** (`api/app/pairing/schedules/`): per configuration
  (teams/boats/flights) **one** stored `out.yml`, computed once. A seed value shuffles starting
  positions in milliseconds and leaves every quality metric unchanged — they depend on structure,
  not names. Extend with a list the Java tool computed:
  `uv run python -m app.pairing.catalog pairing_list.yml --teams 18 --boats 6 --flights 16`.
- **Four states of an event, deliberately not one state machine** (Story VA-8,
  `app/services/event_readiness.py`): **Saving never requires validity** — title alone is
  enough, and an event with no date, no boats and the wrong number of clubs is the normal
  early state. **Publication is orthogonal to status**: `published` on `Event` and `Series`
  decides who can see it, `status` where it stands sportingly, and publishing **locks
  nothing** — a published event stays fully editable and need not be complete; public
  endpoints show published data only and answer 404 for a draft. **Validity is computed,
  never stored**, and returns a list of machine-readable reasons (the UI must say *what* is
  missing); it gates the **draw** and the **start** (`POST …/start`, which also needs a
  pairing list). **The first race freezes the configuration** — dimensions, series/matchday,
  clubs, boats, pairing list — the trigger being any race no longer `scheduled` or any
  result recorded. It **never** freezes results: correcting a result, including a protest
  decision months later, is the point of the race-committee screens.
- **Closing an event is a declaration, never a consequence** (Story VA-10). `finish`
  (`live` → `final`) is the race committee saying racing is over; it deliberately does
  **not** require a complete race list, because a day that loses its last flights to dying
  wind is still over. `cancel` works from every state, deletes nothing, and
  takes the event out of `SCORED_STATES` — so a called-off day costs nobody the
  "participants + 1" that missing an event would. Both undo via `reopen` (`final` → `live`,
  `cancelled` → `planned`, or `live` once racing had started). **"Has racing started?"
  has one answer, `event_readiness.racing_started`**, and any change to who sails before
  it clears the draw (`registrations.field_changing`) — `tests/stories/test_the_field.py`.
  Closing freezes nothing: a protest heard weeks later still has
  to land on a `final` event. The status changes **only** through these transitions
  (`app/services/event_state.py`) — `PATCH` does not carry it.
- **An event's tools are gated on what the model answers for that event**
  (`GET /api/events/{id}/access`, Story WL-3), never on `hasRole`: a summary role says
  someone is a race officer *somewhere*, not here.
- **The printed pairing list is drawn in Python, and its settings belong to the Event**
  (decided 2026-11-11, Story B-3): `api/app/pairing/pdf.py` (reportlab) keeps the layout the
  Java tool printed for years, so nothing outside the API process is needed and every
  installation can print. What varies per event is stored in `Event.print_settings`
  (JSON, like `Series.scoring`): the **organizer** sets font size, landscape and whether
  the per-team pages are included, because they know the venue and the printer. Empty is
  the normal case — the size then follows the number of rows. A boat's colour is printed
  as stored: a name the Java tool knew or the `#rrggbb` a picker produced. `?team=`
  renders one crew's own page.
- **In conflicts, the race committee wins over imports.** Otherwise polling overwrites a
  protest decision just entered. For an event **scored on SAP Sailing** (VA-14) there is
  no conflict to win: SAP is that event's one source of results, the race committee
  enters everything there, and the site refuses result entry (`event-scored-on-sap`,
  WL-5) — two places to type a result would be two results.
- **Permissions are relation tuples, `user:relation:object`, and the model is OpenFGA's
  DSL without the server** (Story Z-2, `MODEL` in `app/models/auth.py`, the facade
  `app/authz.py`, the writes `app/services/grants.py`). Object types `site`, `club`, `series`, `event`, `person`; **`MODEL` is the
  source of truth — where this paragraph or the table below disagrees, `MODEL` wins**; relations
  `admin` (site), `editor` (site, series, event — news, press and pictures, nothing
  else), `manager` (the organizer — club, series, event),
  `race_officer` (site, series, event), `jury` (series, event; the site's `jury_organizer`
  appoints `judge`s, Stories JU-*), `helper` (event — works
  the day, holds no power on it, Story VA-12), `treasurer` (club,
  event — the host club pays its events' costs, so its treasurer is every hosted event's,
  Story F-1), `guardian` (sailor — a parent the child's club linked, who accepts a
  minor's waiver online, Stories V-13, S-8), and `admin` on every object — everything
  within it, people included (a sailor's is only derived: the site's); on a club the `admin` decides who is *in* it
  and the `manager` who *sails*. `or … from …` lines say what implies what: an object's
  admin is each of its relations, a series' people are its events', the host club's
  admin and treasurer are its events', the site's race committee are managers of every event, and
  an editor of the site or a series is one of each event below it. A host club's
  `manager` (its team manager) is **not** its events' manager (review 4.1). **Every permission question goes through `app/authz.py`**, named after
  OpenFGA's API so the interpreter behind it could become an OpenFGA server: `check`
  (`User.can` is its one-line sugar), `read` for the rare place where the tuple itself is
  the fact, `list_objects`, `ensure`, objects as `ObjectRef` (`club:3`). Nothing outside
  it and `grants.py` touches the `Grant` table or walks `user.grants`, and never ask a
  summary role (`User.roles`, navigation only) or a "holds directly" shortcut what the
  model answers. `require_site` guards the league office's screens, `require_on_event` a
  route about one event. An object's admin sees and writes its tuples
  (a club's admin names its treasurer among its members — `grants.grant`). Write and delete one tuple at a time — never
  rebuild a person's rows from a list of names, that is how every per-club grant was once
  silently dropped. A club's `member` is a written tuple like the others (#52, decided
  2026-10-28), but **only the membership writes it**: `participation.activate` writes
  it when a `ClubMembership` row turns active, `participation.end` deletes it with the
  row — never the tuple API (`MEMBERSHIP` in `app/models/auth.py`). Whether someone is
  invited or asked stays on the row, outside the model. Membership implies nothing else:
  a club's `admin` need not be its member.
  A club always keeps one `admin` (Story A-8): removing the last one is refused even
  while managers remain, or nobody could add a member any more.
  Four foreign keys and one small interpreter are the whole model: no authorization
  service.
- **A member and a sailor are one `Person`, and the model knows their clubs** (decided
  2026-10-25, #40, `docs/PLAN_PEOPLE.md`; Stories V-4, Z-5, V-15). A person exists once
  and **has an account, always, with an address of its own** (#52, decided 2026-10-28,
  confirmed 2026-11-12; children included: `Person.user_id` is required,
  `people.new_person` makes both). **The address is one column, the account's**
  (`Person.email` reads `User.email`, `tests/stories/test_one_address.py`), and
  an **active** `ClubMembership` is both "member" and "sails for";
  a person's `manager` is `manager from club` over those. That one answer decides who
  puts them in a squad, changes them, signs their waiver forms and links their parents.
  **Who is in a club is its `admin`'s, who sails its `manager`'s** (decided 2026-10-28):
  only the club's admin creates people for it (a new person is a member at once), adds,
  invites or removes them; the team manager completes and corrects the club's people and
  puts its **members** in squads — never someone in no club. A second club takes consent
  (invited/requested, accepted by the other side), and a person in another club whose
  account cannot sign in yet only the league office adds — no club can simply take
  anyone. An account made with a person is **unverified** and signs in once its address
  is proven, by a code or the club's invitation; it counts as a member all the same.
  Ending an account **deactivates** it (`DELETE /api/auth/me`): sign-in and roles go,
  the account, the person and their memberships stay. An `invited` or `requested` row
  grants nothing — only `active` rows are the edge and the `member`.
- **A person can be in several clubs, and an account has no club of its own.** Membership
  and organizing (`manager` or `admin` on it) are both per
  club and independent; there is no `User.club_id` (removed 2026-09-25, Story Z-3). Which
  club a screen shows is the URL's business (`/me/club/:id`), the account remembers
  nothing; several clubs are several cards in my space, not a choice in the navigation.
  The club's page there is where its people are managed (V-8, Z-5, A-8; one *People*
  section, #45), squads registered
  (V-1) **and crews named** for the club's matchdays (V-2), reached through
  `GET /api/clubs/mine`, never through an admin-only list.
- **A club works with its people only after accepting the data processing agreement**
  (Story V-17, decided 2026-11-07, `app/services/dpa.py`): the club is controller of its
  members' data, the association its processor (Art. 28 GDPR) — **always**, for squads and
  crews too, so nobody has to draw that line. The club's `admin` accepts each version once,
  confirming they may sign for the club; until then the club's side answers
  `dpa-required` — every new club-side write calls `dpa.ensure`. The league office (site
  `admin`) acts for the association and is never held up.
- **A list is narrowed on the server, never in the browser** (Story A-13, decided
  2026-10-25): every paged list's search, sort and filters are one `ListFilter` class in
  `app/filters.py` (on `fastapi-filter`, rules in `app/listing.py`), taken with
  `ListDepends(...)` and applied as `filters.sort(filters.filter(stmt))` before
  `paginate`. A screen showing "this series' events" asks for them; a page of everything
  filtered client-side stops at the page's end without a word.
- **"Mine" has one answer, and my space is assembled from it** (Stories Z-8, S-7,
  `app/services/contexts.py`, `web/src/pages/me/`). `GET /api/me/contexts` lists every
  club, series and event a person is part of: a relation held **directly** on it, or
  **sailing** there (a squad → series, a crew → event — no tuple, reported as `sailor`).
  Site relations are not "mine" — that is the league office, `/office`. What needs the person there comes back
  as **codes with counts**, worded by the page. Each context page is built from sections
  that declare which relations show them, so a new role or panel is a line in that list,
  never a new screen per role — the screens per role (`/club`, `/reimbursements`) are what
  this replaced, and each knew only one role. A mutation that changes what needs someone
  invalidates `/api/me/contexts` along with its own data.
- **The squad's size belongs to the series, or to the event when it stands alone**
  (`squad_min`/`squad_max`, Story V-1) — never a constant in code or in the screen. The
  maximum is enforced when a squad is saved; the minimum is guidance the club screen
  shows, because a squad is built up over weeks and a club must be able to save two
  names in March.
- **The liability waiver is one statement per competition, and age picks the path**
  (Stories S-1, S-3, VA-5, `app/services/waivers.py`). A sailor signs once per **Series**
  they are registered in, which covers every event of it; an event that belongs to no
  series needs its own. The text is versioned and frozen — a new wording is a new version
  that everyone confirms again, never an edit. An **adult** confirms online from their
  own account; a **minor** on the reference date (series start, else 1 January of its
  year; event start) needs a guardian's wet-ink signature: the site prints the form
  (`GET /api/waiver/form`, reportlab) and takes the scan back
  (`POST …/waiver/scan`). The scan is the most sensitive file here: random name under
  `uploads/waivers/`, one serving endpoint that checks who asks, every look in
  `AuditLog`. A minor's **guardian** may instead accept online from their own account
  (`guardian_online`), once the child's club — its manager or admin, nobody else — linked
  that account to the child (`user:guardian:sailor`, decided 2026-10-17). A sailor who is
  not cleared **can still be lined up**: the waiver is said to the sailor, the guardian,
  the club's organizer (`crew_waiver_missing`) and the check-in list, never locked
  (Story VA-5). Without a date of birth nothing can be confirmed — the status says so
  instead of failing open. Status is **computed, never stored**, by the one function the
  account page and the organizer's check-in list both use.
- **Live updates are Server-Sent Events carrying a version token, published after the
  commit** (Story B-5, `api/app/live.py`). The browser invalidates the query keys it was
  given and refetches through the generated client — the stream never carries a second
  copy of a table, except boat positions. Publishing inside the transaction makes the
  subscriber refetch the *old* data and stay stale; that is the one trap. The hub is
  in-process, one uvicorn process, like `app/jobs.py`.
- **Races run one at a time, and one service owns their transitions**
  (`app/services/race_state.py`, Story WL-3). Recall and abandon **clear the race's
  entries** — that is what makes "unscored" true, because scoring reads `RaceEntry`, never
  `Race.status`. A race that has started once keeps the event frozen (the freeze counts
  `AuditLog` rows, not only the current status).
- **The tracker belongs to the boat, not the team, and the committee boat is a tracker
  too** (Stories L-1, L-4). Who sails which boat is what the pairing list says; the
  committee boat's phone *is* the boat end of the start and finish lines.
- **One course family: windward/leeward with a leeward gate** (Story L-2) — start line pin
  to port of the committee boat, port rounding at the windward mark, either gate mark,
  finish pin left or right. Nothing else is modelled until real data asks for it.
- **Legs, passings, distance to go and rank are derived, never stored** — the same rule as
  points. The algorithms sit behind Protocols (`api/app/tracking/`) and are chosen in one
  place, `default_pipeline()`, so a change can be decided on recorded data (a `compare.py` for that is planned).
- **A claim is on an event or on a club; the event's manager or treasurer, or the club's
  treasurer, settles it**
  (Stories F-2, F-3, decision of 2026-10-07, `app/services/expenses.py`). On an event the
  host club pays and those holding a relation *directly* on it (or its series) file; on a
  club the club pays and its members file. Who decides is checked on the **tuple** — the
  event's own manager, the treasurer by the model (the host club's included) — never
  `can(manager)`, which would hand every event's purse to the site's editors. A club's
  `manager` is its team manager and holds none of the club's money (decided 2026-10-26):
  its claims, account and payment runs are the treasurer's and the admin's. Nobody
  decides their own claim. Holder and IBAN are **copied onto the claim at submission**
  from the person's saved bank account (Story S-6), which only its owner ever reads.
- **A person's documents are seen by their organizers, and every look is logged**
  (Story S-5, `app/services/personal.py`): the managers of events they work at directly
  and of clubs they are members of. Private uploads — waiver scans, receipts, personal
  documents — share one validator and store (`app/services/uploads.py`): checked by
  content, random names, one serving endpoint each.
- **Money goes to the bank as a file, never through a bank login** (Story F-7,
  `app/services/payments.py`). A payment run turns approved claims into one `issued`
  payment per payee and one SEPA file (pain.001.001.09, `sepaxml`, XSD-validated) the
  treasurer uploads to the club's online banking; "booked" settles the run, a return fails
  one payment and its claims open again. The run keeps its message id, so the bank
  refuses the same file twice. **Decided money is frozen, and a claim is paid once**
  (decided 2026-11-11, `app/models/finance.py`): the approved total is stored at
  approval, a payment's amount at its issue, the SEPA file when the run is made; a claim
  is paid whole, and a partial unique index allows one live payment per claim — showing
  its GiroCode issues one, "Not paid" takes a hand payment back. Formats come from libraries — `sepaxml`, `schwifty` (IBAN,
  BIC), `openpyxl` (the spreadsheets), `segno` (the GiroCode for one claim, Story F-8) —
  never written by hand.
- **News and press releases are posts editorial writes on the site** (Story R-1,
  `app/routers/posts.py`): the `editor` alone (and `admin`) — the site's for every post,
  a series' or an event's for posts and pictures about that regatta, whose league they
  then appear in (`app/services/editorial.py`, decided 2026-10-24). **Editorial writes;
  it organizes nothing**: no clubs, sailors, events or rosters — that is `admin` and the
  objects' own managers. A draft until published, like an event; one league's or the
  association's. The text is HTML from a
  TipTap editor, **cleaned to an allowlist on every write** (`app/services/rich_text.py`,
  `nh3`) — the public page shows the stored HTML as it is, so nothing may reach the table
  around that cleaner. An editor library must be MIT or Apache licensed (decided
  2026-10-19), which ruled out CKEditor 5 and TinyMCE.
- **Every stored file goes through `app/storage.py`, and where it lives is a setting**
  (`SBL_STORAGE=local` under `SBL_UPLOADS_DIR`, or `s3` with the `SBL_S3_*` settings,
  decided 2026-10-27). Callers speak in keys (`clubs/3.png`), never in paths: no `Path`,
  `open` or `FileResponse` on an upload outside that module. A file is served through
  the endpoint that checks who asks, on S3 as on disk — no presigned links. **A deployment
  keeps its files in S3, and the provider is interchangeable** (decided 2026-10-27):
  `deploy/compose/` has no uploads volume, SeaweedFS is only its default provider, and a
  key means the same file everywhere, so moving between disk and S3 or between providers
  is `python -m app.storage_copy` — nothing provider-specific beyond the `SBL_S3_*`
  settings. Local disk stays for development, the tests and staging.
- **A deployment's secrets are sops-encrypted in the repository, for SSH public keys**
  (decided 2026-10-27, `.sops.yaml`, `deploy/compose/secrets.sops.env`): no age keys to
  hand out — a recipient decrypts with their `~/.ssh/id_ed25519`, as in the team's other
  repositories. Only secrets go in the file; settings stay in `.env`. Decrypted values
  reach `docker compose` as environment (`compose.sh`, `sops exec-env`), never as a file.
  A new recipient means `sops updatekeys`; `scripts/check-sops.py` fails until it is done,
  and on any value committed in plaintext.
- **An upload's type is its content, never its name** (decided 2026-10-19,
  `app/services/uploads.py::sniffed`, libmagic): a browser declares a file's type from its
  extension, so neither the name nor `content_type` is read; the browser checks early by
  first bytes (`web/src/lib/sniff.ts`). Pictures must also decode in Pillow.
- **Every picture is a library entry, fed through one import API** (Story R-2,
  `app/services/media.py`, `docs/PLAN_MEDIA.md`): editorial's uploads and every outside
  source (our `/upload` page first, later Nextcloud or Flickr bridges) end in `MediaItem`;
  a source holds an **import key** (hashed, shown once, revocable) and uses only
  `/api/import/*`. A picture may belong to an event *or* a series; a web picture is
  copied, never hot-linked — a post's text and cover take only the library's or the
  site's own addresses. **The upload is kept as it came, privately, and never served**
  (it carries the camera's location); the site serves WebP at 480/960/1600/2400 px made
  from it, a cache rebuilt from the original when a size is missing (decided
  2026-10-20). A post's text stores only the address; alt text, size and credit come
  from the library when it is read (`media.for_readers`).
- **SAP Sailing Analytics: an offline oracle for tracking, the live scoring for 2027,
  hosted by SAP** (decided 2026-11-01). For **tracking and analytics** it stays an oracle,
  never our runtime: self-hosting it for six boats is the wrong size (8 GB, MongoDB,
  RabbitMQ, one maintainer); its recorded Mövenstein dataset and its detectors are used
  once, locally, to check ours (`docs/PLAN_LIVE_IMPLEMENTATION.md` §2). For **scoring**,
  SAP runs it for the league, and the 2027 season is scored there; our own scoring stays
  for every event not scored on SAP. **Configuration flows to SAP, results flow back** —
  the two directions carry disjoint data, so neither can overwrite the other.
  **DSL→SAP** (Story VA-15): "Send to SAP Sailing", before the first race and again after
  a new draw or a withdrawal, sends the event, its teams (club code as short name), boats
  with colours and **our pairing list** race by race through SAP's REST API — refused once
  the first race froze the event (VA-8), because SAP's draw must be the one sailed.
  **SAP→DSL** (Story WL-5): every 10–30 s while live, and on request for a final event
  after a protest, the site takes raw results only through
  `app/imports/sap_results.py::apply_results` — onto the teams and races of our draw,
  **creating nothing**; an unknown competitor is reported (decided 2026-11-12, review
  6.2). Points are still derived here (`compute_event`), SAP's net points only compared.
  The pages are told only when a result changed, and each event records when SAP last
  answered and its last error, shown as "may be behind" (6.3). The SAP **leaderboard
  name is chosen once, at the first send**, and kept as the event's `ExternalId` — never
  computed again from a venue or series renamed since (6.1). The season table stays ours;
  `app/imports/sap.py` is the historical importer only. Embedding SAP's race viewer (B-20) needs SAP
  to list our domains in its frame-ancestors setting. **SAP is credited wherever its results
  show** (Story B-21, SAP's condition for using a server it hosts, 2026-11-03): under every
  act and table with a result from SAP, and in the footer — one component,
  `SapAttribution`. Tried against a local SAP: `deploy/sap-local/`.


### Logged in or guest

Most requests carry a user, but the public site also serves guests.
Endpoints open to everyone use `app/auth.py::optional_user` — which returns
`User | None`. An **invalid or expired** token is treated as "not logged in"
not an error: otherwise the public site would be unusable for someone with an old session instead
of just treating them as a guest. Protected areas still use `current_user` and respond with 401.


### Testing different roles

**Registration:** `POST /api/auth/register` creates an account and sends a confirmation code.
Until redeemed, the address is unverified (`User.email_verified`) — without proof the account
cannot request club membership. Such an account has neither role nor club. Controllable via
`SBL_ALLOW_REGISTRATION`; distinct from `allow_self_signup`, which only controls **silent**
account creation when logging in with an unknown address.

**Club membership is a `ClubMembership` row — person · club · status** (decided 2026-10-25,
##40, `docs/PLAN_PEOPLE.md`; Stories Z-5, V-15). The club's admin adds a person in no club at
once — the club knows who is in it (2026-09-24); a person **already in another club** joins
only with consent, invited by the club or asking themselves, the other side accepting. A
member leaves by ending their own membership. The club's half is
`/api/clubs/{id}/members`, the person's `/api/me/memberships` (*Me › My clubs*, *Ask to
join* on the club page); either side deletes a waiting row to decline or withdraw.

**Someone who cannot sign in yet is invited — account first, then the club** (Story
V-16, decided 2026-10-28, `app/services/invitations.py`). The club's admin sends a mail
whose link verifies the account made with the person (#52) and makes the pending
(`invited`) membership active; it works with registration closed and self-signup off,
being the club's explicit enrollment. One valid invitation per address at a time
(`invitation-pending`, naming no club), 14 days, single use, the token stored hashed; a
lapsed one is the admin's to-do `invitation_expired`.

`SBL_DEV_LOGIN=true` enables `/api/dev`: there you can list test accounts and issue access tokens
**without verification**. A role switcher then appears in the UI (bottom right). Deliberately a
separate setting, not tied to `debug` — in a reachable environment this would be a security hole,
and the server warns on startup while it is on. **Never on in production or on the Compose
staging**: `compose.yaml` fixes it off; it is for `tilt up` and `scripts/dev-stack.sh` —
and, until the Compose staging replaces it, the interim Render instance (`api/render.env`).

`app.seed_users` creates a **small cast on one club, one series, one event** — 44 accounts. **The 2026 season is real** (decided 2026-10-27,
`docs/PLAN_SEEDING.md`): the 1. and 2. Liga's 11 acts as sailed — clubs, pairing lists,
results, dates — imported from TracTrac's recorded scoreboards
(`app/seed_data/dsbl-2026/`, `app.imports tractrac`), and **the Junioren-Liga's** four acts
(decided 2026-10-23) from SAP's recorded answer (`app/seed_junioren.py`,
`app/seed_data/junioren-2026/`); `app.imports sap` refreshes them from SAP. No
source names who sailed, so the real acts have no squads or crews. **The seed holds
nothing invented**. **A test that needs a squad, a
crew or a live act builds it — through a fixture** (decided 2026-11-08): the
*practice season* (`app/practice.py`), a published series of a division's 18 real clubs
in the league `practice`, ten new people per club as its squad, and three acts — final,
live (two thirds sailed), planned — with the catalog's draw, crews and raw results. pytest
asks for `season` / `season_2` (`tests/conftest.py`, built once per run); Playwright for
`season` / `season2` (`e2e/fixtures.ts`), which build it on the stack through
`POST /api/dev/season` — dev login only, so never on a real site or staging. A test that
changes the shared season puts it back. The people who sign in are concentrated:

- **club** ASVW, a 2. Liga club: `board@asvw.example.com` (its `admin`,
  Gundram Leifert), `teams@` (its `manager`, the team manager, Gunnar Voigt),
  `treasurer@`, and every ASVW sailor — all members of it. A sailor needs an
  account to sign a waiver; a sailor of any other club has none, and the specs pick their
  adults and juniors from ASVW's squad;
- **series** the 2. Liga 2026 (`dsbl-2-2026`), ASVW's: `serie@` (its `manager`, and
  of the 1. and 2. Liga's 2027 drafts); `presse@` (its `editor`, Paula Presse — writes about its
  matchdays, organizes nothing);
  `junioren@` (Jocki Hellmich, `manager` of the Junioren-Segelliga 2026 and its 2027
  draft);
- **event** Warnemünde 2027 (`dsbl-1-2027-warnemuende`), **hosted by ASVW** — so its claims
  are ASVW's to pay and ASVW's officials are the event's too: `orga@` (manager), `regatta@`
  (race officer), `jury@`, `helfer@` (helper). A test that needs them on a practice act
  grants it there itself;
- the **league office** `admin@`, `redaktion@` (editor — the journalist, Sven Jürgensen,
  who writes and keeps pictures and organizes nothing), `wl@` (race officer, Christoph Zanter), and
  `gast@sbl.example.com` with no relation.

**Next year, to practise on** (`app.seed`, decided 2026-10-22): the 1. and 2.
Segel-Bundesliga 2027 and the
Junioren-Segelliga 2027 are **drafts**, so the public site stays on 2026.
Six weekends, with hosts (league office, 2026-11-01): Friedrichshafen (WYC with KYC,
act 1, 16–18 April), Überlingen (BYCÜ with SMCÜ, 2), Berlin (BYCB, 3), Kiel/Strande (KYC,
4 — **the 1. Liga's alone**: the 2. Liga sails one act fewer, as every year since 2018,
so it counts Warnemünde as 4 and Hamburg as 5), Warnemünde (ASVW, 5), Hamburg (NRV, 6,
14–16 October) — dates from the association's "Termine 2027" (deutsche-segelliga.de,
2026-10-13). **The 1. Liga 2027's clubs follow
from the 2026 tables** (decided 2026-11-02, `seed.py::_first_division_next_year`): places
1–14 of the 1. Liga and 1–4 of the 2. Liga, entered in all six acts with the six boats,
each with its draw. The 2. Liga 2027 has no clubs yet: its 2026 places 13–18 requalify at the
DSL-Pokal. `scripts/sap-season.py` plays the 1. Liga's season on the local SAP. **ASVW hosts Warnemünde 2027**, so its
officials are that event's organizers — and `orga@`, `regatta@`, `jury@` and `helfer@` hold
their relation on it (decided 2026-11-06). Only what was announced is seeded; nothing invented.

The role switcher groups them the same way (league office · series · event · club ·
sailors · guest, the `group` of `/api/dev/users`), the sailors folded until searched.

Test addresses use `example.com`: `.test` and `.example` are reserved domains that email validation
rejects — including in real login flows.

