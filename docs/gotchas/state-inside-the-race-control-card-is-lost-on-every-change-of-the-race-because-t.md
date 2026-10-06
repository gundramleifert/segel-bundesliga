# State inside the race-control card is lost on every change of the race, because the card is keyed by the race's version

**Symptom** — Hauling AP down started the one-minute-then-sequence countdown, and a moment
later the countdown was gone and the screen offered "Start sequence" again. A preparatory
flag chosen as I fell back to P the same way.

**Cause** — `RaceCard` is rendered with `key={`${race.id}-${race.status}-${race.version}`}`
(`web/src/pages/RaceControl.tsx`). Every change to the race — setting or clearing a signal
is one, and so is every live-stream refetch after another device's change — bumps the
version, React unmounts the card and mounts a fresh one, and every `useState` in it starts
over. The countdown was set in the same tap that cleared AP, so the refetch that tap
caused threw it away. Nothing in the card's own code looks wrong; the reset comes from
the parent's `key`.

**Rule** — Anything in the race-control card that must outlive a change to the race lives
outside the card's state: mirrored per race in `localStorage` like the finish order
(`useFinishOrder`) and the start sequence (`useStartSequence` in
`web/src/lib/startSequence.ts`), or on the server. Plain `useState` there is only for what
may reset on any update.

**Evidence** — `web/src/pages/RaceControl.tsx` (the `key` on `<RaceCard>`);
`web/src/lib/startSequence.ts::useStartSequence`; `e2e/race-control.spec.ts`, the 3-2-1-0
test.

**Seen** — 2026-10-06
