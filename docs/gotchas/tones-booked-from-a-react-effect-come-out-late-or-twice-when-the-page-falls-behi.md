# Tones booked from a React effect come out late or twice when the page falls behind; sound needs its own timer

**Symptom** — In race control the count-in was uneven or the page "got stuck" in the dev
build. The e2e timing test, with the main thread kept busy, recorded
`ping@0.020 beep@6.979 beep@7.978 beep@9.924 signal@10.924 signal@10.926`: the third beep
almost a second late, the signal booked twice — intermittently, only in the full run.

**Cause** — The tones were booked from a `useEffect` in the race card, re-run by a 50 ms
"now" tick that re-rendered the whole race-control page twenty times a second. A page that
falls behind (dev build, busy phone) runs that effect late, so a tone in the look-ahead
window is booked late; and a card that is mounted afresh starts with no memory of what the
old one booked, so it books it again. What misled: the first fix (book on the audio clock
instead of playing at tick time) was right but kept the *booking* inside the render cycle,
and a test passed alone while failing under the full run's load.

**Rule** — Sound (and anything else that must happen on time) is driven by its own small
timer outside React; components only tell it what is armed, idempotently. Re-render a
countdown when its digit changes (aligned to the signal times), not many times a second.

**Evidence** — `web/src/lib/sequenceSound.ts` (the player), `web/src/lib/useNow.ts::useAlignedNow`;
`e2e/race-control.spec.ts`, "the count-in keeps time on a busy phone" — green twice in a
row after the change, and the spec's run time fell from 2.7 to 1.1 minutes.

**Seen** — 2026-10-07
