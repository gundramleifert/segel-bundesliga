# A relationship on a row you just appended is not loaded after the commit, and reading it in the response fails with MissingGreenlet

**Symptom** — writing a tuple on an event (`POST /api/auth/tuples`) answered 500
with `sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called; can't call
await_only() here`. The same endpoint worked for a site-wide grant, and the club-scoped
rows the test seeded directly rendered fine.

**Cause** — `UserRole.event` is `lazy="selectin"`, which only means *when the row is
loaded from the database*. A row built in Python, appended to `user.role_rows` and
committed was never loaded, so `GrantOut.of(row)` touching `row.event` after the commit
was a lazy load — synchronous IO inside the async session, hence the greenlet error. What
misled: the error reads like an async-driver misuse, and the working site-wide case made
the relationship look loaded in general when it was only loaded on rows that came from a
query.

**Rule** — when a response names a related object of a row created in the same request,
hand the row the object you already fetched (`row.event = event`), or `refresh` the parent
with that relationship after the commit. The service already had the object in hand from
its existence check, so returning it from there cost nothing.

**Evidence** — `api/app/services/grants.py::grant` (the `row.event = obj` assignment),
`api/app/routers/auth.py::delete_tuple` (the account is fetched through its own query for the
same reason) and
`api/tests/stories/test_login_and_roles.py::TestTuples::test_the_same_tuple_twice_is_refused`,
which failed with exactly this trace until the assignment was added.

**Seen** — 2026-09-18
