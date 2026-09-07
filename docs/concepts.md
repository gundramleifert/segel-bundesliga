# Terms and Concepts

What words in this project mean. Anyone who changes something here changes the model —
which is why the reasoning is included each time.

---

## Series

**A set of events that are scored together.**
Examples: "1. German Sailing Bundesliga 2026", "Juniors 2026", "Sailing Champions League 2026".

The name includes the **year**. A series *is* a competition for one year — there is no
separate "season" anymore. The earlier separation into *league* and *season* was redundant:
it always meant a league for one year anyway, and clubs had to be assigned anew each year.
Two concepts became one.

- Model: `Series` (`api/app/models/competition.py`)
- Fields: `name` ("DSBL 2026"), `short_name`, `year`, `level`, `scoring`
- `year` serves for sorting and finding the current year, not for naming.

**The current year** is the youngest one that is *not in the future* — deliberately not
simply the highest. "DSBL 2027" is created in 2026 so clubs can be assigned; it must not
switch the public page to a year in which no one has registered yet
(`api/app/services/series.py`).

---

## Team — Also the Assignment

**A club's entry into a competition.** Model: `Team`.

There is no separate assignment table: a club entering *is* the team. It is attached to a
**series**, to an **event**, or to both:

| `series_id` | `event_id` | Meaning |
|---|---|---|
| set | empty | **Registration for the series.** Squad is attached to this; public visibility depends on it. |
| set | set | **Entry to a matchday.** Pairing list, results, and crew are attached to this. |
| empty | set | **Entry to a standalone event** without a series. |
| empty | empty | forbidden — a team without a competition does not exist. |

The principle behind this: **The pairing list is attached to the event, and so are the teams
in it.** Drawing and scoring happen among those who enter *this* event — not all who are
registered for the series.

Anyone who enters a matchday is thereby **also registered for the series**: the row carries
both identifiers, and without series registration the endpoint does not accept the entry.
The reverse does not apply — being registered for the series does not mean entering every
matchday.

This leads naturally to:

- A club can enter **multiple series** at the same time (first division, juniors, SCL).
- An assignment to "DSBL 2026" does **not** apply to "DSBL 2027" — the year is in the series.

**A club appears publicly only when assigned to at least one active series.** Creating it
requires only its name; it becomes visible through assignment. What counts is the **series
registration**, not entry to an individual matchday.

Which data hangs at which level:

| Data | Level |
|---|---|
| `RaceEntry` (pairing and result), `EventCrew` (crew), race scoring | **Entry** |
| `TeamMembership` (squad), series standings, public club list | **Series registration** |

The series standings table translates between the two via the club.

### Two Ways to Participate

`Team.status` distinguishes how an entry came about and where it stands:

| Status | Meaning |
|---|---|
| `requested` | The club has applied. Does not count anywhere. |
| `accepted` | Participant. Publicly visible, in scoring, eligible for crew selection. |
| `rejected` | Rejected, with reason. A new attempt is possible. |

Administration can **assign directly** (then immediately `accepted`) or **accept an
application**. Both end in the same row — there is no second source of truth. An entry
under which racing has already occurred cannot be revoked.

**Consent is unilateral — and intentionally so.** The administration runs the competition;
it assigns a club without asking. Only the opposite direction — the club applying — requires
consent. This distinguishes entry from **club membership**, where two equal parties face each
other and both must always consent (see below).

**Only club leadership can register.** An ordinary member cannot register a club, nor can
the race committee.

---

## Event and Act

An **event** is a date with races. It belongs to a series — or to none. There is no second
kind of event; "without series" is not a separate concept, just an empty field.

| | Series set | Example |
|---|---|---|
| **Matchday of a series** | yes, with `matchday` | "Matchday 2, Kiel" of DSBL 2026 |
| **Standalone event** | no | Cup, training weekend, invitational regatta |

Without a series, it appears in the calendar but does **not** flow into series scoring.
`series_id` and `matchday` are therefore optional.

**A series only bundles events together** — it means nothing more. In particular, it can
have **more clubs and sailors than any single one of its events**: anyone who does not enter
a matchday still belongs to the series and receives a substitute score there.

Series and event each have a **time period** (`starts_on`, `ends_on`). A fixed deadline
structure is deliberately not in place yet.

**The matchday number belongs to the event**, not to the series (`Event.matchday`).

Other fields on the event because they can vary per event:
`team_count`, `boat_count`, `flight_count` (yielding `races_per_flight = ceil(team/boat)`)
and `crew_size` — the standard scope for crew selection, a guideline, not a limit.

**Host club and venue are different:** `host_club_id` is the club hosting the event,
`venue_id` is the venue. The latter is optional — often not set at creation time.

**Boats belong to the event, not to the draw.** `Boat` is attached to the event and carries
a number, **color**, and **name** — the same boats sit at the dock regardless of how many
times the list is redraw. A new pairing list exchanges the assignment, not the boats.

---

## Squad and Crew

Two levels that must not be confused:

| | Model | Scope | Story |
|---|---|---|---|
| **Squad** of a series | `TeamMembership` | X sailors (typically: 10) | V-1 |
| **Crew** of a matchday | `EventCrew` | those who sail there (typically: 4) | V-2 |

**Only those in the squad can be selected for crew.** This is checked by `api/app/routers/crew.py`,
not by the interface. The **number is flexible** — illness, late additions, and different
formats would not work otherwise.

### One Sailor, Multiple Clubs — But Once Per Competition

**A sailor can race for multiple clubs.** For one in the first division, for another in
the juniors — this happens and is not an exception.

**Within a series or an event, however, they appear only once.** Otherwise they would
race against themselves.

| Level | Rule | Enforced by |
|---|---|---|
| Club | any number | no restriction |
| Series | at most one squad | check when registering (Story V-1) |
| Event | at most one crew | `UniqueConstraint(event_id, sailor_id)` |

At the event level, the database enforces the rule itself. At the series level it cannot be
expressed as a foreign key — `TeamMembership` knows only the team; the series is one level
up. The endpoint must check when the squad is registered; a test maintains the invariant.

---

## Club Membership — Both Sides Must Consent

**Who belongs to which club.** Model: `ClubMember` (club × account).

Not to be confused with `Team`: `ClubMember` says who is a **member**; `Team` says where the
**club competes**. A person can be in multiple clubs — the limit "once" applies only per
series and event.

Membership arises in two ways, and **both require consent from the other party**:

| Status | Meaning | Who acts |
|---|---|---|
| `pending_club` | The person has applied | the club |
| `pending_user` | The club has invited | the person |
| `active` | Member | — |
| `rejected` | Rejected, with reason; new attempt possible | — |

No one becomes a member of a club without being asked, and no club gets members without
asking. If both sides want the same — application meets invitation — the matter is decided
without a third step.

`User.club_id` is something else: the club **for which an account acts**. A person can be
in multiple clubs but always acts for only one.

---

## Pairing Catalog

A pairing list depends on only three numbers: **Teams, boats, flights**. Which club sits
at start position 7 is decided only by the assignment at publication.

Therefore it is **calculated once and stored** (`api/app/pairing/schedules/`), not newly
for each event — optimization takes minutes, lookup takes milliseconds. **Exactly one file
per configuration** is stored: the `out.yml` from the Java tool. It carries all the
information, and the configuration is read from its contents, not from the filename.

A **seed value** shuffles the start positions. This does not change quality: boat
distribution, matchups, and boat changes depend on the structure of the list, not on names.
The same seed yields the same draw — reproducible if disputed.

---

## Scoring

One direction, no paths back:

```
RaceEntry (raw data)  ->  app.scoring  ->  RaceEntry.points, EventStanding, SeriesStanding
```

**The authoritative source is the raw data** on `RaceEntry`: `code` (FINISHED, DNF, DSQ,
RDG …), `finish_position`, `redress_points`. Points are **derived** and rewritten with
every change — never set by hand. A protest decision changes one row of raw data; it never
becomes a data migration.

Stored anyway so queries, sorting, and export can read directly. **Read endpoints recalculate
fresh** so a forgotten recalculation never shows wrong numbers anywhere.

### Race Scoring

Low-point per World Sailing RRS Appendix A: finish position = points, lower is better.
Non-scoring codes count number of starters + 1, percentage penalties add a surcharge,
tie-break per A8. Discards and percentage depend on `Series.scoring`, not hardcoded.

### Series Scoring — And the Missing Clubs

The series standings table **adds the placements from matchdays**; lower is better.

**Anyone who misses a matchday receives number of starters + 1 for that matchday.** If a
club competes in matchday 1 but not matchday 2, the substitute score counts for matchday 2.
The reason is the same as for a race not sailed: **not competing must never be better than
competing and finishing last.**

Calculated in `api/app/services/standings.py::compute_series`. `SeriesStanding` records how
many matchdays a team competed in and for how many they received substitute scores —
otherwise a score could not be explained.

---

## Identity and Rights

**No passwords.** Identity comes from Google, Microsoft (checking the ID token against the
provider's keys), or via a one-time code by email. Linked via verified email address, so all
paths lead to the same account.

**Roles are separate records** and rechecked with every request so revocation takes
immediate effect: `admin`, `editor`, `race_officer`, `club_manager`.

**Guest or logged in:** The public page serves both. `optional_user` returns `User | None`;
an expired token does not make the page unusable, just makes the caller a guest.

**Public personal data is name and role — nothing else.** No email, no birth year on club or
sailor pages. Names appear on every results list anyway.

---

## Addressing

**Routes address via primary key** — short, familiar integers, not UUIDs. The `slug` remains
in responses and serves for display and search, not as an address.

---

## Errors — one machine-readable type, translated by the client

Error responses are [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457) *Problem Details*
(`application/problem+json`). The **contract is the `type`** — a stable URI reference like
`/errors/guardian-confirmation-needed`. The client maps the last segment (the *code*) to
its own wording, in its own language. The backend never ships the localized sentence as
the contract.

```json
{
  "type": "/errors/waiver-already-confirmed",
  "title": "This sailor has already confirmed the current waiver version.",
  "status": 409,
  "detail": "…",                     // optional English elaboration, for logs and curl
  "instance": "/api/series/3/waiver",
  "required_version": 2               // extension members: extra facts for the client
}
```

**Backend** (`api/app/problems.py`): a router raises `Problem(status, code, title, **extra)`
— never a `tr(locale, …)` sentence for a typed error. `title` is a fixed English summary
of the *type* (a fallback, and useful in logs); extension members carry the specifics.
Plain `HTTPException` and request-validation failures are also rendered as `problem+json`
with a generic `type` (`/errors/http-409`, `/errors/validation`) while keeping `detail`
where clients already read it — routers adopt real codes one at a time. The waiver router
(`app/routers/waivers.py`) is the worked example.

**Frontend** (`web/src/api/problems.ts`): `describeProblem()` turns a problem into a
message via the `errors` i18n namespace — `errors:<code>`, with the extension members
passed as interpolation values (`"… version {{required_version}} …"`), falling back to
`title` then `errors:unknown`. `ApiError` carries `.code` and `.problem` so a component
can branch on the code or re-translate on a language switch.

Adding a language is then a frontend-only change: `en/errors.json` and `de/errors.json`
hold every code, and no backend string needs touching.
