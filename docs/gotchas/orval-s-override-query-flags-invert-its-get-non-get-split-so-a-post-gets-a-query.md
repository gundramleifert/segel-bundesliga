# orval's override.query flags invert its GET/non-GET split, so a POST gets a query hook

**Symptom** — after generating the client, `useCreateClub` was a **query** hook:
`getCreateClubQueryOptions`, a `queryFn` that POSTs on render, and no `mutationFn`
anywhere. Meanwhile `useListSeries` had grown a `getListSeriesMutationOptions`. Across the
file the split was exactly backwards: 55 mutations for the 35 GETs and 35 queries for the
55 writes.

**Cause** — `output.override.query.useQuery: true` and `useMutation: true` in
`web/orval.config.ts`. They read like "generate query hooks, and mutation hooks too", but
they mean "**also** generate a query hook for operations that would not get one" and the
same for mutations — so setting both asks for the opposite variant of every operation, and
the wanted one is not produced. What misled me: the two flags sit under `query`, which
looks like a section describing how queries are generated, not a pair of per-operation
overrides.

**Rule** — leave `useQuery` / `useMutation` out of `override.query` unless you specifically
want the *other* kind of hook for some operation. orval already maps GET to `useQuery` and
every other verb to `useMutation` on its own, which is what this project wants. Keep
`signal: true` — that one does what it says, and it is what lets a navigation cancel an
in-flight request.

**Evidence** — `grep -c "MutationOptions = <" web/src/api/generated/sbl.ts` against
`grep -c "QueryOptions = <"`: 55/35 with the flags removed (correct — 55 writes, 35 GETs),
35/55 with them set. orval 8.31.0.

**Seen** — 2026-09-13
