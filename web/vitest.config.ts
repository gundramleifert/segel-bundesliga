import { defineConfig } from "vitest/config";

// Unit tests live in `tests/` as `test_<name>.ts` (the platform's convention); a co-located
// `*.test.ts` would not run.
export default defineConfig({
  test: { include: ["tests/**/test_*.ts"] },
});
