# An account reached through selectinload(Grant.user) has no grants loaded, and a test with only the caller in the result hides it

**Symptom** — `GET /api/clubs/{id}/members` answered 500 with `MissingGreenlet:
greenlet_spawn has not been called` as soon as the roster held anyone besides the person
asking. A roster of one — the caller alone — rendered fine.

**Cause** — the endpoint loaded the club's tuples with `selectinload(Grant.user)` and then
called `user.manages_club(...)`, which reads `user.grants`. `User.grants` is
`lazy="selectin"`, but SQLAlchemy stops an eager load where the path cycles back to a
mapper it came from (Grant → User → Grant), so those users arrive with `grants` unloaded
and reading it is a lazy load in the async session. The caller's own `User` was already in
the identity map with its grants loaded by `current_user`, which is why a one-member
roster passed. What misled: `lazy="selectin"` on the relationship reads as "always
loaded", and the passing single-member case looked like proof.

**Rule** — for rows reached through another row's relationship, do not call `User`
methods that walk `grants`; derive the answer from the rows you already queried (the
roster builds `organizer`/`admin` from the relations it collected), or load the users with
an explicit `selectinload(Grant.user).selectinload(User.grants)`. And a list test needs at
least one entry that is **not** the caller.

**Evidence** — `api/app/routers/club_members.py::list_club_members` (the comment above
`members`) and
`api/tests/stories/test_club_members.py::TestMemberRoster::test_a_member_sees_the_roster_with_relations`,
which failed with this trace until `organizer`/`admin` stopped reading `user.grants`.

**Seen** — 2026-09-25
