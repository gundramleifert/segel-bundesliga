import { test as base } from "@playwright/test";

/** The `test` every spec here imports — Playwright's, pointed at this worker's own stack.
 *
 * The suite used to run on one worker because every spec talks to one database and
 * `lifecycle.spec.ts` writes to it: run two at once and a test reads a list while another
 * is changing it. Ordering those writes is not possible and not the point — the fix is to
 * stop sharing the data. `scripts/dev-stack.sh --workers N` runs N stacks, each with its
 * own SQLite file, and this hands worker *i* the *i*-th of them.
 *
 * `baseURL` is an option fixture, which is why this works at all: a worker cannot change
 * `use.baseURL` in the config, but it can override the fixture that provides it, and every
 * spec navigates with relative paths.
 */
export const test = base.extend<object, { stackBaseURL: string }>({
  // Worker-scoped: computed once per worker rather than per test.
  stackBaseURL: [
    async ({}, use, workerInfo) => {
      // `parallelIndex`, **not** `workerIndex`. `workerIndex` counts every worker the run
      // has ever started and keeps climbing as workers are replaced after a failure — it
      // reached 5187 here, addressing servers that were never started. `parallelIndex` is
      // the slot, 0 .. workers-1, which is what "the n-th stack" means.
      await use(`http://127.0.0.1:${5173 + workerInfo.parallelIndex}`);
    },
    { scope: "worker" },
  ],
  baseURL: async ({ stackBaseURL }, use) => {
    await use(stackBaseURL);
  },
});

export { expect } from "@playwright/test";
