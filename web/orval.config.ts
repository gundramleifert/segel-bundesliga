import { defineConfig } from "orval";

/** Generates the API client and its React Query hooks from the backend's OpenAPI document.
 *
 * Run it through `scripts/gen-api-client.sh`, which produces the document from the FastAPI
 * app object first — there is no server to start and no way to generate against a stale
 * build.
 *
 * Everything under `src/api/generated/` is written by this and must never be edited: the
 * whole point is that a changed response shape breaks `pnpm typecheck` instead of the page
 * in someone's browser. Hand edits there are lost on the next run without a word.
 */
export default defineConfig({
  sbl: {
    input: {
      target: "./openapi.json",
    },
    output: {
      // One file rather than `tags-split`: the tags on the backend grew organically
      // (`admin` *and* `administration`), so splitting by them would invent a folder
      // structure that matches nothing. The import path is `api/generated` either way.
      mode: "single",
      target: "./src/api/generated/sbl.ts",
      schemas: "./src/api/generated/model",
      client: "react-query",
      httpClient: "fetch",
      // No prettier run on the output — it is generated, nobody reads the diff, and the
      // formatting pass doubles the generation time.
      prettier: false,
      override: {
        // Our own fetch: the bearer token, and RFC 9457 problem bodies turned into
        // `ApiError` so every screen keeps reporting failures the same way.
        mutator: {
          path: "./src/api/http.ts",
          name: "http",
        },
        query: {
          // The hooks pass Query's AbortSignal through, so navigating away actually
          // cancels the request rather than leaving it to resolve into a dead component.
          signal: true,
        },
        fetch: {
          // The hooks resolve to the response body, not to `{ status, data, headers }`.
          // The wrapper only makes sense when a caller reads status codes, and none here
          // does: a failure throws an `ApiError` out of the mutator instead, which is what
          // TanStack Query wants and what every screen already handles.
          includeHttpResponseReturnType: false,
        },
      },
    },
  },
});
