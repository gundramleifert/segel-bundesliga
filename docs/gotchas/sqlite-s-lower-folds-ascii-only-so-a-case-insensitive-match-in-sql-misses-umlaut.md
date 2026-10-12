# SQLite's lower() folds ASCII only, so a case-insensitive match in SQL misses umlauts that Postgres would find

**Symptom** — The SAP import (Story A-14) linked the seed's `NRV` and `VSaW` to SAP's
codes, but created a **second** `BYCÜ` club (slug `bycue-2`) instead of linking the seed's.
The test asking for exactly one club `BYCÜ` found **none**, which looked like the club had
gone missing rather than been duplicated.

**Cause** — `func.lower(Club.short_name) == code.lower()`: Python lowers `BYCÜ` to `bycü`,
SQLite's built-in `lower()` leaves non-ASCII alone and gives `bycÜ`, so the two never meet.
`LIKE` is case-insensitive for ASCII only, too. Postgres folds Unicode, so the same query
would have worked in production — dev and production disagree, silently. What misled: the
test's own lookup used the same `func.lower`, so it reported zero clubs, hiding the
duplicate it was written to catch.

**Rule** — Never rely on SQL `lower()`/`LIKE`/`ilike` for a case-insensitive match on text
that can hold umlauts (club codes, cities, names). Compare in Python with `casefold()`
(`app/imports/common.py::club_by_code`), or store a normalised column.

**Evidence** — `sqlite3 :memory: "select lower('BYCÜ')"` prints `bycÜ`. The failing run of
`api/tests/stories/test_imports.py::TestSapImport::test_a_club_this_site_has_is_linked_not_duplicated`
before `club_by_code` compared in Python.

**Seen** — 2026-10-12
