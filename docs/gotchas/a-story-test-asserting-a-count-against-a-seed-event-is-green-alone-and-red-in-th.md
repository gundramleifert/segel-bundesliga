# A story test asserting a count against a seed event is green alone and red in the full suite, because another story added a participant to that same event

**Symptom** — A new story test for `GET /api/events/{id}/crew` asserted
`len(teams) == 18` against the seed's planned matchday `dsbl-1-2026-act-3`. Run on its own
(`pytest tests/stories/test_visitor.py -k TestMatchdayCrew`) it passed. In the full run the
same assertion failed, with nothing in the endpoint changed in between — which reads as a
flaky endpoint or a leaking session.

**Cause** — The seed database is **session-scoped and shared by every story test**
(`tests/conftest.py::seeded`), and other stories *write* to the same seed rows:
`test_participation.py` gets a nineteenth club accepted into act 3, and `test_lineup.py` and
`test_sailors_and_squads.py` rewrite act 3's lineups. What misled me: the test passing in
isolation looked like proof the endpoint was right, so the full-run failure looked like a
different, new problem rather than the same assertion being wrong all along.

**Rule** — Never assert an exact count, or a specific crew, against a seed row that another
story can add to. Either derive the expectation from the same request (compare sets, assert
per-row invariants), or pick a seed row nothing else mutates — the **finished** matchday
`dsbl-1-2026-act-1` is the stable one, because a sailed event's configuration is frozen
(Story VA-8) so no story can enter a further club in it. And before believing a new story
test, run the **whole** suite once: a story test that has only ever been run with `-k` has
not been tested against the state the suite actually creates.

**Evidence** — `api/tests/stories/test_visitor.py::TestMatchdayCrew` (its class docstring
names this); `api/tests/stories/test_participation.py:343`;
`api/tests/conftest.py::seeded`. The failing run:
`1 failed, 461 passed` with `-k TestMatchdayCrew` green immediately before it.

**Seen** — 2026-09-14
