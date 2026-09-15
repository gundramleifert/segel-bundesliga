import { useEffect, useState } from "react";

/** A ticking "now", once a second — for countdowns and elapsed clocks.
 *
 * One interval per caller and nothing shared: a page has at most a couple of these, and a
 * shared ticker would need its own subscription bookkeeping for no saving.
 */
export function useNow(): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  return now;
}

export function clock(millis: number): string {
  const total = Math.max(0, Math.round(millis / 1000));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}
