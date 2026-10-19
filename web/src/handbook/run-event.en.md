---
id: run-event
type: guide
order: 120
audience: [event-organizer]
stories: [VA-8, VA-7, B-3, VA-12]
journey: null
route: /admin
tags: [readiness, draw, seed, publish, start, frozen, print, pdf, people, auslosung, pairing-liste, veröffentlichen, helfer]
title: "Prepare and start an event"
---
## Prepare and start an event

[*Administration*, tab *Events*](place:admin.events), *Manage*. Each block saves on its own, even on an
incomplete event.

### What is still missing {#run-event-readiness}

*Still missing* lists what blocks the draw and the start; when nothing does:
*Ready: this event can be drawn and started.*

| It says | What to do |
|---|---|
| the clubs entered do not match the setup | tick or untick clubs under *Clubs entered: … of …*, then *Enter … clubs* ② |
| no date yet | set *Starts on*, press *Save date* ① |
| no pre-computed list for this size, or the boats do not match | the panel cannot change the size or the boats — ask the league office |

![The panel: what is still missing, *Save date* ①, the clubs and *Enter … clubs* ②, the draw ③](shot:help-event-readiness)

### Draw the pairing list {#run-event-draw}

Today only the league office's administrators draw: when *Still missing* is empty, ask
them. The event's manager sees *Draw* ③, but gets a permission error.

- The *Draw seed* shuffles the pre-computed list's starting positions; the same seed
  gives the same draw, provable later.
- *Draw again* replaces the list until the first race starts.

### Publish {#run-event-publish}

- *Publish* (under *Publication and start*): the event appears on the public site, where
  it did not exist before. Locks nothing, needs nothing complete.
- *Unpublish*: a draft again; pairing list and results stay.
- An unpublished series hides its events ([states of an event](#terms-event-states)).

### How the list prints {#run-event-print}

*How it prints*: *Font size* (empty is *automatic*), *Landscape*, *One page per team*,
then *Save print settings*. The PDF is on a published event's public pairing list, if
this installation can print; else no link.

### Start {#run-event-start}

*Start event* needs an empty *Still missing* and a pairing list; until then it is
disabled and says why. A date passing never starts an event; the event's race officers
may also start it. Then: *Running*, and *Race control* leads to the
[race committee's screen](#race-control-start).

### After the first race {#run-event-frozen}

Once a race has started (even one later recalled) or a result is recorded, the panel
says *Racing has started …*.

| Fixed | Still editable |
|---|---|
| size, series and act, clubs, boats, pairing list | dates, publication, print settings, results — a protest decision months later still lands |

### People on the event {#run-event-helpers}

*People*: *Email of an existing account*, *As* (*Race officer*, *Jury*, *Helper* …),
*Add*; ✕ removes.

| | |
|---|---|
| a *Helper* (RIB, pontoon, boats) | has no power on the event, but may [file a claim](#file-a-claim-where); its organizers may see their documents |
| who writes here | on screen, the event's own admin, its series' admin and the league office; a manager alone gets an error, and the host club's admin cannot reach this panel — ask one of them |

[Open the administration](place:admin.events)
