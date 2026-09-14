# An exists() subquery over a table the outer query also joins correlates itself away, and fails with 'no FROM clauses' instead of returning nothing

**Symptom** — `GET /api/events?year=2026` answered 500 with
`InvalidRequestError: Select statement '<...Select object...>' returned no FROM clauses due
to auto-correlation; specify correlate(<tables>) to control correlation manually`. The same
endpoint without `year` worked. The traceback names a `Select` by its repr, so it points at
no line of our code and at no table.

**Cause** — `_only_public_events` builds `select(Series.id).where(Series.id ==
Event.series_id, ...).exists()`. SQLAlchemy auto-correlates every table a subquery mentions
that is already in the enclosing FROM. As long as the outer query was just `select(Event)`,
only `Event` matched and `Series` stayed in the subquery. The moment a caller added
`.join(Series, ...)` — which the year filter does, and which a search over the venue and
host would have done next — `Series` was in the outer FROM too, so the subquery correlated
*both* of its tables away and had nothing left to select from. What misled me: the error
arrived while I was adding joins for a search, so it read as "my new joins are wrong",
when the year filter alone had been raising it for as long as it had existed — untested,
because no story asked the calendar for one year.

**Rule** — an `exists()` (or any scalar subquery) that names a table a caller might also
join must say `.correlate(<the one table it means>)` explicitly. Auto-correlation is
decided by the *enclosing* query, so a helper that takes a statement from its callers
cannot rely on it: it is correct until someone joins one more table.

**Evidence** — `api/app/routers/public.py::_only_public_events` carries `.correlate(Event)`;
removing it makes `api/tests/stories/test_pagination.py::TestSearchingTheEventCalendar::test_searching_narrows_the_year_it_is_asked_for`
fail with the message above, and it was how `GET /api/events?year=2026` behaved before
2026-09-14.

**Seen** — 2026-09-14
