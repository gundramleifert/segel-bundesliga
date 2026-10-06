import { useEffect, useState } from "react";

/** A ticking "now", once a second by default — for countdowns and elapsed clocks. The
 *  start sequence ticks faster, so its sounds and its gun are not up to a second late.
 *
 * One interval per caller and nothing shared: a page has at most a couple of these, and a
 * shared ticker would need its own subscription bookkeeping for no saving.
 */
export function useNow(intervalMs = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(timer);
  }, [intervalMs]);
  return now;
}

export function clock(millis: number): string {
  const total = Math.max(0, Math.round(millis / 1000));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

/** A countdown as it should read when it is meant to turn *with* a sound: rounded up, so
 *  "0:05" appears at exactly five seconds to go — the moment of the count-in beep — and
 *  "0:00" only at the signal. `clock` rounds to the nearest second, which turned the digit
 *  half a second before the beep. */
export function countdown(millis: number): string {
  return clock(Math.ceil(Math.max(0, millis) / 1000) * 1000);
}
