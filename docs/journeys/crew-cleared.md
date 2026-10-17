# J-5 ◐ A club's crew is cleared for a matchday

As a **club** I want **to register who may sail for us, name the crew for a matchday and
get every one of them cleared — the liability waiver accepted online by an adult, and for
a minor by their guardian: online from the parent's own account the club linked, or on
paper** — so that **the organizer's check-in list is green before anyone
reaches the dock**. The squad belongs to the series (or to an event that stands alone),
the crew to one matchday, the waiver to the competition: three things the club does at
three different times, and each one is the next one's input.

Who: team manager, sailor, guardian, event organizer
Starting point: the club is registered for a published series and entered in one of its
matchdays (or entered in an event in no series); the event has its organizer; the waiver
text is in force; the club's sailors exist, each with an account under their address.
Goal: every sailor in the club's squad shows "cleared" on the event's check-in list.

### Main path — a series matchday, an adult crew

```mermaid
sequenceDiagram
  actor TM as Team manager
  participant P as Site
  actor S as Sailor
  actor O as Event organizer

  TM->>P: [J-5.1] registers the squad for the series
  Note over TM,P: too few? — branch "squad too small" — an event in no series — branch "stand-alone event"
  TM->>P: [J-5.5] names the crew for the matchday, from the squad only
  P-->>S: [J-5.6] my space: the competition's waiver is missing
  P-->>TM: [J-5.17] my space: a crew member's waiver is not cleared yet
  Note over S,P: no date of birth? — branch "no date of birth"
  S->>P: [J-5.8] reads the waiver and confirms it online
  Note over S,P: a minor — branch "guardian online" or "on paper"
  O->>P: [J-5.14] opens the event's check-in list
  P-->>O: every squad member cleared, scans on file for minors
  Note over P: the public matchday page lists the crew (B-12)
```

### Branch "squad too small" — fewer than the series' minimum

After J-5.1; saved anyway, completed later.

```mermaid
sequenceDiagram
  actor TM as Team manager
  participant P as Site

  P-->>TM: [J-5.2] "3 of 4–10" — guidance, saved anyway — my space says so
  TM->>P: [J-5.3] completes the squad later
```

### Branch "stand-alone event" — an event in no series

Instead of J-5.1; the main path goes on at J-5.5.

```mermaid
sequenceDiagram
  actor TM as Team manager
  participant P as Site

  TM->>P: [J-5.4] registers the squad on the club's entry to the event
```

### Branch "no date of birth" — the age cannot be judged yet

Before the waiver, after J-5.17.

```mermaid
sequenceDiagram
  actor S as Sailor
  participant P as Site

  S->>P: [J-5.7] enters their date of birth
```

### Branch "guardian online" — a minor, a parent's account linked

Instead of J-5.8; the main path goes on at J-5.14.

```mermaid
sequenceDiagram
  actor TM as Team manager
  actor G as Guardian
  participant P as Site

  TM->>P: [J-5.15] links the parent's account to the sailor as guardian
  G->>P: [J-5.16] reads the waiver and accepts it for the child online
```

### Branch "on paper" — a minor, the guardian signs the form

Instead of J-5.8; the sailor uploads the scan (or the club does — branch "club uploads"),
and the main path goes on at J-5.14.

```mermaid
sequenceDiagram
  actor S as Sailor
  actor G as Guardian
  participant P as Site

  S->>P: [J-5.9] downloads the guardian form (an own click is refused)
  S->>G: [J-5.10] hands the form over
  G-->>S: [J-5.11] signs it on paper
  S->>P: [J-5.12] uploads the signed scan
```

### Branch "club uploads" — the club collects the signed forms

Instead of J-5.12.

```mermaid
sequenceDiagram
  actor S as Sailor
  actor TM as Team manager
  participant P as Site

  S-->>TM: hands in the signed form
  TM->>P: [J-5.13] uploads the signed scan for the sailor
```

| Step | Path | Story | Who | What is then true |
|---|---|---|---|---|
| J-5.1 | series | V-1 | team manager | the squad is saved on the club's series registration, within the series' maximum |
| J-5.2 | squad too small | V-1 | site | below the series' minimum: the squad says `squad_min`, my space shows `squad_below_min` — and it is saved |
| J-5.3 | squad too small | V-1 | team manager | the squad reaches the minimum; the need is gone |
| J-5.4 | stand-alone event | V-12 | team manager | the squad is saved on the event entry, within the event's own limits |
| J-5.5 | main | V-2 | team manager | the crew is named for the matchday — only from the squad |
| J-5.6 | main | Z-8 | site | each sailor's my space shows `waiver` on the series (or the stand-alone event) |
| J-5.17 | main | VA-5 | site | the club's card in the manager's my space shows `crew_waiver_missing` — the crew stays named, nothing is locked |
| J-5.7 | no date of birth | S-2 | sailor | the age can be judged; until then the page says "add your date of birth first" and confirming is refused (`waiver-birth-date-required`) |
| J-5.8 | adult | S-1 | sailor | an `online` confirmation of the version in force; the sailor is cleared for every event of the series |
| J-5.15 | guardian online | V-13 | team manager | the parent holds `guardian` on the sailor — only the child's club may link |
| J-5.16 | guardian online | S-8 | guardian | a `guardian_online` confirmation from the parent's own account; the minor is cleared, nothing on paper |
| J-5.9 | on paper | S-1 | sailor | the form PDF with the wording, name, date of birth and competition; an online click is refused (`guardian-confirmation-needed`) |
| J-5.10 | on paper | S-1 | sailor (offline) | the guardian has the form |
| J-5.11 | on paper | S-1 | guardian (offline) | the form is signed |
| J-5.12 | sailor uploads | S-1 | sailor | a `guardian` confirmation with the scan; the sailor is cleared |
| J-5.13 | club uploads | S-1 | team manager | the same, recorded by the team manager for a form the club collected |
| J-5.14 | main | VA-5 | event organizer | the check-in list shows every squad member `cleared`, nothing outstanding, the minors' scans on file |

Retired steps: none

The check-in list (J-5.14) lists the club's whole **squad**, not only the crew named in
J-5.5 — the waiver is per competition, and whoever may still be lined up has to be
cleared. Steps J-5.10 and J-5.11 happen on paper and no test can walk them.

Decided 2026-10-17 (VA-5): a sailor whose waiver is not cleared **can** be lined up —
the crew (J-5.5) comes before the waiver, and stays — but the waiver has to be filled:
my space says so to the sailor (J-5.6), to their linked guardian (S-8) and to the club's
organizer (J-5.17), and the check-in list (J-5.14) to the organizer. A minor's guardian
accepts online once the club linked their account (J-5.15, J-5.16); paper stays the way
for everyone else.

Tests: `api/tests/stories/test_journey_crew.py::TestACrewIsClearedForAMatchday::test_adult_crew_for_a_series_matchday`, `api/tests/stories/test_journey_crew.py::TestACrewIsClearedForAMatchday::test_minor_crew_with_a_guardian`, `api/tests/stories/test_journey_crew.py::TestACrewIsClearedForAMatchday::test_stand_alone_event`, `api/tests/stories/test_journey_crew.py::TestACrewIsClearedForAMatchday::test_minor_crew_with_a_linked_guardian`
