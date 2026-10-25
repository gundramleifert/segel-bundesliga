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
([terms](#terms-competition)). Only a site admin creates one; an editor's *Series* tab
shows only *Series are created by the business office only.*

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

A name whose address another series already has is refused. The screen cannot change
name, year or dates afterwards — the site would allow it, but no screen offers it yet.

![The Series tab: *New series* ①, and on each row *Edit clubs* ② and *Publish* or *Unpublish* ③](shot:help-admin-series)

### Publish a series {#admin-series-publish}

- **Draft:** the series and its events are hidden publicly; its page answers "not found",
  and its clubs are not listed through it.
- *Publish* ③ — the badge turns *Public*. It locks nothing; each event is still published on
  its own ([publish an event](#run-event-publish)).
- *Unpublish* — back to *Draft*; standings and events stay.

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

| | |
|---|---|
| *Series* tab | only the note that series are created by the business office. The manager may change their series' clubs, squad size, description and publication, but has no controls there — they ask the league office (name, year and dates no screen changes after creating) |
| *Events* tab | they organize the series' events; creating one saves only for the league office's admin today, so they ask the league office ([create an event](#create-event-wizard)) |
| *Race officer*, *Jury* | on a series: that role at each of its events |
| *Admin* | every role; names the series' people |

✕ *Remove* takes a role away. See [roles](#roles-list).

[Create a series](place:admin.new-series)
