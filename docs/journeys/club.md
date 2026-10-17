# J-2 ◐ A new club gets going and runs itself

As the **association** I want **a club to be set up once by the league office and then to
run itself** — its own admin, its crest, its organizers, its applications to compete — so
that **nobody at the league office maintains a club's people, and the club appears in
public exactly when it competes**.

Who: league office, club manager, visitor
Starting point: a running installation; the club does not exist. The person who will
organize the club's sailing has an account already (registered herself, Story Z-4 —
Journey J-3 shows that part). A published series of the current year exists.
Goal: the club has an admin and a manager of its own, a crest, and is a participant of a
series — and therefore listed publicly.

```mermaid
sequenceDiagram
  autonumber
  actor A as League office
  actor CM as Club manager
  participant P as Site
  actor V as Visitor

  A->>P: [J-2.1] creates the club — name, abbreviation, city
  V->>P: [J-2.2] looks for it in the club list
  P-->>V: not listed — it competes nowhere yet
  A->>P: [J-2.3] creates the first person's account and makes them the club's admin
  CM->>P: [J-2.4] opens my space
  P-->>CM: the club as a card, "admin"
  CM->>P: [J-2.5] uploads the crest
  opt tries to step down while the only organizer
    CM->>P: [J-2.6] deletes their own admin tuple
    P-->>CM: refused — at least one organizer must remain
  end
  CM->>P: [J-2.7] names a second club manager, by email
  CM->>P: [J-2.8] applies for the series
  A->>P: [J-2.9] accepts the application
  V->>P: [J-2.10] finds the club in the list and opens its page
```

| Step | Path | Story | Who | What is then true |
|---|---|---|---|---|
| J-2.1 | main | A-1 | league office | the club exists, its address made from the abbreviation |
| J-2.2 | main | A-7 | visitor | the club is not in the public club list — it competes nowhere yet |
| J-2.3 | main | A-8 | league office | the account exists (verified by administration) and holds `admin` on the club |
| J-2.4 | main | Z-8 | club manager | my space lists the club, with the relation `admin` |
| J-2.5 | main | V-3 | club manager | the crest is stored; the club's `logo_url` points at it |
| J-2.6 | last organizer | A-8 | club manager | refused with `last-organizer` (409); the club keeps its admin |
| J-2.7 | main | A-8 | club manager | a second person holds `manager` on the club — no acceptance step |
| J-2.8 | main | V-5 | club manager | an application for the series, status `requested`; still not public |
| J-2.9 | main | A-9 | league office | accepted: the club is a participant of the series |
| J-2.10 | main | B-7 | visitor | the club is in the public list, and its page shows the series |

Retired steps: none

Open: V-11 ("manage our own club page" — description, contact) is ○ and so not a step.
(Drawing this journey found that a club's admin had no screen for the crest, J-2.5; since
2026-10-17 it is on the Members tab of the club's page in my space.)

Tests: `api/tests/stories/test_journey_club.py::TestANewClubRunsItself::test_from_nothing_to_a_public_club`
