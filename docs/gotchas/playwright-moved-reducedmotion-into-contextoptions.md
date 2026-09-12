# Playwright accepts unknown `use` keys silently — `reducedMotion` moved under `contextOptions`

**Symptom** — `use: { reducedMotion: "reduce" }` in `playwright.config.ts` ran without any
error and appeared verbatim in `testInfo.project.use`, yet had no effect. The type check
was the only thing that objected: *"'reducedMotion' does not exist in type UseOptions"*.

**Cause** — As of Playwright 1.62 the option lives at `use.contextOptions.reducedMotion`.
The config loader does not reject unknown top-level `use` keys, so a stale spelling is
carried around and quietly ignored.

**Rule** — Run `pnpm typecheck` at the repo root after editing `playwright.config.ts`; it
is the only thing that catches a silently-ignored option. When an option "has no effect",
confirm it is still spelled where the installed version expects it —
`node_modules/.pnpm/playwright@*/node_modules/playwright/types/test.d.ts` is the authority,
not a remembered example.

**Evidence** — `playwright.config.ts`; the root `tsconfig.json` exists to typecheck the
specs and the config.

**Seen** — 2026-09-11.
