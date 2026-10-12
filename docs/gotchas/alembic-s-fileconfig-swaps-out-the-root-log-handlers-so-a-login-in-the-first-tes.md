# Alembic's fileConfig swaps out the root log handlers, so a login in the first test's fixture finds no code in caplog

**Symptom** — `IndexError: list index out of range` at `code = caplog.records[-1]...` in
`tests/stories/test_login_and_roles.py::login_as`, reported as an **ERROR** (setup), on
exactly one test: the first one of the run, and only when it signs in from a fixture
(`test_waiver.py`'s `version_two`). The same file passes when another file runs first, so
the full suite was green and only a single-file run showed it.

**Cause** — the session fixture `seeded` runs the migrations inside the first test's setup,
and `alembic/env.py` called `logging.config.fileConfig(alembic.ini)`, which replaces the
root logger's handlers — including the one `caplog` had just attached for that setup
phase. The mail warning carrying the code went nowhere. What misled: it looked like an
order dependency between test files, not like logging.

**Rule** — anything that calls `fileConfig` (or `dictConfig`) inside a test run takes
`caplog` down with it. The suite sets `config.attributes["configure_logger"] = False` and
`env.py` honours it (Alembic's own cookbook pattern); keep it that way.

**Evidence** — `uv run pytest -q tests/stories/test_waiver.py`: `22 passed, 1 error`
without the attribute, `23 passed` with it.

**Seen** — 2026-10-12, pruning the backend suite.
