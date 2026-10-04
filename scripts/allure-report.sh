#!/usr/bin/env bash
# One Allure report over both suites, grouped by user story.
#
#   scripts/allure-report.sh            # backend tests + browser tests (evidence mode) + report
#   scripts/allure-report.sh --no-e2e   # backend tests only, no servers needed
#   scripts/allure-report.sh --open     # … and open the report afterwards
#
# Every test is labelled with the stories it names — the backend's docstrings, the
# browser's `describeStory` titles — so the report's tree is one group per story
# (`allurerc.mjs`), with each journey's steps and each browser test's video, screenshot and
# trace attached. Nobody writes an Allure decorator; see `api/tests/conftest.py` and
# `e2e/fixtures.ts`.
#
# The browser half starts its own stacks (`scripts/dev-stack.sh --workers 4`) in this same
# shell and stops them afterwards: a server started in another sandboxed call would be
# unreachable from this one (docs/gotchas). A failing suite still produces the report —
# that is when it is most wanted — and the script exits non-zero afterwards.
set -uo pipefail

cd "$(dirname "$0")/.."
ROOT="$PWD"
LOGS="${TMPDIR:-/tmp}/sbl-allure"
mkdir -p "$LOGS"
export UV_CACHE_DIR="${UV_CACHE_DIR:-${TMPDIR:-/tmp}/uv-cache}"

E2E=1
OPEN=()
for arg in "$@"; do
  case "$arg" in
    --no-e2e) E2E=0 ;;
    --open) OPEN=(--open) ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

rm -rf "$ROOT/allure-results" "$ROOT/allure-report"
status=0

echo "▸ backend tests → allure-results/"
(cd "$ROOT/api" && uv run pytest -q -p no:cacheprovider --alluredir="$ROOT/allure-results") \
  > "$LOGS/pytest.log" 2>&1 || status=1
grep -E "^[0-9]+ (passed|failed)|[0-9]+ passed|[0-9]+ failed" "$LOGS/pytest.log" | tail -1

if [[ "$E2E" == 1 ]]; then
  echo "▸ browser tests (evidence mode) → allure-results/"
  scripts/dev-stack.sh --workers 4 > "$LOGS/stack.log" 2>&1 &
  stack=$!
  for _ in $(seq 1 180); do
    grep -q "^ready\.\|not ready\|failed" "$LOGS/stack.log" && break
    sleep 1
  done
  if grep -q "^ready\." "$LOGS/stack.log"; then
    EVIDENCE=1 node_modules/.bin/playwright test > "$LOGS/playwright.log" 2>&1 || status=1
    grep -E "^\s+[0-9]+ (passed|failed|flaky)" "$LOGS/playwright.log"
  else
    echo "  the stacks did not come up — see $LOGS/stack.log"
    status=1
  fi
  kill "$stack" 2>/dev/null
  wait "$stack" 2>/dev/null
fi

echo "▸ report → allure-report/"
node_modules/.bin/allure generate allure-results "${OPEN[@]}" > "$LOGS/allure.log" 2>&1 \
  || { echo "  allure generate failed — see $LOGS/allure.log"; exit 1; }
echo "  open allure-report/index.html (or: node_modules/.bin/allure open allure-report)"
echo "  logs: $LOGS"
exit $status
