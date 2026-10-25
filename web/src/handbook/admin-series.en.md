---
id: admin-series
type: guide
order: 210
audience: [administration]
stories: [A-6, VA-8, A-14]
journey: null
route: /office/series/new
tags: [series, serie, year, jahrgang, publish, veröffentlichen, draft, entwurf, squad size, kadergröße]
title: Create and publish a series
---
## Create and publish a series

A series is a set of events scored together; its name carries the year
([terms](#terms-competition)). Only the site's admin creates one.

### Create a series {#admin-series-create}

1. [*League office* › *Series*](place:admin.series): [*New series*](place:admin.new-series) ①.
2. *Name*: at least three characters. *Year*, *Starts* and *Ends* are optional.
3. Tick the *Participating clubs*; they take part from the start.
4. *Create Series*.

The series is a *Draft*. *Edit clubs* ② in its row opens the rest of its setup:

- the clubs — [enter a club in a series](#admin-clubs-series);
- *Squad minimum* and *Squad maximum*, then *Save squad size*: the maximum is enforced
  when a club saves its squad, the minimum shown as a target;
- *Description*, in Markdown, on the public standings page — *Save description*;
- *People* — [the series' manager](#admin-series-manager).

Its organizers find all but *People*, and its dates, in the series' own context
([its manager](#admin-series-manager)). A name whose address another series already has
is refused. No screen changes name or year afterwards.

![The Series section: *New series* ①, and on each row *Edit clubs* ② and *Publish* or *Unpublish* ③](shot:help-admin-series)

### Publish a series {#admin-series-publish}

- **Draft:** the series and its events are hidden publicly; its page answers "not found",
  and its clubs are not listed through it.
- *Publish* ③ — the badge turns *Public*. It locks nothing; each event is still published on
  its own ([publish an event](#run-event-publish)).
- *Unpublish* — back to *Draft*; standings and events stay.
- Its organizers: [*the series* › *Dates & publication*](place:series.dates).

### Past seasons and Manage2Sail {#admin-series-import}

No screen does this: whoever runs the server imports past seasons from SAP Sailing, and an
event's entry list and notice-board documents from Manage2Sail. A club is recognised by its
*Short name*; an unknown one is created. Sailors are not imported. Imported series and
events arrive as drafts unless the import publishes them — [publish](#admin-series-publish)
them yourself. Points are computed here, and a result the race committee recorded is never
overwritten.

### Give a series its manager {#admin-series-manager}

The person has an account ([where accounts come from](#admin-accounts-create)).

1. On the series' row, *Edit clubs*.
2. Under *People*: *Email of an existing account*, *As* *Manager*, *Add*.

The manager finds the series in the context switcher, under *Organize* and *Series*:

| Section | What the manager does there |
|---|---|
| [*Clubs & registrations*](place:series.organize) | sets the clubs under *Registered clubs*; decides those under *Applications to decide* |
| [*Dates & publication*](place:series.dates) | *First day*, *Last day*; *Publish*, *Unpublish*; *Description* |
| [*Squad size & scoring*](place:series.scoring) | *Squad minimum*, *Squad maximum*; the scoring has no screen |
| [*Events*](place:series.events) | every act, drafts too; each opens the event's context, where they organize it. A new act: [*New event*](place:admin.new-event) ([create an event](#create-event-wizard)) |
| *Race committee & jury* | shown, but only the series' *Admin* names people there |

| Role on a series | |
|---|---|
| *Race officer*, *Jury* | that role at each of its events |
| *Admin* | every role; names the series' people — also at *Race committee & jury* |

✕ *Remove* takes a role away. See [roles](#roles-list).

[Create a series](place:admin.new-series)
