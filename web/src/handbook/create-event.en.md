---
id: create-event
type: guide
order: 110
audience: [event-organizer]
stories: [VA-6, A-2, A-10]
journey: null
route: /office/events/new
tags: [new event, matchday, act, boats, colors, wizard, veranstaltung anlegen, spieltag, boote, zuschnitt]
title: "Create an event"
---
## Create an event

May create one: the league office and its race committee, any event; a series' manager
the acts of their series, with any club as host; a club's manager an event their own
club hosts outside a series. The form offers only what you may pick — your series, the
hosts you may name — and *＋ New event* is there only if you may create one. Every
screen of the league office and of My space works on a phone: a table wider than the screen scrolls sideways,
the page itself does not.

### The three steps {#create-event-wizard}

1. The league office: [*League office* › *Events*](place:admin.events),
   [*＋ New event*](place:admin.new-event). A club's organizer:
   [*your club* › *Hosting*](place:club.hosting), *+ New event*. A series' manager:
   [*the series* › *Events*](place:series.events), *+ New event*.
2. *General data*: only *Name* ① (three characters or more) is required. *Create Event*
   ② saves a draft nobody else sees.
3. *Clubs*: tick the entrants, then *Enter … clubs and continue*. In a series only its
   registered clubs can enter, already ticked; outside a series, any club.
4. *Pairing list*: [the draw](#run-event-draw).
5. The last screen: *Ready for the event 🚀*, or *Saved — not ready yet* with what is
   missing; plus *Publish*.

Steps 2 and 3 have *Skip for now*; finish the rest in the event's own context in My
space ([what is missing](#run-event-readiness)).

![The first step: *Name* ①, dates, series, host club, size and boats, *Create Event* ②](shot:help-event-wizard)

### Size, series and dates {#create-event-config}

| Field | |
|---|---|
| *Teams and boats* | only sizes with a pre-computed pairing list; another size must be added first — the form names whom to ask |
| *Flights* | 1 to that list's length; a shorter day sails its first flights. Below: races per flight (teams ÷ boats, rounded up) and the total |
| *Series* | empty: the event stands alone, in no series table; set: it becomes the next act by itself |
| *Starts on* | may stay empty, but without a date no draw or start |
| *Ends on* | empty: a one-day event; an end before the start is refused |
| *Host club* | may stay *- to be determined -* |

Until the first race, all of it can be changed in [*the event* › *General*](place:event.organize);
then size, series and clubs are fixed ([after the first race](#run-event-frozen)).

### Boats {#create-event-boats}

- One row per boat, in league colours, named *Boat 1*, *Boat 2* … — its call on the water.
- *Color*: a named colour, the colour picker, or text such as `#ff69b4`; picker or text
  switches the list to *Custom …*.
- Every boat needs a *Name*, or *Create Event* stays disabled.
- Boats belong to the event: a new draw changes who sails which boat, not the boats.
  Colours and names can be changed in [*the event* › *Boats*](place:event.boats) until the first race.

[Create an event](place:admin.new-event)
