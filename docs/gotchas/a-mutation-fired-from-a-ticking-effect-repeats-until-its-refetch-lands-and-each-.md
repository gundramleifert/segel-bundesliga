# A mutation fired from a ticking effect repeats until its refetch lands, and each repeat's invalidation cancels that refetch

**Symptom** — In race control, a postponed sequence reached "AP down": the server had
`signal: null` (audit row and all), yet the screen kept showing "AP — postponed" for good.
The network log showed `POST …/signal {"signal":null}` again every half second or so, and
not one `GET …/races` completing after the first of them.

**Cause** — The AP-down request was fired from a `useEffect` that runs on every tick of
the sequence clock (50 ms), guarded by `!signal.isPending` and `race.signal === "AP"`.
After the first POST succeeded, `isPending` was false again while `race.signal` was still
the old "AP" — the refetch had not landed yet — so the next tick posted again. Every
success ran `invalidateQueries`, which cancels the in-flight refetch and starts a new one;
the next repeat cancelled that one too. The refetch never finished, so the guard never
became false. What misled: the server state was right and the success handler ran each
time, so it looked like a stale-cache bug, not a loop. The same call from a click (AP up)
worked, because a click fires once.

**Rule** — An action fired from an effect that re-runs on a clock must fire **once**, by
a ref (or by a state transition the same render commits), never by "not pending and the
data still says so" — the data lags the request by a refetch. Reset the ref on error so a
failure can retry.

**Evidence** — `web/src/pages/RaceControl.tsx`, `apDownSent` in `RaceCard`; reproduced in
real time with Playwright logging requests: four `POST …/signal` after AP down, no
`GET …/races` response, the AP badge still shown 18 s later.

**Seen** — 2026-10-06
