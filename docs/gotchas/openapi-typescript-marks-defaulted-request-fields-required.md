# A field with a server-side default is *required* in the generated request type

**Symptom** — After regenerating `web/src/api/schema.d.ts`, `createEvent({...})` stopped
typechecking: `published` was missing. The backend has defaulted it since it was written and
nothing about it had changed.

**Cause** — `openapi-typescript` marks a request-body field as required whenever the schema
does not list it as optional, regardless of a default. The types had simply been stale long
enough that the discrepancy looked like a new bug.

**Rule** — Regenerating the schema surfaces old drift as if it were new breakage. Pass
defaulted request fields explicitly (`published: false`) rather than loosening the type. And
when the generated types suddenly disagree with working code, suspect the *types* were out
of date, not the code — the same regeneration exposed three long-dead German schema names
(`KatalogEintragOut`, `KaderOut`, `KaderEintrag`).

**Evidence** — `web/src/api/client.ts`; regenerate with `pnpm gen:api` in `web/` against a
running backend.

**Seen** — 2026-09-09, commit `56b5e48`.
