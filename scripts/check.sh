#!/usr/bin/env bash
# Everything that has to be green before a commit, in the order that fails fastest.
#
# Not a CI script — it is the list you would otherwise have to remember, and the reason it
# exists is that the pieces are easy to *half*-run. Two traps in particular:
#
#   * `tsc --noEmit` checks **nothing** in this Vite template (it uses project references).
#     The real check is `pnpm typecheck`, i.e. `tsc -b`.
#   * The Playwright specs and `playwright.config.ts` are not covered by the web project at
#     all. They have their own tsconfig at the repo root — which is the only thing that
#     catches a config option that has silently moved between Playwright versions
#     (docs/gotchas/playwright-moved-reducedmotion-into-contextoptions.md).
#
# The e2e suite is deliberately NOT run here: it needs servers (scripts/dev-stack.sh) and a
# throwaway database, so it is a separate, deliberate step.
#
#   scripts/check.sh          # everything
#   scripts/check.sh --fast   # skip the backend test suite (~40 s)
set -euo pipefail

cd "$(dirname "$0")/.."
export UV_CACHE_DIR="${UV_CACHE_DIR:-${TMPDIR:-/tmp}/uv-cache}"

failed=()
step() {
  local name="$1"; shift
  printf '\n\033[1m▸ %s\033[0m\n' "$name"
  if "$@"; then
    printf '  ok\n'
  else
    printf '  FAILED\n'
    failed+=("$name")
  fi
}

step "docs"            python3 scripts/check-docs.py
# The agent sandbox shows a denied path as an empty file; staged, it would overwrite real
# configuration elsewhere with nothing (.gitignore, "Claude Code's local state").
step "claude files"    bash -c '! git ls-files -co --exclude-standard .claude | xargs -r -d "\\n" find 2>/dev/null -maxdepth 0 -type f -empty | grep .'
step "ruff"            bash -c 'cd api && uv run ruff check .'
# One process per core (pytest-xdist): each worker imports conftest.py and so gets a
# database and an uploads directory of its own. ~40 s instead of ~90 s.
[[ "${1:-}" == "--fast" ]] || step "pytest" bash -c 'cd api && uv run pytest -q -n auto'
step "web typecheck"   bash -c 'cd web && pnpm typecheck'
step "web i18n"        bash -c 'cd web && pnpm check:i18n'
# A shade class (`text-slate-500`) has one value; a page naming one breaks in the other theme.
step "web colours"     bash -c 'cd web && pnpm check:colours'
step "web lint"        bash -c 'cd web && pnpm lint'
step "web build"       bash -c 'cd web && pnpm build'
step "spec typecheck"  pnpm typecheck
step "specs load"      pnpm e2e:list

printf '\n'
if (( ${#failed[@]} )); then
  printf '\033[31m%d failed: %s\033[0m\n' "${#failed[@]}" "${failed[*]}"
  exit 1
fi
printf '\033[32mall green\033[0m — e2e still needs: scripts/dev-stack.sh --workers 4, then playwright test\n'
