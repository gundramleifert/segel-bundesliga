# A test run piped into tail reports tail's exit code — a failing suite reads as green

**Symptom** — `uv run pytest -q | tail -15`, run in the background, finishes with
"exited with code 0", yet the suite has a failure, which shows up on the next run.

**Cause** — a pipeline's status is its last command's: `tail` succeeds whatever pytest
returns. What misled: the harness reports the exit code as if it were the test run's,
and the condensed output hid the one `FAILED` line.

**Rule** — never read a pass from a piped run: write the output to a file and echo
pytest's own status (`pytest … > log 2>&1; echo "exit=$?"`), or `set -o pipefail`; and
read the `passed`/`failed` summary line, not the exit code alone.

**Evidence** — 2026-11-02: a full run piped into `tail` reported exit 0 while
`tests/stories/test_imports.py::TestSapImport::test_an_imported_season_is_a_draft_until_published`
failed (a sent event's series lookup in `app/imports/sap.py` also caught imported events).

**Seen** — 2026-11-02
