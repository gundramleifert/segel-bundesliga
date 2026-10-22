---
id: journey-lifecycle
type: journey
order: 10
audience: [administration, event-organizer, race-committee]
stories: [A-1, A-6, VA-8, VA-6, VA-7, B-3, WL-2, B-1, VA-10, VA-9]
journey: J-1
route: null
tags: [lifecycle, season, matchday, spieltag, serie, veranstaltung, auslosung, wertung]
title: From an empty series to a scored matchday
---

## From an empty series to a scored matchday

Who: the league office, the event organizer, the race committee, the jury, a visitor.

From nothing — no clubs, series or event — to a final event whose points still change
when a protest is decided after the last race.

| Step | Who | What is then true | How |
|---|---|---|---|
| J-1.1 | League office | the clubs exist; none is shown publicly yet | [Create clubs](#admin-clubs-create) |
| J-1.2 | League office | the series exists with its clubs, as a draft nobody else can see | [Create a series](#admin-series-create) |
| J-1.3 | League office | the series is published and listed | [Publish a series](#admin-series-publish) |
| J-1.4 | Event organizer | the event exists with a title and its boats; the clubs registered for the series are its entries — today the form saves only for the league office's admin, so an organizer may need to ask them | [Create an event](#create-event-wizard) |
| J-1.5 | Event organizer | *Still missing* names what the event lacks — here the team count and the date | [Readiness](#run-event-readiness) |
| J-1.16 | Event organizer | team count and date are set; nothing is missing any more | [Configuration](#create-event-config) |
| J-1.6 | League office | the pairing list is drawn; drawing again replaces it while nothing has been sailed | [Draw](#run-event-draw) |
| J-1.7 | Event organizer | the event is in the public calendar | [Publish](#run-event-publish) |
| J-1.8 | Visitor | the pairing list can be printed — where the server cannot print, the download is not offered | the public site |
| J-1.9 | Event organizer | the event is *live* | [Start the event](#run-event-start) |
| J-1.10 | Race committee | every race has its results; the points follow from them | [Enter results](#results-entry-enter) |
| J-1.11 | Visitor | the series table has the act in it, every club with its placement | the public site |
| J-1.12 | Event organizer | dimensions, clubs, boats and pairing list are frozen; the title can still be corrected | [Frozen after the first race](#run-event-frozen) |
| J-1.13 | Jury, then race committee | the jury disqualifies a winner, months later, and a race officer enters the decision; the points and the tables follow at once | [Correct a result](#results-entry-correct) |
| J-1.14 | Race committee, through the organizer | the race committee says racing is over and the event organizer closes the event: it is *final*; results stay correctable | [Racing is over](#close-event-finish) |

Today only the league office's administration can draw a pairing list (J-1.6); an event
organizer asks the league office for it.

### If … {#journey-lifecycle-variations}

- **Draw tried before the event is ready (J-1.15):** refused with the reasons *Still
  missing* lists. Fix them (J-1.16) and draw again. [Readiness](#run-event-readiness)
