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
#   scripts/check.sh --fast   # skip the backend test suite (~2 min)
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
step "ruff"            bash -c 'cd api && uv run ruff check .'
[[ "${1:-}" == "--fast" ]] || step "pytest" bash -c 'cd api && uv run pytest -q'
step "web typecheck"   bash -c 'cd web && pnpm typecheck'
step "web lint"        bash -c 'cd web && pnpm lint'
step "web build"       bash -c 'cd web && pnpm build'
step "spec typecheck"  pnpm typecheck
step "specs load"      pnpm e2e:list

printf '\n'
if (( ${#failed[@]} )); then
  printf '\033[31m%d failed: %s\033[0m\n' "${#failed[@]}" "${failed[*]}"
  exit 1
fi
printf '\033[32mall green\033[0m — e2e still needs scripts/dev-stack.sh + playwright test\n'
