---
id: run-event
type: guide
order: 120
audience: [event-organizer]
stories: [VA-8, VA-7, B-3, VA-12, VA-13]
journey: null
route: /office/events
tags: [readiness, draw, seed, publish, start, frozen, print, pdf, people, auslosung, pairing-liste, veröffentlichen, helfer]
title: "Prepare and start an event"
---
## Prepare and start an event

Everything is in the event's own context in My space — the league office opens it from
[*League office* › *Events*](place:admin.events). Each section saves on its own, even on
an incomplete event.

### What is still missing {#run-event-readiness}

*Still missing* lists what blocks the draw and the start — in
[*the event* › *Publication*](place:event.publication), and on a planned event's
*Overview*. When nothing does:
*Ready: this event can be drawn and started.*

| It says | What to do |
|---|---|
| the clubs entered do not match the setup | [*the event* › *Clubs*](place:event.clubs): tick or untick clubs under *Teams entered: … of …*, then *Enter … clubs* |
| no date yet | [*the event* › *General*](place:event.organize): set *Starts on*, press *Save date* |
| no pre-computed list for this size, or the boats do not match | *General*: pick another *Teams and boats*, then *Save*; colours and names are under *Boats* |

A club sailing several teams: raise *Teams per club* (*General* or *Clubs*), then set
*Teams of …* for that club. Its teams, `ASVW`, `ASVW 2`, …, all line up from its one squad.

![The event's *Publication*: whether it is ready, and *Publish* or *Unpublish*](shot:help-event-readiness)

### Draw the pairing list {#run-event-draw}

[*the event* › *Pairing list*](place:event.pairing) shows *Draw*, but today only
league office administrators may draw; others get a permission error. Ask them once
*Still missing* is empty.

- The *Draw seed* shuffles the starting positions; the same seed gives the same draw,
  provable later.
- *Draw again* replaces the list until the first race starts.

### Publish {#run-event-publish}

- *Publish* (*Publication*, under *Publication and start*): the event appears on the
  public site. Locks nothing, needs nothing complete.
- *Unpublish*: a draft again; pairing list and results stay.
- An unpublished series hides its events ([states of an event](#terms-event-states)).

### How the list prints {#run-event-print}

*How it prints*, below the draw: *Font size* (empty is *automatic*), *Landscape*, *One
page per team*, then *Save print settings*. A published event's public pairing
list carries the PDF, if this installation can print.

### Start {#run-event-start}

*Start event* is in [*the event* › *Race control*](place:event.race), for its organizers
and race officers. It needs an empty *Still missing* and a pairing list; until then it is
disabled and says why. A date passing never starts an event. Then *Open race control*
leads to the [race committee's screen](#race-control-start).

### After the first race {#run-event-frozen}

Until then, *General* and *Boats* change everything set at creation; a new size discards a
drawn pairing list. A started race (even one later recalled) or a result fixes the setup;
*Publication* then says *Racing has started …*.

| Fixed | Still editable |
|---|---|
| size, series and act, teams per club, clubs, boats, pairing list | title, host club, venue, dates, publication, print settings, results — a protest decision months later still lands |

### People on the event {#run-event-helpers}

[*the event* › *People*](place:event.people): *Email of an existing account*, *As*
(*Race officer*, *Jury*, *Helper* …), *Add*; ✕ removes.

| | |
|---|---|
| a *Helper* (RIB, pontoon, boats) | has no power on the event, but may [file a claim](#file-a-claim-where); its organizers may see their documents |
| who writes here | the admin of the event, of its series or of its host club, and the league office; a manager alone sees the section but gets an error — ask one of them |

[Open the event in My space](place:event.overview)
